"""Stage 6B.3 First-Innings Live Win Probability Model.

Predicts P(batting_first_team_wins | current_match_state) for every eligible
delivery state in the first innings using the approved 35 INNINGS_1_FEATURES.
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
    INNINGS_1_FEATURES,
    TARGET_BATTING_WIN,
    validate_feature_matrix_no_leakage,
)

COMPETITION_CATEGORY_MAP: Final[dict[str, int]] = {"IPL": 0, "T20I": 1, "OTHER_T20": 2}
INNINGS_PHASE_MAP: Final[dict[str, int]] = {"powerplay": 0, "middle": 1, "death": 2}


@dataclass(frozen=True)
class FirstInningsPredictionResult:
    """Structured first-innings live delivery win probability prediction."""

    match_id: int
    innings: int
    legal_balls_completed: int
    overs_completed_notation: str
    score_before: int
    wickets_lost_before: int
    p_batting_team_win: float
    p_bowling_team_win: float
    resource_percentage_remaining: float
    expected_final_score_gap: float

    def __post_init__(self) -> None:
        """Validate probability bounds and complementarity."""
        if not (0.0 <= self.p_batting_team_win <= 1.0):
            raise ValueError(f"p_batting_team_win out of bounds [0, 1]: {self.p_batting_team_win}")
        if not (0.0 <= self.p_bowling_team_win <= 1.0):
            raise ValueError(f"p_bowling_team_win out of bounds [0, 1]: {self.p_bowling_team_win}")
        if abs(self.p_batting_team_win + self.p_bowling_team_win - 1.0) > 1e-4:
            raise ValueError(
                f"Probabilities must sum to 1.0: {self.p_batting_team_win} + {self.p_bowling_team_win} = "
                f"{self.p_batting_team_win + self.p_bowling_team_win}"
            )


class FirstInningsModel:
    """First-innings live win-probability model estimating P(batting_first_team_wins | state)."""

    def __init__(
        self,
        model_type: Literal["logistic_regression", "hist_gbt"] = "logistic_regression",
        c_reg: float = 0.5,
        random_state: int = 42,
    ) -> None:
        """Initialize the first-innings model with selected architecture."""
        self.model_type = model_type
        self.c_reg = c_reg
        self.random_state = random_state

        # Authoritative 35 candidate features
        self.features = list(INNINGS_1_FEATURES)
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
        """Ensure all 35 features are present, resolving merge aliases and encoding categories."""
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

        # Validate that all 35 features are now available
        missing = [f for f in self.features if f not in df_work.columns]
        if missing:
            raise KeyError(f"Missing required first-innings features: {missing}")

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

    def fit(self, train_df: pd.DataFrame, target_col: str = TARGET_BATTING_WIN) -> FirstInningsModel:
        """Fit the first-innings live model on historical training deliveries."""
        # Ensure only Innings 1 data is fitted
        if "innings" in train_df.columns:
            inns_vals = train_df["innings"].unique()
            if not np.all(inns_vals == 1):
                raise ValueError(f"FirstInningsModel must be fitted only on innings=1 data, got: {inns_vals}")

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
        """Predict P(batting_first_team_wins | state) for delivery rows."""
        if not self.is_fitted:
            raise RuntimeError("FirstInningsModel must be fitted before predict_proba.")

        X = self._prepare_feature_dataframe(df)

        if self.model_type == "logistic_regression":
            X_scaled = self.scaler.transform(X)
            probs = self.model.predict_proba(X_scaled)[:, 1]
        else:
            probs = self.model.predict_proba(X)[:, 1]

        # All-out / 10-wicket override: if batting team is all out, resources are 0
        if "wickets_lost_before" in df.columns:
            all_out_mask = df["wickets_lost_before"].values >= 10
            probs = np.where(all_out_mask, np.minimum(probs, 0.05), probs)

        return np.clip(probs, 0.01, 0.99)

    def predict_delivery(self, delivery_dict: dict[str, Any]) -> FirstInningsPredictionResult:
        """Predict structured win probability for a single first-innings delivery state."""
        df_single = pd.DataFrame([delivery_dict])
        p_bat = float(self.predict_proba(df_single)[0])
        p_bowl = float(1.0 - p_bat)

        m_id = int(delivery_dict.get("match_id", 0))
        inns = int(delivery_dict.get("innings", 1))
        balls_comp = int(delivery_dict.get("legal_balls_completed_before", 0))
        overs_notation = f"{balls_comp // 6}.{balls_comp % 6}"
        score = int(delivery_dict.get("score_before", 0))
        wkts = int(delivery_dict.get("wickets_lost_before", 0))
        res = float(delivery_dict.get("resource_percentage_remaining", 0.0))
        efs_gap = float(delivery_dict.get("expected_final_score_gap", 0.0))

        return FirstInningsPredictionResult(
            match_id=m_id,
            innings=inns,
            legal_balls_completed=balls_comp,
            overs_completed_notation=overs_notation,
            score_before=score,
            wickets_lost_before=wkts,
            p_batting_team_win=p_bat,
            p_bowling_team_win=p_bowl,
            resource_percentage_remaining=res,
            expected_final_score_gap=efs_gap,
        )


def evaluate_first_innings_predictions(
    y_true: np.ndarray | pd.Series, y_prob: np.ndarray | pd.Series
) -> dict[str, float]:
    """Calculate standard evaluation metrics for first-innings win probability predictions."""
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

