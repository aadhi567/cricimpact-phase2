"""Unit tests for Match Leverage Engine."""
import pandas as pd
import pytest

from ml.contribution.bowling.leverage_engine import MatchLeverageEngine


@pytest.fixture
def lev_engine():
    return MatchLeverageEngine()


def test_leverage_bounds_enforcement(lev_engine):
    # Test blowout (low leverage)
    lev_blowout = lev_engine.evaluate_delivery(
        innings=2,
        phase="middle",
        wickets_lost_before=1,
        required_run_rate=2.0,  # 15 req off 40 balls
        legal_balls_remaining_before=40,
    )
    assert lev_blowout >= 0.50
    assert lev_blowout <= 0.80

    # Test high-pressure thriller (high leverage)
    lev_thriller = lev_engine.evaluate_delivery(
        innings=2,
        phase="death",
        wickets_lost_before=6,
        required_run_rate=10.5,
        legal_balls_remaining_before=12,
    )
    assert lev_thriller > 1.50
    assert lev_thriller <= 2.00


def test_leverage_first_innings_stability(lev_engine):
    # First innings leverage increases moderately with phase and wickets
    lev_i1_pp = lev_engine.evaluate_delivery(innings=1, phase="powerplay", wickets_lost_before=0)
    lev_i1_death = lev_engine.evaluate_delivery(innings=1, phase="death", wickets_lost_before=5)
    assert 0.50 <= lev_i1_pp <= 2.00
    assert 0.50 <= lev_i1_death <= 2.00
    assert lev_i1_death > lev_i1_pp


def test_leverage_dataframe_vectorized(lev_engine):
    df = pd.DataFrame({
        "innings": [1, 2, 2],
        "innings_phase": ["middle", "death", "middle"],
        "wickets_lost_before": [2, 5, 1],
        "required_run_rate": [None, 9.5, 3.0],
        "legal_balls_remaining_before": [60, 18, 50],
    })
    levs = lev_engine.evaluate_dataframe(df)
    assert len(levs) == 3
    assert all(0.50 <= x <= 2.00 for x in levs)
    assert levs[1] > levs[2]  # Tight death chase > dead blowout
