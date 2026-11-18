"""PCS Bowling Analytics Dashboard API route."""

from fastapi import APIRouter, Depends
from backend.schemas.pcs import PCSDashboardResponse
from backend.services.pcs_data_service import PCSDataService
from backend.api.pcs.dependencies import get_pcs_service

router = APIRouter()


@router.get(
    "/dashboard",
    response_model=PCSDashboardResponse,
    summary="Get PCS Dashboard Overview",
    description="Returns high-level PCS statistics, bipolar distribution breakdown, highest/lowest spells, and career/season leaders.",
)
def get_pcs_dashboard(
    service: PCSDataService = Depends(get_pcs_service),
) -> PCSDashboardResponse:
    """Get dashboard summary metrics for Bowling Pressure Contribution Score."""
    return service.get_dashboard()
