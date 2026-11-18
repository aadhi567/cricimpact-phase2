"""Stage PRI-2: Comprehensive Automated Verification Suite for Pressure Reliability Index (PRI).

Tests all mathematical invariants, anti-shrinkage rules, dual-axis separation,
Wilson CI exactness, custom minimum opportunity validation, B8 Pakistan visibility policy,
reconciliation across career/season/tournament outputs, and zero-leakage isolation.
"""

from __future__ import annotations

import json
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

from ml.contribution.pressure_reliability.batting_pri_engine import BattingPRIEngine
from ml.contribution.pressure_reliability.bowling_pri_engine import BowlingPRIEngine
from ml.contribution.pressure_reliability.confidence import (
    classify_sample_confidence,
    wilson_confidence_interval,
    wilson_interval_pair,
)
from ml.contribution.pressure_reliability.filters import (
    apply_min_opportunity_filter,
    apply_overall_leaderboard_visibility,
    load_pakistan_player_ids,
    validate_min_opportunities,
)
from ml.contribution.pressure_reliability.schema import (
    BATTING_T10_MEAN_P_THRESHOLD,
    BATTING_T10_PEAK_P_THRESHOLD,
    BOWLING_EXO2_MAX_ENTRY_PTI_THRESHOLD,
    BOWLING_EXO2_MIN_LEGAL_BALLS,
    DEFAULT_PRI_OUTPUT_DIR,
    HPC_NEUTRAL_ANCHOR,
    PCS_NEUTRAL_ANCHOR,
)

EXPECTED_ARTIFACTS = [
    "batting_pri_pressure_innings_v1.pkl.gz",
    "batting_pri_career_v1.pkl.gz",
    "batting_pri_season_v1.pkl.gz",
    "batting_pri_tournament_v1.pkl.gz",
    "bowling_pri_pressure_spells_v1.pkl.gz",
    "bowling_pri_career_v1.pkl.gz",
    "bowling_pri_season_v1.pkl.gz",
    "bowling_pri_tournament_v1.pkl.gz",
    "pri_validation_metrics_v1.json",
    "pri_pipeline_manifest_v1.json",
]


@pytest.fixture(scope="module")
def pri_artifacts():
    for fname in EXPECTED_ARTIFACTS:
        p = DEFAULT_PRI_OUTPUT_DIR / fname
        assert p.exists(), f"Missing PRI-2 output artifact: {p}"

    with open(DEFAULT_PRI_OUTPUT_DIR / "pri_pipeline_manifest_v1.json", "r", encoding="utf-8") as f:
        manifest = json.load(f)
    with open(DEFAULT_PRI_OUTPUT_DIR / "pri_validation_metrics_v1.json", "r", encoding="utf-8") as f:
        val_metrics = json.load(f)

    return {
        "bat_inns": pd.read_pickle(DEFAULT_PRI_OUTPUT_DIR / "batting_pri_pressure_innings_v1.pkl.gz"),
        "bat_career": pd.read_pickle(DEFAULT_PRI_OUTPUT_DIR / "batting_pri_career_v1.pkl.gz"),
        "bat_season": pd.read_pickle(DEFAULT_PRI_OUTPUT_DIR / "batting_pri_season_v1.pkl.gz"),
        "bat_tourney": pd.read_pickle(DEFAULT_PRI_OUTPUT_DIR / "batting_pri_tournament_v1.pkl.gz"),
        "bowl_spells": pd.read_pickle(DEFAULT_PRI_OUTPUT_DIR / "bowling_pri_pressure_spells_v1.pkl.gz"),
        "bowl_career": pd.read_pickle(DEFAULT_PRI_OUTPUT_DIR / "bowling_pri_career_v1.pkl.gz"),
        "bowl_season": pd.read_pickle(DEFAULT_PRI_OUTPUT_DIR / "bowling_pri_season_v1.pkl.gz"),
        "bowl_tourney": pd.read_pickle(DEFAULT_PRI_OUTPUT_DIR / "bowling_pri_tournament_v1.pkl.gz"),
        "manifest": manifest,
        "val_metrics": val_metrics,
    }


class TestPRIGovernanceAndManifest:
    def test_all_10_artifacts_exist(self, pri_artifacts):
        assert len(pri_artifacts) == 10

    def test_manifest_governance_flags(self, pri_artifacts):
        gov = pri_artifacts["manifest"]["governance"]
        assert gov["shrinkage_applied"] is False
        assert gov["composite_score_applied"] is False
        assert gov["dnb_excluded_strictly"] is True
        assert gov["neutral_never_counted_positive"] is True
        assert gov["pakistan_overall_leaderboard_hidden_by_default"] is True
        assert gov["pakistan_underlying_data_mutated"] is False

    def test_all_10_scenarios_passed(self, pri_artifacts):
        assert pri_artifacts["val_metrics"]["scenario_stress_tests"]["all_10_scenarios_passed"] is True


