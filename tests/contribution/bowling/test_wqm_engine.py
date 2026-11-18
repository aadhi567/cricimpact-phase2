"""Unit tests for Wicket Quality Multiplier (WQM) Engine."""
import pytest

from ml.contribution.bowling.wqm_engine import WicketQualityMultiplierEngine


@pytest.fixture
def wqm_engine():
    return WicketQualityMultiplierEngine()


def test_wqm_baseline_average_batter(wqm_engine):
    # Average batter (abc=50, form=50, 0 runs, 0 balls)
    wqm = wqm_engine.evaluate_delivery(
        abc_prior_shrunk=50.0,
        abc_prior_last5_mean=50.0,
        total_career_innings=20,
        striker_cum_runs=0,
        striker_cum_balls=0,
    )
    # q_base = 0.70 * 1.0 + 0.30 * 1.0 = 1.0; threat = 0
    assert wqm == pytest.approx(1.0, abs=1e-3)


def test_wqm_cold_start_fallback(wqm_engine):
    # Less than 5 innings triggers cold-start fallback (form factor = 1.0)
    wqm = wqm_engine.evaluate_delivery(
        abc_prior_shrunk=60.0,
        abc_prior_last5_mean=80.0,  # Ignored due to cold-start
        total_career_innings=3,
        striker_cum_runs=0,
        striker_cum_balls=0,
    )
    # q_base = 0.70 * (60/50) + 0.30 * 1.0 = 0.84 + 0.30 = 1.14
    assert wqm == pytest.approx(1.14, abs=1e-3)


def test_wqm_threat_scaling(wqm_engine):
    # Dangerous set batter (50 runs off 25 balls, SR=200)
    wqm = wqm_engine.evaluate_delivery(
        abc_prior_shrunk=55.0,
        abc_prior_last5_mean=55.0,
        total_career_innings=30,
        striker_cum_runs=50,
        striker_cum_balls=25,
    )
    # Baseline wqm is 1.10; threat should amplify it significantly (> 1.50)
    assert wqm > 1.50
    assert wqm <= 2.50


def test_wqm_bounds_enforcement(wqm_engine):
    # Extreme low-quality batter
    wqm_low = wqm_engine.evaluate_delivery(
        abc_prior_shrunk=10.0,
        abc_prior_last5_mean=10.0,
        total_career_innings=20,
        striker_cum_runs=0,
        striker_cum_balls=5,
    )
    assert wqm_low >= 0.40

    # Extreme god-mode batter
    wqm_high = wqm_engine.evaluate_delivery(
        abc_prior_shrunk=120.0,
        abc_prior_last5_mean=120.0,
        total_career_innings=100,
        striker_cum_runs=100,
        striker_cum_balls=35,
    )
    assert wqm_high <= 2.50
