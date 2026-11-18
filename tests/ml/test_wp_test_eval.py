"""Unit tests for Stage 6B.6 Final 2026 Test Evaluation Artifacts."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest


@pytest.fixture(scope="module")
def test_predictions_df() -> pd.DataFrame:
    """Load the calibrated 2026 test predictions artifact."""
    p = Path("data/processed/calibration/test_2026_calibrated_predictions_v1.pkl.gz")
    assert p.exists(), f"Test predictions artifact not found at {p}"
    return pd.read_pickle(p)


@pytest.fixture(scope="module")
def test_manifest() -> dict:
    """Load the Stage 6B.6 test evaluation manifest."""
    p = Path("data/processed/calibration/test_2026_evaluation_manifest_v1.json")
    assert p.exists(), f"Test evaluation manifest not found at {p}"
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


def test_2026_test_partition_counts(test_predictions_df: pd.DataFrame) -> None:
    """Verify exact match and delivery partition counts for 2026 test evaluation."""
    df = test_predictions_df
    assert df["match_id"].nunique() == 131, f"Expected 131 matches, got {df['match_id'].nunique()}"

    i1 = df[df["innings"] == 1]
    i2 = df[df["innings"] == 2]

    assert len(i1) == 16333, f"Expected 16,333 Inns 1 deliveries, got {len(i1)}"
    assert len(i2) == 14723, f"Expected 14,723 Inns 2 deliveries, got {len(i2)}"
    assert len(df) == 31056, f"Expected 31,056 total deliveries, got {len(df)}"


def test_2026_probability_bounds_and_validity(test_predictions_df: pd.DataFrame) -> None:
    """Verify all probabilities are finite, non-null, and within valid probability range."""
    df = test_predictions_df

    for col in ["uncalibrated_probability", "calibrated_probability"]:
        assert col in df.columns
        assert not df[col].isna().any(), f"Found NaNs in {col}"
        assert not np.isinf(df[col]).any(), f"Found Infs in {col}"
        assert (df[col] >= 0.01).all(), f"Found probabilities < 0.01 in {col}"
        assert (df[col] <= 0.99).all(), f"Found probabilities > 0.99 in {col}"


def test_2026_calibration_method_assignment(test_predictions_df: pd.DataFrame) -> None:
    """Verify Inns 1 is marked as platt and Inns 2 as none (identity)."""
    df = test_predictions_df
    i1 = df[df["innings"] == 1]
    i2 = df[df["innings"] == 2]

    assert (i1["calibration_method"] == "platt").all()
    assert (i2["calibration_method"] == "none (identity)").all()


def test_2026_manifest_structure_and_metrics(test_manifest: dict) -> None:
    """Verify test manifest has all required sections and finite metrics."""
    m = test_manifest
    assert m["stage"] == "Stage 6B.6"
    assert m["test_population"]["matches"] == 131
    assert m["test_population"]["first_innings_deliveries"] == 16333
    assert m["test_population"]["second_innings_deliveries"] == 14723

    # Check metrics
    i1_m = m["first_innings_metrics"]["calibrated_platt"]
    assert 0.15 < i1_m["brier_score"] < 0.30
    assert 0.50 < i1_m["log_loss"] < 0.80
    assert 0.60 < i1_m["roc_auc"] < 0.85
    assert 0.00 < i1_m["ece"] < 0.15

    i2_m = m["second_innings_metrics"]["raw_retained"]
    assert 0.05 < i2_m["brier_score"] < 0.20
    assert 0.20 < i2_m["log_loss"] < 0.55
    assert 0.85 < i2_m["roc_auc"] < 0.99
    assert 0.00 < i2_m["ece"] < 0.12

