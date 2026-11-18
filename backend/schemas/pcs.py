"""Pydantic V2 schemas for Bowling Pressure Contribution Score (PCS) API endpoints."""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, ConfigDict, Field


class APIResponseBase(BaseModel):
    """Base response model with status indicator."""
    model_config = ConfigDict(populate_by_name=True, from_attributes=True)
    status: str = Field(default="success", description="Response status: success or error")


class PaginationMetadata(BaseModel):
    """Standard pagination details."""
    total_items: int = Field(..., description="Total items matching query filters")
    total_pages: int = Field(..., description="Total pages based on page_size")
    current_page: int = Field(..., description="Current 1-based page number")
    page_size: int = Field(..., description="Items per page")


# --- Health & Diagnostic Schemas ---

class PCSHealthResponse(APIResponseBase):
    """Health check and dataset availability status for PCS service."""
    service_initialized: bool
    pipeline_version: str
    total_deliveries: int
    total_spells: int
    total_career_records: int
    total_season_records: int
    datasets: Dict[str, bool]


# --- Summary & Distribution Schemas ---

class PCSTopBowlerItem(BaseModel):
    """Career summary for a pressure bowling performer."""
    bowler_id: int
    bowler_name: str
    team_name: Optional[str] = None
    matches: int
    spells: int
    legal_balls: int
    overs: float
    bowler_runs: int
    wickets: int
    economy: float
    strike_rate: Optional[float] = None
    pcs_career_raw: float
    pcs_career_shrunk: float
    shrinkage_weight: float
    total_rpe: float
    dot_balls: int
    boundaries: int


class PCSTopSpellItem(BaseModel):
    """Summary of an individual match spell pressure performance."""
    spell_id: str
    match_id: int
    innings: int
    match_date: Optional[str] = None
    season: str
    bowler_id: int
    bowler_name: str
    bowling_team: Optional[str] = None
    batting_team: Optional[str] = None
    overs: float
    legal_balls: int
    bowler_runs: int
    wickets: int
    economy: float
    dot_balls: int
    total_swi: float
    total_dci: float
    total_sup: float
    total_leakage: float
    total_rpe: float
    pcs_spell: float
    pressure_category: str = Field(..., description="positive (>=50.01), neutral (50.00), or negative (<50.00)")


class PCSDistributionBin(BaseModel):
    """Bipolar distribution histogram bucket."""
    bin_label: str
    min_pcs: float
    max_pcs: float
    count: int
    percentage: float
    category: str


class PCSDistributionSummary(BaseModel):
    """Statistical distribution of match spell PCS values."""
    mean: float
    std: float
    median: float
    min: float
    max: float
    q25: float
    q75: float
    iqr: float
    positive_spells_count: int
    neutral_spells_count: int
    negative_spells_count: int
    positive_spells_pct: float
    neutral_spells_pct: float
    negative_spells_pct: float
    bins: List[PCSDistributionBin]


class PCSDashboardResponse(APIResponseBase):
    """Dashboard summary payload for PCS analytics."""
    total_matches: int
    total_spells: int
    total_deliveries: int
    legal_balls: int
    total_wickets: int
    total_bowler_runs: int
    overall_economy: float
    average_spell_pcs: float
    highest_spell_pcs: PCSTopSpellItem
    lowest_spell_pcs: PCSTopSpellItem
    pcs_distribution: PCSDistributionSummary
    top_career_leaders: List[PCSTopBowlerItem]
    top_season_leaders: List[Dict[str, Any]]
    season_trends: List[Dict[str, Any]] = Field(default_factory=list)
    available_seasons: List[str]


# --- Leaderboard Schemas ---

class PCSLeaderboardItem(BaseModel):
    """Bowler leaderboard entry under PCS."""
    rank: int
    bowler_id: int
    bowler_name: str
    team_name: Optional[str] = None
    season: Optional[str] = None
    matches: int
    spells: int
    legal_balls: int
    overs: float
    bowler_runs: int
    wickets: int
    economy: float
    strike_rate: Optional[float] = None
    pcs_raw: float
    pcs_shrunk: float
    shrinkage_weight: float
    total_rpe: float
    dot_balls: int
    boundaries: int
    positive_spells_pct: float
    negative_spells_pct: float


class PCSTournamentItem(BaseModel):
    """Authoritative competition / tournament item for PCS."""
    comp_id: int = Field(..., description="Unique competition / tournament identifier")
    comp_name: str = Field(..., description="Authoritative competition name")
    display_name: str = Field(..., description="User-friendly formatted display name")
    season: str = Field(..., description="Season or year")
    match_format: str = Field(..., description="Match format (T20, T20I)")
    match_count: int = Field(0, description="Number of matches present in dataset")
    spells_count: int = Field(0, description="Number of bowling spells present in dataset")


class PCSTournamentsResponse(APIResponseBase):
    """Authoritative list of tournaments/competitions for PCS."""
    total: int
    items: List[PCSTournamentItem]


