"""Bowling Leaderboard API route."""

from typing import Optional
from fastapi import APIRouter, Depends, Query
from backend.core.config import settings
from backend.schemas.bowling import BowlingLeaderboardResponse, BowlingTournamentsResponse
from backend.services.bowling_data_service import BowlingDataService

router = APIRouter()


def get_bowling_service() -> BowlingDataService:
    """Dependency injection helper for BowlingDataService singleton."""
    return BowlingDataService.get_instance()


@router.get(
    "/tournaments",
    response_model=BowlingTournamentsResponse,
    summary="Get Authoritative List of Tournaments",
    description="Retrieves all tournaments from competitions.csv with match and spell counts.",
)
def get_bowling_tournaments(
    service: BowlingDataService = Depends(get_bowling_service),
) -> BowlingTournamentsResponse:
    """Fetch authoritative tournaments metadata."""
    return service.get_tournaments()


@router.get(
    "/leaderboard",
    response_model=BowlingLeaderboardResponse,
    summary="Get Filterable & Sortable Bowling Leaderboard",
    description=(
        "Retrieves a paginated bowling leaderboard with support for filtering by season (e.g. '2024'), "
        "tournament/competition (e.g. 'IPL 2024'), or match phase ('powerplay', 'middle', 'death'), "
        "thresholding by minimum legal balls bowled, and sorting by key metrics."
    ),
)
def get_bowling_leaderboard(
    season: Optional[str] = Query(
        None,
        description="Filter by season (e.g. '2024', '2023/24') or omit/'all' for career aggregate.",
    ),
    tournament: Optional[str] = Query(
        None,
        description="Filter by tournament name or comp_id (e.g. 'IPL 2024', '2193').",
    ),
    phase: Optional[str] = Query(
        None,
        description="Filter by match phase: 'powerplay', 'middle', or 'death'.",
    ),
    min_balls: int = Query(
        settings.DEFAULT_MIN_BALLS,
        ge=0,
        description="Minimum legal balls bowled threshold (default 60).",
    ),
    sort_by: str = Query(
        "total_bcs",
        description="Sorting metric: total_bcs, total_bwpa, bcs_per_over, wickets, economy, dot_pct, strike_rate, bowling_average.",
    ),
    order: str = Query(
        "desc",
        pattern="^(asc|desc|ASC|DESC)$",
        description="Sort direction: 'desc' (default) or 'asc'.",
    ),
    page: int = Query(
        1,
        ge=1,
        description="Page number (1-based index).",
    ),
    page_size: int = Query(
        settings.DEFAULT_PAGE_SIZE,
        ge=1,
        le=settings.MAX_PAGE_SIZE,
        description="Items per page (1 to 100).",
    ),
    service: BowlingDataService = Depends(get_bowling_service),
) -> BowlingLeaderboardResponse:
    """Fetch paginated bowling leaderboard."""
    return service.get_leaderboard(
        season=season,
        phase=phase,
        tournament=tournament,
        min_balls=min_balls,
        sort_by=sort_by,
        order=order,
        page=page,
        page_size=page_size,
    )
