"""Stage 6B authoritative Win Probability schema definitions, feature catalogs, and contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final, Literal

from ml.ingestion.dataset_registry import PROJECT_ROOT

STAGE_VERSION: Final[str] = "Stage 6B.1"
DEFAULT_WP_DIR: Final[Path] = PROJECT_ROOT / "data" / "processed" / "win_probability"
DEFAULT_WP_VALIDATION_DIR: Final[Path] = PROJECT_ROOT / "data" / "validation" / "stage_6b"

# Chronological partition boundaries
TRAIN_END_DATE: Final[str] = "2024-12-31"
VAL_START_DATE: Final[str] = "2025-01-01"
VAL_END_DATE: Final[str] = "2025-12-31"
TEST_START_DATE: Final[str] = "2026-01-01"

# Target column definitions
TARGET_BATTING_WIN: Final[str] = "target_batting_team_win"
TARGET_HOME_WIN: Final[str] = "target_home_team_win"

# Forbidden leakage columns (MUST NEVER enter any model feature matrix)
FORBIDDEN_LEAKAGE_COLUMNS: Final[frozenset[str]] = frozenset(
    {
        "win_team_id",
        "win_team_id_raw",
        "target_batting_team_win",
        "target_home_team_win",
        "result",
        "winning_margin",
        "chase_completion_status",
        "terminal_innings_status_audit",
        "contribution_score",
        "raw_contribution",
        "score_after",
        "wickets_lost_after",
        "legal_balls_completed_after",
        "batter_runs",
        "extras_type",
        "extras1_runs",
        "extras_2_runs",
        "team_runs",
        "is_wicket_event",
        "is_boundary_four",
        "is_boundary_six",
        "dismissal_type_id",
        "dismissal_type_canonical",
        "dismissal_type_raw",
        "dismissed_player_id_raw",
        "resolved_dismissed_player_id",
    }
)

# -----------------------------------------------------------------------------
# Authoritative Feature Group Definitions (Total 42 Candidate Features)
# -----------------------------------------------------------------------------

# Group 1: Core Delivery & Match-State Features (14 features)
GROUP_1_MATCH_STATE_FEATURES: Final[tuple[str, ...]] = (
    "innings",
    "score_before",
    "wickets_lost_before",
    "wickets_remaining_before",
    "legal_balls_completed_before",
    "legal_balls_remaining_before",
    "current_run_rate_before",
    "innings_phase",
    "innings_progress_pct",
    "resource_percentage_remaining",
    "target_runs",
    "runs_required_before",
    "required_run_rate_before",
    "rrr_minus_crr_before",
)

# Group 2: Team Strength & Lineup Aggregations (11 features)
GROUP_2_TEAM_STRENGTH_FEATURES: Final[tuple[str, ...]] = (
    "batting_lineup_top3_abc",
    "batting_lineup_mid4_abc",
    "batting_lineup_tail_abc",
    "batting_lineup_mean_abc",
    "batting_lineup_std_abc",
    "batting_cold_start_count",
    "bowling_unit_powerplay_econ",
    "bowling_unit_middle_econ",
    "bowling_unit_death_econ",
    "bowling_unit_strike_rate",
    "relative_batting_edge",
)

# Group 3: Venue, Competition & Historical Priors (5 features)
GROUP_3_VENUE_PRIOR_FEATURES: Final[tuple[str, ...]] = (
    "competition_category",
    "venue_avg_first_inn_score",
    "venue_chase_win_pct",
    "venue_avg_death_rr",
    "venue_pace_spin_wicket_ratio",
)

# Group 4: Pre-Match Anchor & Toss Features (5 features)
GROUP_4_PRE_MATCH_ANCHOR_FEATURES: Final[tuple[str, ...]] = (
    "pre_match_prob_stage_a",
    "pre_match_prob_stage_b",
    "stage_b_prob_delta",
    "is_batting_team_toss_winner",
    "toss_decision_bat",
)

# Group 5: Trajectory & Momentum Dynamics (7 features)
GROUP_5_TRAJECTORY_DYNAMIC_FEATURES: Final[tuple[str, ...]] = (
    "runs_last_12_balls",
    "wickets_last_12_balls",
    "runs_last_24_balls",
    "partnership_runs_current",
    "partnership_balls_current",
    "expected_final_score_gap",
    "target_pressure_index",
)

# Total authoritative candidate feature catalog (Exactly 42 features)
ALL_CATALOG_FEATURES: Final[tuple[str, ...]] = (
    GROUP_1_MATCH_STATE_FEATURES
    + GROUP_2_TEAM_STRENGTH_FEATURES
    + GROUP_3_VENUE_PRIOR_FEATURES
    + GROUP_4_PRE_MATCH_ANCHOR_FEATURES
    + GROUP_5_TRAJECTORY_DYNAMIC_FEATURES
)

# -----------------------------------------------------------------------------
# Lifecycle-Specific Model Input Feature Lists
# -----------------------------------------------------------------------------

# Stage A Pre-Match Model: 7 features (Venue, Competition, Historical Team Priors)
STAGE_A_FEATURES: Final[tuple[str, ...]] = (
    "competition_category",
    "venue_avg_first_inn_score",
    "venue_chase_win_pct",
    "venue_avg_death_rr",
    "venue_pace_spin_wicket_ratio",
    "team_a_prior_win_rate",
    "team_b_prior_win_rate",
)

# Stage B Pre-Match Model: 20 features (Stage A + 11 Lineup ABC + 2 Toss Features)
STAGE_B_FEATURES: Final[tuple[str, ...]] = (
    # Group 3 Venue & Category Priors (5)
    "competition_category",
    "venue_avg_first_inn_score",
    "venue_chase_win_pct",
    "venue_avg_death_rr",
    "venue_pace_spin_wicket_ratio",
    # Stage A Anchor Output (1)
    "pre_match_prob_stage_a",
    # Group 2 Team Strength Aggregations (11)
    "batting_lineup_top3_abc",
    "batting_lineup_mid4_abc",
    "batting_lineup_tail_abc",
    "batting_lineup_mean_abc",
    "batting_lineup_std_abc",
    "batting_cold_start_count",
    "bowling_unit_powerplay_econ",
    "bowling_unit_middle_econ",
    "bowling_unit_death_econ",
    "bowling_unit_strike_rate",
    "relative_batting_edge",
    # Group 4 Toss Information (2)
    "is_batting_team_toss_winner",
    "toss_decision_bat",
    # Team Historical Win Rate Differential (1)
    "team_prior_win_rate_diff",
)

# First-Innings Defense Model: 35 features
# (Excludes 5 Innings 2 chase features: target_runs, runs_required_before,
# required_run_rate_before, rrr_minus_crr_before, target_pressure_index)
INNINGS_1_FEATURES: Final[tuple[str, ...]] = (
    # Group 1 General Match State (10)
    "innings",
    "score_before",
    "wickets_lost_before",
    "wickets_remaining_before",
    "legal_balls_completed_before",
    "legal_balls_remaining_before",
    "current_run_rate_before",
    "innings_phase",
    "innings_progress_pct",
    "resource_percentage_remaining",
    # Group 2 Lineup Strength (11)
    "batting_lineup_top3_abc",
    "batting_lineup_mid4_abc",
    "batting_lineup_tail_abc",
    "batting_lineup_mean_abc",
    "batting_lineup_std_abc",
    "batting_cold_start_count",
    "bowling_unit_powerplay_econ",
    "bowling_unit_middle_econ",
    "bowling_unit_death_econ",
    "bowling_unit_strike_rate",
    "relative_batting_edge",
    # Group 3 Venue Priors (5)
    "competition_category",
    "venue_avg_first_inn_score",
    "venue_chase_win_pct",
    "venue_avg_death_rr",
    "venue_pace_spin_wicket_ratio",
    # Group 4 Pre-Match Anchors (3)
    "pre_match_prob_stage_b",
    "stage_b_prob_delta",
    "is_batting_team_toss_winner",
    # Group 5 Trajectory Dynamics (6: 5 general + expected_final_score_gap)
    "runs_last_12_balls",
    "wickets_last_12_balls",
    "runs_last_24_balls",
    "partnership_runs_current",
    "partnership_balls_current",
    "expected_final_score_gap",
)

# Second-Innings Chase Model: 39 features
# (Excludes 1 Innings 1 specific feature: expected_final_score_gap)
# (Includes all 5 chase-specific features)
INNINGS_2_FEATURES: Final[tuple[str, ...]] = (
    # Group 1 General Match State + Chase Features (14)
    "innings",
    "score_before",
    "wickets_lost_before",
    "wickets_remaining_before",
    "legal_balls_completed_before",
    "legal_balls_remaining_before",
    "current_run_rate_before",
    "innings_phase",
    "innings_progress_pct",
    "resource_percentage_remaining",
    "target_runs",
    "runs_required_before",
    "required_run_rate_before",
    "rrr_minus_crr_before",
    # Group 2 Lineup Strength (11)
    "batting_lineup_top3_abc",
    "batting_lineup_mid4_abc",
    "batting_lineup_tail_abc",
    "batting_lineup_mean_abc",
    "batting_lineup_std_abc",
    "batting_cold_start_count",
    "bowling_unit_powerplay_econ",
    "bowling_unit_middle_econ",
    "bowling_unit_death_econ",
    "bowling_unit_strike_rate",
    "relative_batting_edge",
    # Group 3 Venue Priors (5)
    "competition_category",
    "venue_avg_first_inn_score",
    "venue_chase_win_pct",
    "venue_avg_death_rr",
    "venue_pace_spin_wicket_ratio",
    # Group 4 Pre-Match Anchors (3)
    "pre_match_prob_stage_b",
    "stage_b_prob_delta",
    "is_batting_team_toss_winner",
    # Group 5 Trajectory Dynamics + Chase Pressure (6)
    "runs_last_12_balls",
    "wickets_last_12_balls",
    "runs_last_24_balls",
    "partnership_runs_current",
    "partnership_balls_current",
    "target_pressure_index",
)

# -----------------------------------------------------------------------------
# Dataclasses & Contracts
# -----------------------------------------------------------------------------


@dataclass(frozen=True)
class PreMatchState:
    """Pre-match contextual state representing information known prior to ball 0.1."""

    match_id: int
    match_date: str
    competition_category: str
    venue_id: int
    home_team_id: int
    away_team_id: int
    stage: Literal["STAGE_A", "STAGE_B"]
    team_a_prior_win_rate: float
    team_b_prior_win_rate: float
    venue_avg_first_inn_score: float
    venue_chase_win_pct: float
    venue_avg_death_rr: float
    venue_pace_spin_wicket_ratio: float
    is_toss_known: bool = False
    toss_win_team_id: int | None = None
    toss_opted: str | None = None
    is_xi_confirmed: bool = False
    lineup_features: dict[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class DeliveryState:
    """In-play delivery state evaluating the game position immediately prior to ball b."""

    match_id: int
    innings: int
    innings_ball_num: int
    overid: int
    over_ball_num: int
    batting_team_id: int
    bowling_team_id: int
    score_before: int
    wickets_lost_before: int
    legal_balls_completed_before: int
    legal_balls_remaining_before: int
    current_run_rate_before: float
    innings_phase: str
    innings_progress_pct: float
    resource_percentage_remaining: float
    target_runs: int | None = None
    runs_required_before: int | None = None
    required_run_rate_before: float | None = None
    rrr_minus_crr_before: float | None = None
    runs_last_12_balls: int = 0
    wickets_last_12_balls: int = 0
    runs_last_24_balls: int = 0
    partnership_runs_current: int = 0
    partnership_balls_current: int = 0
    expected_final_score_gap: float | None = None
    target_pressure_index: float | None = None


@dataclass(frozen=True)
class WinProbabilityOutput:
    """Structured dual complementary win probability prediction."""

    match_id: int
    innings: int | None
    innings_ball_num: int | None
    p_batting_team: float
    p_bowling_team: float
    p_team_a: float
    p_team_b: float
    lifecycle_stage: str
    is_calibrated: bool = False
    is_low_sample_exploratory: bool = False

    def __post_init__(self) -> None:
        """Validate probability axioms."""
        if not (-1e-5 <= self.p_batting_team <= 1.0 + 1e-5):
            raise ValueError(f"p_batting_team out of bounds: {self.p_batting_team}")
        if abs(self.p_batting_team + self.p_bowling_team - 1.0) > 1e-4:
            raise ValueError(f"Batting and bowling probabilities do not sum to 1.0: {self.p_batting_team} + {self.p_bowling_team}")
        if abs(self.p_team_a + self.p_team_b - 1.0) > 1e-4:
            raise ValueError(f"Team A and Team B probabilities do not sum to 1.0: {self.p_team_a} + {self.p_team_b}")


def validate_feature_matrix_no_leakage(columns: list[str] | set[str]) -> None:
    """Verify that no forbidden leakage or target column appears in a feature matrix."""
    forbidden_found = set(columns).intersection(FORBIDDEN_LEAKAGE_COLUMNS)
    if forbidden_found:
        raise ValueError(f"CRITICAL TARGET LEAKAGE: Forbidden columns found in feature matrix: {sorted(forbidden_found)}")