class TestBattingPRIInvariants:
    def test_t10_qualification_and_dnb_exclusion(self, pri_artifacts):
        inns = pri_artifacts["bat_inns"]
        assert len(inns) > 0
        assert int(inns["is_dnb"].sum()) == 0
        assert bool(((inns["mean_p"] >= BATTING_T10_MEAN_P_THRESHOLD) | (inns["peak_p"] >= BATTING_T10_PEAK_P_THRESHOLD)).all())
        assert int((inns["player_id"] == -1).sum()) == 0
        assert int(inns.duplicated(subset=["match_id", "innings", "player_id"]).sum()) == 0

    def test_neutral_hpc_never_positive(self, pri_artifacts):
        inns = pri_artifacts["bat_inns"]
        neu = inns[inns["hpc"] == HPC_NEUTRAL_ANCHOR]
        if len(neu) > 0:
            assert int(neu["is_positive_hpc"].sum()) == 0
            assert bool((neu["hpc_outcome"] == "neutral").all())

        # Synthetic exact boundary check
        assert (0.0 > HPC_NEUTRAL_ANCHOR) is False

    def test_batting_zero_shrinkage_exactness(self, pri_artifacts):
        for key in ["bat_career", "bat_season", "bat_tourney"]:
            df = pri_artifacts[key]
            ev = df[df["has_pressure_opportunities"]]
            assert len(ev) > 0
            # Polarity partition
            assert bool(
                (
                    ev["positive_hpc_innings"]
                    + ev["negative_hpc_innings"]
                    + ev["neutral_hpc_innings"]
                    == ev["pressure_innings"]
                ).all()
            )
            # Exact unshrunk positive % (within half-ULP of 2-decimal rounding)
            expected_pct = ev["positive_hpc_innings"] / ev["pressure_innings"] * 100.0
            assert float((ev["positive_hpc_pct"] - expected_pct).abs().max()) <= 0.005001
            # Exact unshrunk average HPC (within half-ULP of 4-decimal rounding)
            expected_avg = ev["total_hpc_under_pressure"] / ev["pressure_innings"]
            assert float((ev["avg_hpc_under_pressure"] - expected_avg).abs().max()) <= 0.000051

    def test_batting_zero_opportunity_handling(self, pri_artifacts):
        for key in ["bat_career", "bat_season", "bat_tourney"]:
            df = pri_artifacts[key]
            zero_df = df[~df["has_pressure_opportunities"]]
            if len(zero_df) > 0:
                assert bool((zero_df["pressure_innings"] == 0).all())
                assert bool((zero_df["status"] == "No Pressure Opportunities").all())
                assert int(zero_df["positive_hpc_pct"].notna().sum()) == 0
                assert int(zero_df["avg_hpc_under_pressure"].notna().sum()) == 0

    def test_batting_exact_reconciliation_and_no_tournament_leakage(self, pri_artifacts):
        inns = pri_artifacts["bat_inns"]
        c = pri_artifacts["bat_career"]
        s = pri_artifacts["bat_season"]
        t = pri_artifacts["bat_tourney"]

        assert int(c["pressure_innings"].sum()) == len(inns)
        assert int(s["pressure_innings"].sum()) == len(inns)
        assert int(t["pressure_innings"].sum()) == len(inns)
        assert abs(float(c["total_hpc_under_pressure"].sum()) - float(inns["hpc"].sum())) < 1e-2
        assert abs(float(s["total_hpc_under_pressure"].sum()) - float(inns["hpc"].sum())) < 1e-2
        assert abs(float(t["total_hpc_under_pressure"].sum()) - float(inns["hpc"].sum())) < 1e-2

        # Tournament cross-check: no cross-tournament contamination
        src_grp = inns.groupby(["comp_id", "player_id"]).agg(
            src_n=("match_id", "count"),
            src_hpc=("hpc", "sum"),
        ).reset_index()
        merged = t[t["has_pressure_opportunities"]].merge(src_grp, on=["comp_id", "player_id"], how="outer")
        assert int(merged["src_n"].isna().sum()) == 0
        assert bool((merged["pressure_innings"] == merged["src_n"]).all())
        assert float((merged["total_hpc_under_pressure"] - merged["src_hpc"]).abs().max()) < 1e-3


