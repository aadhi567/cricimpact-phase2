"""Stage 6B.2 Pre-Match Models and Expanding-Window Out-of-Fold Anchor Generator."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Final

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, brier_score_loss, log_loss, roc_auc_score
from sklearn.preprocessing import StandardScaler

from ml.win_probability.schema import (
    STAGE_A_FEATURES,
    STAGE_B_FEATURES,
    TARGET_HOME_WIN,
    validate_feature_matrix_no_leakage,
)

MIN_TRAIN_MATCHES_OOF: Final[int] = 30
DEFAULT_PRE_MATCH_PROB: Final[float] = 0.50


@dataclass(frozen=True)
class PreMatchPredictionResult:
    """Structured pre-match prediction result across Stage A and Stage B."""

    match_id: int
    p_team_a_stage_a: float
    p_team_b_stage_a: float
    p_team_a_stage_b: float
    p_team_b_stage_b: float
    stage_b_prob_delta: float
    stage_b_pending: bool

    def __post_init__(self) -> None:
        """Validate complementarity."""
        if abs(self.p_team_a_stage_a + self.p_team_b_stage_a - 1.0) > 1e-4:
            raise ValueError("Stage A probabilities must sum to 1.0")
        if abs(self.p_team_a_stage_b + self.p_team_b_stage_b - 1.0) > 1e-4:
            raise ValueError("Stage B probabilities must sum to 1.0")


class PreMatchModel:
    """Pre-match prediction engine implementing Stage A and Stage B models."""

    def __init__(self, c_stage_a: float = 0.5, c_stage_b: float = 0.3) -> None:
        """Initialize models with regularization constants."""
        self.c_stage_a = c_stage_a
        self.c_stage_b = c_stage_b

        # Feature lists (excluding raw string competition_category which is mapped to dummy/prior)
        self.features_a = [f for f in STAGE_A_FEATURES if f != "competition_category"]
        self.features_b = [f for f in STAGE_B_FEATURES if f != "competition_category"]

        self.scaler_a = StandardScaler()
        self.scaler_b = StandardScaler()

        self.model_a = LogisticRegression(C=self.c_stage_a, random_state=42, max_iter=200)
        self.model_b = LogisticRegression(C=self.c_stage_b, random_state=42, max_iter=200)

        self.is_fitted = False

    def fit(self, train_df: pd.DataFrame, target_col: str = TARGET_HOME_WIN) -> PreMatchModel:
        """Fit Stage A and Stage B models on historical training matches."""
        validate_feature_matrix_no_leakage(self.features_a)
        validate_feature_matrix_no_leakage(self.features_b)

        y = train_df[target_col].astype(int)

        # 1. Fit Stage A
        X_a = self.scaler_a.fit_transform(train_df[self.features_a])
        self.model_a.fit(X_a, y)

        # 2. Fit Stage B
        X_b = self.scaler_b.fit_transform(train_df[self.features_b])
        self.model_b.fit(X_b, y)

        self.is_fitted = True
        return self

    def predict_stage_a(self, df: pd.DataFrame) -> np.ndarray:
        """Predict Stage A win probability for Team A (Home Team)."""
        if not self.is_fitted:
            raise RuntimeError("PreMatchModel must be fitted before predict_stage_a.")
        X_a = self.scaler_a.transform(df[self.features_a])
        return self.model_a.predict_proba(X_a)[:, 1]

    def predict_stage_b(self, df: pd.DataFrame) -> np.ndarray:
        """Predict Stage B win probability for Team A (Home Team).

        If stage_b_pending is True on any row, Stage A probability is retained.
        """
        if not self.is_fitted:
            raise RuntimeError("PreMatchModel must be fitted before predict_stage_b.")

        p_a = self.predict_stage_a(df)
        X_b = self.scaler_b.transform(df[self.features_b])
        p_b = self.model_b.predict_proba(X_b)[:, 1]

        # Handle pending Stage B
        if "stage_b_pending" in df.columns:
            pending_mask = df["stage_b_pending"].astype(bool).values
            p_b = np.where(pending_mask, p_a, p_b)

        return np.clip(p_b, 0.05, 0.95)

    def predict_match(self, match_features: dict[str, Any]) -> PreMatchPredictionResult:
        """Predict structured probabilities for a single match feature dictionary."""
        df_single = pd.DataFrame([match_features])
        p_a = float(self.predict_stage_a(df_single)[0])
        p_b = float(self.predict_stage_b(df_single)[0])
        pending = bool(match_features.get("stage_b_pending", False))

        delta = 0.0 if pending else (p_b - p_a)

        return PreMatchPredictionResult(
            match_id=int(match_features["match_id"]),
            p_team_a_stage_a=p_a,
            p_team_b_stage_a=1.0 - p_a,
            p_team_a_stage_b=p_b,
            p_team_b_stage_b=1.0 - p_b,
            stage_b_prob_delta=delta,
            stage_b_pending=pending,
        )


class PreMatchAnchorGenerator:
    """Generates strictly causal out-of-fold pre-match anchors for live model training."""

    def __init__(self, min_train_matches: int = MIN_TRAIN_MATCHES_OOF) -> None:
        """Initialize with minimum training sample size for first model fit."""
        self.min_train_matches = min_train_matches

    def generate_expanding_window_oof_anchors(
        self,
        train_matches_b_df: pd.DataFrame,
        target_col: str = TARGET_HOME_WIN,
    ) -> pd.DataFrame:
        """Generate out-of-fold Stage B anchors across training matches chronologically.

        Every prediction for match k is generated strictly using matches with
        match_date < match_date_k. Same-day matches and current-match outcomes
        are categorically excluded.
        """
        df = train_matches_b_df.sort_values("match_date").reset_index(drop=True)
        numeric_b = [f for f in STAGE_B_FEATURES if f != "competition_category"]

        records: list[dict[str, Any]] = []

        for idx in range(len(df)):
            row = df.iloc[idx]
            m_id = int(row["match_id"])
            m_date = str(row["match_date"])
            diff = float(row.get("team_prior_win_rate_diff", 0.0))

            # Filter strictly prior matches (excluding same date)
            prior_df = df[df["match_date"] < m_date]

            if len(prior_df) < self.min_train_matches:
                # Deterministic cold-start prior fallback
                p_stage_a = float(np.clip(DEFAULT_PRE_MATCH_PROB + 0.5 * diff, 0.20, 0.80))
                p_stage_b = p_stage_a
                delta = 0.0
                is_oof = False
                n_train = len(prior_df)
            else:
                # Fit model on historical matches prior to m_date
                model = PreMatchModel()
                model.fit(prior_df, target_col=target_col)

                row_df = pd.DataFrame([row])
                p_stage_a = float(model.predict_stage_a(row_df)[0])
                p_stage_b = float(model.predict_stage_b(row_df)[0])
                delta = p_stage_b - p_stage_a
                is_oof = True
                n_train = len(prior_df)

            records.append(
                {
                    "match_id": m_id,
                    "match_date": m_date,
                    "pre_match_prob_stage_a": p_stage_a,
                    "pre_match_prob_stage_b": p_stage_b,
                    "stage_b_prob_delta": delta,
                    "is_oof_generated": is_oof,
                    "training_sample_size": n_train,
                }
            )

        return pd.DataFrame(records)


def evaluate_pre_match_predictions(y_true: np.ndarray | pd.Series, y_prob: np.ndarray | pd.Series) -> dict[str, float]:
    """Calculate standard evaluation metrics for pre-match probability predictions."""
    y_t = np.asarray(y_true).astype(int)
    y_p = np.asarray(y_prob).astype(float)

    bs = float(brier_score_loss(y_t, y_p))
    ll = float(log_loss(y_t, y_p))
    auc = float(roc_auc_score(y_t, y_p)) if len(np.unique(y_t)) > 1 else 0.50
    acc = float(accuracy_score(y_t, (y_p >= 0.50).astype(int)))

    return {
        "brier_score": bs,
        "log_loss": ll,
        "roc_auc": auc,
        "accuracy": acc,
    }

