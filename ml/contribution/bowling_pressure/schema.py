"""Stage B7.5 Bowling Pressure Contribution Score (PCS) Schema & Contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final, Literal

from ml.ingestion.dataset_registry import PROJECT_ROOT

STAGE_VERSION: Final[str] = "Stage B7.5.1"
DEFAULT_PCS_OUTPUT_DIR: Final[Path] = PROJECT_ROOT / "data" / "processed" / "contributions" / "bowling_pressure"

# Approved Chronological Partition Boundaries
TRAIN_END_DATE: Final[str] = "2024-12-31"
VAL_START_DATE: Final[str] = "2025-01-01"
VAL_END_DATE: Final[str] = "2025-12-31"
TEST_START_DATE: Final[str] = "2026-01-01"

# Bipolar PCS Scale Boundaries
PCS_SCALE_MIN: Final[float] = 0.0
PCS_SCALE_MAX: Final[float] = 100.0
PCS_SCALE_NEUTRAL: Final[float] = 50.0

# Calibrated Normalization Parameters
K_SIGMOID_SLOPE: Final[float] = 0.85
SIGMA_REF_1ST: Final[float] = 17.50
SIGMA_REF_2ND: Final[float] = 18.80
MU_REF_RPE: Final[float] = 0.00

# Authoritative Shrinkage Parameters
M0_SHRINKAGE_BALLS: Final[float] = 48.0  # 48 legal balls = 8 overs = 2 spells
POPULATION_NEUTRAL_PCS: Final[float] = 50.00

# Acceleration Windows
PRIMARY_ACCELERATION_WINDOW: Final[int] = 12
SENSITIVITY_ACCELERATION_WINDOW: Final[int] = 18

# Non-linear Resource Elasticity
ALPHA_RES: Final[float] = 0.55

# Dismissal Categorization
BOWLER_CREDITED_DISMISSALS: Final[frozenset[str]] = frozenset(
    {
        "bowled",
        "caught",
        "caught and bowled",
        "lbw",
        "stumped",
        "hit wicket",
    }
)

NON_BOWLER_DISMISSALS: Final[frozenset[str]] = frozenset(
    {
        "run out",
        "retired out",
        "retired hurt",
        "obstructing the field",
        "hit the ball twice",
        "timed out",
    }
)

NON_BOWLER_EXTRAS: Final[frozenset[str]] = frozenset({"byes", "legbyes"})

# Forbidden Post-Delivery Leakage Columns
FORBIDDEN_LEAKAGE_COLUMNS: Final[frozenset[str]] = frozenset(
    {
        "score_after",
        "wickets_lost_after",
        "legal_balls_completed_after",
        "batter_runs",
        "team_runs",
        "is_wicket_event",
        "dismissal_type_id",
        "dismissal_type_canonical",
        "dismissed_player_id_raw",
        "resolved_dismissed_player_id",
        "win_team_id",
        "win_team_id_raw",
    }
)


@dataclass(frozen=True)
class DeliveryPressureState:
    """Pre-delivery causal match state evaluated strictly prior to ball t."""

    match_id: int
    innings: int
    innings_ball_num: int
    overid: int
    over_ball_num: int
    bowler_id: int
    striker_id: int
    non_striker_id: int
    score_before: int
    wickets_lost_before: int
    legal_balls_completed_before: int
    legal_balls_remaining_before: int
    current_run_rate_before: float
    innings_phase: str
    target_runs: int | None = None
    runs_required_before: int | None = None
    required_run_rate_before: float | None = None
    leverage: float = 1.00
    venue_avg_first_inn_score: float = 165.0


@dataclass(frozen=True)
class PartnershipThreatState:
    """Evaluates dynamic danger and momentum of the active partnership."""

    partnership_runs: int
    partnership_balls: int
    partnership_run_rate: float
    acc_12_rpo: float
    acc_18_rpo: float
    phi_acc: float
    striker_runs: int
    striker_balls: int
    striker_share: float
    striker_threat: float
    non_striker_threat: float
    composite_threat: float
    pti: float


@dataclass(frozen=True)
class DeliveryPressureResult:
    """Complete delivery-level PCS evaluation."""

    match_id: int
    innings: int
    innings_ball_num: int
    bowler_id: int
    is_legal: bool
    is_bowler_wicket: bool
    is_non_bowler_wicket: bool
    is_dot_ball: bool
    runs_conceded: int
    leverage: float
    swi: float
    pti_neutralized: float
    dci: float
    sup: float
    leakage: float
    rpe: float
    alpha_attr: float


@dataclass(frozen=True)
class SpellPressureResult:
    """Aggregated match-spell pressure summary."""

    match_id: int
    innings: int
    bowler_id: int
    bowler_name: str
    legal_balls: int
    overs_notation: str
    runs_conceded: int
    wickets: int
    dot_balls: int
    boundaries_conceded: int
    mean_leverage: float
    total_swi: float
    total_dci: float
    total_sup: float
    total_leakage: float
    total_rpe: float
    pcs_raw: float
    pcs_calibrated: float


def validate_causal_timing(columns: list[str] | set[str]) -> None:
    """Verify that no forbidden future leakage column appears in a predictive feature set."""
    forbidden = set(columns).intersection(FORBIDDEN_LEAKAGE_COLUMNS)
    if forbidden:
        raise ValueError(f"CRITICAL CAUSAL LEAKAGE: Forbidden columns found in feature matrix: {sorted(forbidden)}")
