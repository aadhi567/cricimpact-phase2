"""Extras semantics, team-runs arithmetic, legal-delivery derivation, and anomaly validation (Stage 4 Phase 3C)."""

from __future__ import annotations

import pandas as pd

from ml.ingestion.csv_loader import DatasetLoadBundle
from ml.ingestion.dataset_registry import (
    KNOWN_EXCEPTIONS,
    NON_LEGAL_EXTRAS_TYPES,
    VALID_EXTRAS_TYPES,
)
from ml.validation.validation_engine import (
    Severity,
    ValidationResult,
    ValidationStatus,
    check_required_columns,
    format_row_id,
    make_skipped_result,
)


def derive_team_runs(bbb: pd.DataFrame) -> pd.Series:
    """Approved Phase 2 scoring formula (derived validation field, non-mutating)."""
    return (
        bbb["runs"].fillna(0)
        + bbb["extras1_runs"].fillna(0)
        + bbb["extras_2_runs"].fillna(0)
    )


def derive_is_legal_delivery(bbb: pd.DataFrame) -> pd.Series:
    """Approved legal-delivery classification: extras_type not in {'wide', 'Overstep', 'other'}."""
    return ~bbb["extras_type"].astype(str).isin(NON_LEGAL_EXTRAS_TYPES)


def validate_extras(bundle: DatasetLoadBundle) -> list[ValidationResult]:
    """Execute VAL-EXT-001..004 on ball_by_ball.csv."""
    return [
        _check_val_ext_001_legacy_regression_guard(bundle),
        _check_val_ext_002_extras_type_vocab(bundle),
        _check_val_ext_003_extras_arithmetic_invariants(bundle),
        _check_val_ext_004_known_tagging_anomalies(bundle),
    ]


def _check_val_ext_001_legacy_regression_guard(
    bundle: DatasetLoadBundle,
) -> ValidationResult:
    req = {"ball_by_ball": ("match_id", "innings", "overid", "over_ball_num", "extras_type", "extras1_runs")}
    skip_reason = check_required_columns(bundle, req)
    if skip_reason:
        return make_skipped_result(
            rule_id="VAL-EXT-001",
            dataset="ball_by_ball",
            field="extras_type, extras1_runs",
            severity=Severity.CRITICAL,
            reason=skip_reason,
            recommended_action="Ensure ball_by_ball extras columns are present and parsed.",
        )

    bbb = bundle.get("ball_by_ball")
    assert bbb is not None
    if not pd.api.types.is_numeric_dtype(bbb["extras1_runs"].dtype):
        return make_skipped_result(
            rule_id="VAL-EXT-001",
            dataset="ball_by_ball",
            field="extras_type, extras1_runs",
            severity=Severity.CRITICAL,
            reason="extras1_runs failed numeric integer parsing.",
            recommended_action="Inspect VAL-SCH-002 parse errors first.",
        )

    none_rows = bbb.loc[bbb["extras_type"].astype(str) == "None"]
    total_none = int(len(none_rows))
    if total_none == 0:
        return ValidationResult(
            rule_id="VAL-EXT-001",
            dataset="ball_by_ball",
            field="extras_type, extras1_runs",
            severity=Severity.CRITICAL,
            status=ValidationStatus.FAIL,
            affected_record_count=0,
            new_anomaly_count=0,
            short_description="Zero extras_type='None' rows found; possible literal 'None' -> NaN coercion or corrupt feed.",
            recommended_action="Abort and inspect CSV null-value parsing (literal 'None' must be preserved).",
        )

    zero_count = int((none_rows["extras1_runs"] == 0).sum())
    zero_rate = zero_count / total_none
    legacy_six = none_rows.loc[none_rows["extras1_runs"] == 6]
    nonzero_none = none_rows.loc[none_rows["extras1_runs"] != 0]

    known_coords: frozenset[tuple[int, int, int, int]] = KNOWN_EXCEPTIONS["extras_none_with_e1_coords"]  # type: ignore[assignment]
    known_cnt = 0
    for _, r in nonzero_none.iterrows():
        coord = (int(r["match_id"]), int(r["innings"]), int(r["overid"]), int(r["over_ball_num"]))
        if coord in known_coords:
            known_cnt += 1

    passes = (zero_rate >= 0.9999) and (len(legacy_six) == 0)
    examples = [
        f"{format_row_id(r, ['match_id', 'innings', 'overid', 'over_ball_num', 'extras1_runs'])}"
        for _, r in nonzero_none.head(5).iterrows()
    ]

    return ValidationResult(
        rule_id="VAL-EXT-001",
        dataset="ball_by_ball",
        field="extras_type, extras1_runs",
        severity=Severity.CRITICAL,
        status=ValidationStatus.PASS if passes else ValidationStatus.FAIL,
        affected_record_count=int(len(nonzero_none)),
        known_exception_count=known_cnt if passes else 0,
        new_anomaly_count=0 if passes else int(len(nonzero_none)),
        short_description=(
            f"Regression guard passed: {zero_count:,}/{total_none:,} ({zero_rate * 100:.5f}%) "
            "extras_type='None' rows have extras1_runs=0; 0 rows with legacy code 6."
            if passes
            else f"Regression guard FAILED: None-row extras1_runs==0 rate={zero_rate * 100:.4f}%, extras1_runs==6 count={len(legacy_six)}."
        ),
        example_record_identifiers=examples,
        recommended_action="Abort immediately if extras1_runs==6 or non-zero rate on 'None' exceeds 0.01% (legacy Phase 1 schema risk).",
        known_exceptions_summary="1 known documented row (match 36097 inn 2 8.6) with None|e1=1 covered in VAL-EXT-004.",
        metadata={
            "none_rows": total_none,
            "none_with_e1_zero": zero_count,
            "none_zero_rate": round(zero_rate, 6),
            "legacy_e1_eq_6_count": int(len(legacy_six)),
        },
    )


