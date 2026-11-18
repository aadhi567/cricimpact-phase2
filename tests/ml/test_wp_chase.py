"""Unit tests for Stage 6B.4 Second-Innings Chase Win Probability Model."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from ml.win_probability.chase_model import (
    ChaseModel,
    ChasePredictionResult,
    evaluate_chase_predictions,
)
from ml.win_probability.schema import (
    INNINGS_2_FEATURES,
    TARGET_BATTING_WIN,
    validate_feature_matrix_no_leakage,
)


@pytest.fixture
def synthetic_innings2_data() -> pd.DataFrame:
    """Generate 60 synthetic second-innings chase delivery records across phases."""
    np.random.seed(42)
    n = 60
    records = []
    target = 165

    for i in range(n):
        balls = i * 2  # 0 to 118
        wkts = min(int(i / 10), 9)
        phase = "powerplay" if balls < 36 else ("middle" if balls < 90 else "death")
        score = int(balls * 1.35 + np.random.normal(0, 3))
        comp = "IPL" if i % 2 == 0 else "T20I"
        balls_rem = 120 - balls
        runs_req = max(1, target - score)
        rrr = (runs_req / max(1, balls_rem)) * 6.0
        crr = (score / max(1, balls)) * 6.0

        row = {
            "match_id": 9000 + (i // 20),
            "innings": 2,
            "legal_balls_completed_before": balls,
            "legal_balls_remaining_before": balls_rem,
            "score_before": max(0, score),
            "wickets_lost_before": wkts,
            "wickets_remaining_before": 10 - wkts,
            "current_run_rate_before": crr,
            "innings_phase": phase,
            "innings_progress_pct": balls / 120.0,
            "resource_percentage_remaining": max(0.0, 100.0 - (balls * 0.7) - (wkts * 3.0)),
            # Chase specific features
            "target_runs": target,
            "runs_required_before": runs_req,
            "required_run_rate_before": rrr,
            "rrr_minus_crr_before": rrr - crr,
            "target_pressure_index": (rrr / 8.0) * (1.0 + wkts / 5.0),
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
            "batting_team_id": 10,
            "home_team_id": 10,
            # Trajectory
            "runs_last_12_balls": 16,
            "wickets_last_12_balls": 0 if i % 5 != 0 else 1,
            "runs_last_24_balls": 32,
            "partnership_runs_current": 25,
            "partnership_balls_current": 18,
            TARGET_BATTING_WIN: 1 if i % 3 != 0 else 0,
        }
        records.append(row)

    return pd.DataFrame(records)


def test_chase_prediction_result_validation() -> None:
    """Verify ChasePredictionResult enforces complementarity, innings=2, and finite bounds."""
    res = ChasePredictionResult(
        match_id=101,
        innings=2,
        legal_balls_completed=36,
        legal_balls_remaining=84,
        overs_completed_notation="6.0",
        target_runs=170,
        score_before=52,
        runs_required_before=118,
        required_run_rate_before=8.43,
        wickets_lost_before=1,
        wickets_remaining_before=9,
        p_chasing_team_win=0.58,
        p_defending_team_win=0.42,
        resource_percentage_remaining=85.0,
        target_pressure_index=1.25,
        is_terminal_state=False,
    )
    assert res.p_chasing_team_win == 0.58
    assert res.p_defending_team_win == 0.42
    assert abs(res.p_chasing_team_win + res.p_defending_team_win - 1.0) < 1e-6
    assert res.innings == 2
    assert not res.is_terminal_state

    # Innings != 2 violation
    with pytest.raises(ValueError, match="requires innings=2"):
        ChasePredictionResult(
            match_id=102,
            innings=1,
            legal_balls_completed=0,
            legal_balls_remaining=120,
            overs_completed_notation="0.0",
            target_runs=170,
            score_before=0,
            runs_required_before=170,
            required_run_rate_before=8.5,
            wickets_lost_before=0,
            wickets_remaining_before=10,
            p_chasing_team_win=0.50,
            p_defending_team_win=0.50,
            resource_percentage_remaining=100.0,
            target_pressure_index=1.0,
        )

    # Probability bounds violation
    with pytest.raises(ValueError, match="out of bounds"):
        ChasePredictionResult(
            match_id=103,
            innings=2,
            legal_balls_completed=0,
            legal_balls_remaining=120,
            overs_completed_notation="0.0",
            target_runs=170,
            score_before=0,
            runs_required_before=170,
            required_run_rate_before=8.5,
            wickets_lost_before=0,
            wickets_remaining_before=10,
            p_chasing_team_win=1.20,
            p_defending_team_win=-0.20,
            resource_percentage_remaining=100.0,
            target_pressure_index=1.0,
        )

    # Sum violation
    with pytest.raises(ValueError, match="must sum to 1.0"):
        ChasePredictionResult(
            match_id=104,
            innings=2,
            legal_balls_completed=0,
            legal_balls_remaining=120,
            overs_completed_notation="0.0",
            target_runs=170,
            score_before=0,
            runs_required_before=170,
            required_run_rate_before=8.5,
            wickets_lost_before=0,
            wickets_remaining_before=10,
            p_chasing_team_win=0.55,
            p_defending_team_win=0.55,
            resource_percentage_remaining=100.0,
            target_pressure_index=1.0,
        )


def test_chase_model_fit_and_predict(synthetic_innings2_data: pd.DataFrame) -> None:
    """Verify fitting and predicting ChaseModel with Logistic Regression."""
    train_df = synthetic_innings2_data.iloc[:40]
    test_df = synthetic_innings2_data.iloc[40:]

    model = ChaseModel(model_type="logistic_regression", c_reg=0.5)
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
    assert isinstance(res, ChasePredictionResult)
    assert res.match_id == int(single_del["match_id"])
    assert res.innings == 2
    assert abs(res.p_chasing_team_win + res.p_defending_team_win - 1.0) < 1e-4


def test_chase_model_hist_gbt(synthetic_innings2_data: pd.DataFrame) -> None:
    """Verify fitting and predicting ChaseModel with HistGBDT."""
    train_df = synthetic_innings2_data.iloc[:40]
    test_df = synthetic_innings2_data.iloc[40:]

    model = ChaseModel(model_type="hist_gbt")
    model.fit(train_df)
    assert model.is_fitted

    probs = model.predict_proba(test_df)
    assert len(probs) == len(test_df)
    assert np.all(probs >= 0.01) and np.all(probs <= 0.99)


def test_chase_edge_cases(synthetic_innings2_data: pd.DataFrame) -> None:
    """Verify chase edge-case overrides: target reached, all-out, balls exhausted, target of 1."""
    train_df = synthetic_innings2_data.iloc[:40]
    model = ChaseModel()
    model.fit(train_df)

    # 1. Target reached: runs_required <= 0 -> P >= 0.99
    df_won = synthetic_innings2_data.iloc[40:45].copy()
    df_won["runs_required_before"] = 0
    p_won = model.predict_proba(df_won)
    assert np.all(p_won >= 0.99)

    # 2. All-out before target reached: wickets_lost >= 10 and runs_required > 0 -> P <= 0.01
    df_out = synthetic_innings2_data.iloc[40:45].copy()
    df_out["wickets_lost_before"] = 10
    df_out["runs_required_before"] = 25
    p_out = model.predict_proba(df_out)
    assert np.all(p_out <= 0.01)

    # 3. Balls exhausted before target reached: balls_remaining == 0 and runs_required > 0 -> P <= 0.01
    df_balls = synthetic_innings2_data.iloc[40:45].copy()
    df_balls["legal_balls_remaining_before"] = 0
    df_balls["runs_required_before"] = 12
    p_balls = model.predict_proba(df_balls)
    assert np.all(p_balls <= 0.01)

    # 4. Target of 1 run remaining with ample balls and wickets
    df_one = synthetic_innings2_data.iloc[40:45].copy()
    df_one["runs_required_before"] = 1
    df_one["wickets_lost_before"] = 3
    df_one["legal_balls_remaining_before"] = 40
    p_one = model.predict_proba(df_one)
    assert np.all(p_one >= 0.99)


def test_chase_leakage_detector() -> None:
    """Verify that ChaseModel feature catalog contains zero forbidden leakage columns."""
    model = ChaseModel()
    validate_feature_matrix_no_leakage(model.features)
    assert len(model.features) == 39
    assert "expected_final_score_gap" not in model.features
    assert "target_pressure_index" in model.features
    assert "runs_required_before" in model.features


def test_chase_column_alias_handling(synthetic_innings2_data: pd.DataFrame) -> None:
    """Verify that if merge suffixes (_x or _y) are present, ChaseModel resolves them."""
    train_df = synthetic_innings2_data.copy()
    train_df["competition_category_x"] = train_df.pop("competition_category")
    train_df["is_batting_team_toss_winner_x"] = train_df.pop("is_batting_team_toss_winner")

    model = ChaseModel()
    model.fit(train_df)
    assert model.is_fitted

    p = model.predict_proba(train_df)
    assert len(p) == len(train_df)


def test_chase_pre_match_orientation(synthetic_innings2_data: pd.DataFrame) -> None:
    """Verify that pre_match_prob_stage_b is oriented to the chasing team when away team chases."""
    df_home_chase = synthetic_innings2_data.iloc[:10].copy()
    df_home_chase["batting_team_id"] = 100
    df_home_chase["home_team_id"] = 100
    df_home_chase["pre_match_prob_stage_b"] = 0.70

    df_away_chase = synthetic_innings2_data.iloc[:10].copy()
    df_away_chase["batting_team_id"] = 200
    df_away_chase["home_team_id"] = 100
    df_away_chase["pre_match_prob_stage_b"] = 0.70

    model = ChaseModel()
    prep_home = model._prepare_feature_dataframe(df_home_chase)
    prep_away = model._prepare_feature_dataframe(df_away_chase)

    # When home team chases, probability remains 0.70
    assert np.allclose(prep_home["pre_match_prob_stage_b"].values, 0.70)
    # When away team chases, probability is inverted to 1.0 - 0.70 = 0.30
    assert np.allclose(prep_away["pre_match_prob_stage_b"].values, 0.30)


def test_evaluate_chase_predictions() -> None:
    """Verify evaluation metric calculations for chase win predictions."""
    y_true = np.array([1, 0, 1, 0, 1])
    y_prob = np.array([0.90, 0.10, 0.85, 0.15, 0.95])

    m = evaluate_chase_predictions(y_true, y_prob)
    assert "brier_score" in m
    assert "log_loss" in m
    assert "roc_auc" in m
    assert "accuracy" in m
    assert 0.0 <= m["brier_score"] <= 0.25
    assert m["accuracy"] == 1.0

