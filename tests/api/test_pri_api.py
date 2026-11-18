"""Stage PRI-3: Comprehensive Backend API & Data-Parity Test Suite for Pressure Reliability Index (PRI)."""

from __future__ import annotations

import time
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from backend.core.config import settings
from backend.main import app
from backend.services.pri_data_service import PRIDataService
from ml.contribution.pressure_reliability.filters import load_pakistan_player_ids


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def pak_ids():
    return load_pakistan_player_ids(settings.PLAYER_MAPPING_FILE)


class TestPRIHealthAndOverview:
    def test_pri_health_and_10_artifacts(self, client):
        r = client.get("/api/pri/health")
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "healthy"
        assert body["service_initialized"] is True
        assert body["artifacts_loaded"] == 10
        assert body["governance"]["shrinkage_applied"] is False
        assert body["governance"]["composite_score_applied"] is False
        assert body["counts"]["batting_pressure_innings"] == 4857
        assert body["counts"]["bowling_pressure_spells"] == 5027
        assert body["counts"]["batting_career_players"] == 880
        assert body["counts"]["bowling_career_players"] == 638

    def test_system_health_backward_compatible_with_pri(self, client):
        r = client.get("/api/health")
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "healthy"
        assert body["service_initialized"] is True
        assert body["pcs_service_initialized"] is True
        assert body["batting_service_initialized"] is True
        assert body["pri_service_initialized"] is True
        assert body["pri_batting_pressure_innings"] == 4857
        assert body["pri_bowling_pressure_spells"] == 5027

    def test_overview_exact_corpus_counts(self, client):
        r = client.get("/api/pri/overview")
        assert r.status_code == 200
        body = r.json()
        assert body["scope"] == "corpus_level"
        assert body["methodology"]["shrinkage_applied"] is False
        assert body["methodology"]["composite_score_applied"] is False

        bat = body["batting"]
        assert bat["total_qualifying_pressure_innings"] == 4857
        assert bat["evaluated_batters"] == 749
        assert bat["positive_pressure_innings"] + bat["negative_pressure_innings"] + bat["neutral_pressure_innings"] == 4857
        assert len(bat["season_series"]) == 5

        bowl = body["bowling"]
        assert bowl["total_qualifying_pressure_spells"] == 5027
        assert bowl["evaluated_bowlers"] == 522
        assert bowl["positive_pressure_spells"] + bowl["negative_pressure_spells"] + bowl["neutral_pressure_spells"] == 5027
        assert len(bowl["season_series"]) == 5

    def test_filters_metadata(self, client):
        r = client.get("/api/pri/filters")
        assert r.status_code == 200
        body = r.json()
        assert "2026" in body["seasons"] and "2022" in body["seasons"]
        assert len(body["batting_tournaments"]) == 137
        assert len(body["bowling_tournaments"]) == 137
        assert len(body["batting_teams"]) > 10
        assert len(body["bowling_teams"]) > 10


