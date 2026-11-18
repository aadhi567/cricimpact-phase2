"""Unit tests for Stage 6B.3 First-Innings Live Win Probability Model."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from ml.win_probability.first_innings_model import (
    FirstInningsModel,
    FirstInningsPredictionResult,
    evaluate_first_innings_predictions,
)
from ml.win_probability.schema import (
    INNINGS_1_FEATURES,
    TARGET_BATTING_WIN,
    validate_feature_matrix_no_leakage,
)


@pytest.fixture
def synthetic_innings1_data() -> pd.DataFrame:
    """Generate 60 synthetic first-innings delivery records across match phases."""
    np.random.seed(42)
    n = 60
    records = []

    for i in range(n):
        balls = i * 2  # 0 to 118
        wkts = min(int(i / 10), 9)
        phase = "powerplay" if balls < 36 else ("middle" if balls < 90 else "death")
        score = int(balls * 1.3 + np.random.normal(0, 3))
        comp = "IPL" if i % 2 == 0 else "T20I"

        row = {
            "match_id": 9000 + (i // 20),
            "innings": 1,
            "legal_balls_completed_before": balls,
            "legal_balls_remaining_before": 120 - balls,
            "score_before": max(0, score),
            "wickets_lost_before": wkts,
            "wickets_remaining_before": 10 - wkts,
            "current_run_rate_before": (score / max(1, balls)) * 6.0,
            "innings_phase": phase,
            "innings_progress_pct": balls / 120.0,
            "resource_percentage_remaining": max(0.0, 100.0 - (balls * 0.7) - (wkts * 3.0)),
            # Lineup
            "batting_lineup_top3_abc": 58.0,
            "batting_lineup_mid4_abc": 55.0,
            "batting_lineup_tail_abc": 45.0,
            "batting_lineup_mean_abc": 53.0,
            "batting_lineup_std_abc": 6.5,
            "batting_cold_start_count": 0,
            "bowling_unit_powerplay_econ": 7.4,
            "bowling_unit_middle_econ": 7.1,
            "bowling_unit_death_econ": 9.8,
            "bowling_unit_strike_rate": 18.0,
            "relative_batting_edge": 1.5,
            # Venue
            "competition_category": comp,
            "venue_avg_first_inn_score": 168.0,
            "venue_chase_win_pct": 0.52,
            "venue_avg_death_rr": 9.6,
            "venue_pace_spin_wicket_ratio": 1.25,
            # Anchors
            "pre_match_prob_stage_b": 0.54,
            "stage_b_prob_delta": 0.02,
            "is_batting_team_toss_winner": bool(i % 2 == 0),
            # Trajectory
            "runs_last_12_balls": 16,
            "wickets_last_12_balls": 0 if i % 5 != 0 else 1,
            "runs_last_24_balls": 32,
            "partnership_runs_current": 25,
            "partnership_balls_current": 18,
            "expected_final_score_gap": 5.0,
            TARGET_BATTING_WIN: 1 if i % 3 != 0 else 0,
        }
        records.append(row)

    return pd.DataFrame(records)


def test_first_innings_prediction_result_validation() -> None:
    """Verify FirstInningsPredictionResult enforces complementarity and finite bounds."""
    res = FirstInningsPredictionResult(
        match_id=101,
        innings=1,
        legal_balls_completed=36,
        overs_completed_notation="6.0",
        score_before=48,
        wickets_lost_before=1,
        p_batting_team_win=0.62,
        p_bowling_team_win=0.38,
        resource_percentage_remaining=82.5,
        expected_final_score_gap=4.2,
    )
    assert res.p_batting_team_win == 0.62
    assert res.p_bowling_team_win == 0.38
    assert abs(res.p_batting_team_win + res.p_bowling_team_win - 1.0) < 1e-6

    # Probability bounds violation
    with pytest.raises(ValueError, match="out of bounds"):
        FirstInningsPredictionResult(
            match_id=102,
            innings=1,
            legal_balls_completed=0,
            overs_completed_notation="0.0",
            score_before=0,
            wickets_lost_before=0,
            p_batting_team_win=1.20,
            p_bowling_team_win=-0.20,
            resource_percentage_remaining=100.0,
            expected_final_score_gap=0.0,
        )

    # Sum violation
    with pytest.raises(ValueError, match="must sum to 1.0"):
        FirstInningsPredictionResult(
            match_id=103,
            innings=1,
            legal_balls_completed=0,
            overs_completed_notation="0.0",
            score_before=0,
            wickets_lost_before=0,
            p_batting_team_win=0.55,
            p_bowling_team_win=0.55,
            resource_percentage_remaining=100.0,
            expected_final_score_gap=0.0,
        )


def test_first_innings_model_fit_and_predict(synthetic_innings1_data: pd.DataFrame) -> None:
    """Verify fitting and predicting FirstInningsModel with Logistic Regression."""
    train_df = synthetic_innings1_data.iloc[:40]
    test_df = synthetic_innings1_data.iloc[40:]

    model = FirstInningsModel(model_type="logistic_regression", c_reg=0.5)
    assert not model.is_fitted

    with pytest.raises(RuntimeError, match="must be fitted"):
        model.predict_proba(test_df)

    model.fit(train_df)
    assert model.is_fitted

    probs = model.predict_proba(test_df)
    assert len(probs) == len(test_df)
    assert np.all(probs >= 0.01) and np.all(probs <= 0.99)

    # Test single delivery prediction
    single_del = test_df.iloc[0].to_dict()
    res = model.predict_delivery(single_del)
    assert isinstance(res, FirstInningsPredictionResult)
    assert res.match_id == int(single_del["match_id"])
    assert res.innings == 1
    assert abs(res.p_batting_team_win + res.p_bowling_team_win - 1.0) < 1e-4


def test_first_innings_model_hist_gbt(synthetic_innings1_data: pd.DataFrame) -> None:
    """Verify fitting and predicting FirstInningsModel with HistGBDT."""
    train_df = synthetic_innings1_data.iloc[:40]
    test_df = synthetic_innings1_data.iloc[40:]

    model = FirstInningsModel(model_type="hist_gbt")
    model.fit(train_df)
    assert model.is_fitted

    probs = model.predict_proba(test_df)
    assert len(probs) == len(test_df)
    assert np.all(probs >= 0.01) and np.all(probs <= 0.99)


def test_first_innings_all_out_override(synthetic_innings1_data: pd.DataFrame) -> None:
    """Verify that when 10 wickets are lost (all out), batting win probability is capped at 0.05."""
    train_df = synthetic_innings1_data.iloc[:40]
    test_df = synthetic_innings1_data.iloc[40:].copy()

    model = FirstInningsModel()
    model.fit(train_df)

    # Force all out
    test_df["wickets_lost_before"] = 10
    test_df["resource_percentage_remaining"] = 0.0

    probs = model.predict_proba(test_df)
    assert np.all(probs <= 0.05)


def test_first_innings_leakage_detector() -> None:
    """Verify that FirstInningsModel feature catalog contains zero forbidden leakage columns."""
    model = FirstInningsModel()
    validate_feature_matrix_no_leakage(model.features)
    assert len(model.features) == 35


def test_first_innings_column_alias_handling(synthetic_innings1_data: pd.DataFrame) -> None:
    """Verify that if merge suffixes (_x or _y) are present, FirstInningsModel resolves them."""
    train_df = synthetic_innings1_data.copy()
    # Rename to simulate merge suffix
    train_df["competition_category_x"] = train_df.pop("competition_category")
    train_df["is_batting_team_toss_winner_x"] = train_df.pop("is_batting_team_toss_winner")

    model = FirstInningsModel()
    model.fit(train_df)
    assert model.is_fitted

    p = model.predict_proba(train_df)
    assert len(p) == len(train_df)


def test_evaluate_first_innings_predictions() -> None:
    """Verify evaluation metric calculations for delivery win predictions."""
    y_true = np.array([1, 0, 1, 0, 1])
    y_prob = np.array([0.85, 0.15, 0.70, 0.30, 0.90])

    m = evaluate_first_innings_predictions(y_true, y_prob)
    assert "brier_score" in m
    assert "log_loss" in m
    assert "roc_auc" in m
    assert "accuracy" in m
    assert 0.0 <= m["brier_score"] <= 0.25
    assert m["accuracy"] == 1.0