class TestBowlingPRIInvariants:
    def test_exo2_qualification_and_uniqueness(self, pri_artifacts):
        sp = pri_artifacts["bowl_spells"]
        assert len(sp) > 0
        assert bool((sp["max_over_entry_pti"] >= BOWLING_EXO2_MAX_ENTRY_PTI_THRESHOLD).all())
        assert bool((sp["legal_balls"] >= BOWLING_EXO2_MIN_LEGAL_BALLS).all())
        assert int(sp.duplicated(subset=["match_id", "innings", "bowler_id"]).sum()) == 0

    def test_neutral_pcs_never_positive(self, pri_artifacts):
        sp = pri_artifacts["bowl_spells"]
        neu = sp[sp["pcs_spell"] == PCS_NEUTRAL_ANCHOR]
        if len(neu) > 0:
            assert int(neu["is_positive_pcs"].sum()) == 0
            assert bool((neu["pcs_outcome"] == "neutral").all())
        assert (50.0 > PCS_NEUTRAL_ANCHOR) is False

    def test_bowling_zero_shrinkage_exactness(self, pri_artifacts):
        sp = pri_artifacts["bowl_spells"]
        for key, gcols in [
            ("bowl_career", ["bowler_id"]),
            ("bowl_season", ["season", "bowler_id"]),
            ("bowl_tourney", ["comp_id", "bowler_id"]),
        ]:
            df = pri_artifacts[key]
            ev = df[df["has_pressure_opportunities"]]
            assert len(ev) > 0
            assert bool(
                (
                    ev["positive_pcs_spells"]
                    + ev["negative_pcs_spells"]
                    + ev["neutral_pcs_spells"]
                    == ev["pressure_spells"]
                ).all()
            )
            expected_pct = ev["positive_pcs_spells"] / ev["pressure_spells"] * 100.0
            assert float((ev["positive_pcs_pct"] - expected_pct).abs().max()) <= 0.005001

        # Career exact unshrunk avg_pcs directly from pressure spells (NO 48-ball shrinkage)
        src_avg = sp.groupby("bowler_id")["pcs_spell"].mean().reset_index().rename(columns={"pcs_spell": "src_avg"})
        ev_c = pri_artifacts["bowl_career"][pri_artifacts["bowl_career"]["has_pressure_opportunities"]].merge(
            src_avg, on="bowler_id", how="inner"
        )
        assert float((ev_c["avg_pcs_under_pressure"] - ev_c["src_avg"]).abs().max()) <= 0.005001

    def test_bowling_zero_opportunity_handling(self, pri_artifacts):
        for key in ["bowl_career", "bowl_season", "bowl_tourney"]:
            df = pri_artifacts[key]
            zero_df = df[~df["has_pressure_opportunities"]]
            if len(zero_df) > 0:
                assert bool((zero_df["pressure_spells"] == 0).all())
                assert bool((zero_df["status"] == "No Pressure Opportunities").all())
                assert int(zero_df["positive_pcs_pct"].notna().sum()) == 0
                assert int(zero_df["avg_pcs_under_pressure"].notna().sum()) == 0

    def test_bowling_exact_reconciliation_and_no_tournament_leakage(self, pri_artifacts):
        sp = pri_artifacts["bowl_spells"]
        c = pri_artifacts["bowl_career"]
        s = pri_artifacts["bowl_season"]
        t = pri_artifacts["bowl_tourney"]

        assert int(c["pressure_spells"].sum()) == len(sp)
        assert int(s["pressure_spells"].sum()) == len(sp)
        assert int(t["pressure_spells"].sum()) == len(sp)
        assert abs(float(c["total_pressure_contribution_rpe"].sum()) - float(sp["total_rpe"].sum())) < 1e-2
        assert abs(float(s["total_pressure_contribution_rpe"].sum()) - float(sp["total_rpe"].sum())) < 1e-2
        assert abs(float(t["total_pressure_contribution_rpe"].sum()) - float(sp["total_rpe"].sum())) < 1e-2

        src_grp = sp.groupby(["comp_id", "bowler_id"]).agg(
            src_n=("match_id", "count"),
            src_rpe=("total_rpe", "sum"),
        ).reset_index()
        merged = t[t["has_pressure_opportunities"]].merge(src_grp, on=["comp_id", "bowler_id"], how="outer")
        assert int(merged["src_n"].isna().sum()) == 0
        assert bool((merged["pressure_spells"] == merged["src_n"]).all())
        assert float((merged["total_pressure_contribution_rpe"] - merged["src_rpe"]).abs().max()) < 1e-3


