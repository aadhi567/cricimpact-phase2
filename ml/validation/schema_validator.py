"""Schema, type, non-null, sentinel, and domain validation (Stage 4 Phase 3A)."""

from __future__ import annotations

import re

import pandas as pd

from ml.ingestion.csv_loader import DatasetLoadBundle
from ml.ingestion.dataset_registry import DATASET_ORDER, DATASET_SPECS
from ml.validation.validation_engine import (
    Severity,
    ValidationResult,
    ValidationStatus,
    format_row_id,
)


_UTC_TS_RE = re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} UTC$")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def validate_schema(bundle: DatasetLoadBundle) -> list[ValidationResult]:
    """Execute VAL-SCH-001..005 across all six raw datasets."""
    results: list[ValidationResult] = []
    results.append(_check_val_sch_001_files_headers_ragged(bundle))
    results.append(_check_val_sch_002_data_types(bundle))
    results.append(_check_val_sch_003_required_non_nulls(bundle))
    results.append(_check_val_sch_004_ranges_and_domains(bundle))
    results.append(_check_val_sch_005_sentinel_inventory(bundle))
    return results


def _check_val_sch_001_files_headers_ragged(
    bundle: DatasetLoadBundle,
) -> ValidationResult:
    hard_fail_tables = 0
    warn_only_tables = 0
    bad_rows_total = 0
    examples: list[str] = []
    per_table: dict[str, dict[str, object]] = {}

    for name in DATASET_ORDER:
        spec = DATASET_SPECS[name]
        s = bundle.summaries[name]
        hard_issues: list[str] = []
        soft_issues: list[str] = []
        if not s.exists:
            hard_issues.append("file_missing")
        elif not s.readable or not s.loaded:
            hard_issues.append(f"unreadable({s.error_message})")
        if s.missing_columns:
            hard_issues.append(f"missing_cols={list(s.missing_columns)}")
        if s.bad_col_rows > 0:
            hard_issues.append(f"bad_col_rows={s.bad_col_rows}")
            bad_rows_total += s.bad_col_rows
        if s.unexpected_columns:
            soft_issues.append(f"unexpected_cols={list(s.unexpected_columns)}")
        if s.order_mismatch:
            soft_issues.append("column_order_mismatch")

        per_table[name] = {
            "exists": s.exists,
            "loaded": s.loaded,
            "rows": s.row_count,
            "columns": s.column_count,
            "expected_columns": spec.column_count,
            "missing_columns": list(s.missing_columns),
            "unexpected_columns": list(s.unexpected_columns),
            "bad_col_rows": s.bad_col_rows,
            "order_mismatch": s.order_mismatch,
        }
        all_issues = hard_issues + soft_issues
        if hard_issues:
            hard_fail_tables += 1
        elif soft_issues:
            warn_only_tables += 1
        if all_issues and len(examples) < 10:
            extra = f" | bad_row_examples={list(s.bad_col_row_examples)}" if s.bad_col_row_examples else ""
            examples.append(f"{s.filename}: {'; '.join(all_issues)}{extra}")

    if hard_fail_tables > 0:
        status = ValidationStatus.FAIL
    elif warn_only_tables > 0:
        status = ValidationStatus.WARNING
    else:
        status = ValidationStatus.PASS

    affected = bad_rows_total if bad_rows_total > 0 else (hard_fail_tables + warn_only_tables)
    return ValidationResult(
        rule_id="VAL-SCH-001",
        dataset="all_raw_csvs",
        field="*",
        severity=Severity.CRITICAL,
        status=status,
        affected_record_count=affected,
        new_anomaly_count=affected,
        short_description=(
            "All 6 raw CSVs present with exact column names, counts (4, 22, 3, 6, 9, 33), and 0 ragged rows."
            if status == ValidationStatus.PASS
            else (
                f"{warn_only_tables} file(s) contain unexpected extra columns or column-order differences (preserved without discarding data)."
                if status == ValidationStatus.WARNING
                else f"{hard_fail_tables} file(s) failed presence, required-column, or ragged-row checks (unexpected extra columns preserved)."
            )
        ),
        example_record_identifiers=examples,
        recommended_action="Halt ingestion on missing files/columns or ragged rows; flag unexpected extra columns without discarding data.",
        metadata={"tables": per_table},
    )


