"""PCS Spell Delivery-Level Breakdown API route."""

from fastapi import APIRouter, Depends, Path, HTTPException
from backend.schemas.pcs import PCSSpellDeliveriesResponse
from backend.services.pcs_data_service import PCSDataService
from backend.api.pcs.dependencies import get_pcs_service

router = APIRouter()


@router.get(
    "/spells/{spell_id}/deliveries",
    response_model=PCSSpellDeliveriesResponse,
    summary="Get Spell Delivery-Level Breakdown",
    description="Returns ball-by-ball pressure metrics, RPE, SWI, DCI, Sup, Leakage, and sequential notes for a bowler spell.",
)
def get_spell_deliveries(
    spell_id: str = Path(..., description="Canonical spell ID format: {match_id}_{innings}_{bowler_id}"),
    service: PCSDataService = Depends(get_pcs_service),
) -> PCSSpellDeliveriesResponse:
    """Get delivery-level analysis for an individual bowler spell."""
    res = service.get_spell_deliveries(spell_id)
    if not res:
        raise HTTPException(
            status_code=404,
            detail=f"Spell with ID {spell_id} not found in PCS corpus",
        )
    return res
