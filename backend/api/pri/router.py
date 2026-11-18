"""Read-only REST API router for Stage PRI-2/PRI-3 Pressure Reliability Index (PRI).

Exposes independent Batting (T10) and Bowling (EXO_2) pressure reliability endpoints
directly from frozen PRI-2 production outputs with zero shrinkage and zero composite scoring.
"""

from __future__ import annotations

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status

from backend.services.pri_data_service import PRIDataService
from ml.contribution.pressure_reliability.filters import validate_min_opportunities


def get_pri_service() -> PRIDataService:
    svc = PRIDataService.get_instance()
    if not svc.is_initialized:
        svc.initialize()
    return svc


def _parse_min_opp(raw: str) -> int:
    try:
        return validate_min_opportunities(raw)
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc


def _parse_id_list(raw: str, max_count: int = 5) -> List[int]:
    tokens = [t.strip() for t in raw.split(",") if t.strip()]
    if not tokens:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide between 1 and 5 comma-separated numeric player IDs.",
        )
    if len(tokens) > max_count:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot compare more than {max_count} players at once (got {len(tokens)}).",
        )
    parsed: List[int] = []
    for tok in tokens:
        if not tok.isdigit():
            raise HTTPException(
                status_code=422,
                detail=f"Invalid player ID '{tok}'. Expected positive integer IDs.",
            )
        parsed.append(int(tok))
    return parsed


pri_router = APIRouter(prefix="/pri", tags=["Pressure Reliability Index (PRI)"])


@pri_router.get("/health", summary="PRI Service Health & Artifact Verification")
def pri_health(svc: PRIDataService = Depends(get_pri_service)):
    return svc.get_health()


@pri_router.get("/overview", summary="Corpus-Level Batting & Bowling PRI Overview")
def pri_overview(svc: PRIDataService = Depends(get_pri_service)):
    return svc.get_overview()


@pri_router.get("/filters", summary="Authoritative PRI Filter Metadata")
def pri_filters(svc: PRIDataService = Depends(get_pri_service)):
    return svc.get_filters()


# ---------------------------------------------------------------------------
# Batting PRI Leaderboards (T10, Unshrunk, Default Overall Excludes Pakistan)
# ---------------------------------------------------------------------------