def _check_val_sch_002_data_types(bundle: DatasetLoadBundle) -> ValidationResult:
    total_bad = 0
    examples: list[str] = []
    available_tables = 0
    bad_details: dict[str, dict[str, int]] = {}

    for name in DATASET_ORDER:
        spec = DATASET_SPECS[name]
        summary = bundle.summaries[name]
        df = bundle.get(name)
        if df is None:
            continue
        available_tables += 1

        if summary.parse_error_columns:
            bad_details[name] = dict(summary.parse_error_columns)
            for col, cnt in summary.parse_error_columns.items():
                total_bad += cnt
                for ex in summary.parse_error_examples.get(col, ())[:3]:
                    if len(examples) < 10:
                        examples.append(f"{name}.{col}: {ex}")

        for col in spec.date_columns:
            if col not in df.columns:
                continue
            non_null = df[col].dropna().astype(str)
            fmt_ok = non_null.str.match(_DATE_RE)
            parsed = pd.to_datetime(non_null, format="%Y-%m-%d", errors="coerce")
            bad = non_null.loc[~(fmt_ok & parsed.notna())]
            if len(bad) > 0:
                total_bad += int(len(bad))
                bad_details.setdefault(name, {})[col] = int(len(bad))
                for idx, val in bad.head(3).items():
                    if len(examples) < 10:
                        examples.append(f"{name}.{col} row_idx={idx}: invalid date {val!r}")

        for col in spec.timestamp_columns:
            if col not in df.columns:
                continue
            non_null = df[col].dropna().astype(str)
            fmt_ok = non_null.str.match(_UTC_TS_RE)
            parsed = pd.to_datetime(
                non_null, format="%Y-%m-%d %H:%M:%S UTC", errors="coerce"
            )
            bad = non_null.loc[~(fmt_ok & parsed.notna())]
            if len(bad) > 0:
                total_bad += int(len(bad))
                bad_details.setdefault(name, {})[col] = int(len(bad))
                for idx, val in bad.head(3).items():
                    if len(examples) < 10:
                        examples.append(
                            f"{name}.{col} row_idx={idx}: invalid UTC timestamp {val!r}"
                        )

    if available_tables == 0:
        return ValidationResult(
            rule_id="VAL-SCH-002",
            dataset="all_raw_csvs",
            field="typed_columns",
            severity=Severity.CRITICAL,
            status=ValidationStatus.SKIPPED,
            affected_record_count=0,
            short_description="Check skipped: no datasets loaded.",
            recommended_action="Resolve file loading errors first.",
        )

    status = ValidationStatus.PASS if total_bad == 0 else ValidationStatus.FAIL
    return ValidationResult(
        rule_id="VAL-SCH-002",
        dataset="all_raw_csvs",
        field="typed_columns",
        severity=Severity.CRITICAL,
        status=status,
        affected_record_count=total_bad,
        new_anomaly_count=total_bad,
        short_description=(
            f"All integer, float, boolean, date, and UTC timestamp columns parsed cleanly across {available_tables} loaded table(s)."
            if total_bad == 0
            else f"{total_bad} cell value(s) failed declared data type parsing."
        ),
        example_record_identifiers=examples,
        recommended_action="Halt ingestion and inspect malformed numeric, boolean, date, or timestamp fields.",
        metadata={"parse_errors": bad_details},
    )


