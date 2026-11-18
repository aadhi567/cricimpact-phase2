"""Delivery sequence, timestamp ordering, boundary flag, and bowl_speed validation (Stage 4 Phase 3D)."""

from __future__ import annotations

import pandas as pd

from ml.ingestion.csv_loader import DatasetLoadBundle
from ml.ingestion.dataset_registry import KNOWN_EXCEPTIONS
from ml.validation.extras_validator import derive_is_legal_delivery
from ml.validation.validation_engine import (
    Severity,
    ValidationResult,
    ValidationStatus,
    check_required_columns,
    format_row_id,
    make_skipped_result,
)


def validate_deliveries(bundle: DatasetLoadBundle) -> list[ValidationResult]:
    """Execute VAL-SEQ-001, VAL-SEQ-002, VAL-BND-001, and VAL-TEL-001."""
    return [
        _check_val_seq_001_over_and_ball_progression(bundle),
        _check_val_seq_002_delivery_timestamps(bundle),
        _check_val_bnd_001_boundary_flags(bundle),
        _check_val_tel_001_bowl_speed(bundle),
    ]


def _check_val_seq_001_over_and_ball_progression(
    bundle: DatasetLoadBundle,
) -> ValidationResult:
    req = {
        "ball_by_ball": (
            "match_id",
            "innings",
            "overid",
            "over_ball_num",
            "innings_ball_num",
            "extras_type",
        )
    }
    skip_reason = check_required_columns(bundle, req)
    if skip_reason:
        return make_skipped_result(
            rule_id="VAL-SEQ-001",
            dataset="ball_by_ball",
            field="overid, over_ball_num, innings_ball_num, extras_type",
            severity=Severity.WARNING,
            reason=skip_reason,
            recommended_action="Ensure ball_by_ball sequence columns are loaded cleanly.",
        )

    bbb = bundle.get("ball_by_ball")
    assert bbb is not None
    for col in ("match_id", "innings", "overid", "over_ball_num", "innings_ball_num"):
        if not pd.api.types.is_numeric_dtype(bbb[col].dtype):
            return make_skipped_result(
                rule_id="VAL-SEQ-001",
                dataset="ball_by_ball",
                field=col,
                severity=Severity.WARNING,
                reason=f"{col} failed numeric parsing.",
                recommended_action="Fix schema parse errors first.",
            )

    work = bbb[
        ["match_id", "innings", "overid", "over_ball_num", "innings_ball_num", "extras_type"]
    ].copy()
    work = work.sort_values(["match_id", "innings", "innings_ball_num"], kind="mergesort")
    work["_is_legal"] = derive_is_legal_delivery(work).astype("int64")

    # 1) Non-decreasing overid within (match_id, innings)
    over_diff = work.groupby(["match_id", "innings"], sort=False)["overid"].diff()
    backward_over_df = work.loc[over_diff < 0]
    skipped_over_df = work.loc[over_diff > 1]

    # 2) Contiguous over_ball_num 1..K within (match_id, innings, overid)
    ob_stats = (
        work.groupby(["match_id", "innings", "overid"], sort=False)["over_ball_num"]
        .agg(["count", "min", "max", "nunique"])
        .reset_index()
    )
    bad_ob = ob_stats.loc[
        (ob_stats["min"] != 1)
        | (ob_stats["max"] != ob_stats["count"])
        | (ob_stats["nunique"] != ob_stats["count"])
    ]

    # 3) Super Over overid == 1 check (innings >= 3)
    bad_so_overid = work.loc[(work["innings"] >= 3) & (work["overid"] != 1)]

    # 4) Legal-ball counts per over: mid-match overs must have 6 legal deliveries;
    #    no over (including final over) may exceed 6 legal deliveries.
    #    Deduplicate so a mid-match >6-ball over (e.g. 41509 inn 1 ov 12) is counted once.
    over_legal = (
        work.groupby(["match_id", "innings", "overid"], sort=False)["_is_legal"]
        .agg(legal_balls="sum", total_rows="count")
        .reset_index()
    )
    max_over_per_inn = (
        over_legal.groupby(["match_id", "innings"], sort=False)["overid"]
        .max()
        .rename("max_overid")
        .reset_index()
    )
    over_legal = over_legal.merge(max_over_per_inn, on=["match_id", "innings"], how="left")
    mid_match_overs = over_legal.loc[over_legal["overid"] < over_legal["max_overid"]]
    bad_mid_overs = mid_match_overs.loc[mid_match_overs["legal_balls"] != 6]
    over_gt_6 = over_legal.loc[over_legal["legal_balls"] > 6]
    final_over_gt_6 = over_legal.loc[
        (over_legal["overid"] == over_legal["max_overid"]) & (over_legal["legal_balls"] > 6)
    ]
    anomalous_legal_overs = over_legal.loc[
        ((over_legal["overid"] < over_legal["max_overid"]) & (over_legal["legal_balls"] != 6))
        | ((over_legal["overid"] == over_legal["max_overid"]) & (over_legal["legal_balls"] > 6))
    ]

    # 5) Check innings where innings_ball_num > derived legal balls (demonstrates difference)
    inn_totals = (
        work.groupby(["match_id", "innings"], sort=False)
        .agg(max_ib=("innings_ball_num", "max"), legal_balls=("_is_legal", "sum"))
        .reset_index()
    )
    innings_with_extras_inflation = int((inn_totals["max_ib"] != inn_totals["legal_balls"]).sum())

    known_incomplete: frozenset[tuple[int, int, int]] = KNOWN_EXCEPTIONS["incomplete_mid_match_overs"]  # type: ignore[assignment]
    known_cnt = 0
    new_over_cnt = 0
    examples: list[str] = []

    for _, r in backward_over_df.head(3).iterrows():
        examples.append(f"BACKWARD_OVER {format_row_id(r, ['match_id', 'innings', 'overid', 'innings_ball_num'])}")
    for _, r in skipped_over_df.head(3).iterrows():
        examples.append(f"SKIPPED_OVER {format_row_id(r, ['match_id', 'innings', 'overid', 'innings_ball_num'])}")
    for _, r in bad_ob.head(3).iterrows():
        examples.append(f"BAD_OVER_BALL {format_row_id(r, ['match_id', 'innings', 'overid', 'min', 'max', 'count'])}")
    for _, r in bad_so_overid.head(3).iterrows():
        examples.append(f"BAD_SO_OVERID {format_row_id(r, ['match_id', 'innings', 'overid', 'innings_ball_num'])}")
    for _, r in anomalous_legal_overs.iterrows():
        coord = (int(r["match_id"]), int(r["innings"]), int(r["overid"]))
        is_known = coord in known_incomplete and int(r["legal_balls"]) <= 6
        if is_known:
            known_cnt += 1
        else:
            new_over_cnt += 1
        if len(examples) < 10:
            tag = "KNOWN" if is_known else "NEW"
            label = "OVER_GT_6_LEGAL" if int(r["legal_balls"]) > 6 else "INCOMPLETE_MID_OVER"
            examples.append(
                f"[{tag}] {label} {format_row_id(r, ['match_id', 'innings', 'overid', 'legal_balls', 'total_rows'])}"
            )

    hard_seq_errors = (
        int(len(backward_over_df))
        + int(len(skipped_over_df))
        + int(len(bad_ob))
        + int(len(bad_so_overid))
    )
    total_affected = hard_seq_errors + int(len(anomalous_legal_overs))
    new_anomalies = hard_seq_errors + new_over_cnt

    if hard_seq_errors > 0:
        status = ValidationStatus.FAIL
    elif len(anomalous_legal_overs) > 0:
        status = ValidationStatus.WARNING
    else:
        status = ValidationStatus.PASS

    return ValidationResult(
        rule_id="VAL-SEQ-001",
        dataset="ball_by_ball",
        field="overid, over_ball_num, innings_ball_num, extras_type",
        severity=Severity.WARNING,
        status=status,
        affected_record_count=total_affected,
        known_exception_count=known_cnt,
        new_anomaly_count=new_anomalies,
        short_description=(
            f"0 backward/skipped overs, 0 over_ball_num gaps, 0 bad SO overids; "
            f"{len(anomalous_legal_overs)} over(s) with abnormal legal-ball count "
            f"(mid-match != 6: {len(bad_mid_overs)}, >6 legal: {len(over_gt_6)}; known={known_cnt}, new={new_over_cnt}). "
            f"innings_ball_num exceeds legal_balls in {innings_with_extras_inflation:,}/{len(inn_totals):,} innings."
            if hard_seq_errors == 0
            else f"Detected {hard_seq_errors} structural over/ball ordering violation(s) and {len(anomalous_legal_overs)} abnormal legal-ball over(s)."
        ),
        example_record_identifiers=examples[:10],
        recommended_action="Never rewrite raw over_ball_num or innings_ball_num; derive legal balls explicitly via cumsum(is_legal_delivery).",
        known_exceptions_summary="Known documented 5-legal-ball over: match 14130 innings 2 over 14 (5 legal + 1 wide).",
        metadata={
            "backward_overid": int(len(backward_over_df)),
            "skipped_overid": int(len(skipped_over_df)),
            "bad_over_ball_num": int(len(bad_ob)),
            "bad_super_over_overid": int(len(bad_so_overid)),
            "overs_over_6_legal_balls": int(len(over_gt_6)),
            "final_overs_over_6_legal_balls": int(len(final_over_gt_6)),
            "incomplete_mid_match_overs": int(len(bad_mid_overs)),
            "anomalous_legal_ball_overs": int(len(anomalous_legal_overs)),
            "innings_count": int(len(inn_totals)),
            "innings_where_ib_differs_from_legal_balls": innings_with_extras_inflation,
            "super_over_deliveries": int((work["innings"] >= 3).sum()),
            "super_over_matches": int(work.loc[work["innings"] >= 3, "match_id"].nunique()),
        },
    )


