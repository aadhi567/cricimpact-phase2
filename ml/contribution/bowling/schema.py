"""Stage B4: Bowling Contribution Model authoritative schemas, types, and validation contracts."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Literal


BOWLER_CREDITED_DISMISSALS: Final[tuple[str, ...]] = (
    "Caught",
    "Bowled",
    "LBW",
    "Stumped",
    "Hit Wicket",
    "Stump",
)

NON_BOWLER_DISMISSALS: Final[tuple[str, ...]] = (
    "Run Out",
    "RunOut",
    "Obstructing the field",
    "Retire Out",
)

NON_BOWLER_EXTRAS: Final[tuple[str, ...]] = (
    "byes",
    "legbyes",
    "Penalty",
)

BOWLER_CHARGED_EXTRAS: Final[tuple[str, ...]] = (
    "wide",
    "Overstep",
    "other",
)

INNINGS_PHASES: Final[tuple[str, ...]] = (
    "powerplay",
    "middle",
    "death",
)


@dataclass(frozen=True)
class DeliveryContext:
    """Pre-delivery causal match state context for a single ball."""

    match_id: int
    innings: int
    overid: int
    innings_ball_num: int
    over_ball_num: int
    is_legal_delivery: bool
    innings_phase: str
    score_before: int
    wickets_lost_before: int
    legal_balls_completed_before: int
    legal_balls_remaining_before: int
    required_run_rate: float | None
    current_run_rate: float | None
    target_runs: int | None
    bowler_id: int
    striker_id: int


@dataclass(frozen=True)
class DeliveryOutcome:
    """Observed physical delivery event outcome."""

    batter_runs: int
    extras_type: str | None
    extras1_runs: int
    is_wicket_event: bool
    dismissal_type_canonical: str | None
    dismissed_player_id: int | None


@dataclass(frozen=True)
class DeliveryContributionResult:
    """Full delivery-level contribution assessment."""

    match_id: int
    innings: int
    innings_ball_num: int
    bowler_id: int
    striker_id: int
    is_legal: bool
    bowler_runs: int
    is_bowler_wkt: bool
    is_non_bowler_extra: bool
    exp_bowler_runs: float
    erp: float
    v_wkt: float
    wqm: float
    leverage: float
    unweighted_run_impact: float
    bcs: float
    bwpa: float
    alpha_attr: float
    # Explanatory pressure diagnostics
    dot_ball: bool
    exp_dot_prob: float
    dot_residual: float
    consecutive_dots_before: int
    consecutive_dots_after: int
    dot_pressure_index: float
    rrr_before: float | None
    bowler_econ_current: float | None
    rrr_pressure_index: float | None
    first_inns_scoring_restriction: float | None


@dataclass(frozen=True)
class SpellContributionSummary:
    """Match-bowler spell aggregated summary."""

    match_id: int
    match_date: str
    competition_category: str
    venue: str
    bowler_id: int
    bowler_name: str
    team: str
    opponent: str
    innings: int
    legal_balls: int
    overs: float
    bowler_runs: int
    wickets: int
    maidens: int
    dot_balls: int
    boundaries: int
    economy: float
    total_erp: float
    total_wkt_impact: float
    total_bcs: float
    total_bwpa: float
    mean_wqm: float
    mean_leverage: float
    dot_pct: float
    boundary_pct: float
    max_consecutive_dots: int
    mean_dot_pressure: float
    mean_rrr_pressure: float | None
    first_inns_restriction: float | None


def validate_delivery_invariants(
    bcs: float,
    erp: float,
    v_wkt: float,
    wqm: float,
    leverage: float,
    is_bowler_wkt: bool,
    is_non_bowler_extra: bool,
    batter_runs: int,
    bowler_runs: int,
) -> None:
    """Validate mathematical invariants on delivery contribution components."""
    # 1. Bounds
    if not (0.50 - 1e-4 <= leverage <= 2.00 + 1e-4):
        raise ValueError(f"Leverage out of bounds [0.50, 2.00]: {leverage}")
    if not (0.40 - 1e-4 <= wqm <= 2.50 + 1e-4):
        raise ValueError(f"WQM out of bounds [0.40, 2.50]: {wqm}")
    if v_wkt < -1e-4:
        raise ValueError(f"V_wkt must be non-negative: {v_wkt}")

    # 2. Non-bowler extras safeguard
    if is_non_bowler_extra and batter_runs == 0:
        if abs(erp) > 1e-4:
            raise ValueError(f"ERP must be 0 for pure non-bowler extras, got {erp}")

    # 3. Wicket impact non-negativity
    if is_bowler_wkt and (wqm * v_wkt < -1e-4):
        raise ValueError(f"Wicket impact must be non-negative: wqm={wqm}, v_wkt={v_wkt}")