def _check_val_ext_002_extras_type_vocab(bundle: DatasetLoadBundle) -> ValidationResult:
    req = {"ball_by_ball": ("match_id", "innings", "overid", "over_ball_num", "extras_type")}
    skip_reason = check_required_columns(bundle, req)
    if skip_reason:
        return make_skipped_result(
            rule_id="VAL-EXT-002",
            dataset="ball_by_ball",
            field="extras_type",
            severity=Severity.CRITICAL,
            reason=skip_reason,
            recommended_action="Ensure ball_by_ball.extras_type is loaded.",
        )

    bbb = bundle.get("ball_by_ball")
    assert bbb is not None
    et_str = bbb["extras_type"].fillna("<NA>").astype(str)
    bad = bbb.loc[~et_str.isin(VALID_EXTRAS_TYPES)]
    counts = et_str.value_counts().to_dict()
    legal_mask = derive_is_legal_delivery(bbb.loc[et_str.isin(VALID_EXTRAS_TYPES)])

    examples = [
        f"extras_type={r['extras_type']!r} at {format_row_id(r, ['match_id', 'innings', 'overid', 'over_ball_num'])}"
        for _, r in bad.head(8).iterrows()
    ]
    status = ValidationStatus.PASS if len(bad) == 0 else ValidationStatus.FAIL
    return ValidationResult(
        rule_id="VAL-EXT-002",
        dataset="ball_by_ball",
        field="extras_type",
        severity=Severity.CRITICAL,
        status=status,
        affected_record_count=int(len(bad)),
        new_anomaly_count=int(len(bad)),
        short_description=(
            f"All {len(bbb):,} rows use the 7 approved extras_type values; derived is_legal_delivery counts "
            f"{int(legal_mask.sum()):,} legal and {int((~legal_mask).sum()):,} illegal (wide/Overstep/other)."
            if len(bad) == 0
            else f"Detected {len(bad)} row(s) with unapproved extras_type values."
        ),
        example_record_identifiers=examples,
        recommended_action="Halt ingestion and inspect unknown extras_type categories before legal-ball logic runs.",
        metadata={
            "extras_type_counts": {str(k): int(v) for k, v in counts.items()},
            "derived_legal_count": int(legal_mask.sum()),
            "derived_illegal_count": int((~legal_mask).sum()),
        },
    )


