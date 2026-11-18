"""Unit tests for Context-Dependent Wicket Value (V_wkt) Engine."""
import pandas as pd
import pytest

from ml.contribution.bowling.wicket_value_engine import ContextWicketValueEngine


@pytest.fixture
def wkt_val_engine():
    return ContextWicketValueEngine()


def test_wicket_value_phase_gradient(wkt_val_engine):
    # Early overs (Powerplay) should save more future runs than Death overs
    v_pp = wkt_val_engine.evaluate_delivery(overid=2, wickets_lost_before=0, innings_phase="powerplay")
    v_mid = wkt_val_engine.evaluate_delivery(overid=10, wickets_lost_before=2, innings_phase="middle")
    v_death = wkt_val_engine.evaluate_delivery(overid=19, wickets_lost_before=5, innings_phase="death")

    assert v_pp > v_mid > v_death
    assert v_pp >= 10.0
    assert v_death <= 6.0


def test_wicket_value_bounds(wkt_val_engine):
    # Value must be positive and bounded between 2.0 and 18.0
    for ov in [1, 5, 10, 15, 20]:
        for w in [0, 2, 5, 8]:
            val = wkt_val_engine.evaluate_delivery(overid=ov, wickets_lost_before=w)
            assert 2.0 <= val <= 18.0


def test_wicket_value_dataframe(wkt_val_engine):
    df = pd.DataFrame({
        "overid": [3, 11, 18],
        "wickets_lost_before": [1, 3, 6],
        "innings_phase": ["powerplay", "middle", "death"],
    })
    res = wkt_val_engine.evaluate_dataframe(df)
    assert "V_wkt" in res.columns
    assert len(res) == 3
    assert res.loc[0, "V_wkt"] > res.loc[2, "V_wkt"]
