"""Unit tests for Stage 5C Phase 7U and Strategy 4 scoring engines."""

import numpy as np
import pytest

from ml.contribution.expectations import WindowExpectationModels
from ml.contribution.phase7u_scorer import score_stint_phase7u
from ml.contribution.strategy4_scorer import score_stint_strategy4
from ml.contribution.schema import SCORE_MAX, SCORE_MIN, LEVERAGE_MAX, LEVERAGE_MIN


@pytest.fixture
def mock_models():
    b_grid = np.arange(121)
    par_curve = (b_grid / 120.0) * 166.5
    w_curve = {b: (b / 120.0) * 6.0 for b in range(0, 121, 6)}
    return WindowExpectationModels(
        category="IPL",
        regime="WALK_FORWARD_COMP_RF",
        n_prior_matches=50,
        par_total=166.5,
        par_curve=par_curve,
        w_curve=w_curve,
        efs_model=None,
        runs_model=None,
        sr_model=None,
        target_center=166.5,
        rrr_center=8.325,
        p2_runs_mean=19.8,
        p2_runs_std=21.6,
        p2_sr_mean=125.0,
        p2_sr_std=50.0,
        p2_norm_mean=-0.068,
        p2_norm_std=1.029,
        p3_norm_mean=0.159,
        p3_norm_std=1.513,
    )


@pytest.fixture
def sample_stint_inn1():
    return {
        "match_id": 14114,
        "innings": 1,
        "stint_id": 1,
        "player_id": 100,
        "team_id": 1,
        "opponent_team_id": 2,
        "competition_category": "IPL",
        "season": "2022",
        "match_date": "2022-04-01",
        "batting_order": 3,
        "entry_innings_ball_num": 15,
        "exit_innings_ball_num": 60,
        "entry_legal_balls": 14,
        "entry_over_notation": 2.2,
        "entry_over_decimal": 14.0 / 6.0,
        "entry_team_score": 25,
        "entry_wickets_lost": 1,
        "entry_wickets_remaining": 9,
        "entry_balls_remaining": 106,
        "entry_team_rr": 10.71,
        "exit_legal_balls": 55,
        "exit_over_notation": 9.1,
        "exit_over_decimal": 55.0 / 6.0,
        "exit_team_score": 90,
        "exit_wickets_lost": 3,
        "exit_wickets_remaining": 7,
        "exit_balls_remaining": 65,
        "overs_spent": 41.0 / 6.0,
        "team_runs_added": 65,
        "window_team_rr": 65.0 / (41.0 / 6.0),
        "wickets_lost_during_stay": 2,
        "actual_runs": 45,
        "balls_faced": 28,
        "actual_sr": 45.0 / 28.0 * 100.0,
        "fours": 4,
        "sixes": 2,
        "boundary_pct": 28.0 / 45.0 * 100.0,
        "dot_balls": 8,
        "dot_ball_pct": 8.0 / 28.0 * 100.0,
        "dismissal_status": "out",
        "dismissal_type_canonical": "Caught",
        "is_out": True,
        "is_not_out": False,
        "is_retired_hurt": False,
        "is_retire_out": False,
        "is_dnb": False,
        "is_impact": False,
        "is_roster_missing_uae_split": False,
        "has_unresolved_dismissal_in_match": False,
        "target_runs": None,
        "runs_required_entry": None,
        "runs_required_exit": None,
        "required_rr_entry": None,
        "required_rr_exit": None,
        "required_rr_change": None,
        "rr_gap_entry": None,
        "rr_gap_exit": None,
        "rr_gap_change": None,
        "target_progress_change": None,
    }


@pytest.fixture
def sample_stint_inn2():
    return {
        "match_id": 14114,
        "innings": 2,
        "stint_id": 1,
        "player_id": 200,
        "team_id": 2,
        "opponent_team_id": 1,
        "competition_category": "IPL",
        "season": "2022",
        "match_date": "2022-04-01",
        "batting_order": 4,
        "entry_innings_ball_num": 30,
        "exit_innings_ball_num": 90,
        "entry_legal_balls": 28,
        "entry_over_notation": 4.4,
        "entry_over_decimal": 28.0 / 6.0,
        "entry_team_score": 40,
        "entry_wickets_lost": 2,
        "entry_wickets_remaining": 8,
        "entry_balls_remaining": 92,
        "entry_team_rr": 8.57,
        "exit_legal_balls": 85,
        "exit_over_notation": 14.1,
        "exit_over_decimal": 85.0 / 6.0,
        "exit_team_score": 130,
        "exit_wickets_lost": 3,
        "exit_wickets_remaining": 7,
        "exit_balls_remaining": 35,
        "overs_spent": 57.0 / 6.0,
        "team_runs_added": 90,
        "window_team_rr": 90.0 / (57.0 / 6.0),
        "wickets_lost_during_stay": 1,
        "actual_runs": 60,
        "balls_faced": 35,
        "actual_sr": 60.0 / 35.0 * 100.0,
        "fours": 5,
        "sixes": 3,
        "boundary_pct": 38.0 / 60.0 * 100.0,
        "dot_balls": 6,
        "dot_ball_pct": 6.0 / 35.0 * 100.0,
        "dismissal_status": "not out",
        "dismissal_type_canonical": None,
        "is_out": False,
        "is_not_out": True,
        "is_retired_hurt": False,
        "is_retire_out": False,
        "is_dnb": False,
        "is_impact": False,
        "is_roster_missing_uae_split": False,
        "has_unresolved_dismissal_in_match": False,
        "target_runs": 175,
        "runs_required_entry": 135,
        "runs_required_exit": 45,
        "required_rr_entry": 135.0 * 6.0 / 92.0,
        "required_rr_exit": 45.0 * 6.0 / 35.0,
        "required_rr_change": (135.0 * 6.0 / 92.0) - (45.0 * 6.0 / 35.0),
        "rr_gap_entry": (135.0 * 6.0 / 92.0) - 8.57,
        "rr_gap_exit": (45.0 * 6.0 / 35.0) - (130.0 * 6.0 / 85.0),
        "rr_gap_change": ((135.0 * 6.0 / 92.0) - 8.57) - ((45.0 * 6.0 / 35.0) - (130.0 * 6.0 / 85.0)),
        "target_progress_change": (135.0 - 45.0) / 175.0,
    }


