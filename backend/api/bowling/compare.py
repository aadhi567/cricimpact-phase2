"""Bowler Head-to-Head Comparison API route."""

from typing import List, Union
from fastapi import APIRouter, Depends, HTTPException, Query
from backend.core.config import settings
from backend.schemas.bowling import BowlerComparisonResponse
from backend.services.bowling_data_service import BowlingDataService

router = APIRouter()


def get_bowling_service() -> BowlingDataService:
    """Dependency injection helper for BowlingDataService singleton."""
    return BowlingDataService.get_instance()


@router.get(
    "/compare",
    response_model=BowlerComparisonResponse,
    summary="Compare 2 to 5 Bowlers Head-to-Head",
    description=(
        "Returns side-by-side career summary and phase breakdown metrics for between 2 and 5 distinct bowlers. "
        "Accepts either comma-separated string ('?player_ids=4722,6464,6256') or multiple parameters."
    ),
)
def compare_bowlers(
    player_ids: str = Query(
        ...,
        description="Comma-separated player IDs (e.g. '4722,6464,6256'). Minimum 2, maximum 5.",
    ),
    service: BowlingDataService = Depends(get_bowling_service),
) -> BowlerComparisonResponse:
    """Compare multiple bowlers head-to-head."""
    # Parse player IDs
    try:
        parsed_ids = [int(p.strip()) for p in player_ids.split(",") if p.strip()]
    except ValueError:
        raise HTTPException(
            status_code=422,
            detail="Invalid player_ids parameter. Must be a comma-separated list of integers.",
        )

    if len(parsed_ids) < settings.MIN_COMPARISON_PLAYERS or len(parsed_ids) > settings.MAX_COMPARISON_PLAYERS:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Bowler comparison requires between {settings.MIN_COMPARISON_PLAYERS} and "
                f"{settings.MAX_COMPARISON_PLAYERS} bowlers. Received: {len(parsed_ids)}"
            ),
        )

    if len(set(parsed_ids)) != len(parsed_ids):
        raise HTTPException(
            status_code=422,
            detail="Duplicate player IDs are not allowed in bowler comparison.",
        )

    try:
        return service.compare_bowlers(parsed_ids)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
