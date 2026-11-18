"""Spell Delivery-Level Analysis API route."""

from fastapi import APIRouter, Depends, HTTPException, Path
from backend.schemas.bowling import SpellDeliveriesResponse
from backend.services.bowling_data_service import BowlingDataService

router = APIRouter()


def get_bowling_service() -> BowlingDataService:
    """Dependency injection helper for BowlingDataService singleton."""
    return BowlingDataService.get_instance()


@router.get(
    "/spells/{spell_id}/deliveries",
    response_model=SpellDeliveriesResponse,
    summary="Get Delivery-Level Transitions for a Bowling Spell",
    description=(
        "Retrieves delivery-by-delivery transitions for a specific match spell ({match_id}_{innings}_{bowler_id}), "
        "including exact match situation before and after, expected runs, runs prevented (ERP), batter threat, "
        "WQM, physical wicket value (V_wkt), match leverage (L_t), dot & RRR pressure indices, "
        "delivery BCS, and Win Probability swing (bWPA)."
    ),
)
def get_spell_deliveries(
    spell_id: str = Path(..., description="Unique spell ID in format '{match_id}_{innings}_{bowler_id}'."),
    service: BowlingDataService = Depends(get_bowling_service),
) -> SpellDeliveriesResponse:
    """Fetch all deliveries for a specific spell."""
    delivs = service.get_spell_deliveries(spell_id)
    if not delivs:
        raise HTTPException(
            status_code=404,
            detail=f"Bowling spell with ID '{spell_id}' not found.",
        )
    return delivs
