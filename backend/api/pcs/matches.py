"""PCS Match Explorer and Match Pressure Timeline API routes."""

from typing import Optional
from fastapi import APIRouter, Depends, Query, Path, HTTPException
from backend.schemas.pcs import PCSMatchListResponse, PCSMatchDetailResponse
from backend.services.pcs_data_service import PCSDataService
from backend.api.pcs.dependencies import get_pcs_service

router = APIRouter()


@router.get(
    "/matches",
    response_model=PCSMatchListResponse,
    summary="List Matches for PCS Explorer",
    description="Returns a paginated list of matches with highest spell PCS information for match explorer navigation.",
)
def get_matches_list(
    season: Optional[str] = Query(None, description="Filter matches by season"),
    page: int = Query(1, ge=1, description="Page number (1-based)"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    service: PCSDataService = Depends(get_pcs_service),
) -> PCSMatchListResponse:
    """Get paginated matches list."""
    return service.get_matches(season=season, page=page, page_size=page_size)


@router.get(
    "/matches/{match_id}",
    response_model=PCSMatchDetailResponse,
    summary="Get Match Pressure Timeline",
    description="Returns bowler spells and complete delivery-by-delivery pressure metrics and sequential state updates for a match.",
)
def get_match_detail(
    match_id: int = Path(..., description="Match ID"),
    service: PCSDataService = Depends(get_pcs_service),
) -> PCSMatchDetailResponse:
    """Get detailed match pressure breakdown and delivery timeline."""
    res = service.get_match_detail(match_id)
    if not res:
        raise HTTPException(
            status_code=404,
            detail=f"Match with ID {match_id} not found in PCS corpus",
        )
    return res
