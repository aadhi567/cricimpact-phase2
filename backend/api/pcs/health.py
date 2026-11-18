"""PCS Health check API route."""

from fastapi import APIRouter, Depends
from backend.schemas.pcs import PCSHealthResponse
from backend.services.pcs_data_service import PCSDataService
from backend.api.pcs.dependencies import get_pcs_service

router = APIRouter()


@router.get(
    "/health",
    response_model=PCSHealthResponse,
    summary="Get PCS Service Health Status",
    description="Returns initialization status, dataset record counts, and file availability for PCS outputs.",
)
def get_pcs_health(
    service: PCSDataService = Depends(get_pcs_service),
) -> PCSHealthResponse:
    """Get PCS service health and verification metadata."""
    return service.get_health()
