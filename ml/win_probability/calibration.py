"""Stage 6B.5 Probability Calibration Module.

Provides independent probability calibration for first-innings and second-innings
live win probability models:
- First Innings: Platt scaling (sigmoid calibration) fitted on causal out-of-fold historical predictions.
- Second Innings: Retains uncalibrated identity mapping due to optimal natural calibration (ECE 1.72%).

Preserves all deterministic cricket-rule boundary overrides.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Final, Literal

import numpy as np
import pandas as pd
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, brier_score_loss, log_loss, roc_auc_score


def logit(p: np.ndarray | pd.Series) -> np.ndarray:
    """Calculate log-odds with numerical stability clipping."""
    p_arr = np.asarray(p, dtype=float)
    p_clipped = np.clip(p_arr, 1e-6, 1.0 - 1e-6)
    return np.log(p_clipped / (1.0 - p_clipped)).reshape(-1, 1)


@dataclass(frozen=True)
class CalibrationMetrics:
    """Evaluation metrics summary for a probability prediction vector."""

    brier_score: float
    log_loss: float
    roc_auc: float
    accuracy: float
    ece: float
    n_samples: int


class IdentityCalibrator:
    """Pass-through calibrator that preserves uncalibrated probabilities (identity mapping)."""

    def __init__(self) -> None:
        self.is_fitted = True

    def fit(self, p_uncal: np.ndarray | pd.Series, y_true: np.ndarray | pd.Series) -> IdentityCalibrator:
        """No-op fitting for identity calibrator."""
        self.is_fitted = True
        return self

    def predict_proba(self, p_uncal: np.ndarray | pd.Series) -> np.ndarray:
        """Return clipped uncalibrated probabilities."""
        p = np.asarray(p_uncal, dtype=float)
        return np.clip(p, 0.01, 0.99)


class PlattCalibrator:
    """Platt scaling (sigmoid / logistic calibration) on log-odds."""

    def __init__(self, c_reg: float = 1.0, random_state: int = 42) -> None:
        self.c_reg = c_reg
        self.random_state = random_state
        self.model = LogisticRegression(C=self.c_reg, random_state=self.random_state)
        self.is_fitted = False
        self.coef_: float = 1.0
        self.intercept_: float = 0.0

    def fit(self, p_uncal: np.ndarray | pd.Series, y_true: np.ndarray | pd.Series) -> PlattCalibrator:
        """Fit univariate logistic regression on logit-transformed probabilities."""
        p = np.asarray(p_uncal, dtype=float)
        y = np.asarray(y_true, dtype=int)
        x_logits = logit(p)
        self.model.fit(x_logits, y)
        self.coef_ = float(self.model.coef_[0][0])
        self.intercept_ = float(self.model.intercept_[0])
        self.is_fitted = True
        return self

    def predict_proba(self, p_uncal: np.ndarray | pd.Series) -> np.ndarray:
        """Apply fitted Platt scaling to uncalibrated probabilities."""
        if not self.is_fitted:
            raise RuntimeError("PlattCalibrator must be fitted before predict_proba.")
        p = np.asarray(p_uncal, dtype=float)
        x_logits = logit(p)
        cal_probs = self.model.predict_proba(x_logits)[:, 1]
        return np.clip(cal_probs, 0.01, 0.99)


class IsotonicCalibrator:
    """Non-parametric piecewise constant isotonic regression calibrator."""

    def __init__(self, y_min: float = 0.01, y_max: float = 0.99) -> None:
        self.y_min = y_min
        self.y_max = y_max
        self.model = IsotonicRegression(y_min=self.y_min, y_max=self.y_max, out_of_bounds="clip")
        self.is_fitted = False

    def fit(self, p_uncal: np.ndarray | pd.Series, y_true: np.ndarray | pd.Series) -> IsotonicCalibrator:
        """Fit isotonic regression on uncalibrated probabilities."""
        p = np.asarray(p_uncal, dtype=float)
        y = np.asarray(y_true, dtype=int)
        self.model.fit(p, y)
        self.is_fitted = True
        return self

    def predict_proba(self, p_uncal: np.ndarray | pd.Series) -> np.ndarray:
        """Apply fitted isotonic regression to uncalibrated probabilities."""
        if not self.is_fitted:
            raise RuntimeError("IsotonicCalibrator must be fitted before predict_proba.")
        p = np.asarray(p_uncal, dtype=float)
        cal_probs = self.model.predict(p)
        return np.clip(cal_probs, self.y_min, self.y_max)


class WinProbabilityCalibrator:
    """Composite innings-specific calibrator preserving deterministic rule overrides."""

    def __init__(
        self,
        inns1_method: Literal["none", "platt", "isotonic"] = "platt",
        inns2_method: Literal["none", "platt", "isotonic"] = "none",
    ) -> None:
        self.inns1_method = inns1_method
        self.inns2_method = inns2_method

        self.calibrator_1: Any = (
            PlattCalibrator() if inns1_method == "platt" else
            (IsotonicCalibrator() if inns1_method == "isotonic" else IdentityCalibrator())
        )
        self.calibrator_2: Any = (
            PlattCalibrator() if inns2_method == "platt" else
            (IsotonicCalibrator() if inns2_method == "isotonic" else IdentityCalibrator())
        )

    def fit_innings_1(self, p_uncal: np.ndarray | pd.Series, y_true: np.ndarray | pd.Series) -> WinProbabilityCalibrator:
        """Fit the innings 1 calibrator on historical predictions."""
        self.calibrator_1.fit(p_uncal, y_true)
        return self

    def fit_innings_2(self, p_uncal: np.ndarray | pd.Series, y_true: np.ndarray | pd.Series) -> WinProbabilityCalibrator:
        """Fit the innings 2 calibrator on historical predictions."""
        self.calibrator_2.fit(p_uncal, y_true)
        return self

    def calibrate_innings_1(
        self, p_uncal: np.ndarray | pd.Series, df_deliveries: pd.DataFrame | None = None
    ) -> np.ndarray:
        """Calibrate first-innings win probabilities, preserving all-out override."""
        p_cal = self.calibrator_1.predict_proba(p_uncal)

        # Preserve deterministic override: if batting team is all-out (10 wickets lost), cap at 0.05
        if df_deliveries is not None and "wickets_lost_before" in df_deliveries.columns:
            all_out_mask = df_deliveries["wickets_lost_before"].values >= 10
            p_cal = np.where(all_out_mask, np.minimum(p_cal, 0.05), p_cal)

        return np.clip(p_cal, 0.01, 0.99)

    def calibrate_innings_2(
        self, p_uncal: np.ndarray | pd.Series, df_deliveries: pd.DataFrame | None = None
    ) -> np.ndarray:
        """Calibrate second-innings win probabilities, preserving deterministic chase overrides."""
        p_cal = self.calibrator_2.predict_proba(p_uncal)

        # Preserve deterministic chase overrides:
        if df_deliveries is not None:
            # 1. Target reached: runs_required <= 0 -> P >= 0.99
            if "runs_required_before" in df_deliveries.columns:
                target_reached_mask = df_deliveries["runs_required_before"].values <= 0
                p_cal = np.where(target_reached_mask, 0.99, p_cal)

            # 2. All-out before target: wickets_lost >= 10 and runs_required > 0 -> P <= 0.01
            if "wickets_lost_before" in df_deliveries.columns and "runs_required_before" in df_deliveries.columns:
                all_out_mask = (df_deliveries["wickets_lost_before"].values >= 10) & (
                    df_deliveries["runs_required_before"].values > 0
                )
                p_cal = np.where(all_out_mask, 0.01, p_cal)

            # 3. Balls exhausted before target: balls_remaining == 0 and runs_required > 0 -> P <= 0.01
            if "legal_balls_remaining_before" in df_deliveries.columns and "runs_required_before" in df_deliveries.columns:
                balls_exhausted_mask = (df_deliveries["legal_balls_remaining_before"].values == 0) & (
                    df_deliveries["runs_required_before"].values > 0
                )
                p_cal = np.where(balls_exhausted_mask, 0.01, p_cal)

            # 4. Target of 1 run remaining with plenty of balls and wickets
            if (
                "runs_required_before" in df_deliveries.columns
                and "wickets_lost_before" in df_deliveries.columns
                and "legal_balls_remaining_before" in df_deliveries.columns
            ):
                one_run_safe_mask = (
                    (df_deliveries["runs_required_before"].values == 1)
                    & (df_deliveries["wickets_lost_before"].values <= 8)
                    & (df_deliveries["legal_balls_remaining_before"].values >= 30)
                )
                p_cal = np.where(one_run_safe_mask, np.maximum(p_cal, 0.99), p_cal)

        return np.clip(p_cal, 0.01, 0.99)


def compute_ece(
    y_true: np.ndarray | pd.Series, p_pred: np.ndarray | pd.Series, n_bins: int = 10
) -> float:
    """Calculate Expected Calibration Error (ECE) across uniform probability bins."""
    y = np.asarray(y_true, dtype=int)
    p = np.clip(np.asarray(p_pred, dtype=float), 1e-15, 1.0 - 1e-15)

    bins = np.linspace(0.0, 1.0, n_bins + 1)
    binned = np.digitize(p, bins) - 1

    ece = 0.0
    n_total = len(y)
    for b in range(n_bins):
        mask = binned == b
        n_b = int(np.sum(mask))
        if n_b > 0:
            p_mean = float(np.mean(p[mask]))
            y_mean = float(np.mean(y[mask]))
            ece += (n_b / n_total) * abs(y_mean - p_mean)

    return float(ece)


def compute_reliability_table(
    y_true: np.ndarray | pd.Series, p_pred: np.ndarray | pd.Series, n_bins: int = 10
) -> pd.DataFrame:
    """Generate 10-decile reliability diagram table."""
    y = np.asarray(y_true, dtype=int)
    p = np.clip(np.asarray(p_pred, dtype=float), 1e-15, 1.0 - 1e-15)

    bins = np.linspace(0.0, 1.0, n_bins + 1)
    binned = np.digitize(p, bins) - 1

    rows = []
    for b in range(n_bins):
        mask = binned == b
        n_b = int(np.sum(mask))
        if n_b > 0:
            pm = float(np.mean(p[mask]))
            ym = float(np.mean(y[mask]))
            err = ym - pm
            br = float(brier_score_loss(y[mask], p[mask]))
            ll = float(-np.mean(y[mask] * np.log(p[mask]) + (1.0 - y[mask]) * np.log(1.0 - p[mask])))
        else:
            pm = (bins[b] + bins[b + 1]) / 2.0
            ym = 0.0
            err = 0.0
            br = 0.0
            ll = 0.0

        rows.append({
            "bin_lower": bins[b],
            "bin_upper": bins[b + 1],
            "bin_label": f"[{bins[b]:.1f}, {bins[b+1]:.1f})",
            "n_samples": n_b,
            "mean_pred_prob": pm,
            "observed_win_rate": ym,
            "calibration_error": err,
            "brier_score": br,
            "log_loss": ll,
        })

    return pd.DataFrame(rows)


def evaluate_calibrated_predictions(
    y_true: np.ndarray | pd.Series, p_pred: np.ndarray | pd.Series, n_bins: int = 10
) -> CalibrationMetrics:
    """Compute complete suite of probability evaluation metrics."""
    y = np.asarray(y_true, dtype=int)
    p = np.clip(np.asarray(p_pred, dtype=float), 1e-15, 1.0 - 1e-15)

    bs = float(brier_score_loss(y, p))
    ll = float(-np.mean(y * np.log(p) + (1.0 - y) * np.log(1.0 - p)))
    auc = float(roc_auc_score(y, p)) if len(np.unique(y)) > 1 else 0.50
    acc = float(accuracy_score(y, (p >= 0.50).astype(int)))
    ece = compute_ece(y, p, n_bins=n_bins)

    return CalibrationMetrics(
        brier_score=bs,
        log_loss=ll,
        roc_auc=auc,
        accuracy=acc,
        ece=ece,
        n_samples=len(y),
    )

