"""Comprehensive pytest suite for Stage B8 Bowling Pressure Contribution Score (PCS) API."""

import pytest
from fastapi.testclient import TestClient
from backend.main import app


@pytest.fixture(scope="module")
def client():
    """Create test client fixture for FastAPI app."""
    with TestClient(app) as test_client:
        yield test_client


# =============================================================================
# 1. HEALTH ENDPOINT TESTS
# =============================================================================

def test_pcs_health(client: TestClient):
    """Test /api/pcs/health status and dataset verification."""
    res = client.get("/api/pcs/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert data["service_initialized"] is True
    assert data["pipeline_version"] == "1.0.0"
    assert data["total_deliveries"] == 190575
    assert data["total_spells"] == 9482
    assert data["total_career_records"] == 638
    assert data["total_season_records"] == 1587
    assert data["datasets"]["manifest"] is True
    assert data["datasets"]["career"] is True
    assert data["datasets"]["season"] is True
    assert data["datasets"]["spells"] is True
    assert data["datasets"]["deliveries"] is True


def test_system_health_pcs_integration(client: TestClient):
    """Test global /health check endpoint includes PCS initialized status."""
    res = client.get("/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "healthy"
    assert data["pcs_service_initialized"] is True
    assert data["pcs_deliveries"] == 190575


# =============================================================================
# 2. DASHBOARD ENDPOINT TESTS
# =============================================================================

def test_pcs_dashboard_overview(client: TestClient):
    """Test /api/pcs/dashboard statistics and distribution buckets."""
    res = client.get("/api/pcs/dashboard")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"

    # Corpus Totals
    assert data["total_matches"] == 798
    assert data["total_spells"] == 9482
    assert data["total_deliveries"] == 190575
    assert data["legal_balls"] > 0
    assert data["average_spell_pcs"] >= 45.0
    assert data["average_spell_pcs"] <= 55.0

    # Best and Worst Spells
    assert data["highest_spell_pcs"]["pcs_spell"] >= 90.0
    assert data["lowest_spell_pcs"]["pcs_spell"] <= 15.0

    # Distribution
    dist = data["pcs_distribution"]
    assert dist["mean"] >= 50.0
    assert len(dist["bins"]) == 7
    assert (dist["positive_spells_pct"] + dist["neutral_spells_pct"] + dist["negative_spells_pct"]) >= 99.0

    # Top Career Leaders
    assert len(data["top_career_leaders"]) == 10
    top1 = data["top_career_leaders"][0]
    assert top1["pcs_career_shrunk"] >= 60.0
    assert top1["legal_balls"] >= 240

    # Top Season Leaders
    assert len(data["top_season_leaders"]) == 10


# =============================================================================
# 3. LEADERBOARD ENDPOINT TESTS
# =============================================================================

def test_pcs_leaderboard_career(client: TestClient):
    """Test /api/pcs/leaderboard career rankings and pagination."""
    res = client.get("/api/pcs/leaderboard?scope=career&page=1&page_size=20")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert data["current_scope"] == "career"
    assert len(data["items"]) == 20
    assert data["pagination"]["total_items"] > 100
    assert data["pagination"]["current_page"] == 1

    # Check descending order by shrunk PCS
    shrunk_scores = [item["pcs_shrunk"] for item in data["items"]]
    assert shrunk_scores == sorted(shrunk_scores, reverse=True)


def test_pcs_leaderboard_season(client: TestClient):
    """Test /api/pcs/leaderboard season filtering."""
    res = client.get("/api/pcs/leaderboard?scope=season&season=2024&min_balls=100")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert data["current_scope"] == "season"
    assert data["active_season"] == "2024"
    for item in data["items"]:
        assert item["legal_balls"] >= 100
        assert item["season"] == "2024"


def test_pcs_leaderboard_search(client: TestClient):
    """Test /api/pcs/leaderboard bowler name query search."""
    res = client.get("/api/pcs/leaderboard?search=narine")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert len(data["items"]) >= 1
    assert "narine" in data["items"][0]["bowler_name"].lower()


# =============================================================================
# 4. BOWLER PROFILE ENDPOINT TESTS
# =============================================================================

def test_pcs_player_profile_valid(client: TestClient):
    """Test /api/pcs/players/{player_id} with valid bowler."""
    # Test Sunil Narine (781) or Sufiyan Muqeem (34485)
    res = client.get("/api/pcs/players/781")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert data["bowler_id"] == 781
    assert "Narine" in data["bowler_name"]

    # Career summary
    assert data["career"]["legal_balls"] >= 1000
    assert data["career"]["pcs_career_shrunk"] >= 55.0

    # Season history
    assert len(data["season_history"]) >= 2

    # Spells history
    assert len(data["spells_history"]) >= 20

    # Pressure breakdown
    assert data["pressure_breakdown"]["dot_ball_pct"] > 0


def test_pcs_player_profile_invalid(client: TestClient):
    """Test /api/pcs/players/{player_id} returns 404 for non-existent bowler."""
    res = client.get("/api/pcs/players/9999999")
    assert res.status_code == 404
    assert "not found" in res.json()["detail"].lower()


# =============================================================================
# 5. BOWLER COMPARISON ENDPOINT TESTS
# =============================================================================

def test_pcs_comparison_valid(client: TestClient):
    """Test /api/pcs/compare comparing 3 bowlers."""
    res = client.get("/api/pcs/compare?bowlers=28756,34485,781")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert len(data["bowlers"]) == 3
    ids = [b["bowler_id"] for b in data["bowlers"]]
    assert 28756 in ids
    assert 34485 in ids
    assert 781 in ids


def test_pcs_comparison_invalid_ids(client: TestClient):
    """Test /api/pcs/compare with non-integer query."""
    res = client.get("/api/pcs/compare?bowlers=abc,def")
    assert res.status_code == 400


# =============================================================================
# 6. MATCH & SPELL EXPLORER ENDPOINT TESTS
# =============================================================================

def test_pcs_matches_list(client: TestClient):
    """Test /api/pcs/matches list and pagination."""
    res = client.get("/api/pcs/matches?page=1&page_size=10")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert len(data["matches"]) == 10
    assert data["pagination"]["total_items"] == 798


def test_pcs_match_detail(client: TestClient):
    """Test /api/pcs/matches/{match_id} delivery timeline and spell breakdowns."""
    res = client.get("/api/pcs/matches/13511")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert data["match_id"] == 13511
    assert len(data["bowler_spells"]) >= 2
    assert len(data["delivery_timeline"]) > 100

    # Verify delivery fields
    first_del = data["delivery_timeline"][0]
    assert "pcs_delivery" in first_del
    assert "rpe" in first_del
    assert "leverage" in first_del
    assert "score_before" in first_del


def test_pcs_spell_deliveries(client: TestClient):
    """Test /api/pcs/spells/{spell_id}/deliveries for a specific spell."""
    spell_id = "13511_1_2633"
    res = client.get(f"/api/pcs/spells/{spell_id}/deliveries")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert data["spell_id"] == spell_id
    assert len(data["deliveries"]) >= 6