def _check_val_seq_002_delivery_timestamps(
    bundle: DatasetLoadBundle,
) -> ValidationResult:
    req = {"ball_by_ball": ("match_id", "innings", "innings_ball_num", "delivery_ist_time")}
    skip_reason = check_required_columns(bundle, req)
    if skip_reason:
        return make_skipped_result(
            rule_id="VAL-SEQ-002",
            dataset="ball_by_ball",
            field="delivery_ist_time",
            severity=Severity.INFO,
            reason=skip_reason,
            recommended_action="Ensure delivery_ist_time is loaded cleanly.",
        )

    bbb = bundle.get("ball_by_ball")
    assert bbb is not None
    work = bbb[["match_id", "innings", "innings_ball_num", "delivery_ist_time"]].copy()
    work = work.sort_values(["match_id", "innings", "innings_ball_num"], kind="mergesort")
    ts_str = work["delivery_ist_time"].fillna("").astype(str)
    parsed = pd.to_datetime(ts_str, format="%Y-%m-%d %H:%M:%S UTC", errors="coerce")
    unparseable = work.loc[parsed.isna()]

    midnight_mask = ts_str.str.endswith("00:00:00 UTC")
    midnight_matches = set(int(x) for x in work.loc[midnight_mask, "match_id"].dropna().unique())
    known_midnight: frozenset[int] = KNOWN_EXCEPTIONS["midnight_utc_placeholder_matches"]  # type: ignore[assignment]

    work["_ts"] = parsed
    ts_diff = work.groupby(["match_id", "innings"], sort=False)["_ts"].diff()
    backward_df = work.loc[ts_diff < pd.Timedelta(0)]
    known_back: frozenset[tuple[int, int, int]] = KNOWN_EXCEPTIONS["non_monotonic_timestamp_coords"]  # type: ignore[assignment]

    known_cnt = 0
    new_cnt = 0
    examples: list[str] = []

    for _, r in backward_df.iterrows():
        coord = (int(r["match_id"]), int(r["innings"]), int(r["innings_ball_num"]))
        is_known = coord in known_back
        if is_known:
            known_cnt += 1
        else:
            new_cnt += 1
        if len(examples) < 8:
            tag = "KNOWN" if is_known else "NEW"
            examples.append(
                f"[{tag}] BACKWARD_TS {format_row_id(r, ['match_id', 'innings', 'innings_ball_num', 'delivery_ist_time'])}"
            )

    new_midnight = midnight_matches - set(known_midnight)
    if midnight_matches:
        examples.append(f"MIDNIGHT_UTC_MATCHES={sorted(midnight_matches)}")

    if len(unparseable) > 0:
        status = ValidationStatus.FAIL
    elif new_cnt > 0 or len(new_midnight) > 0:
        status = ValidationStatus.WARNING
    else:
        status = ValidationStatus.PASS

    return ValidationResult(
        rule_id="VAL-SEQ-002",
        dataset="ball_by_ball",
        field="delivery_ist_time",
        severity=Severity.INFO,
        status=status,
        affected_record_count=int(len(unparseable)) + int(len(backward_df)) + len(midnight_matches),
        known_exception_count=known_cnt + len(midnight_matches & set(known_midnight)),
        new_anomaly_count=int(len(unparseable)) + new_cnt + len(new_midnight),
        short_description=(
            f"All timestamps parse cleanly as UTC strings (despite 'ist' column name); "
            f"{len(midnight_matches)} midnight placeholder match(es) and {len(backward_df)} non-monotonic timestamp row(s)."
        ),
        example_record_identifiers=examples[:10],
        recommended_action="Sort deliveries strictly by (match_id, innings, innings_ball_num); never sort by delivery_ist_time.",
        known_exceptions_summary=(
            "4 midnight-UTC matches (13511, 17737, 24354, 25158) and 4 non-monotonic rows "
            "(14104 inn 1 ib=8, 17737 inn 2 ib=7, 24354 inn 1 ib=102, 55078 inn 2 ib=69)."
        ),
        metadata={
            "unparseable_count": int(len(unparseable)),
            "midnight_utc_rows": int(midnight_mask.sum()),
            "midnight_utc_matches": sorted(midnight_matches),
            "backward_timestamp_rows": int(len(backward_df)),
        },
    )


