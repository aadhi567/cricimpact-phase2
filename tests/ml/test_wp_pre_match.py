"""Unit tests for Stage 6B.2 Pre-Match Models and Expanding-Window Out-of-Fold Anchor Generator."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from ml.win_probability.pre_match_model import (
    DEFAULT_PRE_MATCH_PROB,
    MIN_TRAIN_MATCHES_OOF,
    PreMatchAnchorGenerator,
    PreMatchModel,
    PreMatchPredictionResult,
    evaluate_pre_match_predictions,
)
from ml.win_probability.schema import (
    STAGE_A_FEATURES,
    STAGE_B_FEATURES,
    TARGET_HOME_WIN,
    validate_feature_matrix_no_leakage,
)


@pytest.fixture
def synthetic_pre_match_data() -> pd.DataFrame:
    """Generate 40 synthetic match rows with realistic feature distributions."""
    np.random.seed(42)
    n = 40
    records = []

    dates = pd.date_range("2024-01-01", periods=n, freq="D").strftime("%Y-%m-%d").tolist()

    for i in range(n):
        comp = "IPL" if i % 2 == 0 else "T20I"
        home_win_rate = float(np.clip(0.5 + np.random.normal(0, 0.1), 0.2, 0.8))
        away_win_rate = float(np.clip(0.5 + np.random.normal(0, 0.1), 0.2, 0.8))
        diff = home_win_rate - away_win_rate

        mean_abc = float(55.0 + np.random.normal(0, 3.0))
        rel_abc = float(np.random.normal(0, 2.0))

        # Outcome with correlation to diff
        prob_win = 1.0 / (1.0 + np.exp(-2.0 * diff))
        y = int(np.random.rand() < prob_win)

        row = {
            "match_id": 1000 + i,
            "match_date": dates[i],
            "competition_category": comp,
            TARGET_HOME_WIN: y,
            # Stage A features
            "venue_avg_first_inn_score": 165.0 + np.random.normal(0, 10.0),
            "venue_chase_win_pct": 0.52 + np.random.normal(0, 0.05),
            "venue_avg_death_rr": 9.5 + np.random.normal(0, 0.5),
            "venue_pace_spin_wicket_ratio": 1.2 + np.random.normal(0, 0.2),
            "team_a_prior_win_rate": home_win_rate,
            "team_b_prior_win_rate": away_win_rate,
            # Stage B features
            "pre_match_prob_stage_a": float(prob_win),
            "batting_lineup_top3_abc": mean_abc + 5.0,
            "batting_lineup_mid4_abc": mean_abc,
            "batting_lineup_tail_abc": mean_abc - 10.0,
            "batting_lineup_mean_abc": mean_abc,
            "batting_lineup_std_abc": 8.0,
            "batting_cold_start_count": int(np.random.choice([0, 1, 2])),
            "bowling_unit_powerplay_econ": 7.5,
            "bowling_unit_middle_econ": 7.2,
            "bowling_unit_death_econ": 10.1,
            "bowling_unit_strike_rate": 18.5,
            "relative_batting_edge": rel_abc,
            "is_batting_team_toss_winner": bool(i % 2 == 0),
            "toss_decision_bat": bool(i % 3 == 0),
            "team_prior_win_rate_diff": diff,
            "stage_b_pending": False,
        }
        records.append(row)

    return pd.DataFrame(records)


def test_pre_match_prediction_result_dataclass() -> None:
    """Verify PreMatchPredictionResult enforces probability bounds and complementarity."""
    # Valid result
    res = PreMatchPredictionResult(
        match_id=101,
        p_team_a_stage_a=0.55,
        p_team_b_stage_a=0.45,
        p_team_a_stage_b=0.58,
        p_team_b_stage_b=0.42,
        stage_b_prob_delta=0.03,
        stage_b_pending=False,
    )
    assert res.match_id == 101
    assert abs(res.p_team_a_stage_a + res.p_team_b_stage_a - 1.0) < 1e-6
    assert abs(res.p_team_a_stage_b + res.p_team_b_stage_b - 1.0) < 1e-6

    # Invalid Stage A sum
    with pytest.raises(ValueError, match="Stage A probabilities must sum to 1.0"):
        PreMatchPredictionResult(
            match_id=102,
            p_team_a_stage_a=0.60,
            p_team_b_stage_a=0.50,
            p_team_a_stage_b=0.58,
            p_team_b_stage_b=0.42,
            stage_b_prob_delta=0.0,
            stage_b_pending=False,
        )

    # Invalid Stage B sum
    with pytest.raises(ValueError, match="Stage B probabilities must sum to 1.0"):
        PreMatchPredictionResult(
            match_id=103,
            p_team_a_stage_a=0.50,
            p_team_b_stage_a=0.50,
            p_team_a_stage_b=0.70,
            p_team_b_stage_b=0.40,
            stage_b_prob_delta=0.0,
            stage_b_pending=False,
        )


def test_pre_match_model_fit_and_predict(synthetic_pre_match_data: pd.DataFrame) -> None:
    """Verify fitting and predicting Stage A and Stage B models."""
    train_df = synthetic_pre_match_data.iloc[:30]
    test_df = synthetic_pre_match_data.iloc[30:]

    model = PreMatchModel(c_stage_a=0.5, c_stage_b=0.3)
    assert not model.is_fitted

    with pytest.raises(RuntimeError, match="must be fitted"):
        model.predict_stage_a(test_df)

    model.fit(train_df)
    assert model.is_fitted

    # Predict Stage A
    p_a = model.predict_stage_a(test_df)
    assert len(p_a) == len(test_df)
    assert np.all(p_a >= 0.0) and np.all(p_a <= 1.0)

    # Predict Stage B
    p_b = model.predict_stage_b(test_df)
    assert len(p_b) == len(test_df)
    assert np.all(p_b >= 0.0) and np.all(p_b <= 1.0)

    # Single match predict
    single_row = test_df.iloc[0].to_dict()
    res = model.predict_match(single_row)
    assert isinstance(res, PreMatchPredictionResult)
    assert res.match_id == int(single_row["match_id"])
    assert 0.0 <= res.p_team_a_stage_a <= 1.0
    assert 0.0 <= res.p_team_a_stage_b <= 1.0
    assert abs(res.p_team_a_stage_a + res.p_team_b_stage_a - 1.0) < 1e-4
    assert abs(res.p_team_a_stage_b + res.p_team_b_stage_b - 1.0) < 1e-4
    assert abs(res.stage_b_prob_delta - (res.p_team_a_stage_b - res.p_team_a_stage_a)) < 1e-4


def test_pre_match_stage_b_pending_behavior(synthetic_pre_match_data: pd.DataFrame) -> None:
    """Verify that when stage_b_pending is True, Stage B falls back to Stage A exactly."""
    train_df = synthetic_pre_match_data.iloc[:30]
    test_df = synthetic_pre_match_data.iloc[30:].copy()

    model = PreMatchModel()
    model.fit(train_df)

    # Mark some rows as pending
    test_df["stage_b_pending"] = [True, False, True, False, True, False, True, False, True, False]

    p_a = model.predict_stage_a(test_df)
    p_b = model.predict_stage_b(test_df)

    pending_mask = test_df["stage_b_pending"].values
    # For pending rows, p_b must match p_a
    np.testing.assert_allclose(p_b[pending_mask], p_a[pending_mask], rtol=1e-5)

    # In predict_match for a pending match
    single_pending = test_df[test_df["stage_b_pending"]].iloc[0].to_dict()
    res_pending = model.predict_match(single_pending)
    assert res_pending.stage_b_pending is True
    assert res_pending.stage_b_prob_delta == 0.0
    assert abs(res_pending.p_team_a_stage_b - res_pending.p_team_a_stage_a) < 1e-5


def test_pre_match_leakage_prevention() -> None:
    """Verify that feature lists in PreMatchModel never include forbidden leakage columns."""
    model = PreMatchModel()
    validate_feature_matrix_no_leakage(model.features_a)
    validate_feature_matrix_no_leakage(model.features_b)

    # Verify Stage A features contain only 6 numeric features (7 minus competition_category)
    assert len(model.features_a) == 6
    # Verify Stage B features contain only 19 numeric features (20 minus competition_category)
    assert len(model.features_b) == 19


def test_oof_anchor_generator_causality_and_no_leakage(synthetic_pre_match_data: pd.DataFrame) -> None:
    """Verify expanding-window out-of-fold generation is strictly causal with zero in-sample leakage."""
    generator = PreMatchAnchorGenerator(min_train_matches=30)
    df = synthetic_pre_match_data.copy()

    oof_df = generator.generate_expanding_window_oof_anchors(df)
    assert len(oof_df) == len(df)
    assert list(oof_df.columns) == [
        "match_id",
        "match_date",
        "pre_match_prob_stage_a",
        "pre_match_prob_stage_b",
        "stage_b_prob_delta",
        "is_oof_generated",
        "training_sample_size",
    ]

    # Verify cold start for first 30 matches
    cold_start_rows = oof_df.iloc[:30]
    assert not cold_start_rows["is_oof_generated"].any()
    assert (cold_start_rows["training_sample_size"] < 30).all()

    # Verify expanding window for matches 30..39
    oof_rows = oof_df.iloc[30:]
    assert oof_rows["is_oof_generated"].all()
    assert (oof_rows["training_sample_size"] >= 30).all()

    # Verify training sample sizes increase monotonically
    sample_sizes = oof_df["training_sample_size"].tolist()
    for k in range(1, len(sample_sizes)):
        assert sample_sizes[k] >= sample_sizes[k - 1]

    # CRITICAL LEAKAGE TEST:
    # Target outcome of match 35 must NOT affect the anchor generated for match 35.
    target_match_id = int(df.iloc[35]["match_id"])
    orig_prob = oof_df.loc[oof_df["match_id"] == target_match_id, "pre_match_prob_stage_b"].values[0]

    # Invert target of match 35
    df_mutated = df.copy()
    df_mutated.loc[df_mutated["match_id"] == target_match_id, TARGET_HOME_WIN] = (
        1 - df_mutated.loc[df_mutated["match_id"] == target_match_id, TARGET_HOME_WIN]
    )

    oof_mutated = generator.generate_expanding_window_oof_anchors(df_mutated)
    mutated_prob = oof_mutated.loc[oof_mutated["match_id"] == target_match_id, "pre_match_prob_stage_b"].values[0]

    # Probabilities must be EXACTLY identical because match 35 is strictly out-of-fold!
    assert abs(orig_prob - mutated_prob) < 1e-7, (
        f"In-sample leakage detected! Changing target of match {target_match_id} changed its anchor: "
        f"{orig_prob} vs {mutated_prob}"
    )


def test_evaluate_pre_match_predictions_metrics() -> None:
    """Verify evaluation metric calculations."""
    y_true = np.array([1, 0, 1, 0, 1])
    y_prob = np.array([0.9, 0.1, 0.8, 0.2, 0.7])

    metrics = evaluate_pre_match_predictions(y_true, y_prob)

    assert "brier_score" in metrics
    assert "log_loss" in metrics
    assert "roc_auc" in metrics
    assert "accuracy" in metrics

    assert 0.0 <= metrics["brier_score"] <= 0.25
    assert metrics["log_loss"] >= 0.0
    assert metrics["roc_auc"] == 1.0  # Perfect rank order
    assert metrics["accuracy"] == 1.0

