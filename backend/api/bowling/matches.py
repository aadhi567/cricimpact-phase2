"""Match Listing and Match Spells API routes."""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Path, Query
from backend.core.config import settings
from backend.schemas.bowling import MatchListResponse, MatchSpellsResponse
from backend.services.bowling_data_service import BowlingDataService

router = APIRouter()


def get_bowling_service() -> BowlingDataService:
    """Dependency injection helper for BowlingDataService singleton."""
    return BowlingDataService.get_instance()


@router.get(
    "/matches",
    response_model=MatchListResponse,
    summary="List Matches with Bowling Summaries",
    description=(
        "Retrieves a paginated list of matches in the bowling corpus with metadata, teams, total spells, "
        "and the standout bowler by total BCS for each match."
    ),
)
def get_matches(
    season: Optional[str] = Query(None, description="Filter matches by season (e.g. '2024')."),
    team: Optional[str] = Query(None, description="Filter matches by team name (case-insensitive)."),
    sort_by: str = Query("match_date", description="Sort by 'match_date', 'total_bcs', or 'match_id'."),
    order: str = Query("desc", pattern="^(asc|desc|ASC|DESC)$", description="Sort order: 'desc' or 'asc'."),
    page: int = Query(1, ge=1, description="Page number."),
    page_size: int = Query(settings.DEFAULT_PAGE_SIZE, ge=1, le=settings.MAX_PAGE_SIZE, description="Page size."),
    service: BowlingDataService = Depends(get_bowling_service),
) -> MatchListResponse:
    """Fetch paginated matches."""
    return service.get_matches(
        season=season,
        team=team,
        sort_by=sort_by,
        order=order,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/matches/{match_id}/spells",
    response_model=MatchSpellsResponse,
    summary="Get Match Bowling Spells",
    description=(
        "Retrieves all bowling spells from both innings of a match, including spell metrics, "
        "phase breakdowns, leverage, pressure indicators, total BCS, and total bWPA."
    ),
)
def get_match_spells(
    match_id: int = Path(..., ge=1, description="Unique integer match ID."),
    service: BowlingDataService = Depends(get_bowling_service),
) -> MatchSpellsResponse:
    """Fetch all spells for a given match."""
    spells = service.get_match_spells(match_id)
    if not spells:
        raise HTTPException(
            status_code=404,
            detail=f"Match with ID {match_id} not found in bowling corpus.",
        )
    return spells
