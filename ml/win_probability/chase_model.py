"""Stage 6B.4 Second-Innings Chase Win Probability Model.

Predicts P(chasing_team_wins | current_chase_state) for every eligible
delivery state in the second innings using the approved 39 INNINGS_2_FEATURES.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Final, Literal

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, brier_score_loss, log_loss, roc_auc_score
from sklearn.preprocessing import StandardScaler

from ml.win_probability.schema import (
    INNINGS_2_FEATURES,
    TARGET_BATTING_WIN,
    validate_feature_matrix_no_leakage,
)

COMPETITION_CATEGORY_MAP: Final[dict[str, int]] = {"IPL": 0, "T20I": 1, "OTHER_T20": 2}
INNINGS_PHASE_MAP: Final[dict[str, int]] = {"powerplay": 0, "middle": 1, "death": 2}


@dataclass(frozen=True)
class ChasePredictionResult:
    """Structured second-innings chase delivery win probability prediction."""

    match_id: int
    innings: int
    legal_balls_completed: int
    legal_balls_remaining: int
    overs_completed_notation: str
    target_runs: int
    score_before: int
    runs_required_before: int
    required_run_rate_before: float
    wickets_lost_before: int
    wickets_remaining_before: int
    p_chasing_team_win: float
    p_defending_team_win: float
    resource_percentage_remaining: float
    target_pressure_index: float
    is_terminal_state: bool = False

    def __post_init__(self) -> None:
        """Validate probability bounds, innings, and complementarity."""
        if self.innings != 2:
            raise ValueError(f"ChasePredictionResult requires innings=2, got: {self.innings}")
        if not (0.0 <= self.p_chasing_team_win <= 1.0):
            raise ValueError(f"p_chasing_team_win out of bounds [0, 1]: {self.p_chasing_team_win}")
        if not (0.0 <= self.p_defending_team_win <= 1.0):
            raise ValueError(f"p_defending_team_win out of bounds [0, 1]: {self.p_defending_team_win}")
        if abs(self.p_chasing_team_win + self.p_defending_team_win - 1.0) > 1e-4:
            raise ValueError(
                f"Probabilities must sum to 1.0: {self.p_chasing_team_win} + {self.p_defending_team_win} = "
                f"{self.p_chasing_team_win + self.p_defending_team_win}"
            )


class ChaseModel:
    """Second-innings live win-probability model estimating P(chasing_team_wins | chase_state)."""

    def __init__(
        self,
        model_type: Literal["logistic_regression", "hist_gbt"] = "logistic_regression",
        c_reg: float = 0.5,
        random_state: int = 42,
    ) -> None:
        """Initialize the chase model with selected architecture."""
        self.model_type = model_type
        self.c_reg = c_reg
        self.random_state = random_state

        # Authoritative 39 candidate features
        self.features = list(INNINGS_2_FEATURES)
        validate_feature_matrix_no_leakage(self.features)

        self.cat_cols = ["competition_category", "innings_phase"]
        self.num_cols = [f for f in self.features if f not in self.cat_cols]

        self.scaler = StandardScaler()
        if self.model_type == "logistic_regression":
            self.model: Any = LogisticRegression(
                C=self.c_reg,
                max_iter=300,
                random_state=self.random_state,
            )
        elif self.model_type == "hist_gbt":
            self.model = HistGradientBoostingClassifier(
                max_iter=150,
                max_depth=6,
                min_samples_leaf=30,
                l2_regularization=1.0,
                random_state=self.random_state,
            )
        else:
            raise ValueError(f"Unknown model_type: {self.model_type}")

        self.is_fitted = False

    def _prepare_feature_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """Ensure all 39 chase features are present, resolving merge aliases and orientation."""
        df_work = df.copy()

        # Handle column name resolution if merge suffixes exist
        if "competition_category" not in df_work.columns:
            if "competition_category_x" in df_work.columns:
                df_work["competition_category"] = df_work["competition_category_x"]
            elif "competition_category_y" in df_work.columns:
                df_work["competition_category"] = df_work["competition_category_y"]

        if "is_batting_team_toss_winner" not in df_work.columns:
            if "is_batting_team_toss_winner_x" in df_work.columns:
                df_work["is_batting_team_toss_winner"] = df_work["is_batting_team_toss_winner_x"]
            elif "is_batting_team_toss_winner_y" in df_work.columns:
                df_work["is_batting_team_toss_winner"] = df_work["is_batting_team_toss_winner_y"]

        # Orient pre-match anchor to chasing team if both team columns exist
        if (
            "batting_team_id" in df_work.columns
            and "home_team_id" in df_work.columns
            and "pre_match_prob_stage_b" in df_work.columns
        ):
            # If batting_team_id != home_team_id, the chasing team is away team,
            # so P(chase) = 1.0 - P(home).
            df_work["pre_match_prob_stage_b"] = np.where(
                df_work["batting_team_id"] == df_work["home_team_id"],
                df_work["pre_match_prob_stage_b"],
                1.0 - df_work["pre_match_prob_stage_b"],
            )

        # Validate that all 39 features are now available
        missing = [f for f in self.features if f not in df_work.columns]
        if missing:
            raise KeyError(f"Missing required second-innings chase features: {missing}")

        # Encode categoricals to deterministic integers
        X = df_work[self.num_cols].copy()
        X["competition_category"] = (
            df_work["competition_category"].map(COMPETITION_CATEGORY_MAP).fillna(1).astype(int)
        )
        X["innings_phase"] = (
            df_work["innings_phase"].map(INNINGS_PHASE_MAP).fillna(1).astype(int)
        )

        # Convert booleans to int/float
        for col in X.columns:
            if X[col].dtype == bool:
                X[col] = X[col].astype(int)

        return X[self.features]

    def fit(self, train_df: pd.DataFrame, target_col: str = TARGET_BATTING_WIN) -> ChaseModel:
        """Fit the second-innings live chase model on historical training deliveries."""
        # Ensure only Innings 2 data is fitted
        if "innings" in train_df.columns:
            inns_vals = train_df["innings"].unique()
            if not np.all(inns_vals == 2):
                raise ValueError(f"ChaseModel must be fitted only on innings=2 data, got: {inns_vals}")

        X = self._prepare_feature_dataframe(train_df)
        y = train_df[target_col].astype(int).values

        if self.model_type == "logistic_regression":
            X_scaled = self.scaler.fit_transform(X)
            self.model.fit(X_scaled, y)
        else:
            cat_indices = [
                X.columns.get_loc("competition_category"),
                X.columns.get_loc("innings_phase"),
            ]
            self.model.set_params(categorical_features=cat_indices)
            self.model.fit(X, y)

        self.is_fitted = True
        return self

    def predict_proba(self, df: pd.DataFrame) -> np.ndarray:
        """Predict P(chasing_team_wins | chase_state) for delivery rows."""
        if not self.is_fitted:
            raise RuntimeError("ChaseModel must be fitted before predict_proba.")

        X = self._prepare_feature_dataframe(df)

        if self.model_type == "logistic_regression":
            X_scaled = self.scaler.transform(X)
            probs = self.model.predict_proba(X_scaled)[:, 1]
        else:
            probs = self.model.predict_proba(X)[:, 1]

        # Domain-driven chase edge cases:
        # 1. Target reached: runs_required <= 0 -> P >= 0.99
        if "runs_required_before" in df.columns:
            target_reached_mask = df["runs_required_before"].values <= 0
            probs = np.where(target_reached_mask, 0.99, probs)

        # 2. All-out before target reached: wickets_lost >= 10 and runs_required > 0 -> P <= 0.01
        if "wickets_lost_before" in df.columns and "runs_required_before" in df.columns:
            all_out_mask = (df["wickets_lost_before"].values >= 10) & (df["runs_required_before"].values > 0)
            probs = np.where(all_out_mask, 0.01, probs)

        # 3. Balls exhausted before target reached: legal_balls_remaining == 0 and runs_required > 0 -> P <= 0.01
        if "legal_balls_remaining_before" in df.columns and "runs_required_before" in df.columns:
            balls_exhausted_mask = (df["legal_balls_remaining_before"].values == 0) & (
                df["runs_required_before"].values > 0
            )
            probs = np.where(balls_exhausted_mask, 0.01, probs)

        # 4. Target of 1 run remaining with plenty of balls and wickets
        if (
            "runs_required_before" in df.columns
            and "wickets_lost_before" in df.columns
            and "legal_balls_remaining_before" in df.columns
        ):
            one_run_safe_mask = (
                (df["runs_required_before"].values == 1)
                & (df["wickets_lost_before"].values <= 8)
                & (df["legal_balls_remaining_before"].values >= 30)
            )
            probs = np.where(one_run_safe_mask, np.maximum(probs, 0.99), probs)

        return np.clip(probs, 0.01, 0.99)

    def predict_delivery(self, delivery_dict: dict[str, Any]) -> ChasePredictionResult:
        """Predict structured win probability for a single second-innings delivery state."""
        df_single = pd.DataFrame([delivery_dict])
        p_chase = float(self.predict_proba(df_single)[0])
        p_defend = float(1.0 - p_chase)

        m_id = int(delivery_dict.get("match_id", 0))
        inns = int(delivery_dict.get("innings", 2))
        balls_comp = int(delivery_dict.get("legal_balls_completed_before", 0))
        balls_rem = int(delivery_dict.get("legal_balls_remaining_before", 120 - balls_comp))
        overs_notation = f"{balls_comp // 6}.{balls_comp % 6}"
        target = int(delivery_dict.get("target_runs", 0))
        score = int(delivery_dict.get("score_before", 0))
        runs_req = int(delivery_dict.get("runs_required_before", target - score))
        rrr = float(delivery_dict.get("required_run_rate_before", 0.0))
        wkts_lost = int(delivery_dict.get("wickets_lost_before", 0))
        wkts_rem = int(delivery_dict.get("wickets_remaining_before", 10 - wkts_lost))
        res = float(delivery_dict.get("resource_percentage_remaining", 0.0))
        tpi = float(delivery_dict.get("target_pressure_index", 0.0))

        # Check terminal state
        is_terminal = (
            runs_req <= 0
            or (wkts_lost >= 10 and runs_req > 0)
            or (balls_rem == 0 and runs_req > 0)
        )

        return ChasePredictionResult(
            match_id=m_id,
            innings=inns,
            legal_balls_completed=balls_comp,
            legal_balls_remaining=balls_rem,
            overs_completed_notation=overs_notation,
            target_runs=target,
            score_before=score,
            runs_required_before=runs_req,
            required_run_rate_before=rrr,
            wickets_lost_before=wkts_lost,
            wickets_remaining_before=wkts_rem,
            p_chasing_team_win=p_chase,
            p_defending_team_win=p_defend,
            resource_percentage_remaining=res,
            target_pressure_index=tpi,
            is_terminal_state=is_terminal,
        )


def evaluate_chase_predictions(
    y_true: np.ndarray | pd.Series, y_prob: np.ndarray | pd.Series
) -> dict[str, float]:
    """Calculate standard evaluation metrics for second-innings win probability predictions."""
    y_t = np.asarray(y_true).astype(int)
    y_p = np.asarray(y_prob).astype(float)
    eps = 1e-15
    y_p_clipped = np.clip(y_p, eps, 1.0 - eps)

    bs = float(brier_score_loss(y_t, y_p_clipped))
    ll = float(log_loss(y_t, y_p_clipped))
    auc = float(roc_auc_score(y_t, y_p_clipped)) if len(np.unique(y_t)) > 1 else 0.50
    acc = float(accuracy_score(y_t, (y_p_clipped >= 0.50).astype(int)))

    return {
        "brier_score": bs,
        "log_loss": ll,
        "roc_auc": auc,
        "accuracy": acc,
    }

