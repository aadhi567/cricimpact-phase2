"""Read-only REST API router for validated Batting HPP/HPC analytics.

Stage B9: Batting HPP Dashboard UI Modernization.
Exposes read-only endpoints over frozen production HPP/HPC outputs without
modifying any underlying batting contribution calculations.
"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query

from backend.services.batting_data_service import BattingDataService


def get_batting_service() -> BattingDataService:
    svc = BattingDataService.get_instance()
    if not svc.is_initialized:
        svc.initialize()
    return svc


batting_router = APIRouter(prefix="/batting", tags=["Batting Analytics (HPP / HPC)"])


@batting_router.get("/health")
async def batting_health(svc: BattingDataService = Depends(get_batting_service)):
    """Health check and corpus telemetry for validated Batting HPP/HPC datasets."""
    return svc.get_health()


@batting_router.get("/filters")
async def batting_filters(svc: BattingDataService = Depends(get_batting_service)):
    """Return authoritative filter metadata (seasons, tournaments, teams, pressure tiers)."""
    return svc.get_filters()


@batting_router.get("/dashboard")
async def batting_dashboard(
    season: Optional[str] = Query(default=None, description="Season year (e.g. 2024) or 'all'"),
    tournament: Optional[str] = Query(default=None, description="Exact tournament name or 'all'"),
    comp_category: Optional[str] = Query(default=None, description="Competition category (IPL, T20I, OTHER_T20) or 'all'"),
    team: Optional[str] = Query(default=None, description="Batting team name or 'all'"),
    tier: Optional[str] = Query(default=None, description="Pressure tier (Low, Medium, High, Extreme) or 'all'"),
    svc: BattingDataService = Depends(get_batting_service),
):
    """Overview KPIs, player performance cohorts, and chart series for Batting Dashboard."""
    return svc.get_dashboard(
        season=season,
        tournament=tournament,
        comp_category=comp_category,
        team=team,
        tier=tier,
    )


@batting_router.get("/explorer")
async def batting_explorer(
    search: Optional[str] = Query(default=None, description="Search batter name or team"),
    season: Optional[str] = Query(default=None),
    team: Optional[str] = Query(default=None),
    tournament: Optional[str] = Query(default=None),
    comp_category: Optional[str] = Query(default=None),
    tier: Optional[str] = Query(default=None),
    min_inns: int = Query(default=1, ge=1),
    min_hpc: Optional[float] = Query(default=None),
    max_hpc: Optional[float] = Query(default=None),
    sort_by: str = Query(default="total_hpc"),
    sort_order: str = Query(default="desc"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    svc: BattingDataService = Depends(get_batting_service),
):
    """Searchable, filterable, sortable Batting HPP Explorer table."""
    return svc.get_explorer(
        search=search,
        season=season,
        team=team,
        tournament=tournament,
        comp_category=comp_category,
        tier=tier,
        min_inns=min_inns,
        min_hpc=min_hpc,
        max_hpc=max_hpc,
        sort_by=sort_by,
        sort_order=sort_order,
        page=page,
        page_size=page_size,
    )


@batting_router.get("/players")
async def batting_players_list(
    search: Optional[str] = Query(default=None),
    limit: int = Query(default=1000, ge=1, le=1500),
    svc: BattingDataService = Depends(get_batting_service),
):
    """List batters for player selectors and autocomplete controls."""
    players = svc.list_players(search=search, limit=limit)
    return {"total": len(players), "players": players}


@batting_router.get("/players/{player_identifier}")
async def batting_player_profile(
    player_identifier: str,
    season: Optional[str] = Query(default=None),
    tournament: Optional[str] = Query(default=None),
    comp_category: Optional[str] = Query(default=None),
    svc: BattingDataService = Depends(get_batting_service),
):
    """Detailed individual batter HPP/HPC profile, season trends, and match breakdown (preserving DNB)."""
    profile = svc.get_player_profile(
        player_identifier,
        season=season,
        tournament=tournament,
        comp_category=comp_category,
    )
    if not profile:
        raise HTTPException(status_code=404, detail=f"Batter '{player_identifier}' not found.")
    return profile


@batting_router.get("/compare")
async def batting_compare(
    players: str = Query(..., description="Comma-separated list of 2 to 5 batter names or IDs"),
    season: Optional[str] = Query(default=None),
    tournament: Optional[str] = Query(default=None),
    comp_category: Optional[str] = Query(default=None),
    svc: BattingDataService = Depends(get_batting_service),
):
    """Compare 2 to 5 batters across career, season, pressure tiers, and shared matches."""
    raw_list = [p.strip() for p in players.split(",") if p.strip()]
    if len(raw_list) < 2 or len(raw_list) > 5:
        raise HTTPException(
            status_code=400,
            detail="Please provide between 2 and 5 batters to compare.",
        )
    result = svc.compare_players(
        raw_list,
        season=season,
        tournament=tournament,
        comp_category=comp_category,
    )
    if len(result["players"]) < 2:
        raise HTTPException(
            status_code=404,
            detail="Could not resolve at least 2 valid batters from the provided names.",
        )
    return result


@batting_router.get("/matches")
async def batting_matches_list(
    search: Optional[str] = Query(default=None),
    season: Optional[str] = Query(default=None),
    tournament: Optional[str] = Query(default=None),
    comp_category: Optional[str] = Query(default=None),
    team: Optional[str] = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=30, ge=1, le=100),
    svc: BattingDataService = Depends(get_batting_service),
):
    """Paginated searchable list of all 798 matches with Win Probability Worm & HPP data."""
    return svc.list_matches(
        search=search,
        season=season,
        tournament=tournament,
        comp_category=comp_category,
        team=team,
        page=page,
        page_size=page_size,
    )


@batting_router.get("/matches/{match_id}")
async def batting_match_detail(
    match_id: str,
    svc: BattingDataService = Depends(get_batting_service),
):
    """Full ball-by-ball win probability trajectory, key moments, and HPP batting scorecards (DNB preserved)."""
    detail = svc.get_match_detail(match_id)
    if not detail:
        raise HTTPException(status_code=404, detail=f"Match '{match_id}' not found.")
    return detail
