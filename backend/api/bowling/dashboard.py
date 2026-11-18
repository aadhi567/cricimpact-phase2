"""Bowling Analytics Dashboard API route."""

from fastapi import APIRouter, Depends
from backend.schemas.bowling import BowlingDashboardResponse
from backend.services.bowling_data_service import BowlingDataService

router = APIRouter()


def get_bowling_service() -> BowlingDataService:
    """Dependency injection helper for BowlingDataService singleton."""
    return BowlingDataService.get_instance()


@router.get(
    "/dashboard",
    response_model=BowlingDashboardResponse,
    summary="Get Bowling Analytics Dashboard Overview",
    description=(
        "Returns high-level summary KPIs for the bowling corpus (798 matches, 190,575 deliveries), "
        "including total wickets, balls bowled, economy rate, dot ball percentage, BCS distribution, "
        "corpus phase-level breakdowns, and previews of top career and match performers."
    ),
)
def get_bowling_dashboard(
    service: BowlingDataService = Depends(get_bowling_service),
) -> BowlingDashboardResponse:
    """Get dashboard summary metrics."""
    return service.get_dashboard()
