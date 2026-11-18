"""PCS Bowler Leaderboard API route."""

from typing import Optional
from fastapi import APIRouter, Depends, Query
from backend.schemas.pcs import PCSLeaderboardResponse, PCSTournamentsResponse
from backend.services.pcs_data_service import PCSDataService
from backend.api.pcs.dependencies import get_pcs_service

router = APIRouter()


@router.get(
    "/tournaments",
    response_model=PCSTournamentsResponse,
    summary="Get Authoritative List of Tournaments for PCS",
    description="Retrieves all tournaments from competitions.csv with match and spell counts for PCS.",
)
def get_pcs_tournaments(
    service: PCSDataService = Depends(get_pcs_service),
) -> PCSTournamentsResponse:
    """Fetch authoritative tournaments metadata for PCS."""
    return service.get_tournaments()


@router.get(
    "/leaderboard",
    response_model=PCSLeaderboardResponse,
    summary="Get Bowler Pressure Contribution Leaderboard",
    description="Returns filtered and paginated bowler rankings for PCS Career or Season, with sorting by shrunk or raw PCS.",
)
def get_pcs_leaderboard(
    scope: str = Query("career", pattern="^(career|season)$", description="Leaderboard scope: career or season"),
    season: Optional[str] = Query(None, description="Specific season filter (e.g. 2024, 2025)"),
    tournament: Optional[str] = Query(None, description="Specific tournament filter (e.g. 'IPL 2024', '2193')"),
    min_balls: int = Query(60, ge=0, description="Minimum legal balls bowled filter"),
    sort_by: str = Query("pcs_shrunk", description="Sort field: pcs_shrunk, pcs_raw, wickets, economy, legal_balls, total_rpe"),
    order: str = Query("desc", pattern="^(asc|desc)$", description="Sort direction"),
    search: Optional[str] = Query(None, description="Player name search term"),
    page: int = Query(1, ge=1, description="Page number (1-based)"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    service: PCSDataService = Depends(get_pcs_service),
) -> PCSLeaderboardResponse:
    """Get paginated and filtered PCS leaderboard."""
    return service.get_leaderboard(
        scope=scope,
        season=season,
        tournament=tournament,
        min_balls=min_balls,
        sort_by=sort_by,
        order=order,
        search=search,
        page=page,
        page_size=page_size,
    )