def _check_val_bnd_001_boundary_flags(bundle: DatasetLoadBundle) -> ValidationResult:
    req = {"ball_by_ball": ("match_id", "innings", "overid", "over_ball_num", "runs", "is_four", "is_six", "extras_type")}
    skip_reason = check_required_columns(bundle, req)
    if skip_reason:
        return make_skipped_result(
            rule_id="VAL-BND-001",
            dataset="ball_by_ball",
            field="runs, is_four, is_six",
            severity=Severity.INFO,
            reason=skip_reason,
            recommended_action="Ensure boundary columns are loaded cleanly.",
        )

    bbb = bundle.get("ball_by_ball")
    assert bbb is not None
    four_false = bbb.loc[(bbb["runs"] == 4) & (~bbb["is_four"].fillna(False))]
    six_false = bbb.loc[(bbb["runs"] == 6) & (~bbb["is_six"].fillna(False))]
    false_pos_four = bbb.loc[(bbb["runs"] != 4) & (bbb["is_four"].fillna(False))]
    false_pos_six = bbb.loc[(bbb["runs"] != 6) & (bbb["is_six"].fillna(False))]

    total_omissions = int(len(four_false) + len(six_false))
    false_positives = int(len(false_pos_four) + len(false_pos_six))
    known_bnd_coords: frozenset[tuple[int, int, int, int]] = KNOWN_EXCEPTIONS["boundary_omission_coords"]  # type: ignore[assignment]
    omissions_df = pd.concat([four_false, six_false]).drop_duplicates()
    known_omissions = sum(
        1
        for _, r in omissions_df.iterrows()
        if (int(r["match_id"]), int(r["innings"]), int(r["overid"]), int(r["over_ball_num"]))
        in known_bnd_coords
    )
    new_omissions = int(len(omissions_df)) - known_omissions
    examples = [
        f"runs={r['runs']} is_four={r['is_four']} is_six={r['is_six']} at {format_row_id(r, ['match_id', 'innings', 'overid', 'over_ball_num'])}"
        for _, r in pd.concat([four_false.head(3), six_false.head(3), false_pos_four.head(2), false_pos_six.head(2)]).iterrows()
    ]

    status = ValidationStatus.WARNING if (false_positives > 0 or new_omissions > 0) else ValidationStatus.PASS
    return ValidationResult(
        rule_id="VAL-BND-001",
        dataset="ball_by_ball",
        field="runs, is_four, is_six",
        severity=Severity.INFO,
        status=status,
        affected_record_count=total_omissions + false_positives,
        known_exception_count=known_omissions,
        new_anomaly_count=false_positives + new_omissions,
        short_description=(
            f"Logged {len(four_false)} rows with runs=4,is_four=false and {len(six_false)} rows with runs=6,is_six=false; "
            f"{false_positives} false-positive boundary flags ({known_omissions} known, {false_positives + new_omissions} new)."
        ),
        example_record_identifiers=examples,
        recommended_action="Rely on numeric runs for team/batter totals and retain is_four/is_six as raw tags.",
        known_exceptions_summary="23 documented 'None' rows have runs=4/6 with false boundary flags (all-run 4s / overthrows / tagging gaps).",
        metadata={
            "runs_4_is_four_false": int(len(four_false)),
            "runs_6_is_six_false": int(len(six_false)),
            "false_positive_four": int(len(false_pos_four)),
            "false_positive_six": int(len(false_pos_six)),
        },
    )


