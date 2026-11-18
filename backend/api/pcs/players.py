"""PCS Individual Bowler Profile API route."""

from fastapi import APIRouter, Depends, HTTPException, Path
from backend.schemas.pcs import PCSBowlerProfileResponse
from backend.services.pcs_data_service import PCSDataService
from backend.api.pcs.dependencies import get_pcs_service

router = APIRouter()


@router.get(
    "/players/{player_id}",
    response_model=PCSBowlerProfileResponse,
    summary="Get Bowler Pressure Contribution Profile",
    description="Returns career pressure KPIs, season history, match spell log, and tactical pressure component breakdown.",
)
def get_player_profile(
    player_id: int = Path(..., description="Canonical player ID"),
    service: PCSDataService = Depends(get_pcs_service),
) -> PCSBowlerProfileResponse:
    """Get complete pressure profile for an individual bowler."""
    profile = service.get_player_profile(player_id)
    if not profile:
        raise HTTPException(
            status_code=404,
            detail=f"Bowler with ID {player_id} not found in PCS corpus",
        )
    return profile
