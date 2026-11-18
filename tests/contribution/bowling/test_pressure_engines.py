"""Unit tests for Explanatory Pressure Diagnostic Engines."""
import numpy as np
import pandas as pd
import pytest

from ml.contribution.bowling.dot_ball_pressure_engine import DotBallPressureEngine
from ml.contribution.bowling.first_innings_scoring_pressure_engine import FirstInningsScoringPressureEngine
from ml.contribution.bowling.required_run_rate_pressure_engine import RequiredRunRatePressureEngine


def test_dot_ball_pressure_engine():
    engine = DotBallPressureEngine()

    # Consecutive dots tracking
    is_dot, exp_prob, res, dots_after, p_idx = engine.evaluate_delivery(
        is_legal=True,
        bowler_runs=0,
        is_non_bowler_extra=False,
        consecutive_dots_before=2,
        innings=1,
        phase="middle",
    )
    assert is_dot is True
    assert dots_after == 3
    assert p_idx == pytest.approx(3 * (1.0 - exp_prob), abs=1e-4)

    # Broken streak
    is_dot2, _, _, dots_after2, p_idx2 = engine.evaluate_delivery(
        is_legal=True,
        bowler_runs=1,
        is_non_bowler_extra=False,
        consecutive_dots_before=3,
        innings=1,
        phase="middle",
    )
    assert is_dot2 is False
    assert dots_after2 == 0
    assert p_idx2 == 0.0


def test_rrr_pressure_engine_first_innings_nan():
    engine = RequiredRunRatePressureEngine()
    rrr, econ, p_idx = engine.evaluate_delivery(
        innings=1,
        required_run_rate=None,
        bowler_cum_runs=20,
        bowler_cum_legal_balls=18,
    )
    assert rrr is None
    assert econ is None
    assert p_idx is None


def test_rrr_pressure_engine_chase():
    engine = RequiredRunRatePressureEngine()
    # Tight bowling in chase: RRR=10.0, bowler economy = 6.0
    rrr, econ, p_idx = engine.evaluate_delivery(
        innings=2,
        required_run_rate=10.0,
        bowler_cum_runs=12,
        bowler_cum_legal_balls=12,  # 2 overs, 12 runs -> econ = 6.0
    )
    assert rrr == 10.0
    assert econ == 6.0
    assert p_idx == pytest.approx(4.0, abs=1e-2)  # Positive pressure exerted


def test_first_innings_scoring_pressure():
    engine = FirstInningsScoringPressureEngine()
    # First innings run restriction
    rest_i1 = engine.evaluate_delivery(
        innings=1,
        exp_bowler_runs=1.35,
        bowler_runs=0,
        is_non_bowler_extra=False,
    )
    assert rest_i1 == pytest.approx(1.35, abs=1e-4)

    # Second innings returns None
    rest_i2 = engine.evaluate_delivery(
        innings=2,
        exp_bowler_runs=1.35,
        bowler_runs=0,
        is_non_bowler_extra=False,
    )
    assert rest_i2 is None