class TestWilsonConfidenceIntervals:
    def test_exact_2_of_2_unshrunk_wide_ci(self):
        lo, hi, width = wilson_confidence_interval(2, 2)
        assert lo == pytest.approx(34.24, abs=0.05)
        assert hi == 100.0
        assert width == pytest.approx(65.76, abs=0.05)
        assert classify_sample_confidence(2) == "Very Low (Provisional)"

    def test_zero_total_returns_none(self):
        assert wilson_confidence_interval(0, 0) == (None, None, None)
        assert classify_sample_confidence(0) == "Insufficient (No Opportunities)"

    def test_ci_bounds_and_monotonicity_across_careers(self, pri_artifacts):
        for key, rate_col in [("bat_career", "positive_hpc_pct"), ("bowl_career", "positive_pcs_pct")]:
            ev = pri_artifacts[key][pri_artifacts[key]["has_pressure_opportunities"]]
            assert bool((ev["wilson_ci95_low"] >= 0.0).all())
            assert bool((ev["wilson_ci95_high"] <= 100.0).all())
            assert bool((ev["wilson_ci95_low"] <= ev[rate_col] + 0.02).all())
            assert bool((ev["wilson_ci95_high"] >= ev[rate_col] - 0.02).all())
            assert bool((ev["wilson_ci95_width"] >= ev["wilson_ci90_width"] - 0.02).all())


class TestCustomMinimumOpportunityFilter:
    @pytest.mark.parametrize("raw,expected", [(0, 0), (1, 1), (7, 7), (13, 13), (50, 50), ("0", 0), ("25", 25)])
    def test_valid_non_negative_integers(self, raw, expected):
        assert validate_min_opportunities(raw) == expected

    @pytest.mark.parametrize("bad", [-1, -100, "-1", 5.5, 0.1, "5.5", True, False, "", "abc", None])
    def test_invalid_inputs_rejected(self, bad):
        with pytest.raises(ValueError):
            validate_min_opportunities(bad)

    def test_filter_preserves_values_and_reranks_contiguously(self, pri_artifacts):
        bat_c = pri_artifacts["bat_career"]
        f0 = apply_min_opportunity_filter(bat_c, "pressure_innings", 0, sort_by="positive_hpc_pct")
        assert int((f0["pressure_innings"] == 0).sum()) == 0
        assert list(f0["rank"]) == list(range(1, len(f0) + 1))

        f13 = apply_min_opportunity_filter(bat_c, "pressure_innings", 13, sort_by="positive_hpc_pct")
        assert bool((f13["pressure_innings"] >= 13).all())
        assert list(f13["rank"]) == list(range(1, len(f13) + 1))
        # Underlying metrics unchanged
        m = f13[["player_id", "positive_hpc_pct", "avg_hpc_under_pressure"]].merge(
            bat_c[["player_id", "positive_hpc_pct", "avg_hpc_under_pressure"]],
            on="player_id",
            suffixes=("_f", "_orig"),
        )
        assert float((m["positive_hpc_pct_f"] - m["positive_hpc_pct_orig"]).abs().max()) == 0.0
        assert float((m["avg_hpc_under_pressure_f"] - m["avg_hpc_under_pressure_orig"]).abs().max()) == 0.0


class TestPakistanOverallLeaderboardPolicy:
    def test_pakistan_hidden_on_default_overall_but_preserved_in_datasets(self, pri_artifacts):
        pak_ids = load_pakistan_player_ids()
        assert 7338 in pak_ids  # Verified Pakistan Haider Ali
        assert 28756 not in pak_ids  # Verified UAE Haider Ali

        # Batting
        bat_c = pri_artifacts["bat_career"]
        assert int(bat_c["player_id"].isin(pak_ids).sum()) > 0
        bat_default = BattingPRIEngine.get_overall_leaderboard(bat_c, min_opportunities=0, exclude_pakistan=True)
        assert int(bat_default["player_id"].isin(pak_ids).sum()) == 0
        bat_all = BattingPRIEngine.get_overall_leaderboard(bat_c, min_opportunities=0, exclude_pakistan=False)
        assert int(bat_all["player_id"].isin(pak_ids).sum()) > 0

        # Bowling
        bowl_c = pri_artifacts["bowl_career"]
        assert int(bowl_c["bowler_id"].isin(pak_ids).sum()) > 0
        bowl_default = BowlingPRIEngine.get_overall_leaderboard(bowl_c, min_opportunities=0, exclude_pakistan=True)
        assert int(bowl_default["bowler_id"].isin(pak_ids).sum()) == 0
        bowl_all = BowlingPRIEngine.get_overall_leaderboard(bowl_c, min_opportunities=0, exclude_pakistan=False)
        assert int(bowl_all["bowler_id"].isin(pak_ids).sum()) > 0

        # Unknown / missing player_id is NEVER classified as Pakistan
        synth = pd.DataFrame([
            {"player_id": 7338, "pressure_innings": 5},
            {"player_id": 28756, "pressure_innings": 5},
            {"player_id": np.nan, "pressure_innings": 5},
        ])
        vis = apply_overall_leaderboard_visibility(synth, player_id_col="player_id", exclude_pakistan=True, pakistan_ids=pak_ids)
        assert len(vis) == 2
        assert 7338 not in set(vis["player_id"].dropna().astype(int))
        assert 28756 in set(vis["player_id"].dropna().astype(int))