class TestPRIBattingEndpoints:
    def test_batting_career_exact_parity_with_pri2_artifact(self, client):
        r = client.get("/api/pri/batting/career?min_opportunities=20&page=1&page_size=20")
        assert r.status_code == 200
        body = r.json()
        assert body["domain"] == "batting"
        assert body["scope"] == "career"
        assert body["governance"]["shrinkage_applied"] is False
        assert len(body["items"]) > 0

        # Exact parity check against PRI-2 frozen pickle
        src_df = pd.read_pickle(settings.PRI_BATTING_CAREER_FILE).set_index("player_id")
        for row in body["items"]:
            pid = row["player_id"]
            src = src_df.loc[pid]
            assert row["pressure_innings"] >= 20
            assert row["pressure_innings"] == int(src["pressure_innings"])
            assert row["positive_hpc_pct"] == pytest.approx(float(src["positive_hpc_pct"]), abs=1e-6)
            assert row["avg_hpc_under_pressure"] == pytest.approx(float(src["avg_hpc_under_pressure"]), abs=1e-6)
            assert row["total_hpc_under_pressure"] == pytest.approx(float(src["total_hpc_under_pressure"]), abs=1e-6)
            assert row["wilson_ci95_low"] == pytest.approx(float(src["wilson_ci95_low"]), abs=1e-6)
            assert row["wilson_ci95_high"] == pytest.approx(float(src["wilson_ci95_high"]), abs=1e-6)

    def test_batting_season_filter(self, client):
        r = client.get("/api/pri/batting/season?season=2025&min_opportunities=5")
        assert r.status_code == 200
        body = r.json()
        assert body["scope"] == "season"
        assert len(body["items"]) > 0
        assert all(item["season"] == "2025" for item in body["items"])
        assert all(item["pressure_innings"] >= 5 for item in body["items"])

    def test_batting_tournament_isolation(self, client):
        r = client.get("/api/pri/batting/tournament?tournament=2193&min_opportunities=3")
        assert r.status_code == 200
        body = r.json()
        assert body["scope"] == "tournament"
        assert len(body["items"]) > 0
        assert all(item["comp_id"] == 2193 for item in body["items"])
        assert all(item["comp_name"] == "IPL 2024" for item in body["items"])
        assert all(item["pressure_innings"] >= 3 for item in body["items"])

    def test_batting_sorting_and_pagination(self, client):
        for sort_col in ["positive_hpc_pct", "avg_hpc_under_pressure", "total_hpc_under_pressure", "pressure_innings"]:
            r = client.get(f"/api/pri/batting/career?min_opportunities=10&sort_by={sort_col}&order=desc&page=1&page_size=10")
            assert r.status_code == 200
            vals = [x[sort_col] for x in r.json()["items"]]
            assert vals == sorted(vals, reverse=True)

        p1 = client.get("/api/pri/batting/career?min_opportunities=10&page=1&page_size=10").json()
        p2 = client.get("/api/pri/batting/career?min_opportunities=10&page=2&page_size=10").json()
        assert p1["items"][0]["rank"] == 1
        assert p2["items"][0]["rank"] == 11
        ids1 = {x["player_id"] for x in p1["items"]}
        ids2 = {x["player_id"] for x in p2["items"]}
        assert ids1.isdisjoint(ids2)


class TestPRIBowlingEndpoints:
    def test_bowling_career_exact_parity_with_pri2_artifact(self, client):
        r = client.get("/api/pri/bowling/career?min_opportunities=18&page=1&page_size=20")
        assert r.status_code == 200
        body = r.json()
        assert body["domain"] == "bowling"
        assert body["governance"]["shrinkage_applied"] is False
        assert len(body["items"]) > 0

        src_df = pd.read_pickle(settings.PRI_BOWLING_CAREER_FILE).set_index("bowler_id")
        for row in body["items"]:
            bid = row["bowler_id"]
            src = src_df.loc[bid]
            assert row["pressure_spells"] >= 18
            assert row["pressure_spells"] == int(src["pressure_spells"])
            assert row["positive_pcs_pct"] == pytest.approx(float(src["positive_pcs_pct"]), abs=1e-6)
            assert row["avg_pcs_under_pressure"] == pytest.approx(float(src["avg_pcs_under_pressure"]), abs=1e-6)
            assert row["total_pressure_contribution_rpe"] == pytest.approx(float(src["total_pressure_contribution_rpe"]), abs=1e-6)
            assert row["wilson_ci95_low"] == pytest.approx(float(src["wilson_ci95_low"]), abs=1e-6)
            assert row["wilson_ci95_high"] == pytest.approx(float(src["wilson_ci95_high"]), abs=1e-6)

    def test_bowling_season_filter(self, client):
        r = client.get("/api/pri/bowling/season?season=2024&min_opportunities=5")
        assert r.status_code == 200
        body = r.json()
        assert len(body["items"]) > 0
        assert all(item["season"] == "2024" for item in body["items"])
        assert all(item["pressure_spells"] >= 5 for item in body["items"])

    def test_bowling_tournament_isolation(self, client):
        r = client.get("/api/pri/bowling/tournament?tournament=IPL%202025&min_opportunities=4")
        assert r.status_code == 200
        body = r.json()
        assert len(body["items"]) > 0
        assert all(item["comp_name"] == "IPL 2025" for item in body["items"])
        assert all(item["pressure_spells"] >= 4 for item in body["items"])

    def test_bowling_sorting(self, client):
        for sort_col in ["positive_pcs_pct", "avg_pcs_under_pressure", "total_pressure_contribution_rpe", "pressure_spells"]:
            r = client.get(f"/api/pri/bowling/career?min_opportunities=10&sort_by={sort_col}&order=desc&page=1&page_size=10")
            assert r.status_code == 200
            vals = [x[sort_col] for x in r.json()["items"]]
            assert vals == sorted(vals, reverse=True)


