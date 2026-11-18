"""Automated API & Data Fidelity Tests for Stage B9 Batting HPP Analytics."""

import pytest
from fastapi.testclient import TestClient

from backend.main import app


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def test_batting_health_and_corpus_counts(client):
    r = client.get("/api/batting/health")
    assert r.status_code == 200
    d = r.json()
    assert d["status"] == "healthy"
    assert d["matches_evaluated"] == 798
    assert d["batted_stints"] == 12888
    assert d["dnb_stints"] == 145
    assert d["total_stints"] == 13033
    assert d["unique_batters"] == 880
    assert d["tournaments_count"] == 137
    assert d["teams_count"] >= 35


def test_batting_filters_metadata_not_hardcoded(client):
    r = client.get("/api/batting/filters")
    assert r.status_code == 200
    d = r.json()
    assert set(["2022", "2023", "2024", "2025", "2026"]).issubset(set(d["seasons"]))
    assert len(d["tournaments"]) == 137
    assert len(d["teams"]) >= 35
    assert d["pressure_tiers"] == ["Low", "Medium", "High", "Extreme"]


def test_batting_dashboard_kpis_match_production_data(client):
    r = client.get("/api/batting/dashboard")
    assert r.status_code == 200
    d = r.json()
    kpis = d["kpis"]
    assert kpis["matches_played"] == 798
    assert kpis["batted_stints"] == 12888
    assert kpis["dnb_stints"] == 145
    assert kpis["total_runs"] == 254144
    assert abs(kpis["avg_pressure_faced"] - 35.78) < 0.05
    assert abs(kpis["positive_contribution_pct"] - 35.72) < 0.1
    assert abs(kpis["avg_hpc"] - (-0.83)) < 0.05

    # Career HPC leader matches hpp_leaderboards.json (Abhishek Sharma +522.38)
    top0 = d["top_contributors"][0]
    assert top0["batter_name"] == "Abhishek Sharma"
    assert top0["actual_runs"] == 4076
    assert abs(top0["total_hpc"] - 522.38) < 0.15

    # All required sections present
    assert len(d["best_positive_contributors"]) == 10
    assert len(d["negative_contributors"]) == 10
    assert len(d["recent_trends"]) > 0
    assert len(d["charts"]["hpc_distribution"]) == 8
    assert len(d["charts"]["runs_vs_hpc"]) > 50
    assert len(d["charts"]["season_trend"]) == 5
    assert len(d["charts"]["pressure_vs_contribution"]) == 4


def test_batting_explorer_filters_and_sorting(client):
    # Default sort by total_hpc desc
    r = client.get("/api/batting/explorer?page=1&page_size=20")
    assert r.status_code == 200
    d = r.json()
    assert d["items"][0]["batter_name"] == "Abhishek Sharma"
    assert d["items"][0]["rank"] == 1

    # Filter by season + team + search
    r2 = client.get("/api/batting/explorer?season=2024&team=India&search=Surya")
    assert r2.status_code == 200
    d2 = r2.json()
    assert d2["pagination"]["total_items"] >= 1
    assert any("Suryakumar" in it["batter_name"] for it in d2["items"])

    # Contribution range filter
    r3 = client.get("/api/batting/explorer?min_hpc=100&max_hpc=600")
    assert r3.status_code == 200
    d3 = r3.json()
    assert d3["pagination"]["total_items"] > 0
    for it in d3["items"]:
        assert 100 <= it["total_hpc"] <= 600


def test_batting_player_profile_and_dnb_preservation(client):
    # Test Tymal Mills who has a known DNB in match 13511
    r = client.get("/api/batting/players/Tymal%20Mills")
    assert r.status_code == 200
    d = r.json()
    assert d["summary"]["dnb_count"] >= 1

    dnb_rows = [m for m in d["match_log"] if m["is_dnb"]]
    assert len(dnb_rows) == d["summary"]["dnb_count"]
    for row in dnb_rows:
        assert row["dismissal"] == "Not Batted"
        assert row["tier"] == "DNB"
        assert row["runs"] is None
        assert row["exp_runs"] is None
        assert row["rae"] is None
        assert row["mean_p"] is None
        assert row["hpc"] is None
        assert row["cumulative_hpc"] is None

    # Verify Abhishek Sharma profile matches frozen leaderboards exactly
    r2 = client.get("/api/batting/players/Abhishek%20Sharma")
    assert r2.status_code == 200
    d2 = r2.json()
    assert d2["summary"]["innings_batted"] == 126
    assert d2["summary"]["actual_runs"] == 4076
    assert d2["summary"]["balls_faced"] == 2164
    assert abs(d2["summary"]["total_hpc"] - 522.38) < 0.15
    assert len(d2["by_innings"]) == 2
    assert len(d2["by_pressure_tier"]) == 4

    # 404 for unknown batter
    r404 = client.get("/api/batting/players/NonExistentBatterXYZ")
    assert r404.status_code == 404


def test_batting_comparison_and_common_matches(client):
    r = client.get("/api/batting/compare?players=Abhishek%20Sharma,Suryakumar%20Yadav,Virat%20Kohli")
    assert r.status_code == 200
    d = r.json()
    assert len(d["players"]) == 3
    names = [p["batter_name"] for p in d["players"]]
    assert "Abhishek Sharma" in names
    assert "Suryakumar Yadav" in names
    assert "Virat Kohli" in names
    assert len(d["seasons"]) > 0
    assert d["total_common_matches"] >= 1

    # Validation: fewer than 2 players -> 400
    r_bad = client.get("/api/batting/compare?players=Virat%20Kohli")
    assert r_bad.status_code == 400


def test_batting_matches_and_worm_graph_detail_with_dnb(client):
    r = client.get("/api/batting/matches?page=1&page_size=20")
    assert r.status_code == 200
    d = r.json()
    assert d["pagination"]["total_items"] == 798

    # Match 13511 has known DNB Tymal Mills in inn 1
    rm = client.get("/api/batting/matches/13511")
    assert rm.status_code == 200
    dm = rm.json()
    assert dm["team_a_name"] == "England"
    assert dm["team_b_name"] == "West Indies"
    assert len(dm["points"]) == 224
    assert len(dm["moments"]) > 0
    dnb_inn1 = [s for s in dm["innings_1_stints"] if s["is_dnb"]]
    assert len(dnb_inn1) == 1
    assert dnb_inn1[0]["name"] == "Tymal Mills"
    assert dnb_inn1[0]["hpc"] is None
    assert dnb_inn1[0]["runs"] is None
    assert dnb_inn1[0]["dismissal"] == "Not Batted"