def _check_val_ext_003_extras_arithmetic_invariants(
    bundle: DatasetLoadBundle,
) -> ValidationResult:
    req = {
        "ball_by_ball": (
            "match_id",
            "innings",
            "overid",
            "over_ball_num",
            "runs",
            "extras_type",
            "extras1_runs",
            "extras_2_runs",
        )
    }
    skip_reason = check_required_columns(bundle, req)
    if skip_reason:
        return make_skipped_result(
            rule_id="VAL-EXT-003",
            dataset="ball_by_ball",
            field="runs, extras_type, extras1_runs, extras_2_runs",
            severity=Severity.CRITICAL,
            reason=skip_reason,
            recommended_action="Ensure scoring columns are present in ball_by_ball.",
        )

    bbb = bundle.get("ball_by_ball")
    assert bbb is not None
    for col in ("runs", "extras1_runs", "extras_2_runs"):
        if not pd.api.types.is_numeric_dtype(bbb[col].dtype):
            return make_skipped_result(
                rule_id="VAL-EXT-003",
                dataset="ball_by_ball",
                field=col,
                severity=Severity.CRITICAL,
                reason=f"{col} failed integer parsing.",
                recommended_action="Inspect VAL-SCH-002 parse errors first.",
            )

    et = bbb["extras_type"].astype(str)
    team_runs = derive_team_runs(bbb)

    bad_runs = ~bbb["runs"].between(0, 6)
    bad_e1 = bbb["extras1_runs"] < 0
    bad_e2 = bbb["extras_2_runs"] < 0
    bad_nb_e1 = et.isin({"Overstep", "other"}) & (bbb["extras1_runs"] != 1)
    bad_wide_byes_runs = et.isin({"wide", "byes"}) & (bbb["runs"] != 0)
    bad_penalty = (et == "Penalty") & ((bbb["runs"] != 0) | (bbb["extras1_runs"] <= 0))
    bad_e2_with_bat_runs = (bbb["extras_2_runs"] > 0) & (bbb["runs"] != 0)

    hard_mask = (
        bad_runs
        | bad_e1
        | bad_e2
        | bad_nb_e1
        | bad_wide_byes_runs
        | bad_penalty
        | bad_e2_with_bat_runs
    )
    bad_df = bbb.loc[hard_mask]
    examples = [
        f"{format_row_id(r, ['match_id', 'innings', 'overid', 'over_ball_num', 'extras_type', 'runs', 'extras1_runs', 'extras_2_runs'])}"
        for _, r in bad_df.head(8).iterrows()
    ]

    e2_nonzero = bbb.loc[bbb["extras_2_runs"] > 0]
    e2_breakdown = (
        e2_nonzero.groupby(["extras_type", "extras1_runs", "extras_2_runs"], dropna=False)
        .size()
        .to_dict()
    )

    status = ValidationStatus.PASS if len(bad_df) == 0 else ValidationStatus.FAIL
    return ValidationResult(
        rule_id="VAL-EXT-003",
        dataset="ball_by_ball",
        field="runs, extras_type, extras1_runs, extras_2_runs",
        severity=Severity.CRITICAL,
        status=status,
        affected_record_count=int(len(bad_df)),
        new_anomaly_count=int(len(bad_df)),
        short_description=(
            f"All arithmetic invariants passed (team_runs = runs + extras1_runs + extras_2_runs; "
            f"total team runs={int(team_runs.sum()):,}; {len(e2_nonzero)} extras_2_runs>0 rows preserve unresolved bye/legbye split)."
            if len(bad_df) == 0
            else f"{len(bad_df)} delivery row(s) violated critical extras arithmetic constraints."
        ),
        example_record_identifiers=examples,
        recommended_action="Halt on negative runs, non-1 penalty on Overstep/other, or non-zero bat runs on wide/byes.",
        metadata={
            "bad_runs": int(bad_runs.sum()),
            "bad_e1_negative": int(bad_e1.sum()),
            "bad_e2_negative": int(bad_e2.sum()),
            "bad_noball_e1_not_1": int(bad_nb_e1.sum()),
            "bad_wide_or_byes_with_bat_runs": int(bad_wide_byes_runs.sum()),
            "bad_penalty_rows": int(bad_penalty.sum()),
            "bad_e2_with_bat_runs": int(bad_e2_with_bat_runs.sum()),
            "total_team_runs": int(team_runs.sum()),
            "extras_2_runs_nonzero_rows": int(len(e2_nonzero)),
            "extras_2_runs_breakdown": {str(k): int(v) for k, v in e2_breakdown.items()},
        },
    )


