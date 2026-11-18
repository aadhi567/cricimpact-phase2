"""Aggregated Bowling Pressure Contribution Score (PCS) API router."""

from fastapi import APIRouter
from backend.api.pcs.health import router as health_router
from backend.api.pcs.dashboard import router as dashboard_router
from backend.api.pcs.leaderboard import router as leaderboard_router
from backend.api.pcs.players import router as players_router
from backend.api.pcs.compare import router as compare_router
from backend.api.pcs.matches import router as matches_router
from backend.api.pcs.spells import router as spells_router

pcs_router = APIRouter(prefix="/pcs", tags=["Bowling Pressure Contribution (PCS)"])

# Register sub-routers under /api/pcs
pcs_router.include_router(health_router)
pcs_router.include_router(dashboard_router)
pcs_router.include_router(leaderboard_router)
pcs_router.include_router(players_router)
pcs_router.include_router(compare_router)
pcs_router.include_router(matches_router)
pcs_router.include_router(spells_router)
