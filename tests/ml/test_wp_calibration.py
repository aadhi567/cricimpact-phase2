"""Unit tests for Stage 6B.5 Probability Calibration Module."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from ml.win_probability.calibration import (
    CalibrationMetrics,
    IdentityCalibrator,
    IsotonicCalibrator,
    PlattCalibrator,
    WinProbabilityCalibrator,
    compute_ece,
    compute_reliability_table,
    evaluate_calibrated_predictions,
    logit,
)


def test_logit_transformation() -> None:
    """Verify logit transformation handles boundary values smoothly without infs/nans."""
    p = np.array([0.0, 0.01, 0.5, 0.99, 1.0])
    l = logit(p)
    assert l.shape == (5, 1)
    assert np.all(np.isfinite(l))
    assert l[2, 0] == pytest.approx(0.0, abs=1e-5)
    assert l[0, 0] < l[1, 0] < l[2, 0] < l[3, 0] < l[4, 0]


def test_identity_calibrator() -> None:
    """Verify IdentityCalibrator passes through uncalibrated probabilities with clipping."""
    cal = IdentityCalibrator()
    assert cal.is_fitted

    p_in = np.array([0.005, 0.25, 0.50, 0.75, 0.995])
    p_out = cal.predict_proba(p_in)
    assert p_out[0] == 0.01
    assert p_out[1] == 0.25
    assert p_out[2] == 0.50
    assert p_out[3] == 0.75
    assert p_out[4] == 0.99


def test_platt_calibrator_lifecycle() -> None:
    """Verify PlattCalibrator fitting, monotonic scaling, and error on unfitted state."""
    cal = PlattCalibrator()
    assert not cal.is_fitted

    with pytest.raises(RuntimeError, match="must be fitted"):
        cal.predict_proba(np.array([0.5]))

    # Synthetic training data
    np.random.seed(42)
    p_uncal = np.linspace(0.05, 0.95, 100)
    # Slightly overconfident probabilities
    y_true = (p_uncal + np.random.normal(0, 0.1, 100) > 0.5).astype(int)

    cal.fit(p_uncal, y_true)
    assert cal.is_fitted
    assert cal.coef_ > 0.0  # Must be monotonic

    p_test = np.array([0.1, 0.3, 0.5, 0.7, 0.9])
    p_cal = cal.predict_proba(p_test)
    assert len(p_cal) == 5
    assert np.all(p_cal >= 0.01) and np.all(p_cal <= 0.99)
    assert np.all(np.diff(p_cal) > 0)  # Strictly monotonic increasing


def test_isotonic_calibrator_lifecycle() -> None:
    """Verify IsotonicCalibrator non-parametric fitting and monotonic outputs."""
    cal = IsotonicCalibrator()
    assert not cal.is_fitted

    with pytest.raises(RuntimeError, match="must be fitted"):
        cal.predict_proba(np.array([0.5]))

    p_uncal = np.array([0.1, 0.2, 0.4, 0.6, 0.8, 0.9])
    y_true = np.array([0, 0, 1, 0, 1, 1])

    cal.fit(p_uncal, y_true)
    assert cal.is_fitted

    p_cal = cal.predict_proba(np.array([0.15, 0.5, 0.85]))
    assert len(p_cal) == 3
    assert np.all(p_cal >= 0.01) and np.all(p_cal <= 0.99)
    assert p_cal[0] <= p_cal[1] <= p_cal[2]


def test_win_probability_calibrator_innings_dispatch() -> None:
    """Verify WinProbabilityCalibrator dispatches innings-specific calibration methods."""
    cal = WinProbabilityCalibrator(inns1_method="platt", inns2_method="none")

    # Fit both
    p_train = np.linspace(0.1, 0.9, 50)
    y_train = (p_train > 0.5).astype(int)
    cal.fit_innings_1(p_train, y_train)
    cal.fit_innings_2(p_train, y_train)

    # Innings 1 should use Platt
    p1 = cal.calibrate_innings_1(np.array([0.8]))
    assert 0.01 <= p1[0] <= 0.99

    # Innings 2 should use Identity
    p2 = cal.calibrate_innings_2(np.array([0.8]))
    assert p2[0] == pytest.approx(0.8, abs=1e-5)


def test_win_probability_calibrator_preserves_overrides() -> None:
    """Verify WinProbabilityCalibrator preserves all deterministic cricket rule overrides."""
    cal = WinProbabilityCalibrator(inns1_method="platt", inns2_method="none")
    p_train = np.linspace(0.1, 0.9, 50)
    y_train = (p_train > 0.5).astype(int)
    cal.fit_innings_1(p_train, y_train)
    cal.fit_innings_2(p_train, y_train)

    # 1. Innings 1 all-out override: wickets_lost_before >= 10 capped at 0.05
    df_i1 = pd.DataFrame({"wickets_lost_before": [10, 5]})
    p1_cal = cal.calibrate_innings_1(np.array([0.75, 0.75]), df_deliveries=df_i1)
    assert p1_cal[0] <= 0.05
    assert p1_cal[1] > 0.05

    # 2. Innings 2 chase overrides:
    df_i2 = pd.DataFrame({
        "runs_required_before": [0, 15, 12, 1],
        "wickets_lost_before": [2, 10, 4, 3],
        "legal_balls_remaining_before": [40, 20, 0, 35],
    })
    # Input probabilities that would normally be different
    p_raw = np.array([0.50, 0.50, 0.50, 0.50])
    p2_cal = cal.calibrate_innings_2(p_raw, df_deliveries=df_i2)

    # Target reached -> >= 0.99
    assert p2_cal[0] >= 0.99
    # All-out before target -> <= 0.01
    assert p2_cal[1] <= 0.01
    # Balls exhausted before target -> <= 0.01
    assert p2_cal[2] <= 0.01
    # Target of 1 run with ample resources -> >= 0.99
    assert p2_cal[3] >= 0.99


def test_compute_ece_and_reliability_table() -> None:
    """Verify ECE calculation and reliability table structure."""
    y_true = np.array([0, 0, 0, 0, 1, 1, 1, 1])
    p_pred = np.array([0.1, 0.15, 0.2, 0.25, 0.75, 0.8, 0.85, 0.9])

    ece = compute_ece(y_true, p_pred, n_bins=10)
    assert isinstance(ece, float)
    assert 0.0 <= ece <= 1.0

    table = compute_reliability_table(y_true, p_pred, n_bins=10)
    assert len(table) == 10
    assert "bin_label" in table.columns
    assert "mean_pred_prob" in table.columns
    assert "observed_win_rate" in table.columns
    assert "calibration_error" in table.columns
    assert table["n_samples"].sum() == 8


def test_evaluate_calibrated_predictions() -> None:
    """Verify complete calibration metrics evaluation container."""
    y_true = np.array([1, 0, 1, 0, 1])
    p_pred = np.array([0.9, 0.1, 0.8, 0.2, 0.85])

    metrics = evaluate_calibrated_predictions(y_true, p_pred)
    assert isinstance(metrics, CalibrationMetrics)
    assert metrics.brier_score < 0.10
    assert metrics.accuracy == 1.0
    assert metrics.roc_auc == 1.0
    assert 0.0 <= metrics.ece <= 0.20
    assert metrics.n_samples == 5

