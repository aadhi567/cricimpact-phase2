"""Pydantic V2 schemas for Bowling Analytics API responses and models."""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, ConfigDict, Field


class APIResponseBase(BaseModel):
    """Base response model with common metadata."""
    model_config = ConfigDict(populate_by_name=True, from_attributes=True)
    status: str = Field(default="success", description="Status string: success or error")


class PaginationMetadata(BaseModel):
    """Pagination details for paginated endpoints."""
    total_items: int = Field(..., description="Total items matching query filters")
    total_pages: int = Field(..., description="Total pages based on page_size")
    current_page: int = Field(..., description="Current 1-based page number")
    page_size: int = Field(..., description="Items per page")


# --- Dashboard Schemas ---

class TopPerformerSummary(BaseModel):
    """Summary of a top career bowling performer."""
    bowler_id: int
    bowler_name: str
    team: Optional[str] = None
    matches: int
    spells: int
    overs: float
    wickets: int
    economy: float
    total_bcs: float
    total_bwpa: float


class TopSpellSummary(BaseModel):
    """Summary of a top individual match spell."""
    spell_id: str
    match_id: int
    innings: int
    bowler_id: int
    bowler_name: str
    team: str
    opponent: str
    overs: float
    wickets: int
    runs_conceded: int
    total_bcs: float
    total_bwpa: float


class PhaseBreakdownItem(BaseModel):
    """Phase-level performance breakdown."""
    phase: str = Field(..., description="powerplay, middle, or death")
    legal_balls: int
    overs: float
    runs: int
    wickets: int
    economy: float
    dot_pct: float
    boundary_pct: float
    avg_leverage: float
    total_erp: float
    total_bcs: float
    bcs_per_over: float
    total_bwpa: float


class BCSDistribution(BaseModel):
    """Statistical distribution of match spell BCS values."""
    mean: float
    median: float
    std: float
    min: float
    max: float
    p25: float
    p75: float
    positive_share_pct: float
    negative_share_pct: float


class BowlingDashboardResponse(APIResponseBase):
    """Full bowling dashboard response payload."""
    total_matches: int
    total_spells: int
    total_deliveries: int
    legal_balls: int
    total_wickets: int
    total_bowler_runs: int
    overall_economy: float
    dot_ball_pct: float
    bcs_distribution: BCSDistribution
    phase_breakdown: List[PhaseBreakdownItem]
    top_career_bcs: List[TopPerformerSummary]
    top_career_bwpa: List[TopPerformerSummary]
    top_match_spells: List[TopSpellSummary]


# --- Leaderboard Schemas ---

class BowlerLeaderboardItem(BaseModel):
    """Leaderboard entry for a bowler."""
    rank: int
    bowler_id: int
    bowler_name: str
    matches: int
    spells: int
    legal_balls: int
    overs: float
    overs_formatted: str
    bowler_runs: int
    wickets: int
    maidens: int
    dot_balls: int
    boundaries: int
    economy: float
    dot_pct: float
    boundary_pct: float
    strike_rate: Optional[float] = None
    bowling_average: Optional[float] = None
    total_erp: float
    mean_leverage: float
    mean_wqm: float
    total_bcs: float
    bcs_per_over: float
    shrunk_bcs_per_over: Optional[float] = None
    total_bcs_shrunk: Optional[float] = Field(default=None, description="Empirical Bayes shrunk career total BCS (M0=48 balls / 8 overs).")
    shrunk_bcs: Optional[float] = Field(default=None, description="Convenience alias for total_bcs_shrunk.")
    total_bwpa: float


class TournamentItem(BaseModel):
    """Authoritative competition/tournament item from competitions.csv."""
    comp_id: int = Field(..., description="Unique competition / tournament identifier")
    comp_name: str = Field(..., description="Authoritative competition name")
    display_name: str = Field(..., description="User-friendly formatted display name")
    season: str = Field(..., description="Season or year")
    match_format: str = Field(..., description="Match format (T20, T20I)")
    match_count: int = Field(0, description="Number of matches present in dataset")
    spells_count: int = Field(0, description="Number of bowling spells present in dataset")


class BowlingTournamentsResponse(APIResponseBase):
    """Authoritative list of tournaments/competitions."""
    total: int
    items: List[TournamentItem]


class BowlingLeaderboardResponse(APIResponseBase):
    """Paginated bowling leaderboard response."""
    season_filter: Optional[str] = None
    phase_filter: Optional[str] = None
    tournament_filter: Optional[str] = None
    min_balls_filter: int
    sort_by: str
    order: str
    pagination: PaginationMetadata
    items: List[BowlerLeaderboardItem]