def _check_val_sch_003_required_non_nulls(
    bundle: DatasetLoadBundle,
) -> ValidationResult:
    total_missing = 0
    examples: list[str] = []
    missing_by_col: dict[str, int] = {}
    available_tables = 0

    for name in DATASET_ORDER:
        spec = DATASET_SPECS[name]
        df = bundle.get(name)
        if df is None:
            continue
        available_tables += 1
        for col in spec.non_null_columns:
            if col not in df.columns:
                continue
            null_mask = df[col].isna()
            cnt = int(null_mask.sum())
            if cnt > 0:
                total_missing += cnt
                missing_by_col[f"{name}.{col}"] = cnt
                for idx in df.index[null_mask][:3]:
                    if len(examples) < 10:
                        pk_cols = [c for c in spec.primary_key if c in df.columns]
                        row_desc = format_row_id(df.loc[idx], pk_cols) if pk_cols else f"row_idx={idx}"
                        examples.append(f"{name}.{col} NULL at {row_desc}")

    if available_tables == 0:
        return ValidationResult(
            rule_id="VAL-SCH-003",
            dataset="all_raw_csvs",
            field="non_null_columns",
            severity=Severity.CRITICAL,
            status=ValidationStatus.SKIPPED,
            affected_record_count=0,
            short_description="Check skipped: no datasets loaded.",
            recommended_action="Resolve file loading errors first.",
        )

    status = ValidationStatus.PASS if total_missing == 0 else ValidationStatus.FAIL
    return ValidationResult(
        rule_id="VAL-SCH-003",
        dataset="all_raw_csvs",
        field="non_null_columns",
        severity=Severity.CRITICAL,
        status=status,
        affected_record_count=total_missing,
        new_anomaly_count=total_missing,
        short_description=(
            "Zero unexpected nulls in mandatory non-nullable columns (literal 'None' strings preserved intact)."
            if total_missing == 0
            else f"Found {total_missing} unexpected missing value(s) across mandatory non-nullable columns."
        ),
        example_record_identifiers=examples,
        recommended_action="Reject batch or inspect upstream exporter for unexpected blank required fields.",
        metadata={"missing_by_column": missing_by_col},
    )


def _check_val_sch_004_ranges_and_domains(
    bundle: DatasetLoadBundle,
) -> ValidationResult:
    total_invalid = 0
    examples: list[str] = []
    invalid_details: dict[str, int] = {}
    available_tables = 0

    for name in DATASET_ORDER:
        spec = DATASET_SPECS[name]
        df = bundle.get(name)
        if df is None:
            continue
        available_tables += 1
        pk_cols = [c for c in spec.primary_key if c in df.columns]

        for col, allowed in spec.categorical_domains.items():
            if col not in df.columns:
                continue
            non_null = df[col].dropna()
            bad_mask = ~non_null.astype(str).isin(allowed)
            cnt = int(bad_mask.sum())
            if cnt > 0:
                total_invalid += cnt
                invalid_details[f"{name}.{col} (categorical)"] = cnt
                for idx in non_null.index[bad_mask][:3]:
                    if len(examples) < 10:
                        ident = format_row_id(df.loc[idx], pk_cols) if pk_cols else f"row_idx={idx}"
                        examples.append(
                            f"{name}.{col}={df.loc[idx, col]!r} at {ident}"
                        )

        for col, (lo, hi) in spec.numeric_ranges.items():
            if col not in df.columns:
                continue
            if not pd.api.types.is_numeric_dtype(df[col].dtype):
                continue
            non_null = df[col].dropna()
            if len(non_null) == 0:
                continue
            bad_mask = pd.Series(False, index=non_null.index)
            if lo is not None:
                bad_mask = bad_mask | (non_null < lo)
            if hi is not None:
                bad_mask = bad_mask | (non_null > hi)
            cnt = int(bad_mask.sum())
            if cnt > 0:
                total_invalid += cnt
                invalid_details[f"{name}.{col} (range {lo}..{hi})"] = cnt
                for idx in non_null.index[bad_mask][:3]:
                    if len(examples) < 10:
                        ident = format_row_id(df.loc[idx], pk_cols) if pk_cols else f"row_idx={idx}"
                        examples.append(
                            f"{name}.{col}={df.loc[idx, col]} at {ident}"
                        )

    if available_tables == 0:
        return ValidationResult(
            rule_id="VAL-SCH-004",
            dataset="all_raw_csvs",
            field="domains_and_ranges",
            severity=Severity.CRITICAL,
            status=ValidationStatus.SKIPPED,
            affected_record_count=0,
            short_description="Check skipped: no datasets loaded.",
            recommended_action="Resolve file loading errors first.",
        )

    status = ValidationStatus.PASS if total_invalid == 0 else ValidationStatus.FAIL
    return ValidationResult(
        rule_id="VAL-SCH-004",
        dataset="all_raw_csvs",
        field="domains_and_ranges",
        severity=Severity.CRITICAL,
        status=status,
        affected_record_count=total_invalid,
        new_anomaly_count=total_invalid,
        short_description=(
            "All schema numeric bounds (IDs, innings, overid, runs, batting_order, 0/1 flags, revised ball allocations) and categorical enums passed."
            if total_invalid == 0
            else f"{total_invalid} out-of-range numeric or invalid categorical value(s) detected."
        ),
        example_record_identifiers=examples,
        recommended_action="Inspect invalid domain/range records before downstream processing.",
        metadata={"invalid_counts": invalid_details},
    )


