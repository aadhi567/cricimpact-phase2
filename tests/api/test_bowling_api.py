"""Comprehensive pytest suite for Stage B5 Bowling Analytics API."""

import pytest
from fastapi.testclient import TestClient
from backend.main import app


@pytest.fixture(scope="module")
def client():
    """Create a test client fixture for the FastAPI application."""
    with TestClient(app) as test_client:
        yield test_client


# =============================================================================
# 1. SYSTEM & HEALTH ENDPOINT TESTS
# =============================================================================

def test_system_root(client: TestClient):
    """Test the root endpoint for API metadata."""
    res = client.get("/")
    assert res.status_code == 200
    data = res.json()
    assert "name" in data
    assert data["status"] == "active"
    assert "/api/bowling" in data["bowling_api_base"]


def test_system_health(client: TestClient):
    """Test health check endpoints and verified corpus totals."""
    res = client.get("/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "healthy"
    assert data["service_initialized"] is True
    assert data["corpus_matches"] == 798
    assert data["career_bowlers"] == 638
    assert data["match_spells"] == 9482
    assert data["deliveries"] == 190575

    res_api = client.get("/api/health")
    assert res_api.status_code == 200
    assert res_api.json()["status"] == "healthy"


# =============================================================================
# 2. DASHBOARD ENDPOINT TESTS
# =============================================================================

def test_bowling_dashboard_kpis(client: TestClient):
    """Test dashboard KPIs, distribution, and top performers."""
    res = client.get("/api/bowling/dashboard")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"

    # Corpus KPIs
    assert data["total_matches"] == 798
    assert data["total_spells"] == 9482
    assert data["total_deliveries"] == 190575
    assert data["legal_balls"] == 182504
    assert data["total_wickets"] == 9662
    assert 7.0 <= data["overall_economy"] <= 9.5
    assert 30.0 <= data["dot_ball_pct"] <= 50.0

    # BCS Distribution
    dist = data["bcs_distribution"]
    assert dist["min"] < 0
    assert dist["max"] > 100.0
    assert dist["positive_share_pct"] > 50.0
    assert dist["negative_share_pct"] > 30.0

    # Phase Breakdown
    phases = {p["phase"]: p for p in data["phase_breakdown"]}
    assert set(phases.keys()) == {"powerplay", "middle", "death"}
    for p_name, p_data in phases.items():
        assert p_data["legal_balls"] > 0
        assert p_data["wickets"] > 0
        assert p_data["economy"] > 0.0

    # Top Career BCS
    top_bcs = data["top_career_bcs"]
    assert len(top_bcs) == 5
    assert top_bcs[0]["bowler_name"] == "Rashid Khan"
    assert top_bcs[0]["total_bcs"] == 1631.73

    # Top Career bWPA
    top_bwpa = data["top_career_bwpa"]
    assert len(top_bwpa) == 5
    assert top_bwpa[0]["bowler_name"] == "Rashid Khan"
    assert top_bwpa[0]["total_bwpa"] == 9.609

    # Top Match Spells
    top_spells = data["top_match_spells"]
    assert len(top_spells) == 5
    assert top_spells[0]["total_bcs"] > 100.0


# =============================================================================
# 3. LEADERBOARD ENDPOINT TESTS
# =============================================================================

def test_bowling_leaderboard_defaults(client: TestClient):
    """Test leaderboard with default pagination and sorting."""
    res = client.get("/api/bowling/leaderboard")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert data["pagination"]["current_page"] == 1
    assert data["pagination"]["page_size"] == 20
    assert len(data["items"]) == 20

    # Default sort is total_bcs descending -> Rashid Khan #1
    top_bowler = data["items"][0]
    assert top_bowler["rank"] == 1
    assert top_bowler["bowler_name"] == "Rashid Khan"
    assert top_bowler["total_bcs"] == 1631.73
    assert top_bowler["wickets"] == 149
    assert top_bowler["economy"] == 7.43


def test_bowling_leaderboard_pagination(client: TestClient):
    """Test leaderboard pagination and rank offsets."""
    res_p1 = client.get("/api/bowling/leaderboard?page=1&page_size=10")
    res_p2 = client.get("/api/bowling/leaderboard?page=2&page_size=10")
    assert res_p1.status_code == 200
    assert res_p2.status_code == 200

    d1 = res_p1.json()
    d2 = res_p2.json()

    assert len(d1["items"]) == 10
    assert len(d2["items"]) == 10
    assert d1["items"][0]["rank"] == 1
    assert d2["items"][0]["rank"] == 11
    assert d1["items"][-1]["total_bcs"] >= d2["items"][0]["total_bcs"]


def test_bowling_leaderboard_sort_options(client: TestClient):
    """Test sorting by wickets, economy, and bWPA."""
    # Sort by wickets desc -> Arshdeep Singh should be #1 (178 wkts)
    res_w = client.get("/api/bowling/leaderboard?sort_by=wickets&order=desc&page_size=5")
    assert res_w.status_code == 200
    items_w = res_w.json()["items"]
    assert items_w[0]["bowler_name"] == "Arshdeep Singh"
    assert items_w[0]["wickets"] == 178

    # Sort by economy asc
    res_e = client.get("/api/bowling/leaderboard?sort_by=economy&order=asc&min_balls=120&page_size=5")
    assert res_e.status_code == 200
    items_e = res_e.json()["items"]
    e_rates = [it["economy"] for it in items_e]
    assert e_rates == sorted(e_rates)

    # Sort by total_bwpa desc
    res_bwpa = client.get("/api/bowling/leaderboard?sort_by=total_bwpa&order=desc&page_size=5")
    assert res_bwpa.status_code == 200
    items_bwpa = res_bwpa.json()["items"]
    assert items_bwpa[0]["bowler_name"] == "Rashid Khan"
    assert items_bwpa[0]["total_bwpa"] == 9.609


def test_bowling_leaderboard_season_filter(client: TestClient):
    """Test filtering leaderboard by season."""
    res = client.get("/api/bowling/leaderboard?season=2024&min_balls=30&page_size=5")
    assert res.status_code == 200
    data = res.json()
    assert data["season_filter"] == "2024"
    assert len(data["items"]) > 0


def test_bowling_leaderboard_phase_filter(client: TestClient):
    """Test filtering leaderboard by phase (e.g. death overs)."""
    res = client.get("/api/bowling/leaderboard?phase=death&min_balls=60&page_size=5")
    assert res.status_code == 200
    data = res.json()
    assert data["phase_filter"] == "death"
    assert len(data["items"]) == 5
    top_death = data["items"][0]
    assert top_death["bowler_name"] == "Rashid Khan"
    assert top_death["total_bcs"] > 400.0


# =============================================================================
# 4. PLAYER PROFILE ENDPOINT TESTS
# =============================================================================

@pytest.mark.parametrize(
    "player_id,expected_name,expected_matches,expected_overs,expected_wickets,expected_econ,expected_bcs,expected_bwpa",
    [
        (4722, "Rashid Khan", 117, 441.5, 149, 7.43, 1631.73, 9.609),
        (6464, "Arshdeep Singh", 137, 500.4, 178, 9.13, 1282.75, 6.1776),
        (6256, "Varun Chakravarthy", 90, 334.4, 128, 8.03, 1245.44, 2.4303),
        (360, "Bhuvneshwar Kumar", 96, 354.1, 112, 8.29, 1156.50, 3.7277),
        (2876, "Axar Patel", 128, 424.0, 114, 7.84, 1149.39, 3.2865),
        (2933, "Jasprit Bumrah", 69, 263.4, 77, 7.21, 1034.39, 2.0344),
    ],
)
def test_canonical_bowler_profiles(
    client: TestClient,
    player_id: int,
    expected_name: str,
    expected_matches: int,
    expected_overs: float,
    expected_wickets: int,
    expected_econ: float,
    expected_bcs: float,
    expected_bwpa: float,
):
    """Verify canonical bowler profiles match verified Stage B4 production outputs."""
    res = client.get(f"/api/bowling/players/{player_id}")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert data["bowler_id"] == player_id
    assert data["bowler_name"] == expected_name

    summary = data["career_summary"]
    assert summary["matches"] == expected_matches
    assert summary["overs"] == expected_overs
    assert summary["wickets"] == expected_wickets
    assert summary["economy"] == expected_econ
    assert summary["total_bcs"] == expected_bcs
    assert summary["total_bwpa"] == expected_bwpa

    # Phase splits
    splits = {p["phase"]: p for p in data["phase_splits"]}
    assert set(splits.keys()) == {"powerplay", "middle", "death"}

    # Season breakdown
    assert len(data["season_breakdown"]) > 0

    # Spells lists
    assert len(data["top_spells"]) <= 5
    assert len(data["recent_spells"]) <= 5


def test_player_profile_404(client: TestClient):
    """Test 404 response for non-existent bowler ID."""
    res = client.get("/api/bowling/players/999999")
    assert res.status_code == 404
    data = res.json()
    assert data["status"] == "error"
    assert "999999" in data["detail"]


# =============================================================================
# 5. BOWLER COMPARISON ENDPOINT TESTS
# =============================================================================

def test_bowler_comparison_valid(client: TestClient):
    """Test valid comparison between 2 and 5 bowlers."""
    # 2 bowlers
    res2 = client.get("/api/bowling/compare?player_ids=4722,6464")
    assert res2.status_code == 200
    d2 = res2.json()
    assert d2["bowlers_count"] == 2
    assert d2["bowlers"][0]["bowler_name"] == "Rashid Khan"
    assert d2["bowlers"][1]["bowler_name"] == "Arshdeep Singh"

    # 5 bowlers
    res5 = client.get("/api/bowling/compare?player_ids=4722,6464,6256,360,2876")
    assert res5.status_code == 200
    d5 = res5.json()
    assert d5["bowlers_count"] == 5


def test_bowler_comparison_validations(client: TestClient):
    """Test bowler comparison validation rules (min, max, duplicates, 404)."""
    # Too few (<2)
    res_few = client.get("/api/bowling/compare?player_ids=4722")
    assert res_few.status_code == 422

    # Too many (>5)
    res_many = client.get("/api/bowling/compare?player_ids=4722,6464,6256,360,2876,2933")
    assert res_many.status_code == 422

    # Duplicate IDs
    res_dup = client.get("/api/bowling/compare?player_ids=4722,4722")
    assert res_dup.status_code == 422

    # Invalid ID format
    res_inv = client.get("/api/bowling/compare?player_ids=abc,4722")
    assert res_inv.status_code == 422

    # Non-existent player
    res_404 = client.get("/api/bowling/compare?player_ids=4722,999999")
    assert res_404.status_code == 404


# =============================================================================
# 6. MATCH & SPELLS ENDPOINT TESTS
# =============================================================================

def test_match_listing(client: TestClient):
    """Test match list retrieval, filtering, and sorting."""
    res = client.get("/api/bowling/matches?page_size=10")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert data["pagination"]["total_items"] == 798
    assert len(data["items"]) == 10

    # Each match has teams and top bowler
    first_match = data["items"][0]
    assert len(first_match["teams"]) >= 2
    assert first_match["top_bowler"] is not None
    assert first_match["top_bowler"]["total_bcs"] is not None


def test_match_spells(client: TestClient):
    """Test spells retrieval for a specific match (13511)."""
    res = client.get("/api/bowling/matches/13511/spells")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert data["match_id"] == 13511
    assert data["spells_count"] == 13

    # Jason Holder top spell in match 13511
    top_spell = data["spells"][0]
    assert top_spell["bowler_name"] == "Jason Holder"
    assert top_spell["wickets"] == 4
    assert top_spell["total_bcs"] == 64.04
    assert len(top_spell["phase_breakdown"]) > 0


def test_match_spells_404(client: TestClient):
    """Test 404 response for non-existent match ID."""
    res = client.get("/api/bowling/matches/999999/spells")
    assert res.status_code == 404
    data = res.json()
    assert data["status"] == "error"


# =============================================================================
# 7. DELIVERY TRANSITION ENDPOINT TESTS
# =============================================================================

def test_spell_deliveries(client: TestClient):
    """Test delivery-level analysis for spell '13511_1_2633' (Jason Holder)."""
    spell_id = "13511_1_2633"
    res = client.get(f"/api/bowling/spells/{spell_id}/deliveries")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert data["spell_id"] == spell_id
    assert data["deliveries_count"] == 22
    assert data["bowler_name"] == "Jason Holder"

    # Verify delivery schema fields
    deliveries = data["deliveries"]
    wicket_count = 0
    for d in deliveries:
        assert d["striker_name"] is not None
        assert d["non_striker_name"] is not None
        assert d["innings_phase"] in {"powerplay", "middle", "death"}
        assert d["leverage"] >= 0.5
        assert d["WQM"] >= 0.4
        
        # Strict isolation check
        assert isinstance(d["bcs"], float)
        assert isinstance(d["bwpa"], float)

        assert d["V_wkt"] >= 0.0

        if d["is_bowler_wkt"]:
            wicket_count += 1
            assert d["dismissed_player_name"] is not None
            assert d["bcs"] > 5.0

    assert wicket_count == 4


def test_spell_deliveries_404(client: TestClient):
    """Test 404 response for non-existent spell ID."""
    res = client.get("/api/bowling/spells/invalid_spell_123/deliveries")
    assert res.status_code == 404
    data = res.json()
    assert data["status"] == "error"


# =============================================================================
# 8. MATHEMATICAL & NOTATION INTEGRITY TESTS
# =============================================================================

def test_cricket_notation_and_economy_consistency(client: TestClient):
    """Verify economy formula and cricket overs notation across random samples."""
    res = client.get("/api/bowling/leaderboard?min_balls=60&page_size=50")
    assert res.status_code == 200
    items = res.json()["items"]

    for item in items:
        legal_balls = item["legal_balls"]
        runs = item["bowler_runs"]
        econ = item["economy"]
        overs = item["overs"]
        overs_str = item["overs_formatted"]

        # 1. Cricket notation check: legal_balls == (overs_completed * 6 + remaining_balls)
        parts = overs_str.split(".")
        completed_overs = int(parts[0])
        balls_in_over = int(parts[1])
        assert legal_balls == (completed_overs * 6 + balls_in_over)
        assert balls_in_over < 6

        # 2. Economy formula check: runs * 6.0 / legal_balls (within 0.05 due to rounding)
        expected_econ = round(runs * 6.0 / legal_balls, 2)
        assert abs(econ - expected_econ) < 0.05


# =============================================================================
# 9. STAGE B5.1 AUDIT TESTS: BCS SEMANTICS & RECONCILIATION
# =============================================================================

@pytest.mark.parametrize(
    "player_id,expected_name,expected_total_bcs,expected_shrunk_bcs,expected_bcs_per_ov,expected_shrunk_per_ov",
    [
        (4722, "Rashid Khan", 1631.73, 1621.53, 3.69, 3.67),
        (6464, "Arshdeep Singh", 1282.75, 1281.44, 2.56, 2.56),
        (6256, "Varun Chakravarthy", 1245.44, 1235.08, 3.72, 3.69),
        (360, "Bhuvneshwar Kumar", 1156.50, 1149.69, 3.27, 3.25),
        (2876, "Axar Patel", 1149.39, 1146.91, 2.71, 2.70),
        (2933, "Jasprit Bumrah", 1034.39, 1022.53, 3.92, 3.88),
    ],
)
def test_bcs_field_semantics_and_shrinkage(
    client: TestClient,
    player_id: int,
    expected_name: str,
    expected_total_bcs: float,
    expected_shrunk_bcs: float,
    expected_bcs_per_ov: float,
    expected_shrunk_per_ov: float,
):
    """Verify that the API cleanly distinguishes total_bcs vs shrunk_bcs vs per-over rates."""
    res = client.get(f"/api/bowling/players/{player_id}")
    assert res.status_code == 200
    data = res.json()
    summary = data["career_summary"]

    assert summary["bowler_name"] == expected_name
    assert summary["total_bcs"] == expected_total_bcs
    assert summary["shrunk_bcs"] == expected_shrunk_bcs
    assert summary["total_bcs_shrunk"] == expected_shrunk_bcs
    assert summary["bcs_per_over"] == expected_bcs_per_ov
    assert summary["shrunk_bcs_per_over"] == expected_shrunk_per_ov


def test_leaderboard_sorting_by_shrunk_bcs(client: TestClient):
    """Verify sorting leaderboard by shrunk_bcs returns correct top bowlers."""
    res = client.get("/api/bowling/leaderboard?sort_by=shrunk_bcs&order=desc&page_size=5")
    assert res.status_code == 200
    items = res.json()["items"]

    assert len(items) == 5
    assert items[0]["bowler_name"] == "Rashid Khan"
    assert items[0]["shrunk_bcs"] == 1621.53
    assert items[1]["bowler_name"] == "Arshdeep Singh"
    assert items[1]["shrunk_bcs"] == 1281.44
    assert items[2]["bowler_name"] == "Varun Chakravarthy"
    assert items[2]["shrunk_bcs"] == 1235.08


def test_corpus_delivery_to_career_reconciliation(client: TestClient):
    """Verify exact zero-discrepancy aggregation from match spells to career across all 638 bowlers."""
    from backend.services.bowling_data_service import BowlingDataService
    import numpy as np

    service = BowlingDataService.get_instance()
    spells_df = service.spells_df
    career_df = service.career_df

    # Aggregate spells by bowler
    sp_agg = spells_df.groupby("bowler_id").agg(
        bcs=("total_bcs", "sum"),
        bwpa=("total_bwpa", "sum"),
        erp=("total_erp", "sum"),
        legal=("legal_balls", "sum"),
        wkts=("wickets", "sum"),
    ).reset_index()

    merged = career_df.merge(sp_agg, on="bowler_id")
    assert len(merged) == 638

    # Verify zero discrepancies
    diff_bcs = np.abs(merged["total_bcs"] - merged["bcs"].round(2)).max()
    diff_bwpa = np.abs(merged["total_bwpa"] - merged["bwpa"].round(4)).max()
    diff_erp = np.abs(merged["total_erp"] - merged["erp"].round(2)).max()

    assert diff_bcs < 0.001, f"Career BCS aggregation discrepancy: {diff_bcs}"
    assert diff_bwpa < 0.0001, f"Career bWPA aggregation discrepancy: {diff_bwpa}"
    assert diff_erp < 0.001, f"Career ERP aggregation discrepancy: {diff_erp}"
    assert (merged["legal_balls"] == merged["legal"]).all(), "Career legal balls discrepancy"
    assert (merged["wickets"] == merged["wkts"]).all(), "Career wickets discrepancy"

