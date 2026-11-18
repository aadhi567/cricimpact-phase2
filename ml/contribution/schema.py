"""Stage 5C authoritative schema definitions and constants."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from ml.ingestion.dataset_registry import PROJECT_ROOT

STAGE_VERSION: str = "Stage 5C v2.1"
DEFAULT_CONTRIBUTIONS_DIR: Path = PROJECT_ROOT / "data" / "processed" / "contributions"
DEFAULT_STAGE5C_VALIDATION_DIR: Path = PROJECT_ROOT / "data" / "validation" / "stage_5c"

# Track tags
TRACK_A_TAG: str = "RETROSPECTIVE_EVALUATION_ONLY"
TRACK_B_TAG: str = "CAUSAL_PRE_MATCH_WP_FEATURE"

# Engine names
ENGINE_PHASE7U: str = "phase7u_baseline"
ENGINE_STRATEGY4: str = "strategy4_universal"
ENGINE_PHASE1_IPL_REF: str = "phase1_ipl_reference"

# Expectation regimes
REGIME_COLD_START: str = "COLD_START_FALLBACK"
REGIME_WALK_FORWARD_RF: str = "WALK_FORWARD_COMP_RF"
REGIME_LOW_SAMPLE_NO_ML: str = "LOW_SAMPLE_EXPLORATORY_NO_ML"
REGIME_PHASE7U_HEURISTIC: str = "PHASE7U_HEURISTIC"

# Primary Standard T20 matches count
EXPECTED_STANDARD_T20_MATCHES: int = 798
EXPECTED_BATTER_MATCH_RECORDS: int = 18106
EXPECTED_BATTED_INNINGS: int = 13033
EXPECTED_DNB_RECORDS: int = 5073
EXPECTED_IMPACT_DNB_RECORDS: int = 219

# Constants
MIN_MATCHES_FOR_EXPECTATIONS: int = 30
IPL_HISTORICAL_PAR_TOTAL: float = 166.5
FALLBACK_EXPECTED_SR: float = 125.0
FALLBACK_RUN_RATE_PAR: float = 8.325

# Bounds
SCORE_MIN: float = 0.1
SCORE_MAX: float = 99.9
SCORE_PAR: float = 50.0
LEVERAGE_MIN: float = 0.65
LEVERAGE_MAX: float = 1.35
LEVERAGE_PAR: float = 1.0


@dataclass(frozen=True)
class BatterStint:
    """Represents a continuous crease tenure of a batter."""

    match_id: int
    innings: int
    stint_id: int
    player_id: int
    team_id: int
    opponent_team_id: int
    competition_category: str
    season: str
    match_date: str
    batting_order: int
    entry_innings_ball_num: int
    exit_innings_ball_num: int
    entry_legal_balls: int
    entry_over_notation: float
    entry_over_decimal: float
    entry_team_score: int
    entry_wickets_lost: int
    entry_wickets_remaining: int
    entry_balls_remaining: int
    entry_team_rr: float
    exit_legal_balls: int
    exit_over_notation: float
    exit_over_decimal: float
    exit_team_score: int
    exit_wickets_lost: int
    exit_wickets_remaining: int
    exit_balls_remaining: int
    overs_spent: float
    team_runs_added: int
    window_team_rr: float
    wickets_lost_during_stay: int
    actual_runs: int
    balls_faced: int
    actual_sr: float
    fours: int
    sixes: int
    boundary_pct: float
    dot_balls: int
    dot_ball_pct: float
    dismissal_status: str
    dismissal_type_canonical: str | None
    is_out: bool
    is_not_out: bool
    is_retired_hurt: bool
    is_retire_out: bool
    is_dnb: bool
    is_impact: bool
    is_roster_missing_uae_split: bool
    has_unresolved_dismissal_in_match: bool
    target_runs: int | None
    runs_required_entry: int | None
    runs_required_exit: int | None
    required_rr_entry: float | None
    required_rr_exit: float | None
    required_rr_change: float | None
    rr_gap_entry: float | None
    rr_gap_exit: float | None
    rr_gap_change: float | None
    target_progress_change: float | None