def _check_val_ext_004_known_tagging_anomalies(
    bundle: DatasetLoadBundle,
) -> ValidationResult:
    req = {
        "ball_by_ball": (
            "match_id",
            "innings",
            "overid",
            "over_ball_num",
            "innings_ball_num",
            "runs",
            "extras_type",
            "extras1_runs",
            "extras_2_runs",
        )
    }
    skip_reason = check_required_columns(bundle, req)
    if skip_reason:
        return make_skipped_result(
            rule_id="VAL-EXT-004",
            dataset="ball_by_ball",
            field="extras_type, runs, extras1_runs, extras_2_runs",
            severity=Severity.WARNING,
            reason=skip_reason,
            recommended_action="Ensure ball_by_ball extras columns load cleanly.",
        )

    bbb = bundle.get("ball_by_ball")
    assert bbb is not None
    et = bbb["extras_type"].astype(str)

    none_with_e1 = (et == "None") & (bbb["extras1_runs"] > 0)
    none_with_e2 = (et == "None") & (bbb["extras_2_runs"] > 0)
    legbyes_e1_zero_or_bat = (et == "legbyes") & ((bbb["extras1_runs"] == 0) | (bbb["runs"] > 0))
    byes_e1_zero = (et == "byes") & (bbb["extras1_runs"] == 0)
    wide_e1_zero = (et == "wide") & (bbb["extras1_runs"] == 0)

    anom_mask = none_with_e1 | none_with_e2 | legbyes_e1_zero_or_bat | byes_e1_zero | wide_e1_zero
    anom_df = bbb.loc[anom_mask]

    if len(anom_df) == 0:
        return ValidationResult(
            rule_id="VAL-EXT-004",
            dataset="ball_by_ball",
            field="extras_type, runs, extras1_runs, extras_2_runs",
            severity=Severity.WARNING,
            status=ValidationStatus.PASS,
            affected_record_count=0,
            short_description="0 extras tagging anomalies detected.",
            recommended_action="None required.",
        )

    known_coords: set[tuple[int, int, int, int]] = set()
    known_coords |= KNOWN_EXCEPTIONS["extras_none_with_e1_coords"]  # type: ignore[arg-type]
    known_coords |= KNOWN_EXCEPTIONS["extras_none_with_e2_coords"]  # type: ignore[arg-type]
    known_coords |= KNOWN_EXCEPTIONS["extras_legbyes_with_run_coords"]  # type: ignore[arg-type]

    known_count = 0
    new_count = 0
    examples: list[str] = []
    for _, r in anom_df.iterrows():
        coord = (int(r["match_id"]), int(r["innings"]), int(r["overid"]), int(r["over_ball_num"]))
        is_known = coord in known_coords
        if is_known:
            known_count += 1
        else:
            new_count += 1
        if len(examples) < 10:
            tag = "KNOWN" if is_known else "NEW"
            examples.append(
                f"[{tag}] {format_row_id(r, ['match_id', 'innings', 'overid', 'over_ball_num', 'innings_ball_num', 'extras_type', 'runs', 'extras1_runs', 'extras_2_runs'])}"
            )

    # Contract threshold: <= 5 legacy anomalies allowed under WARNING
    exceeds_bound = len(anom_df) > 5
    status = ValidationStatus.FAIL if exceeds_bound else ValidationStatus.WARNING

    return ValidationResult(
        rule_id="VAL-EXT-004",
        dataset="ball_by_ball",
        field="extras_type, runs, extras1_runs, extras_2_runs",
        severity=Severity.WARNING,
        status=status,
        affected_record_count=int(len(anom_df)),
        known_exception_count=known_count,
        new_anomaly_count=new_count,
        short_description=(
            f"Found {len(anom_df)} isolated extras tagging anomalies ({known_count} known legacy, {new_count} new); "
            "team_runs = runs + extras1_runs + extras_2_runs remains preserved without silent edits."
        ),
        example_record_identifiers=examples,
        recommended_action=(
            "Exceeds bounded threshold (>5) — inspect new tagging errors immediately."
            if exceeds_bound
            else "Preserve raw team_runs; handle 37099 inn 1 14.1 batter-credit nuance only in player batting analytics."
        ),
        known_exceptions_summary=(
            "Known 3 anomalies preserved: (1) 36097 inn 2 8.6 (None|1|0), "
            "(2) 17555 inn 1 5.4 (None|0|1), (3) 37099 inn 1 14.1 (legbyes|0|0, runs=1)."
        ),
        metadata={
            "none_with_e1": int(none_with_e1.sum()),
            "none_with_e2": int(none_with_e2.sum()),
            "legbyes_e1_zero_or_bat": int(legbyes_e1_zero_or_bat.sum()),
            "byes_e1_zero": int(byes_e1_zero.sum()),
            "wide_e1_zero": int(wide_e1_zero.sum()),
        },
    )

