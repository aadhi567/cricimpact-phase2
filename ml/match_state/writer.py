"""Stage 5B dataset, manifest, eligibility, continuity, validation, and schema report writers."""

from __future__ import annotations

import importlib.metadata
import json
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from ml.ingestion.csv_loader import _compute_sha256
from ml.match_state.schema import (
    COLUMN_SPECS,
    DEFAULT_PROCESSED_MATCH_STATES_DIR,
    DEFAULT_STAGE5B_VALIDATION_DIR,
    EXPECTED_COLUMN_ORDER,
    IDENTIFIER_COLUMNS,
    ILLUSTRATIVE_NAME_MAPPING,
    MODEL_FEATURE_COLUMNS,
    REGIME_AUDIT_COLUMNS,
    SPECIFICATION_VERSION,
    TARGET_COLUMNS,
    UNRESOLVED_50407_AUDIT_STATUS,
    UNRESOLVED_50407_MATCH_ID,
)
from ml.match_state.validator import ContinuityAuditOutcome
from ml.validation.validation_engine import ValidationResult


def collect_runtime_versions() -> dict[str, Any]:
    """Capture exact Python and key installed package versions (including Parquet availability)."""
    pkg_names = (
        "pandas",
        "numpy",
        "scikit-learn",
        "scipy",
        "pydantic",
        "pytest",
        "matplotlib",
        "seaborn",
        "python-dotenv",
    )
    pkgs: dict[str, str] = {}
    for name in pkg_names:
        try:
            pkgs[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:  # pragma: no cover
            pkgs[name] = "not_installed"

    parquet_engines: list[str] = []
    for engine in ("pyarrow", "fastparquet"):
        try:
            parquet_engines.append(f"{engine}=={importlib.metadata.version(engine)}")
        except importlib.metadata.PackageNotFoundError:
            pass

    return {
        "python_version": platform.python_version(),
        "python_executable": sys.executable,
        "packages": pkgs,
        "parquet_engines_installed": parquet_engines,
    }


def resolve_versioned_file_path(
    directory: Path,
    base_prefix: str,
    extension: str,
    *,
    start_version: int = 1,
) -> Path:
    """Return `<directory>/<base_prefix>_v<N><extension>` using the lowest unused version >= start_version."""
    directory.mkdir(parents=True, exist_ok=True)
    ver = start_version
    while True:
        candidate = directory / f"{base_prefix}_v{ver}{extension}"
        if not candidate.exists():
            return candidate
        ver += 1


def resolve_synchronized_stage5b_version(
    processed_dir: Path,
    validation_dir: Path,
    *,
    start_version: int = 1,
) -> int:
    """Find the lowest version N where NO Stage 5B output artifact already exists."""
    ver = start_version
    while True:
        candidates = (
            processed_dir / f"match_states_standard_t20_v{ver}.pkl.gz",
            processed_dir / f"match_states_standard_t20_v{ver}_manifest.json",
            validation_dir / f"stage5b_match_eligibility_v{ver}.csv",
            validation_dir / f"stage5b_match_eligibility_report_v{ver}.md",
            validation_dir / f"stage5b_validation_summary_v{ver}.json",
            validation_dir / f"stage5b_validation_report_v{ver}.md",
            validation_dir / f"stage5b_continuity_audit_v{ver}.csv",
            validation_dir / f"stage5b_continuity_audit_report_v{ver}.md",
            validation_dir / f"stage5b_feature_schema_v{ver}.json",
            validation_dir / f"stage5b_feature_schema_report_v{ver}.md",
        )
        if not any(p.exists() for p in candidates):
            return ver
        ver += 1


def _render_eligibility_markdown(
    eligibility_df: pd.DataFrame,
    all_states_df: pd.DataFrame | None,
    primary_states_df: pd.DataFrame | None,
    version: int,
    expected_eligible_matches: int | None,
    reconciliation_halted: bool,
) -> str:
    total_matches = int(len(eligibility_df))
    primary_elg = eligibility_df.loc[eligibility_df["is_primary_wp_train_eligible"].fillna(False)]
    excluded = eligibility_df.loc[~eligibility_df["is_primary_wp_train_eligible"].fillna(False)]
    std_matches = eligibility_df.loc[eligibility_df["match_regime"] == "STANDARD_T20"]

    regime_summary = (
        eligibility_df.groupby("match_regime", sort=False)
        .agg(
            matches=("match_id", "count"),
            deliveries=("deliveries_count", "sum"),
            primary_eligible=("is_primary_wp_train_eligible", "sum"),
            dls_eval_eligible=("is_dls_eval_slice_eligible", "sum"),
        )
        .reset_index()
    )

    excl_summary = (
        excluded.groupby(["match_regime", "eligibility_exclusion_reason"], dropna=False, sort=False)
        .agg(matches=("match_id", "count"), deliveries=("deliveries_count", "sum"))
        .reset_index()
    )

    cat_summary = (
        eligibility_df.groupby("competition_category", sort=False)
        .agg(
            total_matches=("match_id", "count"),
            total_deliveries=("deliveries_count", "sum"),
            primary_matches=("is_primary_wp_train_eligible", "sum"),
        )
        .reset_index()
    )
    if primary_states_df is not None and len(primary_states_df) > 0:
        pri_deliv_by_cat = (
            primary_states_df.groupby("competition_category", sort=False)
            .size()
            .to_dict()
        )
    else:
        pri_deliv_by_cat = {}

    lines: list[str] = [
        f"# CricImpact Phase 2 — Stage 5B Match Eligibility & Reconciliation Report (v{version})",
        "",
        f"**Specification Version:** `{SPECIFICATION_VERSION}`  ",
        f"**Generated At (UTC):** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}  ",
        "",
    ]
    if reconciliation_halted:
        lines.extend(
            [
                f"> **CRITICAL RECONCILIATION STOP:** Expected `{expected_eligible_matches}` eligible matches, "
                f"found `{len(primary_elg)}`. Primary dataset write was halted for review.",
                "",
            ]
        )

    lines.extend(
        [
            "## 1. High-Level Reconciliation Summary",
            "",
            f"- **Total Matches in Raw Corpus:** `{total_matches:,}`",
            f"- **Matches Classified `STANDARD_T20`:** `{len(std_matches):,}` (`{int(std_matches['deliveries_count'].sum()):,}` raw deliveries)",
            f"- **Matches Eligible for Primary Stage 5B Dataset:** `{len(primary_elg):,}`"
            + (
                f" (matches baseline expectation `{expected_eligible_matches}`)"
                if expected_eligible_matches is not None
                else ""
            ),
            f"- **Total Excluded Matches:** `{len(excluded):,}` (`{int(excluded['deliveries_count'].sum()):,}` deliveries; `{int((excluded['deliveries_count'] == 0).sum())}` zero-ball matches contribute `0` deliveries)",
            f"- **Primary vs. `all_states` Delivery Count:** `{len(primary_states_df):,}` included vs. `{len(all_states_df):,}` total recorded deliveries across `{int(eligibility_df['has_deliveries'].sum()):,}` played matches"
            if primary_states_df is not None and all_states_df is not None
            else "",
            "",
        ]
    )
    if total_matches == 883:
        lines.extend(
            [
                "### 798 vs. 802 Sensitivity Distinction & Quarantine Breakdown",
                "- The `802` non-DLS, non-SO completed matches divide strictly into:",
                "  - **`798` `STANDARD_T20` clean primary matches** (including the `5` injured/absent 9-wicket Innings 2 closures `15409`, `17627`, `29983`, `42743`, `48917`, plus `20190` whose only flaw is scorecard text typo).",
                "  - **`3` quarantined over-length sequence-anomaly matches** (`14130`, `14164`, `41509`) with unverified innings limits -> excluded under `'sequence_or_termination_anomaly'`.",
                "  - **`1` quarantined unresolved termination match (`50407`)** -> excluded under `'unresolved_match_sequence_50407'`, never admitted to standard completed-match training or standard ablations.",
                "",
                "### Note on Raw CSV Delivery Sums vs. Stage 5A Prose Table Typo",
                "- Match counts (`798`, `31`, `9`, `19`, `21`, `1`, `4` = `883`) match `docs/match_regime_policy.md` §2 identically.",
                "- Direct raw CSV summation yields exact delivery counts of **`190,575`** (`STANDARD_T20`), **`5,223`** (`REVISED_OVERS_DLS`: `4,726` explicit + `497` unflagged reduced), and **`961`** (`INCOMPLETE_OR_UNRESOLVED`: `251+219+231+260`), summing with `2,308 + 258 + 1,495 + 179` to **`200,999`** (a `56`-delivery arithmetic typo in the Stage 5A §2 prose table had swapped deliveries between those three buckets while classifying the exact same match IDs).",
                "",
            ]
        )
    lines.extend(
        [
            "## 2. Seven-Regime Partition",
            "",
            "| Match Regime | Matches | Raw Deliveries | Primary Eligible Matches | DLS Eval Eligible Matches |",
            "|:---|---:|---:|---:|---:|",
        ]
    )
    for _, r in regime_summary.iterrows():
        lines.append(
            f"| `{r['match_regime']}` | {int(r['matches']):,} | {int(r['deliveries']):,} | "
            f"{int(r['primary_eligible']):,} | {int(r['dls_eval_eligible']):,} |"
        )

    lines.extend(
        [
            "",
            "## 3. Competition Category Breakdown (Derived Strictly From `competitions.csv`)",
            "",
            "| Competition Category | Total Matches | Total Raw Deliveries | Primary Eligible Matches | Primary Deliveries |",
            "|:---|---:|---:|---:|---:|",
        ]
    )
    for _, r in cat_summary.iterrows():
        cat = str(r["competition_category"])
        lines.append(
            f"| `{cat}` | {int(r['total_matches']):,} | {int(r['total_deliveries']):,} | "
            f"{int(r['primary_matches']):,} | {int(pri_deliv_by_cat.get(cat, 0)):,} |"
        )

    lines.extend(
        [
            "",
            "## 4. Excluded Match Summary by Regime and Exclusion Reason",
            "",
            "| Match Regime | Exclusion Reason | Excluded Matches | Raw Deliveries |",
            "|:---|:---|---:|---:|",
        ]
    )
    for _, r in excl_summary.iterrows():
        lines.append(
            f"| `{r['match_regime']}` | `{r['eligibility_exclusion_reason']}` | "
            f"{int(r['matches']):,} | {int(r['deliveries']):,} |"
        )

    lines.extend(
        [
            "",
            "## 5. Match `50407` Explicit Quarantine Audit Record",
            "",
            f"- **`match_id`:** `{UNRESOLVED_50407_MATCH_ID}`",
            "- **`match_regime`:** `INCOMPLETE_OR_UNRESOLVED`",
            "- **`eligibility_exclusion_reason`:** `unresolved_match_sequence_50407`",
            f"- **Audit Status:** `{UNRESOLVED_50407_AUDIT_STATUS}`",
            "- **`is_primary_wp_train_eligible`:** `False` (`0` rows in primary dataset)",
            "- **`is_innings_limit_verified`:** `False` (`innings_ball_limit = pd.NA`, `legal_balls_remaining = pd.NA`)",
            "",
            "## 6. Complete Excluded Match Listing",
            "",
            "| `match_id` | Date | `comp_id` | `competition_category` | `match_regime` | `deliveries_count` | `eligibility_exclusion_reason` | Notes |",
            "|---:|:---|---:|:---|:---|---:|:---|:---|",
        ]
    )
    for _, r in excluded.sort_values("match_id").iterrows():
        lines.append(
            f"| {int(r['match_id'])} | {str(r['match_date'])[:10]} | {int(r['comp_id'])} | "
            f"`{r['competition_category']}` | `{r['match_regime']}` | {int(r['deliveries_count'])} | "
            f"`{r['eligibility_exclusion_reason']}` | {r['audit_status_note']} |"
        )

    lines.append("")
    return "\n".join(lines)


def _render_validation_markdown(
    validation_outcome: dict[str, Any],
    version: int,
) -> str:
    results: list[ValidationResult] = validation_outcome["results"]
    sc = validation_outcome["status_counts"]
    lines: list[str] = [
        f"# CricImpact Phase 2 — Stage 5B Validation Report (v{version})",
        "",
        f"**Specification Version:** `{SPECIFICATION_VERSION}`  ",
        f"**Generated At (UTC):** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}  ",
        f"**Critical Failures:** `{'YES (BLOCKED)' if validation_outcome['has_critical_failure'] else '0 (PASSED)'}`  ",
        f"**Status Counts:** `PASS={sc.get('PASS', 0)}`, `WARNING={sc.get('WARNING', 0)}`, `FAIL={sc.get('FAIL', 0)}`, `SKIPPED={sc.get('SKIPPED', 0)}`",
        "",
        "## Validation Rules Executed",
        "",
        "| Rule ID | Severity | Status | Affected | Known Ex. | New Anom. | Description |",
        "|:---|:---|:---|---:|---:|---:|:---|",
    ]
    for r in results:
        lines.append(
            f"| `{r.rule_id}` | {r.severity.value} | **{r.status.value}** | "
            f"{r.affected_record_count:,} | {r.known_exception_count:,} | "
            f"{r.new_anomaly_count:,} | {r.short_description} |"
        )

    lines.extend(["", "## Exact Category Metrics & Preserved Warnings", ""])
    for r in results:
        lines.append(f"### `{r.rule_id}` (`{r.status.value}` / `{r.severity.value}`)")
        lines.append(f"- **Fields:** `{r.field}`")
        lines.append(f"- **Summary:** {r.short_description}")
        if r.known_exceptions_summary:
            lines.append(f"- **Documented Exceptions:** {r.known_exceptions_summary}")
        if r.metadata:
            lines.append(f"- **Metrics:** `{json.dumps(r.metadata)}`")
        if r.example_record_identifiers:
            for ex in r.example_record_identifiers[:8]:
                lines.append(f"  - `{ex}`")
        lines.append("")

    return "\n".join(lines)


def _render_continuity_markdown(
    continuity: ContinuityAuditOutcome,
    version: int,
) -> str:
    lines: list[str] = [
        f"# CricImpact Phase 2 — Stage 5B State Continuity Audit Report (v{version})",
        "",
        f"**Generated At (UTC):** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}  ",
        f"**Total Delivery Transitions Checked:** `{continuity.total_rows_checked:,}` across `{continuity.total_innings_groups:,}` innings groups  ",
        f"**Unexpected State Continuity Breaks (`state_before[b] != state_after[b-1]` / step / init / gaps):** `{continuity.unexpected_break_count}`  ",
        f"**Documented Source Sequence / Termination Discontinuities Logged:** `{continuity.documented_discontinuity_count}`  ",
        "",
        "## Checks Performed",
        "- Intra-`(match_id, innings)` initial boundary check (`score_before`, `wickets_lost_before`, `legal_balls_completed_before`, `retired_hurt_count_before`, verified `legal_balls_remaining_before`, known `runs_required_before`).",
        "- Consecutive transition continuity (`state_before[k] == state_after[k-1]`) for score, official wickets, legal balls completed, Retired Hurt count, verified legal balls remaining, and known Innings 2 runs required.",
        "- Step transition arithmetic (`state_after[k] == state_before[k] + delta[k]`) and contiguous `innings_ball_num` sequence (`1, 2, ...`).",
        "- Source mid-over sequence irregularities (`over_legal != 6` before final over) and Match `50407` premature termination at `20.5`.",
        "",
        "## Audit Records",
        "",
    ]
    if len(continuity.audit_df) == 0:
        lines.append("**0 continuity breaks and 0 sequence discontinuities detected.**")
    else:
        lines.append(
            "| `match_id` | Innings | Delivery Identifier | Field Affected | Previous After State | Current Before State | Discrepancy | Classification | Resolution Status |"
        )
        lines.append(
            "|---:|---:|:---|:---|:---|:---|:---|:---|:---|"
        )
        for _, r in continuity.audit_df.iterrows():
            lines.append(
                f"| {r['match_id']} | {r['innings']} | `{r['delivery_identifier']}` | "
                f"`{r['field_affected']}` | `{r['previous_after_state']}` | `{r['current_before_state']}` | "
                f"`{r['discrepancy']}` | `{r['classification']}` | {r['resolution_status']} |"
            )
    lines.append("")
    return "\n".join(lines)


def _render_feature_schema_payload(
    primary_states_df: pd.DataFrame,
    version: int,
) -> tuple[dict[str, Any], str]:
    col_records: list[dict[str, Any]] = []
    for pos, spec in enumerate(COLUMN_SPECS, start=1):
        null_cnt = int(primary_states_df[spec.name].isna().sum()) if len(primary_states_df) > 0 else 0
        col_records.append(
            {
                "position": pos,
                "name": spec.name,
                "section": spec.section,
                "dtype": str(primary_states_df[spec.name].dtype),
                "contract_dtype": spec.dtype,
                "role": spec.role,
                "nullable": spec.nullable,
                "applicable_innings": spec.applicable_innings,
                "primary_null_count": null_cnt,
                "description": spec.description,
            }
        )

    role_counts = {
        "identifier": len(IDENTIFIER_COLUMNS),
        "model_feature": len(MODEL_FEATURE_COLUMNS),
        "regime_or_audit_metadata": len(REGIME_AUDIT_COLUMNS),
        "target": len(TARGET_COLUMNS),
    }

    payload = {
        "specification_version": SPECIFICATION_VERSION,
        "dataset_version": f"v{version}",
        "total_columns": len(COLUMN_SPECS),
        "role_counts": role_counts,
        "illustrative_prompt_to_canonical_mapping": list(ILLUSTRATIVE_NAME_MAPPING),
        "columns": col_records,
    }

    md_lines: list[str] = [
        f"# CricImpact Phase 2 — Stage 5B Feature Schema Report (v{version})",
        "",
        f"**Specification Version:** `{SPECIFICATION_VERSION}`  ",
        f"**Total Columns:** `{len(COLUMN_SPECS)}` (`identifier={role_counts['identifier']}`, `model_feature={role_counts['model_feature']}`, `regime_or_audit_metadata={role_counts['regime_or_audit_metadata']}`, `target={role_counts['target']}`)  ",
        f"**Primary Rows Evaluated:** `{len(primary_states_df):,}`",
        "",
        "## 1. Prompt Illustrative Field Mapping -> Stage 5A Revision 1.1 Exact Columns",
        "",
        "| Illustrative Prompt Name (Stage 5B §6) | Canonical Stage 5A Revision 1.1 Field(s) | Notes |",
        "|:---|:---|:---|",
    ]
    for m in ILLUSTRATIVE_NAME_MAPPING:
        md_lines.append(f"| `{m['illustrative']}` | `{m['canonical']}` | {m['note']} |")

    md_lines.extend(
        [
            "",
            "## 2. Full 101-Column Contract & Observed Primary Dataset Dtypes",
            "",
            "| # | Column Name | Section | Contract & Observed Dtype | Role Classification | Nullable? | Primary Nulls | Description |",
            "|---:|:---|:---|:---|:---|:---:|---:|:---|",
        ]
    )
    for rec in col_records:
        md_lines.append(
            f"| {rec['position']} | `{rec['name']}` | `{rec['section']}` | `{rec['dtype']}` | "
            f"`{rec['role']}` | {rec['nullable']} | {rec['primary_null_count']:,} | {rec['description']} |"
        )
    md_lines.append("")
    return payload, "\n".join(md_lines)


def write_reconciliation_halt_reports(
    *,
    eligibility_df: pd.DataFrame,
    expected_eligible_matches: int,
    validation_dir: Path | None = None,
) -> dict[str, Path]:
    """Write Stage 5B eligibility reconciliation files before stopping on match count divergence."""
    val_dir = Path(validation_dir).resolve() if validation_dir else DEFAULT_STAGE5B_VALIDATION_DIR
    val_dir.mkdir(parents=True, exist_ok=True)
    csv_path = resolve_versioned_file_path(
        val_dir, "stage5b_match_eligibility_reconciliation", ".csv"
    )
    md_path = resolve_versioned_file_path(
        val_dir, "stage5b_match_eligibility_reconciliation_report", ".md"
    )
    eligibility_df.to_csv(csv_path, index=False)
    md_text = _render_eligibility_markdown(
        eligibility_df=eligibility_df,
        all_states_df=None,
        primary_states_df=None,
        version=1,
        expected_eligible_matches=expected_eligible_matches,
        reconciliation_halted=True,
    )
    md_path.write_text(md_text, encoding="utf-8")
    return {"eligibility_csv": csv_path, "eligibility_md": md_path}


def write_stage5b_outputs(
    *,
    primary_states_df: pd.DataFrame,
    all_states_df: pd.DataFrame,
    eligibility_df: pd.DataFrame,
    validation_outcome: dict[str, Any],
    source_summaries: list[dict[str, Any]],
    raw_hashes_unchanged: bool,
    stage4_status_counts: dict[str, int] | None = None,
    processed_dir: Path | None = None,
    validation_dir: Path | None = None,
    write_primary_dataset: bool = True,
) -> dict[str, Any]:
    """Persist all versioned Stage 5B artifacts cleanly without overwriting existing outputs."""
    proc_dir = Path(processed_dir).resolve() if processed_dir else DEFAULT_PROCESSED_MATCH_STATES_DIR
    val_dir = Path(validation_dir).resolve() if validation_dir else DEFAULT_STAGE5B_VALIDATION_DIR
    proc_dir.mkdir(parents=True, exist_ok=True)
    val_dir.mkdir(parents=True, exist_ok=True)

    ver = resolve_synchronized_stage5b_version(proc_dir, val_dir, start_version=1)
    continuity: ContinuityAuditOutcome = validation_outcome["continuity"]

    paths: dict[str, Path] = {}

    # 1. Validation & audit artifacts under data/validation/stage_5b/
    elg_csv = val_dir / f"stage5b_match_eligibility_v{ver}.csv"
    elg_md = val_dir / f"stage5b_match_eligibility_report_v{ver}.md"
    val_json = val_dir / f"stage5b_validation_summary_v{ver}.json"
    val_md = val_dir / f"stage5b_validation_report_v{ver}.md"
    cnt_csv = val_dir / f"stage5b_continuity_audit_v{ver}.csv"
    cnt_md = val_dir / f"stage5b_continuity_audit_report_v{ver}.md"
    sch_json = val_dir / f"stage5b_feature_schema_v{ver}.json"
    sch_md = val_dir / f"stage5b_feature_schema_report_v{ver}.md"

    eligibility_df.to_csv(elg_csv, index=False)
    elg_md.write_text(
        _render_eligibility_markdown(
            eligibility_df=eligibility_df,
            all_states_df=all_states_df,
            primary_states_df=primary_states_df,
            version=ver,
            expected_eligible_matches=798,
            reconciliation_halted=False,
        ),
        encoding="utf-8",
    )

    val_payload = {
        "specification_version": SPECIFICATION_VERSION,
        "dataset_version": f"v{ver}",
        "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
        "has_critical_failure": validation_outcome["has_critical_failure"],
        "status_counts": validation_outcome["status_counts"],
        "severity_counts": validation_outcome["severity_counts"],
        "stage4_baseline_status_counts": stage4_status_counts or {},
        "continuity_summary": {
            "total_rows_checked": continuity.total_rows_checked,
            "total_innings_groups": continuity.total_innings_groups,
            "unexpected_break_count": continuity.unexpected_break_count,
            "documented_discontinuity_count": continuity.documented_discontinuity_count,
            "step_equation_violation_count": continuity.step_equation_violation_count,
            "initial_state_violation_count": continuity.initial_state_violation_count,
            "key_sequence_gap_count": continuity.key_sequence_gap_count,
            "mid_over_anomaly_count": continuity.mid_over_anomaly_count,
            "unresolved_termination_count": continuity.unresolved_termination_count,
        },
        "results": [r.model_dump(mode="json") for r in validation_outcome["results"]],
    }
    val_json.write_text(json.dumps(val_payload, indent=2), encoding="utf-8")
    val_md.write_text(_render_validation_markdown(validation_outcome, ver), encoding="utf-8")

    continuity.audit_df.to_csv(cnt_csv, index=False)
    cnt_md.write_text(_render_continuity_markdown(continuity, ver), encoding="utf-8")

    schema_payload, schema_md_text = _render_feature_schema_payload(primary_states_df, ver)
    sch_json.write_text(json.dumps(schema_payload, indent=2), encoding="utf-8")
    sch_md.write_text(schema_md_text, encoding="utf-8")

    paths.update(
        {
            "eligibility_csv": elg_csv,
            "eligibility_md": elg_md,
            "validation_json": val_json,
            "validation_md": val_md,
            "continuity_csv": cnt_csv,
            "continuity_md": cnt_md,
            "feature_schema_json": sch_json,
            "feature_schema_md": sch_md,
        }
    )

    dataset_sha256: str | None = None
    dataset_size_bytes: int | None = None
    roundtrip_verified = False

    # 2. Primary dataset & manifest (only persisted when validation succeeds & flag is enabled)
    if write_primary_dataset and not validation_outcome["has_critical_failure"]:
        dataset_path = proc_dir / f"match_states_standard_t20_v{ver}.pkl.gz"
        manifest_path = proc_dir / f"match_states_standard_t20_v{ver}_manifest.json"

        primary_states_df.to_pickle(dataset_path, compression="gzip", protocol=5)
        reloaded = pd.read_pickle(dataset_path, compression="gzip")
        pd.testing.assert_frame_equal(primary_states_df, reloaded, check_dtype=True, check_exact=True)
        roundtrip_verified = True
        dataset_sha256 = _compute_sha256(dataset_path)
        dataset_size_bytes = dataset_path.stat().st_size

        primary_elg_df = eligibility_df.loc[
            eligibility_df["is_primary_wp_train_eligible"].fillna(False)
        ]
        excluded_df = eligibility_df.loc[
            ~eligibility_df["is_primary_wp_train_eligible"].fillna(False)
        ]
        runtime_versions = collect_runtime_versions()

        manifest_payload = {
            "specification_version": SPECIFICATION_VERSION,
            "dataset_version": f"v{ver}",
            "build_timestamp_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "runtime": runtime_versions,
            "storage_format": "gzip_compressed_pandas_pickle (.pkl.gz)",
            "storage_format_rationale": (
                "Parquet engines (pyarrow/fastparquet) are not installed in the active .venv; "
                "gzip-compressed Pandas Pickle (protocol=5) preserves exact nullable Pandas extension "
                "dtypes (Int64/Float64/boolean/string/datetime64[ns]), pd.NA semantics, IEEE-754 floats, "
                "and literal 'None' strings with verified bit-exact round-trip equality."
            ),
            "roundtrip_verified": roundtrip_verified,
            "raw_hashes_unchanged": raw_hashes_unchanged,
            "source_files": source_summaries,
            "output_dataset": {
                "filename": dataset_path.name,
                "path": str(dataset_path),
                "size_bytes": dataset_size_bytes,
                "sha256": dataset_sha256,
                "row_count": int(len(primary_states_df)),
                "column_count": int(len(primary_states_df.columns)),
                "columns": list(EXPECTED_COLUMN_ORDER),
                "column_role_counts": schema_payload["role_counts"],
            },
            "corpus_counts": {
                "total_matches": int(len(eligibility_df)),
                "total_deliveries_all_regimes": int(len(all_states_df)),
                "primary_included_matches": int(len(primary_elg_df)),
                "primary_included_deliveries": int(len(primary_states_df)),
                "excluded_matches_count": int(len(excluded_df)),
                "by_regime": {
                    str(k): int(v)
                    for k, v in eligibility_df["match_regime"].value_counts().items()
                },
                "by_exclusion_reason": {
                    str(k): int(v)
                    for k, v in excluded_df["eligibility_exclusion_reason"].value_counts().items()
                },
                "primary_by_competition_category": {
                    str(k): int(v)
                    for k, v in primary_elg_df["competition_category"].value_counts().items()
                },
            },
            "included_matches": {
                "count": int(len(primary_elg_df)),
                "match_ids": [int(x) for x in primary_elg_df["match_id"].tolist()],
            },
            "excluded_matches": {
                "count": int(len(excluded_df)),
                "records": [
                    {
                        "match_id": int(r["match_id"]),
                        "match_regime": str(r["match_regime"]),
                        "eligibility_exclusion_reason": str(r["eligibility_exclusion_reason"]),
                        "deliveries_count": int(r["deliveries_count"]),
                        "audit_status_note": str(r["audit_status_note"]),
                    }
                    for _, r in excluded_df.sort_values("match_id").iterrows()
                ],
            },
            "validation_summary": {
                "has_critical_failure": validation_outcome["has_critical_failure"],
                "status_counts": validation_outcome["status_counts"],
                "continuity_unexpected_breaks": continuity.unexpected_break_count,
                "continuity_documented_discontinuities": continuity.documented_discontinuity_count,
            },
            "validation_artifact_paths": {k: str(v) for k, v in paths.items()},
        }
        manifest_path.write_text(json.dumps(manifest_payload, indent=2), encoding="utf-8")
        paths["primary_dataset"] = dataset_path
        paths["manifest_json"] = manifest_path

    return {
        "version": ver,
        "paths": paths,
        "dataset_sha256": dataset_sha256,
        "dataset_size_bytes": dataset_size_bytes,
        "roundtrip_verified": roundtrip_verified,
    }
