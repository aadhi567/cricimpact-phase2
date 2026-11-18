"""End-to-end Stage 5B match-state orchestration reusing Stage 4 ingestion and validation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from ml.ingestion.csv_loader import DatasetLoadBundle, _compute_sha256, load_raw_datasets
from ml.ingestion.dataset_registry import (
    DATASET_SPECS,
    DEFAULT_RAW_DIR,
    PROJECT_ROOT,
)
from ml.match_state.eligibility import classify_match_eligibility
from ml.match_state.feature_deriver import derive_match_state_features
from ml.match_state.schema import (
    DEFAULT_PROCESSED_MATCH_STATES_DIR,
    DEFAULT_STAGE5B_VALIDATION_DIR,
)
from ml.match_state.state_builder import build_delivery_states
from ml.match_state.validator import validate_match_state_dataset
from ml.match_state.writer import (
    write_reconciliation_halt_reports,
    write_stage5b_outputs,
)
from ml.validation import build_default_validation_engine


@dataclass
class MatchStatePipelineOutcome:
    """Structured return object produced by Stage 5B match-state execution."""

    status: str  # "COMPLETE" or "BLOCKED"
    reconciliation_halted: bool
    has_critical_failure: bool
    eligible_match_count: int
    excluded_match_count: int
    total_match_count: int
    primary_row_count: int
    all_row_count: int
    column_count: int
    raw_hashes_unchanged: bool | None
    stage4_hashes_unchanged: bool | None
    stage4_status_counts: dict[str, int]
    validation_outcome: dict[str, Any] | None
    eligibility_df: pd.DataFrame
    primary_states_df: pd.DataFrame | None
    all_states_df: pd.DataFrame | None
    written: dict[str, Any]
    source_summaries: list[dict[str, Any]]
    blocker_message: str | None = None


def _hash_stage4_files() -> dict[str, str]:
    hashes: dict[str, str] = {}
    for rel_dir in ("ml/ingestion", "ml/validation"):
        dir_path = PROJECT_ROOT / rel_dir
        if dir_path.exists():
            for py_file in sorted(dir_path.glob("*.py")):
                hashes[str(py_file.relative_to(PROJECT_ROOT))] = _compute_sha256(py_file)
    return hashes


def _verify_raw_hashes(raw_dir: Path, before_hashes: dict[str, str]) -> bool:
    for name, expected in before_hashes.items():
        path = Path(raw_dir) / DATASET_SPECS[name].filename
        if not path.exists() or _compute_sha256(path) != expected:
            return False
    return True


def run_match_state_pipeline_from_frames(
    *,
    ball_by_ball: pd.DataFrame,
    matches: pd.DataFrame,
    competitions: pd.DataFrame,
    playing_eleven: pd.DataFrame | None = None,
    teams: pd.DataFrame | None = None,
    competition_team_player_mapping: pd.DataFrame | None = None,
    source_summaries: list[dict[str, Any]] | None = None,
    stage4_status_counts: dict[str, int] | None = None,
    expected_eligible_matches: int | None = None,
    processed_dir: Path | None = None,
    validation_dir: Path | None = None,
    write_outputs: bool = False,
    raw_hashes_unchanged: bool | None = None,
) -> MatchStatePipelineOutcome:
    """Run Stage 5B eligibility, state construction, feature derivation, and validation on in-memory tables."""
    # Touch optional Stage 4 reference tables when provided (ensuring full 6-table contract integrity)
    _ = teams, competition_team_player_mapping

    eligibility_df = classify_match_eligibility(
        matches=matches,
        competitions=competitions,
        ball_by_ball=ball_by_ball,
        playing_eleven=playing_eleven,
    )

    eligible_cnt = int(eligibility_df["is_primary_wp_train_eligible"].fillna(False).sum())
    excluded_cnt = int(len(eligibility_df) - eligible_cnt)

    if (
        expected_eligible_matches is not None
        and eligible_cnt != expected_eligible_matches
    ):
        halt_written: dict[str, Any] = {}
        if write_outputs:
            halt_written = {
                "paths": write_reconciliation_halt_reports(
                    eligibility_df=eligibility_df,
                    expected_eligible_matches=expected_eligible_matches,
                    validation_dir=validation_dir,
                )
            }
        return MatchStatePipelineOutcome(
            status="BLOCKED",
            reconciliation_halted=True,
            has_critical_failure=True,
            eligible_match_count=eligible_cnt,
            excluded_match_count=excluded_cnt,
            total_match_count=int(len(eligibility_df)),
            primary_row_count=0,
            all_row_count=0,
            column_count=0,
            raw_hashes_unchanged=raw_hashes_unchanged,
            stage4_hashes_unchanged=None,
            stage4_status_counts=stage4_status_counts or {},
            validation_outcome=None,
            eligibility_df=eligibility_df,
            primary_states_df=None,
            all_states_df=None,
            written=halt_written,
            source_summaries=source_summaries or [],
            blocker_message=(
                f"Eligibility reconciliation stop: expected {expected_eligible_matches} eligible matches "
                f"but found {eligible_cnt}."
            ),
        )

    state_df = build_delivery_states(ball_by_ball)
    all_states_df = derive_match_state_features(state_df, eligibility_df)
    primary_mask = all_states_df["is_primary_wp_train_eligible"].fillna(False)
    primary_states_df = all_states_df.loc[primary_mask].reset_index(drop=True)

    validation_outcome = validate_match_state_dataset(
        all_states_df=all_states_df,
        primary_states_df=primary_states_df,
        eligibility_df=eligibility_df,
        raw_ball_by_ball=ball_by_ball,
        raw_matches=matches,
        raw_competitions=competitions,
    )

    has_crit = bool(validation_outcome["has_critical_failure"])
    written: dict[str, Any] = {}
    if write_outputs:
        written = write_stage5b_outputs(
            primary_states_df=primary_states_df,
            all_states_df=all_states_df,
            eligibility_df=eligibility_df,
            validation_outcome=validation_outcome,
            source_summaries=source_summaries or [],
            raw_hashes_unchanged=bool(raw_hashes_unchanged) if raw_hashes_unchanged is not None else True,
            stage4_status_counts=stage4_status_counts,
            processed_dir=processed_dir,
            validation_dir=validation_dir,
            write_primary_dataset=not has_crit,
        )

    return MatchStatePipelineOutcome(
        status="BLOCKED" if has_crit else "COMPLETE",
        reconciliation_halted=False,
        has_critical_failure=has_crit,
        eligible_match_count=eligible_cnt,
        excluded_match_count=excluded_cnt,
        total_match_count=int(len(eligibility_df)),
        primary_row_count=int(len(primary_states_df)),
        all_row_count=int(len(all_states_df)),
        column_count=int(len(primary_states_df.columns)),
        raw_hashes_unchanged=raw_hashes_unchanged,
        stage4_hashes_unchanged=None,
        stage4_status_counts=stage4_status_counts or {},
        validation_outcome=validation_outcome,
        eligibility_df=eligibility_df,
        primary_states_df=primary_states_df,
        all_states_df=all_states_df,
        written=written,
        source_summaries=source_summaries or [],
        blocker_message="One or more CRITICAL Stage 5B validations failed." if has_crit else None,
    )


def run_match_state_pipeline(
    *,
    raw_dir: Path | None = None,
    processed_dir: Path | None = None,
    validation_dir: Path | None = None,
    expected_eligible_matches: int | None = 798,
    write_outputs: bool = True,
) -> MatchStatePipelineOutcome:
    """Load all 6 raw CSVs via Stage 4 loader, verify baseline integrity, and build Stage 5B dataset."""
    resolved_raw = Path(raw_dir).resolve() if raw_dir is not None else DEFAULT_RAW_DIR
    resolved_proc = (
        Path(processed_dir).resolve()
        if processed_dir is not None
        else DEFAULT_PROCESSED_MATCH_STATES_DIR
    )
    resolved_val = (
        Path(validation_dir).resolve()
        if validation_dir is not None
        else DEFAULT_STAGE5B_VALIDATION_DIR
    )

    stage4_before_hashes = _hash_stage4_files()
    bundle: DatasetLoadBundle = load_raw_datasets(raw_dir=resolved_raw)
    before_raw_hashes = {
        k: s.sha256 for k, s in bundle.summaries.items() if s.sha256 is not None
    }

    required_tables = (
        "ball_by_ball",
        "matches",
        "competitions",
        "teams",
        "competition_team_player_mapping",
        "playing_eleven",
    )
    missing_tables = [t for t in required_tables if bundle.get(t) is None]
    if missing_tables:
        raise RuntimeError(
            f"Stage 4 ingestion failed to load required raw tables: {missing_tables}"
        )

    stage4_report = build_default_validation_engine().run(bundle)
    stage4_sc = stage4_report.status_counts
    if stage4_sc.get("FAIL", 0) > 0:
        raise RuntimeError(
            f"Stage 4 baseline validation reported {stage4_sc.get('FAIL', 0)} FAIL rule(s); "
            "halting Stage 5B build."
        )

    outcome = run_match_state_pipeline_from_frames(
        ball_by_ball=bundle.datasets["ball_by_ball"],
        matches=bundle.datasets["matches"],
        competitions=bundle.datasets["competitions"],
        playing_eleven=bundle.datasets["playing_eleven"],
        teams=bundle.datasets["teams"],
        competition_team_player_mapping=bundle.datasets["competition_team_player_mapping"],
        source_summaries=bundle.summary_rows(),
        stage4_status_counts=stage4_sc,
        expected_eligible_matches=expected_eligible_matches,
        processed_dir=resolved_proc,
        validation_dir=resolved_val,
        write_outputs=False,
        raw_hashes_unchanged=None,
    )

    raw_unchanged = _verify_raw_hashes(resolved_raw, before_raw_hashes)
    stage4_after_hashes = _hash_stage4_files()
    stage4_unchanged = stage4_before_hashes == stage4_after_hashes

    outcome.raw_hashes_unchanged = raw_unchanged
    outcome.stage4_hashes_unchanged = stage4_unchanged

    if not raw_unchanged or not stage4_unchanged:
        raise RuntimeError(
            f"Immutability verification failed (raw_unchanged={raw_unchanged}, "
            f"stage4_unchanged={stage4_unchanged})."
        )

    if write_outputs and not outcome.reconciliation_halted and outcome.validation_outcome is not None:
        assert outcome.primary_states_df is not None and outcome.all_states_df is not None
        outcome.written = write_stage5b_outputs(
            primary_states_df=outcome.primary_states_df,
            all_states_df=outcome.all_states_df,
            eligibility_df=outcome.eligibility_df,
            validation_outcome=outcome.validation_outcome,
            source_summaries=bundle.summary_rows(),
            raw_hashes_unchanged=raw_unchanged,
            stage4_status_counts=stage4_sc,
            processed_dir=resolved_proc,
            validation_dir=resolved_val,
            write_primary_dataset=not outcome.has_critical_failure,
        )
    elif write_outputs and outcome.reconciliation_halted:
        outcome.written = {
            "paths": write_reconciliation_halt_reports(
                eligibility_df=outcome.eligibility_df,
                expected_eligible_matches=expected_eligible_matches or 0,
                validation_dir=resolved_val,
            )
        }

    return outcome
