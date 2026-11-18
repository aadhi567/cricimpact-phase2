"""Integration tests for frontend and static asset serving in CricImpact Phase 2."""

import pytest
from fastapi.testclient import TestClient
from backend.main import app


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as test_client:
        yield test_client


def test_frontend_app_endpoint(client: TestClient):
    """Verify /app serves index.html with 200 OK and expected HTML content."""
    res = client.get("/app")
    assert res.status_code == 200
    assert "text/html" in res.headers.get("content-type", "")
    assert "CricImpact Phase 2" in res.text
    assert "sidebar-container" in res.text
    assert "page-container" in res.text


def test_browser_root_navigation(client: TestClient):
    """Verify GET / with browser Accept header serves frontend index.html."""
    res = client.get("/", headers={"Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"})
    assert res.status_code == 200
    assert "text/html" in res.headers.get("content-type", "")
    assert "CricImpact Phase 2" in res.text


def test_api_root_navigation(client: TestClient):
    """Verify GET / with API client returns JSON metadata."""
    res = client.get("/", headers={"Accept": "application/json"})
    assert res.status_code == 200
    assert "application/json" in res.headers.get("content-type", "")
    data = res.json()
    assert data["status"] == "active"
    assert "/api/bowling" in data["bowling_api_base"]
    assert "/app" in data["frontend_app"]


def test_frontend_static_assets_serving(client: TestClient):
    """Verify JavaScript ES modules and CSS are served properly."""
    res_css = client.get("/src/assets/styles/main.css")
    assert res_css.status_code == 200
    assert "#EC4899" in res_css.text

    res_router = client.get("/src/utils/router.js")
    assert res_router.status_code == 200
    assert "class Router" in res_router.text

    res_service = client.get("/src/services/bowlingApiService.js")
    assert res_service.status_code == 200
    assert "class BowlingApiService" in res_service.text

    # PCS static asset tests
    res_pcs_service = client.get("/src/services/pcsApiService.js")
    assert res_pcs_service.status_code == 200
    assert "class PCSApiService" in res_pcs_service.text

    res_dashboard = client.get("/src/pages/BowlingDashboard.js")
    assert res_dashboard.status_code == 200
    assert "renderPCSSection" in res_dashboard.text

    res_leaderboard = client.get("/src/pages/BowlingLeaderboard.js")
    assert res_leaderboard.status_code == 200
    assert "renderPCSTable" in res_leaderboard.text

    res_profile = client.get("/src/pages/BowlerProfile.js")
    assert res_profile.status_code == 200
    assert "renderPCSProfileSection" in res_profile.text

    res_compare = client.get("/src/pages/BowlerComparison.js")
    assert res_compare.status_code == 200
    assert "PCS Pressure Analytics" in res_compare.text

    res_match = client.get("/src/pages/MatchAnalysis.js")
    assert res_match.status_code == 200
    assert "pcs_delivery" in res_match.text

    res_overview = client.get("/src/pages/OverviewPage.js")
    assert res_overview.status_code == 200
    assert "Pressure Contribution" in res_overview.text


def test_batting_static_mounts(client: TestClient):
    """Verify existing validated batting dashboards are mounted and served without modification."""
    res_hpp = client.get("/batting/hpp_dashboard.html")
    assert res_hpp.status_code == 200
    assert "text/html" in res_hpp.headers.get("content-type", "")

    res_worm = client.get("/batting/worm_graph.html")
    assert res_worm.status_code == 200
    assert "text/html" in res_worm.headers.get("content-type", "")

    res_exp = client.get("/batting/hpp_explorer.html")
    assert res_exp.status_code == 200
    assert "text/html" in res_exp.headers.get("content-type", "")
