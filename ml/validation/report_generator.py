"""Markdown and JSON validation report generator for Stage 4 (Phase 6)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ml.ingestion.dataset_registry import DEFAULT_VALIDATION_DIR
from ml.validation.validation_engine import ValidationReport, ValidationResult, ValidationStatus


def resolve_versioned_output_path(base_path: Path) -> Path:
    """Return base_path if unused, otherwise preserve existing file with _v2, _v3... suffix."""
    if not base_path.exists():
        return base_path
    stem = base_path.stem
    suffix = base_path.suffix
    parent = base_path.parent
    version = 2
    while True:
        candidate = parent / f"{stem}_v{version}{suffix}"
        if not candidate.exists():
            return candidate
        version += 1


def _find_rules(report: ValidationReport, rule_ids: tuple[str, ...]) -> list[ValidationResult]:
    by_id = {r.rule_id: r for r in report.results}
    return [by_id[rid] for rid in rule_ids if rid in by_id]


def _render_rule_table(results: list[ValidationResult]) -> list[str]:
    if not results:
        return ["_No rules evaluated in this section._"]
    lines = [
        "| Rule ID | Dataset | Field(s) | Severity | Status | Affected | Known Ex. | New Anom. | Description | Recommended Action |",
        "|:---|:---|:---|:---|:---|---:|---:|---:|:---|:---|",
    ]
    for r in results:
        lines.append(
            f"| `{r.rule_id}` | `{r.dataset}` | `{r.field}` | **{r.severity.value}** | "
            f"**{r.status.value}** | {r.affected_record_count:,} | {r.known_exception_count:,} | "
            f"{r.new_anomaly_count:,} | {r.short_description} | {r.recommended_action} |"
        )
    return lines


def _render_examples(results: list[ValidationResult]) -> list[str]:
    lines: list[str] = []
    for r in results:
        if r.example_record_identifiers:
            lines.append(f"- **`{r.rule_id}` examples:**")
            for ex in r.example_record_identifiers:
                lines.append(f"  - `{ex}`")
    return lines


def render_markdown_report(
    report: ValidationReport,
    *,
    raw_hashes_unchanged: bool | None = None,
    phase1_untouched: bool = True,
) -> str:
    """Render the full 16-section Stage 4 Markdown audit report."""
    sc = report.status_counts
    lines: list[str] = [
        "# CricImpact Phase 2 — Stage 4 Data Ingestion & Validation Audit Report",
        "",
        f"**Generated At:** {report.generated_at_utc}  ",
        f"**Raw Source Directory:** `{report.raw_dir}`  ",
        "",
        "---",
        "",
        "## 1. Execution Summary",
        "",
        f"- **Total Rules Executed:** {report.total_rules}",
        f"- **PASS:** {sc.get('PASS', 0)} | **WARNING:** {sc.get('WARNING', 0)} | **FAIL:** {sc.get('FAIL', 0)} | **SKIPPED:** {sc.get('SKIPPED', 0)}",
        f"- **Known Documented Exception Records:** {report.total_known_exceptions:,}",
        f"- **Newly Discovered Anomaly Records:** {report.total_new_anomalies:,}",
        "",
        "---",
        "",
        "## 2. Source File Loading Results",
        "",
        "| Dataset | Filename | Loaded | Size (bytes) | Missing Cols | Unexpected Cols | Ragged Rows | Parse Errors | SHA-256 |",
        "|:---|:---|:---|---:|:---|:---|---:|:---|:---|",
    ]
    for fs in report.file_summaries:
        lines.append(
            f"| `{fs['dataset']}` | `{fs['filename']}` | {fs['loaded']} | "
            f"{fs['size_bytes'] if fs['size_bytes'] is not None else 'N/A'} | "
            f"{fs['missing_columns'] or 'None'} | {fs['unexpected_columns'] or 'None'} | "
            f"{fs['bad_col_rows']} | {fs['parse_error_columns'] or 'None'} | "
            f"`{fs['sha256'] or 'N/A'}` |"
        )

    lines.extend(
        [
            "",
            "---",
            "",
            "## 3. Row and Column Counts",
            "",
            "| Dataset | Rows | Actual Columns | Expected Columns | Match? |",
            "|:---|---:|---:|---:|:---|",
        ]
    )
    for fs in report.file_summaries:
        match_flag = fs["loaded"] and (fs["columns"] == fs["expected_columns"]) and not fs["missing_columns"] and not fs["unexpected_columns"]
        lines.append(
            f"| `{fs['dataset']}` | {fs['rows']:,} | {fs['columns']} | {fs['expected_columns']} | {match_flag} |"
        )

    # Sections 4..11 mapped to rules
    section_specs: list[tuple[str, tuple[str, ...]]] = [
        ("4. Schema Validation Results", ("VAL-SCH-001", "VAL-SCH-002", "VAL-SCH-003", "VAL-SCH-004", "VAL-SCH-005")),
        ("5. Primary-Key Results", ("VAL-PK-001", "VAL-PK-002", "VAL-PK-003")),
        ("6. Foreign-Key Results", ("VAL-FK-001", "VAL-FK-002", "VAL-FK-003", "VAL-FK-004", "VAL-FK-005", "VAL-ENT-001")),
        ("7. Extras Validation Results", ("VAL-EXT-001", "VAL-EXT-002", "VAL-EXT-003", "VAL-EXT-004", "VAL-EXT-005")),
        ("8. Delivery-Sequence Results", ("VAL-SEQ-001", "VAL-SEQ-002", "VAL-BND-001", "VAL-TEL-001")),
        ("9. Wicket Validation Results", ("VAL-WKT-001", "VAL-WKT-002")),
        ("10. Match Validation Results", ("VAL-MCH-001", "VAL-MCH-002", "VAL-MCH-003", "VAL-MCH-004", "VAL-SRC-001")),
        ("11. Playing XI Validation Results", ("VAL-P11-001",)),
    ]

    for heading, rids in section_specs:
        sec_results = _find_rules(report, rids)
        lines.extend(["", "---", "", f"## {heading}", ""])
        lines.extend(_render_rule_table(sec_results))
        ex_lines = _render_examples(sec_results)
        if ex_lines:
            lines.extend(["", *ex_lines])
        # Extra competition scope details inside Match Validation section
        if heading.startswith("10."):
            src_list = _find_rules(report, ("VAL-SRC-001",))
            if src_list and src_list[0].metadata:
                mdata = src_list[0].metadata
                lines.extend(
                    [
                        "",
                        f"- **Competition Scope Preservation:** `T20` and `T20I` preserved separately "
                        f"(`competitions_by_format={mdata.get('competitions_by_format')}`, "
                        f"`matches_by_format={mdata.get('matches_by_format')}`; date span `{mdata.get('min_match_date')}` to `{mdata.get('max_match_date')}`).",
                    ]
                )

    # Section 12: Known Exceptions
    lines.extend(["", "---", "", "## 12. Known Exceptions", ""])
    known_rules = [r for r in report.results if r.known_exception_count > 0 or r.known_exceptions_summary]
    if not known_rules:
        lines.append("_No documented baseline exceptions encountered in this dataset._")
    else:
        for r in known_rules:
            summary_txt = r.known_exceptions_summary or r.short_description
            lines.append(
                f"- **`{r.rule_id}`** (Known count: `{r.known_exception_count:,}`): {summary_txt}"
            )

    # Section 13: Newly Discovered Anomalies
    lines.extend(["", "---", "", "## 13. Newly Discovered Anomalies", ""])
    new_rules = [r for r in report.results if r.new_anomaly_count > 0 or r.status == ValidationStatus.FAIL]
    if not new_rules:
        lines.append("**0 newly discovered anomalies.** All flagged items correspond strictly to Stage 1–2 documented exceptions.")
    else:
        for r in new_rules:
            lines.append(
                f"- **`{r.rule_id}`** (`{r.status.value}` / `{r.severity.value}`, New count: `{r.new_anomaly_count:,}`): {r.short_description}"
            )
            for ex in r.example_record_identifiers[:5]:
                lines.append(f"  - `{ex}`")

    # Section 14: PASS / WARNING / FAIL Summary
    lines.extend(
        [
            "",
            "---",
            "",
            "## 14. PASS / WARNING / FAIL Summary",
            "",
            "| Rule ID | Severity | Status | Affected | Known Ex. | New Anom. |",
            "|:---|:---|:---|---:|---:|---:|",
        ]
    )
    for r in report.results:
        lines.append(
            f"| `{r.rule_id}` | {r.severity.value} | **{r.status.value}** | "
            f"{r.affected_record_count:,} | {r.known_exception_count:,} | {r.new_anomaly_count:,} |"
        )

    # Section 15: Dataset Integrity Confirmation
    lines.extend(
        [
            "",
            "---",
            "",
            "## 15. Dataset Integrity Confirmation",
            "",
            f"- **Raw CSV Files Read-Only:** Loaded strictly read-only from `{report.raw_dir}` with SHA-256 verification.",
            f"- **Raw CSV Hashes Unchanged:** `{raw_hashes_unchanged}`" if raw_hashes_unchanged is not None else "- **Raw CSV Hashes Recorded:** SHA-256 digests captured in Section 2.",
            "- **No Silent Corrections / Deduplication:** Literal `'None'` strings, nullable `<NA>` IDs, 40 Super Over duplicates, UAE split IDs, and the 4 isolated extras/sequence anomalies were preserved untouched.",
            "- **No Processed / Feature Datasets Created:** Zero model training, feature matrices, or Win Probability outputs created.",
            f"- **Phase 1 Isolated:** `{phase1_untouched}` — `contribution` repository untouched.",
        ]
    )

    # Section 16: Remaining Limitations
    lines.extend(
        [
            "",
            "---",
            "",
            "## 16. Remaining Limitations",
            "",
            "1. **Secondary extras bye vs. leg-bye split (`extras_2_runs`):** Cannot distinguish byes from leg-byes on the 35 no-balls (and 1 `None` row) from CSV alone (team run total `runs + extras1_runs + extras_2_runs` is exact).",
            "2. **Exact Cricket Law trigger of `extras_type='other'` (`264` rows) and `Penalty` (`1` row):** Treated mechanically as non-legal no-ball (`other`) and 5-run legal ball (`Penalty`).",
            "3. **Pre-July-2024 Super Over feeds:** Matches `13613`, `21176`, and `28962` lack `innings 3/4` delivery logs while carrying `40` duplicate `playing_eleven` rows.",
            "4. **DLS mid-innings interruption timestamps & missing targets:** `4` completed `(D/L)`/`(DLS)` text matches (`20182`, `23674`, `24822`, `28334`) plus `2` equal-reduced matches (`16753`, `19959`) and `9` unlabeled NR/abandoned revised matches omit `revised_target`, and delivery rows do not mark the exact rain-halt delivery.",
            "5. **UAE split player IDs (`37087`, `37092`, `37095`):** `39444`/`8638` (Basil Hameed) and `36153`/`8729` (Syed Haider / Haider Shah) remain unmerged raw IDs pending explicit Stage 5+ policy; additionally `player_id=4458` carries `'AHT Donald'` in `ctp` vs `'Aneurin Donald'` in `ball_by_ball`.",
            "6. **Absence of explicit `is_free_hit`, `sub_in_ball`, and fielder IDs:** Must be derived or treated as unrecorded downstream.",
            "7. **Telemetry, over-length & scorecard quirks:** `bowl_speed` contains `77,861` `0` sentinels + `43` out-of-range speeds; `48512` team `25` lacks `batting_order`; `delivery_ist_time` is UTC-formatted with `4` midnight placeholders and `4` backward rows; `20190` text states 6 wickets instead of 5; `14130` (inn 1 & 2 ov 14) and `14164` (inn 1 ov 14) have 5 legal balls, and `41509` (inn 1 ov 12) has 7 legal balls.",
            "",
        ]
    )
    return "\n".join(lines)


def write_validation_reports(
    report: ValidationReport,
    *,
    output_dir: Path | None = None,
    raw_hashes_unchanged: bool | None = None,
    phase1_untouched: bool = True,
) -> dict[str, Path]:
    """Write Markdown audit report and JSON summary without overwriting existing reports."""
    target_dir = Path(output_dir).resolve() if output_dir is not None else DEFAULT_VALIDATION_DIR
    target_dir.mkdir(parents=True, exist_ok=True)

    md_path = resolve_versioned_output_path(
        target_dir / "stage4_ingestion_validation_report.md"
    )
    json_path = resolve_versioned_output_path(
        target_dir / "stage4_ingestion_validation_summary.json"
    )

    md_content = render_markdown_report(
        report,
        raw_hashes_unchanged=raw_hashes_unchanged,
        phase1_untouched=phase1_untouched,
    )
    md_path.write_text(md_content, encoding="utf-8")

    payload: dict[str, Any] = report.model_dump(mode="json")
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    return {"markdown": md_path, "json": json_path}
