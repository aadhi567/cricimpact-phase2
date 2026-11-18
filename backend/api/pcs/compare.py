"""PCS Multi-Bowler Comparison API route."""

from typing import List
from fastapi import APIRouter, Depends, Query, HTTPException
from backend.schemas.pcs import PCSComparisonResponse
from backend.services.pcs_data_service import PCSDataService
from backend.api.pcs.dependencies import get_pcs_service

router = APIRouter()


@router.get(
    "/compare",
    response_model=PCSComparisonResponse,
    summary="Compare Bowlers on Pressure Dimensions",
    description="Returns side-by-side career, spell, and season pressure metrics for up to 5 bowlers.",
)
def compare_bowlers(
    bowlers: str = Query(..., description="Comma-separated player IDs (e.g. 28756,34485,781)"),
    service: PCSDataService = Depends(get_pcs_service),
) -> PCSComparisonResponse:
    """Compare multiple bowlers on PCS metrics."""
    try:
        player_ids = [int(p.strip()) for p in bowlers.split(",") if p.strip()]
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Invalid player IDs format; must be comma-separated integers",
        )

    if not player_ids:
        raise HTTPException(
            status_code=400,
            detail="At least one player ID must be provided",
        )

    return service.compare_bowlers(player_ids)
