"""Unit tests for Spell, Career, and Season Aggregators."""
import pandas as pd
import pytest

from ml.contribution.bowling.bowling_aggregator import BowlingSpellAggregator
from ml.contribution.bowling.bowling_season_aggregator import BowlingCareerSeasonAggregator


def test_spell_aggregator():
    aggregator = BowlingSpellAggregator()
    # Mock deliveries for 1 over: 6 legal dots -> 1 maiden, 0 runs, 0 wkts
    df = pd.DataFrame({
        "match_id": [1] * 6,
        "innings": [1] * 6,
        "bowler_id": [999] * 6,
        "overid": [4] * 6,
        "innings_ball_num": list(range(19, 25)),
        "is_legal_delivery": [True] * 6,
        "batter_runs": [0] * 6,
        "bowler_runs": [0] * 6,
        "extras_type": [None] * 6,
        "extras1_runs": [0] * 6,
        "is_wicket_event": [False] * 6,
        "is_bowler_wkt": [False] * 6,
        "erp": [1.3] * 6,
        "bcs": [1.3] * 6,
        "bwpa": [0.01] * 6,
        "leverage": [1.0] * 6,
        "wqm": [1.0] * 6,
        "v_wkt": [0.0] * 6,
        "unweighted_run_impact": [1.3] * 6,
        "dot_ball": [True] * 6,
        "consecutive_dots_after": list(range(1, 7)),
        "dot_pressure_index": [0.5] * 6,
        "rrr_pressure_index": [None] * 6,
        "first_inns_scoring_restriction": [1.3] * 6,
        "match_date": ["2024-05-01"] * 6,
        "season": ["2024"] * 6,
        "competition_category": ["IPL"] * 6,
        "venue_country": ["India"] * 6,
        "bowling_team_id": [1] * 6,
        "batting_team_id": [2] * 6,
    })
    spells = aggregator.aggregate_spells(df)
    assert len(spells) == 1
    spell = spells.iloc[0]
    assert spell["legal_balls"] == 6
    assert spell["overs"] == 1.0
    assert spell["bowler_runs"] == 0
    assert spell["maidens"] == 1
    assert spell["economy"] == 0.0
    assert spell["dot_pct"] == 100.0
    assert spell["total_bcs"] == pytest.approx(7.8, abs=1e-2)


def test_career_season_shrinkage():
    aggregator = BowlingCareerSeasonAggregator()
    # Mock spells for 2 bowlers: bowler A (12 balls, 20 BCS) vs bowler B (240 balls, 200 BCS)
    spells = pd.DataFrame({
        "bowler_id": [1, 2],
        "bowler_name": ["Bowler A", "Bowler B"],
        "match_id": [101, 102],
        "season": ["2024", "2024"],
        "legal_balls": [12, 240],
        "bowler_runs": [10, 260],
        "wickets": [1, 12],
        "maidens": [0, 2],
        "dot_balls": [6, 95],
        "boundaries": [1, 25],
        "total_erp": [5.0, 40.0],
        "total_bcs": [20.0, 200.0],
        "total_bwpa": [0.05, 0.40],
        "mean_leverage": [1.0, 1.0],
        "mean_wqm": [1.1, 1.2],
        "first_inns_restriction": [5.0, 40.0],
    })

    career = aggregator.aggregate_career(spells)
    assert len(career) == 2
    row_a = career[career["bowler_id"] == 1].iloc[0]
    row_b = career[career["bowler_id"] == 2].iloc[0]

    # Bowler A raw rate is 20/2 = 10.0 per over; after shrinkage toward mean, shrunk rate should be pulled down
    assert row_a["shrunk_bcs_per_over"] < row_a["bcs_per_over"]
    # Bowler B with large sample size should have shrunk rate very close to raw rate
    assert abs(row_b["shrunk_bcs_per_over"] - row_b["bcs_per_over"]) < 0.5