# --- Player Profile Schemas ---

class SeasonRecord(BaseModel):
    """Season summary record for a bowler."""
    season: str
    matches: int
    spells: int
    legal_balls: int
    overs: float
    bowler_runs: int
    wickets: int
    economy: float
    dot_pct: float
    total_erp: float
    total_bcs: float
    bcs_per_over: float
    total_bwpa: float


class BowlerSpellSummary(BaseModel):
    """Spell summary entry for a bowler profile."""
    spell_id: str
    match_id: int
    match_date: str
    season: str
    venue: str
    team: str
    opponent: str
    innings: int
    legal_balls: int
    overs: float
    overs_formatted: str
    bowler_runs: int
    wickets: int
    economy: float
    dot_balls: int
    total_erp: float
    total_bcs: float
    total_bwpa: float


class BowlerProfileResponse(APIResponseBase):
    """Comprehensive bowler profile response."""
    bowler_id: int
    bowler_name: str
    career_summary: BowlerLeaderboardItem
    phase_splits: List[PhaseBreakdownItem]
    season_breakdown: List[SeasonRecord]
    top_spells: List[BowlerSpellSummary]
    recent_spells: List[BowlerSpellSummary]


# --- Comparison Schemas ---

class BowlerComparisonItem(BaseModel):
    """Bowler item in comparison payload."""
    bowler_id: int
    bowler_name: str
    career_summary: BowlerLeaderboardItem
    phase_splits: List[PhaseBreakdownItem]


class BowlerComparisonResponse(APIResponseBase):
    """Multi-bowler head-to-head comparison response."""
    bowlers_count: int
    bowlers: List[BowlerComparisonItem]


# --- Match & Spell Schemas ---

class MatchListItem(BaseModel):
    """Summary of a match for match listings."""
    match_id: int
    match_date: str
    season: str
    venue: str
    competition_category: str
    teams: List[str]
    total_spells: int
    total_wickets: int
    top_bowler: Optional[TopSpellSummary] = None


class MatchListResponse(APIResponseBase):
    """Paginated match list response."""
    season_filter: Optional[str] = None
    team_filter: Optional[str] = None
    pagination: PaginationMetadata
    items: List[MatchListItem]


class SpellDetailItem(BaseModel):
    """Detailed spell entry within a match."""
    spell_id: str
    innings: int
    bowler_id: int
    bowler_name: str
    team: str
    opponent: str
    legal_balls: int
    overs: float
    overs_formatted: str
    bowler_runs: int
    wickets: int
    maidens: int
    dot_balls: int
    boundaries: int
    economy: float
    dot_pct: float
    boundary_pct: float
    strike_rate: Optional[float] = None
    bowling_average: Optional[float] = None
    total_erp: float
    mean_wqm: float
    mean_leverage: float
    mean_dot_pressure: float
    mean_rrr_pressure: float
    total_bcs: float
    total_bwpa: float
    phase_breakdown: List[PhaseBreakdownItem]


class MatchSpellsResponse(APIResponseBase):
    """All bowling spells in a given match."""
    match_id: int
    match_date: str
    venue: str
    spells_count: int
    spells: List[SpellDetailItem]


# --- Delivery Analysis Schemas ---

class DeliveryDetailItem(BaseModel):
    """Delivery transition record within a bowling spell."""
    ball_index: int
    innings_ball_num: int
    overid: int
    over_ball_num: int
    innings_phase: str
    striker_id: int
    striker_name: str
    non_striker_id: int
    non_striker_name: str
    batter_runs: int
    bowler_runs: int
    team_runs: int
    extras_type: Optional[str] = None
    is_legal_delivery: bool
    is_dot_ball: bool
    is_boundary: bool
    is_wicket_event: bool
    is_bowler_wkt: bool
    dismissal_type: Optional[str] = None
    dismissed_player_name: Optional[str] = None
    score_before: int
    wickets_lost_before: int
    legal_balls_remaining_before: int
    score_after: int
    wickets_lost_after: int
    required_run_rate: Optional[float] = None
    current_run_rate: Optional[float] = None
    exp_bowler_runs: float
    erp: float
    WQM: float
    V_wkt: float
    leverage: float
    dot_pressure_index: float
    rrr_pressure_index: float
    bcs: float
    bwpa: float
    delta_wp_bowl: float


class SpellDeliveriesResponse(APIResponseBase):
    """All delivery transitions for a single bowling spell."""
    spell_id: str
    match_id: int
    innings: int
    bowler_id: int
    bowler_name: str
    team: str
    opponent: str
    deliveries_count: int
    deliveries: List[DeliveryDetailItem]