class PCSLeaderboardResponse(APIResponseBase):
    """Paginated leaderboard response payload."""
    items: List[PCSLeaderboardItem]
    pagination: PaginationMetadata
    available_seasons: List[str]
    current_scope: str
    active_season: Optional[str] = None
    tournament_filter: Optional[str] = None


# --- Profile Schemas ---

class PCSSeasonHistoryItem(BaseModel):
    """Season-level record for an individual bowler."""
    season: str
    matches: int
    spells: int
    legal_balls: int
    overs: float
    bowler_runs: int
    wickets: int
    economy: float
    strike_rate: Optional[float] = None
    pcs_raw: float
    pcs_shrunk: float
    shrinkage_weight: float
    total_rpe: float


class PCSSpellHistoryItem(BaseModel):
    """Match spell record for a bowler profile."""
    spell_id: str
    match_id: int
    match_date: Optional[str] = None
    season: str
    opposition: str
    venue: str
    innings: int
    overs: float
    legal_balls: int
    bowler_runs: int
    wickets: int
    economy: float
    dot_balls: int
    boundaries: int
    total_swi: float
    total_dci: float
    total_sup: float
    total_leakage: float
    total_rpe: float
    pcs_spell: float
    pressure_category: str


class PCSPressureBreakdown(BaseModel):
    """Tactical pressure contribution components."""
    avg_swi_per_spell: float
    avg_dci_per_spell: float
    avg_sup_per_spell: float
    avg_leakage_per_spell: float
    avg_pti_when_wicket: float
    strike_starvation_index: float
    stand_break_count: int
    multi_wicket_overs_count: int
    dot_ball_pct: float


class PCSBowlerProfileResponse(APIResponseBase):
    """Comprehensive bowler pressure profile."""
    bowler_id: int
    bowler_name: str
    team_name: Optional[str] = None
    career: PCSTopBowlerItem
    season_history: List[PCSSeasonHistoryItem]
    spells_history: List[PCSSpellHistoryItem]
    pressure_breakdown: PCSPressureBreakdown


# --- Comparison Schemas ---

class PCSComparisonItem(BaseModel):
    """Detailed bowler metrics for multi-player comparison."""
    bowler_id: int
    bowler_name: str
    team_name: Optional[str] = None
    matches: int
    spells: int
    legal_balls: int
    overs: float
    wickets: int
    economy: float
    pcs_career_raw: float
    pcs_career_shrunk: float
    avg_spell_pcs: float
    best_spell_pcs: float
    worst_spell_pcs: float
    positive_spells_count: int
    negative_spells_count: int
    positive_spells_pct: float
    negative_spells_pct: float
    total_rpe: float
    avg_swi: float
    avg_dci: float
    avg_sup: float
    avg_leakage: float
    seasons_data: List[Dict[str, Any]]


class PCSComparisonResponse(APIResponseBase):
    """Multi-bowler comparison response (up to 5 bowlers)."""
    bowlers: List[PCSComparisonItem]


# --- Match & Delivery Explorer Schemas ---

class PCSMatchSummaryItem(BaseModel):
    """Match summary item for match explorer listing."""
    match_id: int
    match_date: Optional[str] = None
    season: str
    home_team: str
    away_team: str
    venue: str
    total_spells: int
    best_spell_pcs: float
    best_spell_bowler: str


class PCSMatchListResponse(APIResponseBase):
    """Paginated list of matches for PCS match explorer."""
    matches: List[PCSMatchSummaryItem]
    pagination: PaginationMetadata
    available_seasons: List[str]


class PCSDeliveryDetailItem(BaseModel):
    """Delivery-level pressure contribution item."""
    innings_ball_num: int
    innings: int
    overid: int
    over_ball_num: int
    bowler_id: int
    bowler_name: str
    striker_id: int
    striker_name: str
    non_striker_id: int
    score_before: int
    wickets_lost_before: int
    legal_balls_rem: int
    current_run_rate: float
    req_run_rate: Optional[float] = None
    team_runs: int
    bowler_runs: int
    is_legal: bool
    is_wide: bool
    is_no_ball: bool
    is_dot: bool
    is_boundary: bool
    is_wicket: bool
    dismissal_type: Optional[str] = None
    is_bowler_wkt: bool
    leverage: float
    pti: float
    swi: float
    dci: float
    sup: float
    leakage: float
    rpe: float
    pcs_delivery: float
    sequential_event_note: Optional[str] = None


class PCSMatchDetailResponse(APIResponseBase):
    """Detailed match pressure breakdown."""
    match_id: int
    season: str
    match_date: Optional[str] = None
    competition: str
    venue: str
    bowler_spells: List[PCSTopSpellItem]
    delivery_timeline: List[PCSDeliveryDetailItem]


class PCSSpellDeliveriesResponse(APIResponseBase):
    """Delivery-level pressure analysis for a single spell."""
    spell_id: str
    bowler_id: int
    bowler_name: str
    match_id: int
    innings: int
    overs: float
    legal_balls: int
    wickets: int
    bowler_runs: int
    pcs_spell: float
    deliveries: List[PCSDeliveryDetailItem]
