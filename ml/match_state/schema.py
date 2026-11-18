"""Stage 5B authoritative schema contract matching Stage 5A Revision 1.1."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import pandas as pd

from ml.ingestion.dataset_registry import PROJECT_ROOT

SPECIFICATION_VERSION: str = "Stage 5A Revision 1.1"
DATASET_VERSION: str = "v1"
DEFAULT_PROCESSED_MATCH_STATES_DIR: Path = (
    PROJECT_ROOT / "data" / "processed" / "match_states"
)
DEFAULT_STAGE5B_VALIDATION_DIR: Path = PROJECT_ROOT / "data" / "validation" / "stage_5b"

UNRESOLVED_50407_AUDIT_STATUS: str = (
    "UNRESOLVED — source evidence insufficient to determine match status or missing delivery reason."
)
UNRESOLVED_50407_EXCLUSION_REASON: str = "unresolved_match_sequence_50407"
UNRESOLVED_50407_MATCH_ID: int = 50407

RoleType = Literal[
    "identifier",
    "model_feature",
    "regime_or_audit_metadata",
    "target",
]
DtypeStr = Literal["Int64", "Float64", "boolean", "string", "datetime64[ns]"]

TRANSITION_KEY_COLUMNS: tuple[str, str, str] = (
    "match_id",
    "innings",
    "innings_ball_num",
)

REGIME_CLASSES: tuple[str, ...] = (
    "STANDARD_T20",
    "REVISED_OVERS_DLS",
    "SUPER_OVER",
    "ABANDONED",
    "NO_RESULT",
    "TIED",
    "INCOMPLETE_OR_UNRESOLVED",
)

COMPETITION_CATEGORIES: tuple[str, ...] = ("IPL", "OTHER_T20", "T20I")


@dataclass(frozen=True)
class ColumnSpec:
    """Formal schema definition for one column in the Stage 5B match-state dataset."""

    name: str
    section: str
    dtype: DtypeStr
    role: RoleType
    nullable: bool
    applicable_innings: str
    description: str


COLUMN_SPECS: tuple[ColumnSpec, ...] = (
    # Section 2: Identifiers & Match / Competition Context (28 fields)
    ColumnSpec("match_id", "identifiers_context", "Int64", "identifier", False, "All", "Unique fixture identifier."),
    ColumnSpec("comp_id", "identifiers_context", "Int64", "identifier", False, "All", "Verbatim competition ID from competitions.csv."),
    ColumnSpec("comp_name", "identifiers_context", "string", "identifier", False, "All", "Verbatim competition name from competitions.csv."),
    ColumnSpec("match_format", "identifiers_context", "string", "model_feature", False, "All", "Verbatim match format ('T20' or 'T20I')."),
    ColumnSpec("competition_category", "identifiers_context", "string", "model_feature", False, "All", "Additive verified category ('IPL', 'OTHER_T20', 'T20I') from competition metadata only."),
    ColumnSpec("season", "identifiers_context", "string", "identifier", False, "All", "Verbatim season label from competitions.csv."),
    ColumnSpec("match_date", "identifiers_context", "datetime64[ns]", "identifier", False, "All", "Scheduled match calendar date (YYYY-MM-DD); authoritative chronological ordering key."),
    ColumnSpec("match_number", "identifiers_context", "Int64", "identifier", False, "All", "Fixture sequence number within competition."),
    ColumnSpec("stage", "identifiers_context", "string", "model_feature", False, "All", "Tournament stage label."),
    ColumnSpec("knock_out", "identifiers_context", "boolean", "model_feature", False, "All", "Knockout fixture flag (matches.knock_out == 1)."),
    ColumnSpec("venue_id", "identifiers_context", "Int64", "identifier", False, "All", "Numeric venue/ground identifier."),
    ColumnSpec("venue_country", "identifiers_context", "string", "model_feature", False, "All", "Host country of venue_id."),
    ColumnSpec("home_team_id", "identifiers_context", "Int64", "identifier", False, "All", "Match-sheet Team A identifier."),
    ColumnSpec("away_team_id", "identifiers_context", "Int64", "identifier", False, "All", "Match-sheet Team B identifier."),
    ColumnSpec("toss_win_team_id", "identifiers_context", "Int64", "identifier", True, "All", "Pre-match toss winner team ID."),
    ColumnSpec("toss_opted", "identifiers_context", "string", "model_feature", True, "All", "Pre-match toss decision ('Batting' or 'Fielding')."),
    ColumnSpec("is_batting_team_toss_winner", "identifiers_context", "boolean", "model_feature", True, "All", "True iff current batting_team_id == toss_win_team_id."),
    ColumnSpec("innings", "identifiers_context", "Int64", "model_feature", False, "All", "Innings number (1..4; primary training uses {1, 2})."),
    ColumnSpec("batting_team_id", "identifiers_context", "Int64", "identifier", False, "All", "Currently batting team ID."),
    ColumnSpec("bowling_team_id", "identifiers_context", "Int64", "identifier", False, "All", "Currently bowling/fielding team ID."),
    ColumnSpec("overid", "identifiers_context", "Int64", "identifier", False, "All", "1-indexed raw over number within innings."),
    ColumnSpec("over_ball_num", "identifiers_context", "Int64", "identifier", False, "All", "1-indexed raw delivery number within over."),
    ColumnSpec("innings_ball_num", "identifiers_context", "Int64", "identifier", False, "All", "Contiguous 1-indexed raw delivery sequence within innings."),
    ColumnSpec("delivery_ist_time", "identifiers_context", "string", "regime_or_audit_metadata", False, "All", "Raw UTC-formatted timestamp string (audit only; never sort key)."),
    ColumnSpec("striker_id", "identifiers_context", "Int64", "identifier", False, "All", "Facing batter player ID."),
    ColumnSpec("non_striker_id", "identifiers_context", "Int64", "identifier", False, "All", "Non-striker batter player ID."),
    ColumnSpec("bowler_id", "identifiers_context", "Int64", "identifier", False, "All", "Bowler player ID."),
    ColumnSpec("batting_order", "identifiers_context", "Int64", "model_feature", False, "All", "Striker batting entry position (1..13)."),
    # Section 3: Pre-Delivery State Features (6 fields)
    ColumnSpec("score_before", "pre_delivery_state", "Int64", "regime_or_audit_metadata", False, "All", "Cumulative batting team runs immediately before delivery b."),
    ColumnSpec("wickets_lost_before", "pre_delivery_state", "Int64", "regime_or_audit_metadata", False, "All", "Cumulative official wickets immediately before delivery b."),
    ColumnSpec("legal_balls_completed_before", "pre_delivery_state", "Int64", "regime_or_audit_metadata", False, "All", "Cumulative legal deliveries immediately before delivery b."),
    ColumnSpec("legal_balls_remaining_before", "pre_delivery_state", "Int64", "regime_or_audit_metadata", True, "All", "Un-clamped legal deliveries remaining before delivery b when verified; else pd.NA."),
    ColumnSpec("runs_required_before", "pre_delivery_state", "Int64", "regime_or_audit_metadata", True, "2", "Runs needed before delivery b in Innings 2 when target known; else pd.NA."),
    ColumnSpec("retired_hurt_count_before", "pre_delivery_state", "Int64", "regime_or_audit_metadata", False, "All", "Cumulative Retired Hurt exits before delivery b."),
    # Section 4: Delivery Event Features (22 fields)
    ColumnSpec("batter_runs", "delivery_event", "Int64", "model_feature", False, "All", "Raw runs off the bat (ball_by_ball.runs)."),
    ColumnSpec("extras_type", "delivery_event", "string", "model_feature", False, "All", "Case-sensitive extras category ('None' preserved verbatim)."),
    ColumnSpec("extras1_runs", "delivery_event", "Int64", "model_feature", False, "All", "Primary numerical extra runs (0..5)."),
    ColumnSpec("extras_2_runs", "delivery_event", "Int64", "model_feature", False, "All", "Secondary extra runs (byes/leg-byes on no-balls or 17555)."),
    ColumnSpec("team_runs", "delivery_event", "Int64", "model_feature", False, "All", "Total team runs added on delivery: runs + extras1_runs + extras_2_runs."),
    ColumnSpec("is_legal_delivery", "delivery_event", "boolean", "model_feature", False, "All", "True iff extras_type not in {'wide', 'Overstep', 'other'}."),
    ColumnSpec("is_wide", "delivery_event", "boolean", "model_feature", False, "All", "True iff extras_type == 'wide'."),
    ColumnSpec("is_no_ball", "delivery_event", "boolean", "model_feature", False, "All", "True iff extras_type in {'Overstep', 'other'}."),
    ColumnSpec("is_boundary_four", "delivery_event", "boolean", "model_feature", False, "All", "Raw ball_by_ball.is_four flag (audit/event indicator only)."),
    ColumnSpec("is_boundary_six", "delivery_event", "boolean", "model_feature", False, "All", "Raw ball_by_ball.is_six flag (audit/event indicator only)."),
    ColumnSpec("is_wicket_event", "delivery_event", "boolean", "model_feature", False, "All", "Raw official wicket indicator (ball_by_ball.is_wicket)."),
    ColumnSpec("is_retired_hurt_event", "delivery_event", "boolean", "model_feature", False, "All", "True iff (~is_wicket) & dismissed_player_id.notna() (adds +0 team wickets)."),
    ColumnSpec("is_retire_out_event", "delivery_event", "boolean", "model_feature", False, "All", "True iff is_wicket & (dismissal_type == 'Retire Out') (adds +1 team wicket)."),
    ColumnSpec("dismissal_type_id", "delivery_event", "Int64", "model_feature", True, "All", "Numeric dismissal type ID (pd.NA when is_wicket == False)."),
    ColumnSpec("dismissal_type_canonical", "delivery_event", "string", "model_feature", True, "All", "Normalized dismissal mode ('Obstracting' -> 'Obstructing')."),
    ColumnSpec("dismissal_type_raw", "delivery_event", "string", "regime_or_audit_metadata", True, "All", "Verbatim raw dismissal_type string."),
    ColumnSpec("dismissed_player_id_raw", "delivery_event", "Int64", "identifier", True, "All", "Verbatim raw dismissed_player_id (pd.NA on 40709 2.19.5)."),
    ColumnSpec("resolved_dismissed_player_id", "delivery_event", "Int64", "identifier", True, "All", "Verified exiting player ID (never fabricated; pd.NA when raw ID missing)."),
    ColumnSpec("is_dismissed_player_unresolved", "delivery_event", "boolean", "regime_or_audit_metadata", False, "All", "True iff is_wicket_event & dismissed_player_id_raw.isna()."),
    ColumnSpec("is_extras_2_subtype_unresolved", "delivery_event", "boolean", "regime_or_audit_metadata", False, "All", "True iff extras_2_runs > 0 (bye vs leg-bye breakdown unavailable)."),
    ColumnSpec("scoring_uncertainty_flag", "delivery_event", "boolean", "regime_or_audit_metadata", False, "All", "True when delivery has extras/boundary/law breakdown ambiguity."),
    ColumnSpec("is_super_over_delivery", "delivery_event", "boolean", "regime_or_audit_metadata", False, "All", "True iff innings >= 3."),
    # Section 5: Post-Delivery State & Chase Features (27 fields)
    ColumnSpec("score_after", "post_delivery_state", "Int64", "model_feature", False, "All", "Cumulative batting team runs after delivery b."),
    ColumnSpec("wickets_lost_after", "post_delivery_state", "Int64", "model_feature", False, "All", "Cumulative official wickets fallen after delivery b."),
    ColumnSpec("wickets_remaining", "post_delivery_state", "Int64", "model_feature", False, "All", "Remaining team wickets: max(10 - wickets_lost_after, 0)."),
    ColumnSpec("legal_balls_completed_after", "post_delivery_state", "Int64", "model_feature", False, "All", "Cumulative legal balls completed after delivery b."),
    ColumnSpec("innings_ball_limit", "post_delivery_state", "Int64", "model_feature", True, "All", "Verified legal-ball limit (120/6/revised legal balls); pd.NA when unverified."),
    ColumnSpec("is_innings_limit_verified", "post_delivery_state", "boolean", "model_feature", False, "All", "True iff innings_ball_limit is verified from format/revised metadata."),
    ColumnSpec("innings_limit_source", "post_delivery_state", "string", "regime_or_audit_metadata", False, "All", "Provenance of innings_ball_limit."),
    ColumnSpec("innings_limit_unavailable_reason", "post_delivery_state", "string", "regime_or_audit_metadata", True, "All", "Structured audit reason iff is_innings_limit_verified == False."),
    ColumnSpec("legal_balls_remaining", "post_delivery_state", "Int64", "model_feature", True, "All", "Un-clamped innings_ball_limit - legal_balls_completed_after iff verified; else pd.NA."),
    ColumnSpec("is_legal_balls_remaining_negative", "post_delivery_state", "boolean", "regime_or_audit_metadata", False, "All", "True iff is_innings_limit_verified & (legal_balls_remaining < 0)."),
    ColumnSpec("overs_completed_decimal", "post_delivery_state", "Float64", "model_feature", False, "All", "Continuous decimal overs completed: legal_balls_completed_after / 6.0."),
    ColumnSpec("overs_completed_notation", "post_delivery_state", "Float64", "regime_or_audit_metadata", False, "All", "Cricket scoreboard over.ball display notation (forbidden in math)."),
    ColumnSpec("has_legal_balls_completed", "post_delivery_state", "boolean", "model_feature", False, "All", "True iff legal_balls_completed_after > 0."),
    ColumnSpec("current_run_rate", "post_delivery_state", "Float64", "model_feature", False, "All", "Cumulative run rate after delivery b (0.0 when L_b == 0)."),
    ColumnSpec("innings_phase", "post_delivery_state", "string", "model_feature", False, "All", "T20 tactical phase ('powerplay'/'middle'/'death'/'super_over'/'revised_or_unverified')."),
    ColumnSpec("innings_progress_pct", "post_delivery_state", "Float64", "model_feature", True, "All", "L_b / innings_ball_limit iff verified; else pd.NA."),
    ColumnSpec("retired_hurt_count_after", "post_delivery_state", "Int64", "model_feature", False, "All", "Cumulative Retired Hurt exits after delivery b."),
    ColumnSpec("innings_completion_status_at_ball", "post_delivery_state", "string", "model_feature", False, "All", "Causal in-play innings status at delivery b."),
    ColumnSpec("innings1_total_score", "post_delivery_state", "Int64", "model_feature", True, "2", "Completed 1st innings total attached to Innings 2; pd.NA in Inn 1 / 3..4."),
    ColumnSpec("target_runs", "post_delivery_state", "Int64", "model_feature", True, "2", "Innings 2 chase target (inn1+1 or revised_target); pd.NA in Inn 1 / missing DLS."),
    ColumnSpec("is_target_known", "post_delivery_state", "boolean", "model_feature", False, "All", "True iff (innings == 2) & target_runs.notna()."),
    ColumnSpec("target_source", "post_delivery_state", "string", "regime_or_audit_metadata", False, "All", "Provenance of target_runs assignment."),
    ColumnSpec("runs_required_after", "post_delivery_state", "Int64", "model_feature", True, "2", "max(target_runs - score_after, 0) in Innings 2 when target known; else pd.NA."),
    ColumnSpec("required_run_rate", "post_delivery_state", "Float64", "model_feature", True, "2", "Causal required run rate in Innings 2; 0.0 when runs_required==0; pd.NA if undefined/unverified."),
    ColumnSpec("is_rrr_undefined", "post_delivery_state", "boolean", "model_feature", False, "All", "True iff required_run_rate is pd.NA."),
    ColumnSpec("rrr_minus_crr", "post_delivery_state", "Float64", "model_feature", True, "2", "required_run_rate - current_run_rate when both defined & L_b > 0; else pd.NA."),
    ColumnSpec("chase_completion_status", "post_delivery_state", "string", "model_feature", False, "All", "Causal Innings 2 chase resolution status after delivery b."),
    # Section 6: Regime, Governance & Audit Metadata (13 fields — non-predictive only)
    ColumnSpec("match_regime", "regime_audit_metadata", "string", "regime_or_audit_metadata", False, "All", "Mutually exclusive 7-class match regime enum."),
    ColumnSpec("has_dls_or_revised_meta", "regime_audit_metadata", "boolean", "regime_or_audit_metadata", False, "All", "Explicit DLS text or revised-overs/target metadata flag."),
    ColumnSpec("has_unrecorded_over_reduction", "regime_audit_metadata", "boolean", "regime_or_audit_metadata", False, "All", "Unflagged shortened parity match or curtailed rain tie without DLS columns."),
    ColumnSpec("is_tied_after_regulation", "regime_audit_metadata", "boolean", "regime_or_audit_metadata", False, "All", "Regulation 2nd innings finished tied (SUPER_OVER or TIED)."),
    ColumnSpec("has_super_over_innings", "regime_audit_metadata", "boolean", "regime_or_audit_metadata", False, "All", "True iff match has innings >= 3 in ball_by_ball."),
    ColumnSpec("has_missing_super_over_feed", "regime_audit_metadata", "boolean", "regime_or_audit_metadata", False, "All", "True iff SUPER_OVER match omits innings >= 3 deliveries."),
    ColumnSpec("has_sequence_anomaly", "regime_audit_metadata", "boolean", "regime_or_audit_metadata", False, "All", "Abnormal mid-over legal ball count or unresolved match termination."),
    ColumnSpec("has_extras_anomaly", "regime_audit_metadata", "boolean", "regime_or_audit_metadata", False, "All", "Match contains documented extras/sequence quirk."),
    ColumnSpec("has_margin_text_mismatch", "regime_audit_metadata", "boolean", "regime_or_audit_metadata", False, "All", "matches.result margin differs from computed delivery runs/wickets margin."),
    ColumnSpec("has_uae_split_player_id", "regime_audit_metadata", "boolean", "regime_or_audit_metadata", False, "All", "Match has ball_by_ball player IDs missing from playing_eleven."),
    ColumnSpec("has_deliveries", "regime_audit_metadata", "boolean", "regime_or_audit_metadata", False, "All", "True for all delivery rows (False at match grain for zero-ball abandoned fixtures)."),
    ColumnSpec("terminal_innings_status_audit", "regime_audit_metadata", "string", "regime_or_audit_metadata", False, "All", "Post-match terminal innings closure category (audit only; never live feature)."),
    ColumnSpec("win_team_id_raw", "regime_audit_metadata", "Int64", "regime_or_audit_metadata", True, "All", "Preserved matches.win_team_id (target derivation source only)."),
    # Section 7: Supervised Targets & Training Eligibility Gates (5 fields)
    ColumnSpec("target_batting_team_win", "targets_eligibility", "Int64", "target", True, "All", "Primary binary target: 1 iff batting_team_id == win_team_id_raw, else 0 (pd.NA if win_team_id missing)."),
    ColumnSpec("target_home_team_win", "targets_eligibility", "Int64", "target", True, "All", "Reference binary target: 1 iff home_team_id == win_team_id_raw, else 0 (pd.NA if win_team_id missing)."),
    ColumnSpec("is_primary_wp_train_eligible", "targets_eligibility", "boolean", "regime_or_audit_metadata", False, "All", "Primary Stage 5B / baseline 20-over WP training eligibility gate."),
    ColumnSpec("is_dls_eval_slice_eligible", "targets_eligibility", "boolean", "regime_or_audit_metadata", False, "All", "Isolated DLS evaluation slice eligibility gate."),
    ColumnSpec("eligibility_exclusion_reason", "targets_eligibility", "string", "regime_or_audit_metadata", True, "All", "Deterministic reason when excluded from primary training; pd.NA when eligible."),
)

COLUMN_SPEC_MAP: dict[str, ColumnSpec] = {c.name: c for c in COLUMN_SPECS}
EXPECTED_COLUMN_ORDER: tuple[str, ...] = tuple(c.name for c in COLUMN_SPECS)

IDENTIFIER_COLUMNS: tuple[str, ...] = tuple(
    c.name for c in COLUMN_SPECS if c.role == "identifier"
)
MODEL_FEATURE_COLUMNS: tuple[str, ...] = tuple(
    c.name for c in COLUMN_SPECS if c.role == "model_feature"
)
REGIME_AUDIT_COLUMNS: tuple[str, ...] = tuple(
    c.name for c in COLUMN_SPECS if c.role == "regime_or_audit_metadata"
)
TARGET_COLUMNS: tuple[str, ...] = tuple(
    c.name for c in COLUMN_SPECS if c.role == "target"
)

# Illustrative prompt names (Stage 5B Section 6) mapped to exact Stage 5A Revision 1.1 columns
ILLUSTRATIVE_NAME_MAPPING: tuple[dict[str, str], ...] = (
    {"illustrative": "venue", "canonical": "venue_id, venue_country", "note": "Raw matches.csv has numeric venue_id and venue_country (no stadium name string)."},
    {"illustrative": "over_number", "canonical": "overid", "note": "Exact raw column name retained per Feature Dictionary §2."},
    {"illustrative": "ball_in_over", "canonical": "over_ball_num", "note": "Exact raw column name retained per Feature Dictionary §2."},
    {"illustrative": "batter_id", "canonical": "striker_id", "note": "Exact raw role key retained per Feature Dictionary §2."},
    {"illustrative": "runs_off_bat", "canonical": "batter_runs", "note": "Derived directly from ball_by_ball.runs per Feature Dictionary §4."},
    {"illustrative": "dismissed_player_id", "canonical": "dismissed_player_id_raw, resolved_dismissed_player_id, is_dismissed_player_unresolved", "note": "Separates untouched raw ID, verified resolved ID (pd.NA on 40709 2.19.5), and unresolved flag."},
    {"illustrative": "dismissal_type", "canonical": "dismissal_type_raw, dismissal_type_canonical, dismissal_type_id", "note": "Preserves raw typos alongside canonical Cricket Law strings."},
    {"illustrative": "total_runs_before / total_runs_after", "canonical": "score_before / score_after", "note": "Cumulative pre- and post-delivery team runs per Feature Dictionary §3 & §5."},
    {"illustrative": "overs_completed_after", "canonical": "overs_completed_decimal, overs_completed_notation", "note": "Decimal overs for math/models and notation for display audit only."},
    {"illustrative": "overs_completed_before", "canonical": "Derived from legal_balls_completed_before / 6.0 (not separate §3 column)", "note": "Pre-delivery cumulative state in §3 stores legal_balls_completed_before verbatim per Stage 5A Revision 1.1."},
    {"illustrative": "current_run_rate_after", "canonical": "current_run_rate", "note": "Post-delivery CRR with L_b == 0 zero-division guard per Feature Dictionary §5."},
    {"illustrative": "current_run_rate_before", "canonical": "Derived from score_before / legal_balls_completed_before (not separate §3 column)", "note": "Pre-delivery state in §3 stores score_before and legal_balls_completed_before per Stage 5A Revision 1.1."},
    {"illustrative": "required_run_rate_after", "canonical": "required_run_rate", "note": "Post-delivery RRR with verified-limit and zero-ball guards per Feature Dictionary §5."},
    {"illustrative": "required_run_rate_before", "canonical": "Derived from runs_required_before / legal_balls_remaining_before (not separate §3 column)", "note": "Pre-delivery chase state in §3 stores runs_required_before and legal_balls_remaining_before per Stage 5A Revision 1.1."},
)


def enforce_schema_dtypes(df: pd.DataFrame) -> pd.DataFrame:
    """Reorder columns to the 101-column Stage 5A Revision 1.1 schema and enforce exact nullable dtypes."""
    missing = [c for c in EXPECTED_COLUMN_ORDER if c not in df.columns]
    if missing:
        raise KeyError(f"Match-state DataFrame missing required Stage 5A Revision 1.1 columns: {missing}")

    extra = [c for c in df.columns if c not in COLUMN_SPEC_MAP]
    if extra:
        raise ValueError(f"Unexpected non-contract columns present in match-state DataFrame: {extra}")

    out = df.loc[:, list(EXPECTED_COLUMN_ORDER)].copy()
    for spec in COLUMN_SPECS:
        col = spec.name
        if spec.dtype == "Int64":
            out[col] = pd.array(out[col], dtype="Int64")
        elif spec.dtype == "Float64":
            out[col] = pd.array(out[col], dtype="Float64")
        elif spec.dtype == "boolean":
            out[col] = pd.array(out[col], dtype="boolean")
        elif spec.dtype == "string":
            out[col] = pd.Series(out[col], index=out.index, dtype="string")
        elif spec.dtype == "datetime64[ns]":
            out[col] = pd.to_datetime(out[col], format="%Y-%m-%d", errors="raise").astype("datetime64[ns]")
        else:  # pragma: no cover - defensive exhaustive check
            raise ValueError(f"Unsupported schema dtype {spec.dtype!r} for {col}")
    return out