@pri_router.get("/batting/career", summary="Batting Career Pressure Reliability Leaderboard")
def pri_batting_career(
    min_opportunities: str = Query(default="0", description="Minimum qualifying pressure innings (integer >= 0)"),
    team: Optional[str] = Query(default=None),
    search: Optional[str] = Query(default=None),
    sort_by: str = Query(
        default="positive_hpc_pct",
        description="positive_hpc_pct | avg_hpc_under_pressure | total_hpc_under_pressure | pressure_innings",
    ),
    order: str = Query(default="desc", pattern="^(asc|desc)$"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    svc: PRIDataService = Depends(get_pri_service),
):
    min_n = _parse_min_opp(min_opportunities)
    try:
        return svc.get_batting_career(
            min_opportunities=min_n,
            team=team,
            search=search,
            sort_by=sort_by,
            order=order,
            page=page,
            page_size=page_size,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@pri_router.get("/batting/season", summary="Batting Season Pressure Reliability Leaderboard")
def pri_batting_season(
    season: Optional[str] = Query(default=None, description="Season year (e.g. 2024, 2025) or 'all'"),
    min_opportunities: str = Query(default="0", description="Minimum qualifying pressure innings (integer >= 0)"),
    team: Optional[str] = Query(default=None),
    search: Optional[str] = Query(default=None),
    sort_by: str = Query(default="positive_hpc_pct"),
    order: str = Query(default="desc", pattern="^(asc|desc)$"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    svc: PRIDataService = Depends(get_pri_service),
):
    min_n = _parse_min_opp(min_opportunities)
    try:
        return svc.get_batting_season(
            season=season,
            min_opportunities=min_n,
            team=team,
            search=search,
            sort_by=sort_by,
            order=order,
            page=page,
            page_size=page_size,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@pri_router.get("/batting/tournament", summary="Batting Tournament Pressure Reliability Leaderboard")
def pri_batting_tournament(
    tournament: Optional[str] = Query(default=None, description="Exact comp_id or comp_name"),
    min_opportunities: str = Query(default="0", description="Minimum qualifying pressure innings (integer >= 0)"),
    team: Optional[str] = Query(default=None),
    search: Optional[str] = Query(default=None),
    sort_by: str = Query(default="positive_hpc_pct"),
    order: str = Query(default="desc", pattern="^(asc|desc)$"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    svc: PRIDataService = Depends(get_pri_service),
):
    min_n = _parse_min_opp(min_opportunities)
    try:
        return svc.get_batting_tournament(
            tournament=tournament,
            min_opportunities=min_n,
            team=team,
            search=search,
            sort_by=sort_by,
            order=order,
            page=page,
            page_size=page_size,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


# ---------------------------------------------------------------------------
# Bowling PRI Leaderboards (EXO_2, Unshrunk, Default Overall Excludes Pakistan)
# ---------------------------------------------------------------------------

@pri_router.get("/bowling/career", summary="Bowling Career Pressure Reliability Leaderboard")
def pri_bowling_career(
    min_opportunities: str = Query(default="0", description="Minimum qualifying pressure spells (integer >= 0)"),
    team: Optional[str] = Query(default=None),
    search: Optional[str] = Query(default=None),
    sort_by: str = Query(
        default="positive_pcs_pct",
        description="positive_pcs_pct | avg_pcs_under_pressure | total_pressure_contribution_rpe | pressure_spells",
    ),
    order: str = Query(default="desc", pattern="^(asc|desc)$"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    svc: PRIDataService = Depends(get_pri_service),
):
    min_n = _parse_min_opp(min_opportunities)
    try:
        return svc.get_bowling_career(
            min_opportunities=min_n,
            team=team,
            search=search,
            sort_by=sort_by,
            order=order,
            page=page,
            page_size=page_size,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@pri_router.get("/bowling/season", summary="Bowling Season Pressure Reliability Leaderboard")
def pri_bowling_season(
    season: Optional[str] = Query(default=None, description="Season year (e.g. 2024, 2025) or 'all'"),
    min_opportunities: str = Query(default="0", description="Minimum qualifying pressure spells (integer >= 0)"),
    team: Optional[str] = Query(default=None),
    search: Optional[str] = Query(default=None),
    sort_by: str = Query(default="positive_pcs_pct"),
    order: str = Query(default="desc", pattern="^(asc|desc)$"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    svc: PRIDataService = Depends(get_pri_service),
):
    min_n = _parse_min_opp(min_opportunities)
    try:
        return svc.get_bowling_season(
            season=season,
            min_opportunities=min_n,
            team=team,
            search=search,
            sort_by=sort_by,
            order=order,
            page=page,
            page_size=page_size,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@pri_router.get("/bowling/tournament", summary="Bowling Tournament Pressure Reliability Leaderboard")
def pri_bowling_tournament(
    tournament: Optional[str] = Query(default=None, description="Exact comp_id or comp_name"),
    min_opportunities: str = Query(default="0", description="Minimum qualifying pressure spells (integer >= 0)"),
    team: Optional[str] = Query(default=None),
    search: Optional[str] = Query(default=None),
    sort_by: str = Query(default="positive_pcs_pct"),
    order: str = Query(default="desc", pattern="^(asc|desc)$"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    svc: PRIDataService = Depends(get_pri_service),
):
    min_n = _parse_min_opp(min_opportunities)
    try:
        return svc.get_bowling_tournament(
            tournament=tournament,
            min_opportunities=min_n,
            team=team,
            search=search,
            sort_by=sort_by,
            order=order,
            page=page,
            page_size=page_size,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


# ---------------------------------------------------------------------------
# Individual Player PRI Profiles (ALL Players Preserved, Including Pakistan)
# ---------------------------------------------------------------------------

@pri_router.get("/batting/players/{player_id}", summary="Individual Batter PRI Profile")
def pri_batting_player_profile(
    player_id: int,
    svc: PRIDataService = Depends(get_pri_service),
):
    profile = svc.get_batting_player_profile(player_id)
    if profile is None:
        raise HTTPException(status_code=404, detail=f"Batter PRI profile not found for player_id={player_id}.")
    return profile


@pri_router.get("/bowling/players/{player_id}", summary="Individual Bowler PRI Profile")
def pri_bowling_player_profile(
    player_id: int,
    svc: PRIDataService = Depends(get_pri_service),
):
    profile = svc.get_bowling_player_profile(player_id)
    if profile is None:
        raise HTTPException(status_code=404, detail=f"Bowler PRI profile not found for player_id={player_id}.")
    return profile


# ---------------------------------------------------------------------------
# Up-to-5 Player Comparison (Strictly Domain-Separated)
# ---------------------------------------------------------------------------

@pri_router.get("/batting/compare", summary="Compare Up to 5 Batters Under Pressure")
def pri_batting_compare(
    player_ids: str = Query(..., description="Comma-separated list of 1 to 5 batter player_ids"),
    svc: PRIDataService = Depends(get_pri_service),
):
    ids = _parse_id_list(player_ids, max_count=5)
    result = svc.compare_batters(ids)
    if result["count"] == 0:
        raise HTTPException(status_code=404, detail="None of the requested batter IDs were found.")
    return result


@pri_router.get("/bowling/compare", summary="Compare Up to 5 Bowlers Under Pressure")
def pri_bowling_compare(
    player_ids: str = Query(..., description="Comma-separated list of 1 to 5 bowler player_ids"),
    svc: PRIDataService = Depends(get_pri_service),
):
    ids = _parse_id_list(player_ids, max_count=5)
    result = svc.compare_bowlers(ids)
    if result["count"] == 0:
        raise HTTPException(status_code=404, detail="None of the requested bowler IDs were found.")
    return result
