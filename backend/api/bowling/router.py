"""Aggregated Bowling Analytics API router."""

from fastapi import APIRouter
from backend.api.bowling.dashboard import router as dashboard_router
from backend.api.bowling.leaderboard import router as leaderboard_router
from backend.api.bowling.players import router as players_router
from backend.api.bowling.compare import router as compare_router
from backend.api.bowling.matches import router as matches_router
from backend.api.bowling.spells import router as spells_router

bowling_router = APIRouter(prefix="/bowling", tags=["Bowling Analytics"])

# Register sub-routers
bowling_router.include_router(dashboard_router)
bowling_router.include_router(leaderboard_router)
bowling_router.include_router(players_router)
bowling_router.include_router(compare_router)
bowling_router.include_router(matches_router)
bowling_router.include_router(spells_router)
