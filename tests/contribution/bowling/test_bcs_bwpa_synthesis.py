"""Unit tests for BCS Synthesis, bWPA attribution, and non-bowler safeguards."""
import pandas as pd
import pytest

from ml.contribution.bowling.bcs_engine import BowlingContributionEngine
from ml.contribution.bowling.bwpa_engine import BowlerWinProbabilityAddedEngine


@pytest.fixture
def bcs_engine():
    return BowlingContributionEngine()


@pytest.fixture
def bwpa_engine():
    return BowlerWinProbabilityAddedEngine()


def test_bcs_bowler_wicket_credit(bcs_engine):
    # Bowled dismissal
    res = bcs_engine.evaluate_delivery(
        match_id=1,
        innings=1,
        innings_ball_num=15,
        bowler_id=101,
        striker_id=202,
        is_legal=True,
        innings_phase="powerplay",
        score_before=25,
        wickets_lost_before=1,
        overid=3,
        batter_runs=0,
        extras_type=None,
        extras1_runs=0,
        is_wicket_event=True,
        dismissal_type_canonical="Bowled",
        dismissed_player_id=202,
    )
    assert res.is_bowler_wkt is True
    assert res.v_wkt > 0.0
    assert res.bcs > 0.0
    assert res.alpha_attr == 1.0


def test_bcs_run_out_exclusion(bcs_engine):
    # Run out off a single
    res = bcs_engine.evaluate_delivery(
        match_id=1,
        innings=1,
        innings_ball_num=50,
        bowler_id=101,
        striker_id=202,
        is_legal=True,
        innings_phase="middle",
        score_before=60,
        wickets_lost_before=2,
        overid=9,
        batter_runs=1,
        extras_type=None,
        extras1_runs=0,
        is_wicket_event=True,
        dismissal_type_canonical="RunOut",
        dismissed_player_id=303,
    )
    assert res.is_bowler_wkt is False
    assert res.v_wkt == 0.0
    assert res.alpha_attr == 0.0
    # Bowler only gets credit for 1 run conceded (exp - 1)
    assert res.unweighted_run_impact == pytest.approx(res.erp, abs=1e-4)


def test_bcs_pure_byes_safeguard(bcs_engine):
    # 4 byes conceded due to keeper miss
    res = bcs_engine.evaluate_delivery(
        match_id=1,
        innings=1,
        innings_ball_num=90,
        bowler_id=101,
        striker_id=202,
        is_legal=True,
        innings_phase="middle",
        score_before=110,
        wickets_lost_before=3,
        overid=15,
        batter_runs=0,
        extras_type="byes",
        extras1_runs=4,
        is_wicket_event=False,
        dismissal_type_canonical=None,
        dismissed_player_id=None,
    )
    assert res.is_non_bowler_extra is True
    assert res.bowler_runs == 0
    assert res.erp == 0.0
    assert res.bcs == 0.0
    assert res.alpha_attr == 0.0


def test_bwpa_attribution_filter(bwpa_engine):
    # Standard legal delivery
    bwpa_std, _ = bwpa_engine.evaluate_delivery(p_bat_current=0.60, p_bat_next=0.55, alpha_attr=1.0)
    assert bwpa_std == pytest.approx(0.05, abs=1e-4)

    # Keeper bye or run out: alpha_attr = 0.0 -> bWPA = 0.0
    bwpa_zero, _ = bwpa_engine.evaluate_delivery(p_bat_current=0.60, p_bat_next=0.50, alpha_attr=0.0)
    assert bwpa_zero == 0.0