def _check_val_tel_001_bowl_speed(bundle: DatasetLoadBundle) -> ValidationResult:
    req = {"ball_by_ball": ("match_id", "innings", "overid", "over_ball_num", "bowl_speed")}
    skip_reason = check_required_columns(bundle, req)
    if skip_reason:
        return make_skipped_result(
            rule_id="VAL-TEL-001",
            dataset="ball_by_ball",
            field="bowl_speed",
            severity=Severity.WARNING,
            reason=skip_reason,
            recommended_action="Ensure ball_by_ball.bowl_speed is loaded cleanly.",
        )

    bbb = bundle.get("ball_by_ball")
    assert bbb is not None
    if not pd.api.types.is_numeric_dtype(bbb["bowl_speed"].dtype):
        return make_skipped_result(
            rule_id="VAL-TEL-001",
            dataset="ball_by_ball",
            field="bowl_speed",
            severity=Severity.WARNING,
            reason="bowl_speed failed float parsing.",
            recommended_action="Fix VAL-SCH-002 parse errors first.",
        )

    spd = bbb["bowl_speed"]
    zero_sentinels = int((spd == 0).sum())
    neg_df = bbb.loc[spd < 0]
    slow_df = bbb.loc[(spd > 0) & (spd < 50.0)]
    fast_df = bbb.loc[spd > 170.0]
    valid_cnt = int(((spd >= 50.0) & (spd <= 170.0)).sum())

    invalid_df = pd.concat([neg_df, slow_df, fast_df]).drop_duplicates()
    invalid_cnt = int(len(invalid_df))

    known_spd_coords: frozenset[tuple[int, int, int, int]] = KNOWN_EXCEPTIONS["bowl_speed_outlier_coords"]  # type: ignore[assignment]
    known_cnt = sum(
        1
        for _, r in invalid_df.iterrows()
        if (int(r["match_id"]), int(r["innings"]), int(r["overid"]), int(r["over_ball_num"]))
        in known_spd_coords
    )
    new_cnt = invalid_cnt - known_cnt

    examples = [
        f"[{'KNOWN' if (int(r['match_id']), int(r['innings']), int(r['overid']), int(r['over_ball_num'])) in known_spd_coords else 'NEW'}] "
        f"bowl_speed={r['bowl_speed']} at {format_row_id(r, ['match_id', 'innings', 'overid', 'over_ball_num'])}"
        for _, r in invalid_df.sort_values("bowl_speed", ascending=False).head(8).iterrows()
    ]

    status = ValidationStatus.PASS if invalid_cnt == 0 else ValidationStatus.WARNING
    return ValidationResult(
        rule_id="VAL-TEL-001",
        dataset="ball_by_ball",
        field="bowl_speed",
        severity=Severity.WARNING,
        status=status,
        affected_record_count=invalid_cnt,
        known_exception_count=known_cnt,
        new_anomaly_count=new_cnt,
        short_description=(
            f"Valid speeds [50..170]: {valid_cnt:,}; zero sentinels: {zero_sentinels:,}; "
            f"invalid non-zero speeds: {invalid_cnt} (negative={len(neg_df)}, <50={len(slow_df)}, >170={len(fast_df)})."
        ),
        example_record_identifiers=examples,
        recommended_action="In Stage 5 preprocessing, convert bowl_speed == 0 and out-of-range (<50 or >170) to NaN + has_valid_bowl_speed flag.",
        known_exceptions_summary=(
            "77,861 zero sentinels plus 43 corrupt speeds (1 negative -1, 22 <50, 20 >170 up to 1456.1) documented in Stage 2."
        ),
        metadata={
            "valid_50_to_170_count": valid_cnt,
            "zero_sentinel_count": zero_sentinels,
            "negative_count": int(len(neg_df)),
            "slow_under_50_count": int(len(slow_df)),
            "fast_over_170_count": int(len(fast_df)),
        },
    )