def test_phase7u_scoring_bounds_and_structure(sample_stint_inn1, sample_stint_inn2):
    res1 = score_stint_phase7u(sample_stint_inn1)
    res2 = score_stint_phase7u(sample_stint_inn2)

    for res in [res1, res2]:
        assert SCORE_MIN <= res["contribution_score"] <= SCORE_MAX
        assert SCORE_MIN <= res["p2_score"] <= SCORE_MAX
        assert SCORE_MIN <= res["p3_score"] <= SCORE_MAX
        assert LEVERAGE_MIN <= res["leverage_l"] <= LEVERAGE_MAX
        assert res["raw_contribution"] is not None


def test_strategy4_scoring_bounds_and_decision4_consistency(sample_stint_inn1, sample_stint_inn2, mock_models):
    res1 = score_stint_strategy4(sample_stint_inn1, mock_models)
    res2 = score_stint_strategy4(sample_stint_inn2, mock_models)

    for res in [res1, res2]:
        assert SCORE_MIN <= res["contribution_score"] <= SCORE_MAX
        assert SCORE_MIN <= res["p2_score"] <= SCORE_MAX
        assert SCORE_MIN <= res["p3_score"] <= SCORE_MAX
        assert LEVERAGE_MIN <= res["leverage_l"] <= LEVERAGE_MAX

    # Decision 4 Verification:
    # Inn 1 raw_contribution = 0.5 * (run_dev / 10.0) + 0.5 * p3_raw
    expected_raw_inn1 = round(0.50 * (res1["run_deviation"] / 10.0) + 0.50 * res1["p3_raw"], 4)
    assert abs(res1["raw_contribution"] - expected_raw_inn1) < 1e-4

    # Inn 2 raw_contribution = 0.5 * (z2 * L) + 0.5 * (z3 * L)
    expected_raw_inn2 = round(0.50 * (res1["z2"] * res1["leverage_l"]) + 0.50 * (res1["z3"] * res1["leverage_l"]), 4) # checks formula shape
    expected_raw_inn2_actual = round(0.50 * (res2["z2"] * res2["leverage_l"]) + 0.50 * (res2["z3"] * res2["leverage_l"]), 4)
    assert abs(res2["raw_contribution"] - expected_raw_inn2_actual) < 1e-4


def test_dnb_returns_strict_null(mock_models):
    dnb_stint = {
        "match_id": 99999,
        "innings": 1,
        "player_id": 999,
        "is_dnb": True,
        "actual_runs": 0,
        "balls_faced": 0,
    }
    p7u_res = score_stint_phase7u(dnb_stint)
    s4_res = score_stint_strategy4(dnb_stint, mock_models)

    assert p7u_res["contribution_score"] is None
    assert p7u_res["raw_contribution"] is None
    assert s4_res["contribution_score"] is None
    assert s4_res["raw_contribution"] is None


def test_sensitivity_audit_switches(sample_stint_inn2, mock_models):
    # Option 1C Chase f_res sensitivity
    res_primary = score_stint_strategy4(sample_stint_inn2, mock_models, use_chase_f_res=False)
    res_opt1c = score_stint_strategy4(sample_stint_inn2, mock_models, use_chase_f_res=True)
    assert res_primary["contribution_score"] is not None
    assert res_opt1c["contribution_score"] is not None

    # rr_gap causal sensitivity
    p7u_gap0 = score_stint_phase7u(sample_stint_inn2, use_causal_rr_gap=False)
    p7u_causal = score_stint_phase7u(sample_stint_inn2, use_causal_rr_gap=True)
    assert p7u_gap0["contribution_score"] is not None
    assert p7u_causal["contribution_score"] is not None

    # Personal dismissal sensitivity
    s4_partner = score_stint_strategy4(sample_stint_inn2, mock_models, use_personal_dismissal=False)
    s4_personal = score_stint_strategy4(sample_stint_inn2, mock_models, use_personal_dismissal=True)
    assert s4_partner["contribution_score"] is not None
    assert s4_personal["contribution_score"] is not None