class TestPRICustomMinAndPakistanPolicy:
    def test_zero_minimum_excludes_zero_opp_players_without_fake_zero_pct(self, client):
        rb = client.get("/api/pri/batting/career?min_opportunities=0&page_size=100").json()
        assert rb["pagination"]["total_items"] == 701  # 749 evaluated minus 48 Pakistan batters
        assert all(item["pressure_innings"] >= 1 for item in rb["items"])

        rw = client.get("/api/pri/bowling/career?min_opportunities=0&page_size=100").json()
        assert rw["pagination"]["total_items"] == 485  # 522 evaluated minus 37 Pakistan bowlers
        assert all(item["pressure_spells"] >= 1 for item in rw["items"])

    @pytest.mark.parametrize("bad_min", ["-1", "-25", "5.5", "0.1", "abc", "12a"])
    def test_invalid_min_opportunities_rejected_422(self, client, bad_min):
        r1 = client.get(f"/api/pri/batting/career?min_opportunities={bad_min}")
        r2 = client.get(f"/api/pri/bowling/career?min_opportunities={bad_min}")
        assert r1.status_code == 422
        assert r2.status_code == 422

    def test_pakistan_excluded_on_all_default_overall_leaderboards_but_profiles_intact(self, client, pak_ids):
        for url in [
            "/api/pri/batting/career?min_opportunities=0&page_size=100",
            "/api/pri/batting/season?season=2025&min_opportunities=0&page_size=100",
            "/api/pri/batting/tournament?tournament=3133&min_opportunities=0&page_size=100",
        ]:
            items = client.get(url).json()["items"]
            assert all(item["player_id"] not in pak_ids for item in items)

        for url in [
            "/api/pri/bowling/career?min_opportunities=0&page_size=100",
            "/api/pri/bowling/season?season=2025&min_opportunities=0&page_size=100",
            "/api/pri/bowling/tournament?tournament=3133&min_opportunities=0&page_size=100",
        ]:
            items = client.get(url).json()["items"]
            assert all(item["bowler_id"] not in pak_ids for item in items)

        # Individual profiles remain 100% accessible (e.g., Haris Rauf ID 7364 — Pakistan bowler)
        hr = client.get("/api/pri/bowling/players/7364")
        assert hr.status_code == 200
        assert hr.json()["career"]["bowler_name"] == "Haris Rauf"
        assert hr.json()["career"]["pressure_spells"] == 29
        assert hr.json()["career"]["positive_pcs_pct"] == pytest.approx(72.41, abs=0.01)

    def test_unknown_nationality_not_excluded(self):
        svc = PRIDataService.get_instance()
        df = pd.DataFrame([
            {"player_id": 7338, "pressure_innings": 5},   # Verified Pakistan Haider Ali
            {"player_id": 28756, "pressure_innings": 5},  # Verified UAE Haider Ali
            {"player_id": float("nan"), "pressure_innings": 5},  # Unknown ID
        ])
        res = svc._apply_pakistan_visibility(df, "player_id", exclude_pakistan=True)
        assert len(res) == 2
        assert 7338 not in set(res["player_id"].dropna().astype(int))
        assert 28756 in set(res["player_id"].dropna().astype(int))


