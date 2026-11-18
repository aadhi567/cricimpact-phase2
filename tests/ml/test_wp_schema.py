"""Unit tests for Stage 6B Win Probability schemas, feature contracts, and dataclasses."""

from __future__ import annotations

import pytest

from ml.win_probability.schema import (
    ALL_CATALOG_FEATURES,
    FORBIDDEN_LEAKAGE_COLUMNS,
    GROUP_1_MATCH_STATE_FEATURES,
    GROUP_2_TEAM_STRENGTH_FEATURES,
    GROUP_3_VENUE_PRIOR_FEATURES,
    GROUP_4_PRE_MATCH_ANCHOR_FEATURES,
    GROUP_5_TRAJECTORY_DYNAMIC_FEATURES,
    INNINGS_1_FEATURES,
    INNINGS_2_FEATURES,
    STAGE_A_FEATURES,
    STAGE_B_FEATURES,
    TARGET_BATTING_WIN,
    TARGET_HOME_WIN,
    WinProbabilityOutput,
    validate_feature_matrix_no_leakage,
)


def test_feature_counts_and_reconciliation() -> None:
    """Verify exact authoritative feature counts and group reconciliation."""
    assert len(GROUP_1_MATCH_STATE_FEATURES) == 14
    assert len(GROUP_2_TEAM_STRENGTH_FEATURES) == 11
    assert len(GROUP_3_VENUE_PRIOR_FEATURES) == 5
    assert len(GROUP_4_PRE_MATCH_ANCHOR_FEATURES) == 5
    assert len(GROUP_5_TRAJECTORY_DYNAMIC_FEATURES) == 7

    assert len(ALL_CATALOG_FEATURES) == 42
    assert len(set(ALL_CATALOG_FEATURES)) == 42  # Zero duplicates

    # Lifecycle counts
    assert len(STAGE_A_FEATURES) == 7
    assert len(STAGE_B_FEATURES) == 20
    assert len(INNINGS_1_FEATURES) == 35
    assert len(INNINGS_2_FEATURES) == 39


def test_forbidden_columns_isolation() -> None:
    """Verify that no catalog feature belongs to the forbidden leakage list."""
    overlap = set(ALL_CATALOG_FEATURES).intersection(FORBIDDEN_LEAKAGE_COLUMNS)
    assert len(overlap) == 0, f"Leakage detected in feature catalog: {overlap}"

    # Target columns must be in forbidden list
    assert TARGET_BATTING_WIN in FORBIDDEN_LEAKAGE_COLUMNS
    assert TARGET_HOME_WIN in FORBIDDEN_LEAKAGE_COLUMNS


def test_validate_feature_matrix_leakage_detector() -> None:
    """Verify that validate_feature_matrix_no_leakage raises ValueError on forbidden columns."""
    safe_features = ["score_before", "wickets_lost_before", "current_run_rate_before"]
    validate_feature_matrix_no_leakage(safe_features)

    unsafe_features = ["score_before", "win_team_id", "wickets_lost_before"]
    with pytest.raises(ValueError, match="CRITICAL TARGET LEAKAGE"):
        validate_feature_matrix_no_leakage(unsafe_features)

    unsafe_after_features = ["score_before", "score_after"]
    with pytest.raises(ValueError, match="CRITICAL TARGET LEAKAGE"):
        validate_feature_matrix_no_leakage(unsafe_after_features)


def test_win_probability_output_validation() -> None:
    """Verify probability bounds and strict complementarity in WinProbabilityOutput."""
    # Valid output
    out = WinProbabilityOutput(
        match_id=13511,
        innings=1,
        innings_ball_num=1,
        p_batting_team=0.55,
        p_bowling_team=0.45,
        p_team_a=0.55,
        p_team_b=0.45,
        lifecycle_stage="INNINGS_1_DEFENSE_LIVE",
    )
    assert out.p_batting_team + out.p_bowling_team == pytest.approx(1.0)
    assert out.p_team_a + out.p_team_b == pytest.approx(1.0)

    # Invalid probability (out of bounds)
    with pytest.raises(ValueError, match="out of bounds"):
        WinProbabilityOutput(
            match_id=13511,
            innings=1,
            innings_ball_num=1,
            p_batting_team=1.20,
            p_bowling_team=-0.20,
            p_team_a=1.20,
            p_team_b=-0.20,
            lifecycle_stage="INNINGS_1_DEFENSE_LIVE",
        )

    # Invalid sum (not complementary)
    with pytest.raises(ValueError, match="do not sum to 1.0"):
        WinProbabilityOutput(
            match_id=13511,
            innings=1,
            innings_ball_num=1,
            p_batting_team=0.60,
            p_bowling_team=0.30,
            p_team_a=0.60,
            p_team_b=0.30,
            lifecycle_stage="INNINGS_1_DEFENSE_LIVE",
        )

