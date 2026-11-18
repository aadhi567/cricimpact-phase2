"""Bowler Profile API route."""

from fastapi import APIRouter, Depends, HTTPException, Path
from backend.schemas.bowling import BowlerProfileResponse
from backend.services.bowling_data_service import BowlingDataService

router = APIRouter()


def get_bowling_service() -> BowlingDataService:
    """Dependency injection helper for BowlingDataService singleton."""
    return BowlingDataService.get_instance()


@router.get(
    "/players/{player_id}",
    response_model=BowlerProfileResponse,
    summary="Get Detailed Bowler Profile",
    description=(
        "Returns a comprehensive bowler profile including career aggregates, phase splits (Powerplay, "
        "Middle, Death), season-by-season breakdowns, top historical match spells, and recent spells."
    ),
)
def get_bowler_profile(
    player_id: int = Path(..., ge=1, description="Unique integer ID of the bowler."),
    service: BowlingDataService = Depends(get_bowling_service),
) -> BowlerProfileResponse:
    """Fetch complete bowler profile."""
    profile = service.get_player_profile(player_id)
    if not profile:
        raise HTTPException(
            status_code=404,
            detail=f"Bowler with player_id {player_id} not found in career database.",
        )
    return profile
