"""Unit tests for Stage 6B feature engineering, team strength aggregation, and venue priors."""

from __future__ import annotations

import pandas as pd
import pytest

from ml.win_probability.feature_extractor import calculate_resource_percentage
from ml.win_probability.team_strength import (
    DEFAULT_COLD_START_ABC,
    DEFAULT_TAIL_ABC,
    TeamStrengthAggregator,
)
from ml.win_probability.venue_priors import (
    CATEGORY_VENUE_DEFAULTS,
    VenuePriorsCalculator,
)


@pytest.fixture
def synthetic_pe_and_abc() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Create minimal synthetic playing eleven, Track B ABC, and match states for unit testing."""
    # 1. Playing eleven for 2 teams in match 9001 (standard 11 players each)
    pe_rows = []
    # Team 10: 11 players
    for i in range(1, 12):
        pe_rows.append({"match_id": 9001, "team_id": 10, "player_id": 100 + i, "batting_order": float(i), "is_played": 1, "is_impact": 0, "is_impact_off": 0})
    # Team 20: 12 players (IPL with impact player: player 203 subbed off, player 212 subbed on)
    for i in range(1, 12):
        is_off = 1 if i == 3 else 0
        pe_rows.append({"match_id": 9001, "team_id": 20, "player_id": 200 + i, "batting_order": float(i), "is_played": 1, "is_impact": 0, "is_impact_off": is_off})
    # Add impact player on
    pe_rows.append({"match_id": 9001, "team_id": 20, "player_id": 212, "batting_order": 12.0, "is_played": 1, "is_impact": 1, "is_impact_off": 0})

    pe_df = pd.DataFrame(pe_rows)

    # 2. Track B ABC records
    abc_rows = []
    for i in range(1, 12):
        abc_rows.append({"match_id": 9001, "match_date": "2024-05-10", "team_id": 10, "player_id": 100 + i, "abc_prior_shrunk": 55.0 + i, "is_abc_cold_start": False})
    for i in range(1, 13):
        is_cold = (i == 12)
        score = DEFAULT_COLD_START_ABC if is_cold else 50.0 + i
        abc_rows.append({"match_id": 9001, "match_date": "2024-05-10", "team_id": 20, "player_id": 200 + i, "abc_prior_shrunk": score, "is_abc_cold_start": is_cold})

    abc_df = pd.DataFrame(abc_rows)

    # 3. Match states for bowling history
    ms_rows = [
        {"match_id": 8001, "match_date": "2024-04-01", "venue_id": 99, "competition_category": "IPL", "innings": 1, "bowling_team_id": 20, "innings_phase": "powerplay", "team_runs": 45, "is_legal_delivery": 36, "is_wicket_event": 2, "score_after": 170, "win_team_id_raw": 20, "batting_team_id": 10},
        {"match_id": 8001, "match_date": "2024-04-01", "venue_id": 99, "competition_category": "IPL", "innings": 1, "bowling_team_id": 20, "innings_phase": "middle", "team_runs": 65, "is_legal_delivery": 54, "is_wicket_event": 3, "score_after": 170, "win_team_id_raw": 20, "batting_team_id": 10},
        {"match_id": 8001, "match_date": "2024-04-01", "venue_id": 99, "competition_category": "IPL", "innings": 1, "bowling_team_id": 20, "innings_phase": "death", "team_runs": 60, "is_legal_delivery": 30, "is_wicket_event": 2, "score_after": 170, "win_team_id_raw": 20, "batting_team_id": 10},
        {"match_id": 8001, "match_date": "2024-04-01", "venue_id": 99, "competition_category": "IPL", "innings": 2, "bowling_team_id": 10, "innings_phase": "middle", "team_runs": 70, "is_legal_delivery": 60, "is_wicket_event": 1, "score_after": 171, "win_team_id_raw": 20, "batting_team_id": 20},
    ]
    ms_df = pd.DataFrame(ms_rows)

    return pe_df, abc_df, ms_df


def test_team_strength_active_lineup_and_impact_filtering(synthetic_pe_and_abc) -> None:
    """Verify that Impact Player substitution produces exactly 11 active players."""
    pe_df, abc_df, ms_df = synthetic_pe_and_abc
    agg = TeamStrengthAggregator(pe_df, abc_df, ms_df)

    # Team 10: Standard 11 players
    lineup10 = agg.get_active_lineup(9001, 10)
    assert len(lineup10) == 11
    assert [p[0] for p in lineup10] == [100 + i for i in range(1, 12)]

    # Team 20: 12 players in roster, but player 203 subbed off -> exactly 11 active players
    lineup20 = agg.get_active_lineup(9001, 20)
    assert len(lineup20) == 11
    player_ids_20 = [p[0] for p in lineup20]
    assert 203 not in player_ids_20  # Substituted off
    assert 212 in player_ids_20  # Impact player included


def test_team_strength_aggregations(synthetic_pe_and_abc) -> None:
    """Verify top-3, mid-4, tail, and lineup mean prior ABC calculations."""
    pe_df, abc_df, ms_df = synthetic_pe_and_abc
    agg = TeamStrengthAggregator(pe_df, abc_df, ms_df)

    # Team 10 batters have scores 56, 57, 58 (top 3) -> mean 57.0
    strength10 = agg.compute_batting_strength(9001, 10, "2024-05-10", "IPL")
    assert strength10["batting_lineup_top3_abc"] == pytest.approx(57.0)
    # Batters 4-7 have scores 59, 60, 61, 62 -> mean 60.5
    assert strength10["batting_lineup_mid4_abc"] == pytest.approx(60.5)
    # Batters 8-11 have scores 63, 64, 65, 66 -> mean 64.5
    assert strength10["batting_lineup_tail_abc"] == pytest.approx(64.5)
    assert strength10["batting_cold_start_count"] == 0


def test_team_strength_missing_xi_fallback(synthetic_pe_and_abc) -> None:
    """Verify fallback to franchise historical mean when playing XI is unannounced (Stage A)."""
    pe_df, abc_df, ms_df = synthetic_pe_and_abc
    agg = TeamStrengthAggregator(pe_df, abc_df, ms_df)

    # Query an unknown team with empty XI
    strength_fallback = agg.compute_batting_strength(9999, 999, "2024-05-10", "IPL")
    assert strength_fallback["batting_lineup_mean_abc"] == pytest.approx(DEFAULT_COLD_START_ABC)
    assert strength_fallback["batting_cold_start_count"] == 11.0


def test_venue_priors_bayesian_shrinkage(synthetic_pe_and_abc) -> None:
    """Verify that low-sample venues shrink toward competition category baselines."""
    _, _, ms_df = synthetic_pe_and_abc
    calc = VenuePriorsCalculator(ms_df)

    # Venue 99 has only 1 prior match (score 170) before 2024-05-01
    priors = calc.get_venue_priors(99, "2024-05-01", "IPL")
    default_ipl = CATEGORY_VENUE_DEFAULTS["IPL"]["venue_avg_first_inn_score"]  # 186.5

    # With weight w = 1 / (1 + 5) = 1/6: shrunk = (1/6)*170 + (5/6)*186.5 = 28.33 + 155.42 = 183.75
    assert priors["venue_prior_sample_size"] == 1.0
    assert priors["venue_avg_first_inn_score"] == pytest.approx(183.75, abs=0.5)

    # Completely unvisited venue (sample size 0) gets pure category default
    unvisited = calc.get_venue_priors(777, "2024-05-01", "IPL")
    assert unvisited["venue_prior_sample_size"] == 0.0
    assert unvisited["venue_avg_first_inn_score"] == pytest.approx(default_ipl)


def test_resource_percentage_bounds() -> None:
    """Verify resource percentage physical boundaries and monotonicity."""
    # Full resources at start
    assert calculate_resource_percentage(10, 120) == pytest.approx(100.0)

    # Zero resources when balls exhausted or all out
    assert calculate_resource_percentage(10, 0) == pytest.approx(0.0)
    assert calculate_resource_percentage(0, 60) == pytest.approx(0.0)

    # Monotonicity: losing wickets reduces resources
    r_10_wkts = calculate_resource_percentage(10, 60)
    r_5_wkts = calculate_resource_percentage(5, 60)
    r_1_wkt = calculate_resource_percentage(1, 60)
    assert r_10_wkts > r_5_wkts > r_1_wkt

