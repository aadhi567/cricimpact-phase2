"""Unit tests for Expected Runs Prevented (ERP) Engine."""
import pandas as pd
import pytest

from ml.contribution.bowling.erp_engine import ExpectedRunsPreventedEngine


@pytest.fixture
def erp_engine():
    return ExpectedRunsPreventedEngine()


def test_calculate_bowler_runs_legal_runs(erp_engine):
    # Standard legal runs
    assert erp_engine.calculate_bowler_runs(batter_runs=4, extras_type=None, extras1_runs=0) == 4
    assert erp_engine.calculate_bowler_runs(batter_runs=0, extras_type=None, extras1_runs=0) == 0


def test_calculate_bowler_runs_extras(erp_engine):
    # Wides and no-balls charged to bowler
    assert erp_engine.calculate_bowler_runs(batter_runs=0, extras_type="wide", extras1_runs=1) == 1
    assert erp_engine.calculate_bowler_runs(batter_runs=0, extras_type="Overstep", extras1_runs=1) == 1

    # Byes and leg-byes NOT charged to bowler
    assert erp_engine.calculate_bowler_runs(batter_runs=0, extras_type="byes", extras1_runs=4) == 0
    assert erp_engine.calculate_bowler_runs(batter_runs=0, extras_type="legbyes", extras1_runs=1) == 0


def test_byes_safeguard_zero_erp(erp_engine):
    # Pure non-bowler extras must yield exactly ERP = 0.0
    exp_runs, bowler_runs, erp = erp_engine.evaluate_delivery(
        innings=1,
        phase="middle",
        score_before=80,
        wickets_lost_before=2,
        overid=10,
        is_legal=True,
        batter_runs=0,
        extras_type="byes",
        extras1_runs=4,
    )
    assert bowler_runs == 0
    assert erp == 0.0


def test_dot_ball_positive_erp(erp_engine):
    # A legal dot ball concedes 0 runs, so ERP = exp_runs - 0 > 0
    exp_runs, bowler_runs, erp = erp_engine.evaluate_delivery(
        innings=1,
        phase="middle",
        score_before=80,
        wickets_lost_before=2,
        overid=10,
        is_legal=True,
        batter_runs=0,
        extras_type=None,
        extras1_runs=0,
    )
    assert bowler_runs == 0
    assert erp > 0.0
    assert abs(erp - exp_runs) < 1e-5


def test_boundary_negative_erp(erp_engine):
    # A four concedes 4 runs, so ERP = exp_runs - 4 < 0
    exp_runs, bowler_runs, erp = erp_engine.evaluate_delivery(
        innings=1,
        phase="powerplay",
        score_before=20,
        wickets_lost_before=0,
        overid=3,
        is_legal=True,
        batter_runs=4,
        extras_type=None,
        extras1_runs=0,
    )
    assert bowler_runs == 4
    assert erp < 0.0
    assert erp == pytest.approx(exp_runs - 4.0, abs=1e-4)


def test_erp_dataframe_vectorized(erp_engine):
    df = pd.DataFrame({
        "innings": [1, 2],
        "innings_phase": ["powerplay", "death"],
        "score_before": [10, 160],
        "wickets_lost_before": [0, 5],
        "overid": [2, 18],
        "is_legal_delivery": [True, True],
        "batter_runs": [0, 6],
        "extras_type": [None, None],
        "extras1_runs": [0, 0],
    })
    res = erp_engine.evaluate_dataframe(df)
    assert "erp" in res.columns
    assert "exp_bowler_runs" in res.columns
    assert res.loc[0, "erp"] > 0.0  # Dot
    assert res.loc[1, "erp"] < 0.0  # Six