def _check_val_sch_005_sentinel_inventory(
    bundle: DatasetLoadBundle,
) -> ValidationResult:
    """Log documented sentinel and nullable-field rates cleanly (INFO)."""
    inventory: dict[str, dict[str, int]] = {}
    logged_items = 0

    matches = bundle.get("matches")
    if matches is not None:
        m_inv: dict[str, int] = {}
        for col in (
            "home_team_captain_id",
            "away_team_captain_id",
            "toss_win_team_id",
            "toss_opted",
            "first_inn_revised_overs",
            "second_inn_revised_overs",
            "revised_target",
            "win_team_id",
        ):
            if col in matches.columns:
                m_inv[f"{col}_null"] = int(matches[col].isna().sum())
        if "man_of_the_match" in matches.columns and pd.api.types.is_numeric_dtype(
            matches["man_of_the_match"].dtype
        ):
            motm_zero = int((matches["man_of_the_match"] == 0).sum())
            m_inv["man_of_the_match_zero_sentinel"] = motm_zero
            logged_items += motm_zero
        inventory["matches"] = m_inv

    p11 = bundle.get("playing_eleven")
    if p11 is not None:
        p_inv: dict[str, int] = {}
        for col in ("batting_order", "is_captain", "is_wk"):
            if col in p11.columns:
                p_inv[f"{col}_null"] = int(p11[col].isna().sum())
        if "is_played" in p11.columns and pd.api.types.is_bool_dtype(p11["is_played"].dtype):
            p_inv["bench_rows_is_played_false"] = int((~p11["is_played"].fillna(False)).sum())
        inventory["playing_eleven"] = p_inv

    bbb = bundle.get("ball_by_ball")
    if bbb is not None:
        b_inv: dict[str, int] = {}
        if "bowl_speed" in bbb.columns and pd.api.types.is_numeric_dtype(
            bbb["bowl_speed"].dtype
        ):
            zero_speed = int((bbb["bowl_speed"] == 0).sum())
            b_inv["bowl_speed_zero_sentinel"] = zero_speed
            logged_items += zero_speed
        for col in ("stroke", "delivery_style"):
            if col in bbb.columns:
                blank_cnt = int(bbb[col].isna().sum())
                none_str_cnt = int((bbb[col].astype("string") == "None").sum())
                b_inv[f"{col}_null"] = blank_cnt
                b_inv[f"{col}_literal_None"] = none_str_cnt
                logged_items += blank_cnt + none_str_cnt
        for col in ("over_or_around", "dismissal_type", "dismissed_player_id"):
            if col in bbb.columns:
                b_inv[f"{col}_null"] = int(bbb[col].isna().sum())
        inventory["ball_by_ball"] = b_inv

    if not inventory:
        return ValidationResult(
            rule_id="VAL-SCH-005",
            dataset="matches,playing_eleven,ball_by_ball",
            field="sentinels_and_nullables",
            severity=Severity.INFO,
            status=ValidationStatus.SKIPPED,
            affected_record_count=0,
            short_description="Check skipped: target tables unavailable.",
            recommended_action="Ensure raw tables load cleanly.",
        )

    return ValidationResult(
        rule_id="VAL-SCH-005",
        dataset="matches,playing_eleven,ball_by_ball",
        field="man_of_the_match,bowl_speed,stroke,delivery_style,over_or_around",
        severity=Severity.INFO,
        status=ValidationStatus.PASS,
        affected_record_count=logged_items,
        known_exception_count=0,
        new_anomaly_count=0,
        short_description=(
            "Logged expected nullable rates and raw missing sentinels "
            "(man_of_the_match=0, bowl_speed=0, literal 'None' in stroke/delivery_style) without altering raw records."
        ),
        known_exceptions_summary=None,
        recommended_action="In Stage 5 preprocessing, treat man_of_the_match=0 and bowl_speed=0 as missing alongside explicit indicator flags.",
        metadata={"sentinel_inventory": inventory},
    )
