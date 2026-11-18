"""Unit tests for Stage 5C causality, outcome-invariance, and aggregations."""

import numpy as np
import pandas as pd
import pytest

from ml.contribution.aggregation import (
    build_pre_match_causal_abc_features,
    build_season_competition_metrics,
)
from ml.contribution.schema import TRACK_A_TAG, TRACK_B_TAG


@pytest.fixture
def sample_scored_matches():
    # 3 matches chronologically ordered
    rows = [
        # Match 1: 2022-04-01
        {
            "match_id": 1,
            "match_date": "2022-04-01",
            "innings": 1,
            "player_id": 10,
            "team_id": 100,
            "opponent_team_id": 200,
            "competition_category": "IPL",
            "season": "2022",
            "batting_order": 1,
            "entry_over_notation": 0.0,
            "exit_over_notation": 5.4,
            "balls_faced": 20,
            "actual_runs": 35,
            "is_out": True,
            "is_not_out": False,
            "is_dnb": False,
            "c_eff": 55.0,
            "contribution_score": 62.5,
            "raw_contribution": 1.25,
        },
        {
            "match_id": 1,
            "match_date": "2022-04-01",
            "innings": 1,
            "player_id": 20,
            "team_id": 100,
            "opponent_team_id": 200,
            "competition_category": "IPL",
            "season": "2022",
            "batting_order": 99,
            "entry_over_notation": None,
            "exit_over_notation": None,
            "balls_faced": 0,
            "actual_runs": 0,
            "is_out": False,
            "is_not_out": False,
            "is_dnb": True,
            "c_eff": None,
            "contribution_score": None,
            "raw_contribution": None,
        },
        # Match 2: 2022-04-05
        {
            "match_id": 2,
            "match_date": "2022-04-05",
            "innings": 1,
            "player_id": 10,
            "team_id": 100,
            "opponent_team_id": 300,
            "competition_category": "IPL",
            "season": "2022",
            "batting_order": 1,
            "entry_over_notation": 0.0,
            "exit_over_notation": 18.2,
            "balls_faced": 50,
            "actual_runs": 75,
            "is_out": False,
            "is_not_out": True,
            "is_dnb": False,
            "c_eff": 65.0,
            "contribution_score": 78.4,
            "raw_contribution": 2.10,
        },
        # Match 3: 2022-04-10
        {
            "match_id": 3,
            "match_date": "2022-04-10",
            "innings": 1,
            "player_id": 10,
            "team_id": 100,
            "opponent_team_id": 400,
            "competition_category": "IPL",
            "season": "2022",
            "batting_order": 1,
            "entry_over_notation": 0.0,
            "exit_over_notation": 2.0,
            "balls_faced": 5,
            "actual_runs": 2,
            "is_out": True,
            "is_not_out": False,
            "is_dnb": False,
            "c_eff": 45.0,
            "contribution_score": 38.0,
            "raw_contribution": -0.85,
        },
    ]
    return pd.DataFrame(rows)


def test_season_competition_aggregation_and_dnb_non_dilution(sample_scored_matches):
    season_df = build_season_competition_metrics(sample_scored_matches, engine_name="strategy4_universal")
    assert len(season_df) == 2  # player 10 and player 20

    # Player 10: 3 matches played, 3 batted innings
    p10 = season_df[season_df["player_id"] == 10].iloc[0]
    assert p10["matches_played"] == 3
    assert p10["batting_innings"] == 3
    assert p10["did_not_bat_matches"] == 0
    expected_abc = round((62.5 + 78.4 + 38.0) / 3.0, 2)
    assert abs(p10["average_contribution_score"] - expected_abc) <= 0.005
    assert p10["track_tag"] == TRACK_A_TAG

    # ABC-R01: contribution_per_batting_opportunity = tot_pos_raw / n
    expected_pos_tot = round(1.25 + 2.10, 4)
    expected_per_opp = round(expected_pos_tot / 3.0, 4)
    assert abs(p10["contribution_per_batting_opportunity"] - expected_per_opp) <= 0.001

    # Player 20: 1 match played, 0 batted innings (DNB)
    p20 = season_df[season_df["player_id"] == 20].iloc[0]
    assert p20["matches_played"] == 1
    assert p20["batting_innings"] == 0
    assert p20["did_not_bat_matches"] == 1
    assert pd.isna(p20["average_contribution_score"])
    assert p20["total_positive_raw_contribution"] == 0.0
    assert pd.isna(p20["contribution_per_batting_opportunity"])


def test_causal_track_b_features_monotonicity(sample_scored_matches):
    track_b_df = build_pre_match_causal_abc_features(sample_scored_matches, engine_name="strategy4_universal")
    assert len(track_b_df) == len(sample_scored_matches)
    assert (track_b_df["track_tag"] == TRACK_B_TAG).all()

    # Match 1 (first match on 2022-04-01): player 10 has 0 prior innings
    m1_p10 = track_b_df[(track_b_df["match_id"] == 1) & (track_b_df["player_id"] == 10)].iloc[0]
    assert m1_p10["batted_inns_prior_all"] == 0
    assert pd.isna(m1_p10["abc_prior_all_mean"])
    assert bool(m1_p10["is_abc_cold_start"]) is True
    assert m1_p10["abc_prior_shrunk"] == 50.0

    # Match 2 (2022-04-05): player 10 sees strictly match 1 (cs=62.5)
    m2_p10 = track_b_df[(track_b_df["match_id"] == 2) & (track_b_df["player_id"] == 10)].iloc[0]
    assert m2_p10["batted_inns_prior_all"] == 1
    assert m2_p10["abc_prior_all_mean"] == 62.5
    assert bool(m2_p10["is_abc_cold_start"]) is False

    # Match 3 (2022-04-10): player 10 sees match 1 and match 2 (mean 70.45)
    m3_p10 = track_b_df[(track_b_df["match_id"] == 3) & (track_b_df["player_id"] == 10)].iloc[0]
    assert m3_p10["batted_inns_prior_all"] == 2
    assert abs(m3_p10["abc_prior_all_mean"] - round((62.5 + 78.4) / 2.0, 2)) <= 0.01


def test_future_perturbation_invariance(sample_scored_matches):
    # If we perturb Match 3 score, Match 1 and Match 2 pre-match features must be IDENTICAL
    perturbed = sample_scored_matches.copy()
    perturbed.loc[perturbed["match_id"] == 3, "contribution_score"] = 99.9

    tb_orig = build_pre_match_causal_abc_features(sample_scored_matches, engine_name="strategy4_universal")
    tb_pert = build_pre_match_causal_abc_features(perturbed, engine_name="strategy4_universal")

    # Match 1 and 2 rows must match bit-for-bit
    orig_m12 = tb_orig[tb_orig["match_id"].isin([1, 2])].reset_index(drop=True)
    pert_m12 = tb_pert[tb_pert["match_id"].isin([1, 2])].reset_index(drop=True)

    pd.testing.assert_frame_equal(orig_m12, pert_m12)