class TestPRIProfilesComparisonAndPerformance:
    def test_batting_player_profile_valid_zero_opp_and_404(self, client):
        # Evaluated player: Suryakumar Yadav (1699)
        r = client.get("/api/pri/batting/players/1699")
        assert r.status_code == 200
        body = r.json()
        assert body["career"]["batter_name"] == "Suryakumar Yadav"
        assert body["career"]["pressure_innings"] == 23
        assert body["career"]["positive_hpc_pct"] == pytest.approx(56.52, abs=0.01)
        assert len(body["seasons"]) >= 1
        assert len(body["tournaments"]) >= 1
        assert len(body["pressure_innings"]) == 23

        # Zero-opportunity batter returns status="No Pressure Opportunities" & null reliability (never 0%)
        svc = PRIDataService.get_instance()
        zero_pid = int(svc.batting_career_df[~svc.batting_career_df["has_pressure_opportunities"]].iloc[0]["player_id"])
        rz = client.get(f"/api/pri/batting/players/{zero_pid}")
        assert rz.status_code == 200
        assert rz.json()["career"]["has_pressure_opportunities"] is False
        assert rz.json()["career"]["positive_hpc_pct"] is None
        assert rz.json()["career"]["status"] == "No Pressure Opportunities"

        # Missing player 404
        assert client.get("/api/pri/batting/players/99999999").status_code == 404

    def test_bowling_player_profile_valid_and_404(self, client):
        r = client.get("/api/pri/bowling/players/6523")  # Blessing Muzarabani
        assert r.status_code == 200
        body = r.json()
        assert body["career"]["bowler_name"] == "Blessing Muzarabani"
        assert body["career"]["pressure_spells"] == 24
        assert body["career"]["positive_pcs_pct"] == pytest.approx(79.17, abs=0.01)
        assert len(body["pressure_spells"]) == 24

        assert client.get("/api/pri/bowling/players/99999999").status_code == 404

    def test_comparison_endpoints_and_limits(self, client):
        rb = client.get("/api/pri/batting/compare?player_ids=1699,6396,3125")
        assert rb.status_code == 200
        assert rb.json()["count"] == 3

        rw = client.get("/api/pri/bowling/compare?player_ids=6523,2984,3644")
        assert rw.status_code == 200
        assert rw.json()["count"] == 3

        # Reject > 5 players
        assert client.get("/api/pri/batting/compare?player_ids=1,2,3,4,5,6").status_code == 400
        assert client.get("/api/pri/bowling/compare?player_ids=1,2,3,4,5,6").status_code == 400
        # Reject invalid non-numeric IDs
        assert client.get("/api/pri/batting/compare?player_ids=abc,1699").status_code == 422
        # All missing -> 404
        assert client.get("/api/pri/bowling/compare?player_ids=99999998,99999999").status_code == 404

    def test_warm_api_response_performance(self, client):
        # Warm cache hit & leaderboard latency
        t0 = time.perf_counter()
        assert client.get("/api/pri/overview").status_code == 200
        t_overview_ms = (time.perf_counter() - t0) * 1000.0

        t1 = time.perf_counter()
        assert client.get("/api/pri/batting/career?min_opportunities=12&page=1&page_size=20").status_code == 200
        t_bat_ms = (time.perf_counter() - t1) * 1000.0

        t2 = time.perf_counter()
        assert client.get("/api/pri/bowling/career?min_opportunities=18&page=1&page_size=20").status_code == 200
        t_bowl_ms = (time.perf_counter() - t2) * 1000.0

        assert t_overview_ms < 250.0
        assert t_bat_ms < 250.0
        assert t_bowl_ms < 250.0
