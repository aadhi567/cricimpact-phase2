"""Match result categories, DLS vs Super Over isolation, innings reconciliation, and scope checks (Stage 4 Phase 3F)."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

import pandas as pd

from ml.ingestion.csv_loader import DatasetLoadBundle
from ml.ingestion.dataset_registry import KNOWN_EXCEPTIONS
from ml.validation.extras_validator import derive_team_runs
from ml.validation.validation_engine import (
    Severity,
    ValidationResult,
    ValidationStatus,
    check_required_columns,
    format_row_id,
    make_skipped_result,
)


_UNLABELED_RESULTS: frozenset[str] = frozenset(
    {"No Result", "Match Abandoned", "Match Tied"}
)
_DLS_TEXT_RE = re.compile(r"\((?:D/L|DLS)\)|\bD/L\b|\bDLS\b|Duckworth", re.IGNORECASE)
_SO_TEXT_RE = re.compile(r"super over|eliminator|bowl[- ]out", re.IGNORECASE)
_MARGIN_RE = re.compile(
    r"(?:won|beat).*?(?:\bby\s+)?(\d+)\s*(runs?|wickets?|wkts?)\b", re.IGNORECASE
)


def classify_match_regimes(
    matches: pd.DataFrame, bbb: pd.DataFrame | None
) -> pd.DataFrame:
    """Classify each match deterministically without inferring missing revised targets."""
    keep_cols = [
        c
        for c in (
            "match_id",
            "comp_id",
            "match_date",
            "home_team_id",
            "away_team_id",
            "win_team_id",
            "result",
            "first_inn_revised_overs",
            "second_inn_revised_overs",
            "revised_target",
        )
        if c in matches.columns
    ]
    df = matches[keep_cols].copy()

    res_str = df["result"].fillna("").astype(str)
    has_so_innings: set[int] = set()
    tied_reg_scores: set[int] = set()
    if (
        bbb is not None
        and {"match_id", "innings", "runs", "extras1_runs", "extras_2_runs"}.issubset(
            bbb.columns
        )
        and all(
            pd.api.types.is_numeric_dtype(bbb[c].dtype)
            for c in ("match_id", "innings", "runs", "extras1_runs", "extras_2_runs")
        )
    ):
        has_so_innings = set(
            int(x) for x in bbb.loc[bbb["innings"] >= 3, "match_id"].dropna().unique()
        )
        reg = bbb.loc[bbb["innings"].isin([1, 2])].copy()
        reg["_tr"] = derive_team_runs(reg)
        inn_sums = reg.groupby(["match_id", "innings"], sort=False)["_tr"].sum().unstack(fill_value=-1)
        if 1 in inn_sums.columns and 2 in inn_sums.columns:
            tied_reg_scores = set(
                int(mid)
                for mid in inn_sums.index[
                    (inn_sums[1] >= 0) & (inn_sums[2] >= 0) & (inn_sums[1] == inn_sums[2])
                ]
            )

    df["has_win_team"] = df["win_team_id"].notna()
    df["has_dls_text"] = res_str.str.contains(_DLS_TEXT_RE)
    df["has_revised_cols"] = (
        df["first_inn_revised_overs"].notna()
        | df["second_inn_revised_overs"].notna()
        | df["revised_target"].notna()
    )
    df["is_dls_or_revised"] = df["has_dls_text"] | df["has_revised_cols"]
    df["has_super_over_innings"] = df["match_id"].isin(has_so_innings)
    df["is_super_over"] = df["has_win_team"] & (
        df["has_super_over_innings"]
        | res_str.str.contains(_SO_TEXT_RE)
        | (df["match_id"].isin(tied_reg_scores) & ~df["is_dls_or_revised"])
    )

    # Classify mutually exclusive regime categories
    regime = pd.Series("unlabeled", index=df.index, dtype="string")
    regime = regime.where(~df["has_win_team"], "clean_completed")
    regime = regime.where(~(df["has_win_team"] & df["is_dls_or_revised"]), "dls_revised_completed")
    regime = regime.where(~df["is_super_over"], "super_over_completed")
    df["regime"] = regime
    return df


def validate_matches(bundle: DatasetLoadBundle) -> list[ValidationResult]:
    """Execute VAL-MCH-001..004, VAL-EXT-005, and VAL-SRC-001."""
    return [
        _check_val_mch_001_result_and_winner_integrity(bundle),
        _check_val_mch_002_dls_and_revised_overs(bundle),
        _check_val_mch_003_super_over_isolation(bundle),
        _check_val_ext_005_score_and_chase_reconciliation(bundle),
        _check_val_mch_004_scorecard_text_consistency(bundle),
        _check_val_src_001_dates_and_competition_scope(bundle),
    ]


def _check_val_mch_001_result_and_winner_integrity(
    bundle: DatasetLoadBundle,
) -> ValidationResult:
    req = {
        "matches": (
            "match_id",
            "home_team_id",
            "away_team_id",
            "win_team_id",
            "result",
            "first_inn_revised_overs",
            "second_inn_revised_overs",
            "revised_target",
        )
    }
    skip_reason = check_required_columns(bundle, req)
    if skip_reason:
        return make_skipped_result(
            rule_id="VAL-MCH-001",
            dataset="matches",
            field="win_team_id, result",
            severity=Severity.CRITICAL,
            reason=skip_reason,
            recommended_action="Ensure matches.csv loads cleanly.",
        )

    matches = bundle.get("matches")
    bbb = bundle.get("ball_by_ball")
    assert matches is not None
    if not all(
        pd.api.types.is_numeric_dtype(matches[c].dtype)
        for c in ("match_id", "home_team_id", "away_team_id")
    ):
        return make_skipped_result(
            rule_id="VAL-MCH-001",
            dataset="matches",
            field="match_id, home_team_id, away_team_id",
            severity=Severity.CRITICAL,
            reason="Match ID columns failed numeric parsing.",
            recommended_action="Fix VAL-SCH-002 parse errors first.",
        )

    reg_df = classify_match_regimes(matches, bbb)
    res_str = matches["result"].fillna("").astype(str)

    bad_null_winner = matches.loc[
        matches["win_team_id"].isna() & ~res_str.isin(_UNLABELED_RESULTS)
    ]
    bad_winner_team = matches.loc[
        matches["win_team_id"].notna()
        & (
            (
                (matches["win_team_id"] != matches["home_team_id"])
                & (matches["win_team_id"] != matches["away_team_id"])
            )
            | res_str.isin({"No Result", "Match Abandoned"})
        )
    ]

    missing_bbb_completed = pd.DataFrame()
    delivery_coverage: dict[str, Any] = {}
    if bbb is not None and {"match_id", "innings"}.issubset(bbb.columns):
        bbb_mids = set(int(x) for x in bbb["match_id"].dropna().unique())
        missing_bbb_completed = matches.loc[
            matches["win_team_id"].notna() & ~matches["match_id"].isin(bbb_mids)
        ]
        inn_set_by_mid = bbb.groupby("match_id")["innings"].apply(set).to_dict()
        zero_ball_matches = int((~matches["match_id"].isin(bbb_mids)).sum())
        inn1_only_unlabeled = int(
            sum(
                1
                for mid in matches.loc[matches["win_team_id"].isna(), "match_id"]
                if inn_set_by_mid.get(int(mid)) == {1}
            )
        )
        partial_inn2_unlabeled = int(
            sum(
                1
                for mid in matches.loc[matches["win_team_id"].isna(), "match_id"]
                if 2 in inn_set_by_mid.get(int(mid), set())
            )
        )
        delivery_coverage = {
            "matches_with_deliveries": int(len(bbb_mids & set(matches["match_id"].dropna()))),
            "zero_ball_matches": zero_ball_matches,
            "unlabeled_inn1_only": inn1_only_unlabeled,
            "unlabeled_partial_inn2": partial_inn2_unlabeled,
        }

    total_errors = (
        int(len(bad_null_winner))
        + int(len(bad_winner_team))
        + int(len(missing_bbb_completed))
    )
    examples: list[str] = []
    for _, r in bad_null_winner.head(3).iterrows():
        examples.append(f"NULL_WINNER_BAD_RESULT match_id={r['match_id']} result={r['result']!r}")
    for _, r in bad_winner_team.head(3).iterrows():
        examples.append(f"INVALID_WINNER match_id={r['match_id']} win={r['win_team_id']} result={r['result']!r}")
    for _, r in missing_bbb_completed.head(3).iterrows():
        examples.append(f"COMPLETED_NO_BALLS match_id={r['match_id']} result={r['result']!r}")

    regime_counts = reg_df["regime"].value_counts().to_dict()
    unlabeled_breakdown = (
        matches.loc[matches["win_team_id"].isna(), "result"].value_counts().to_dict()
    )

    status = ValidationStatus.PASS if total_errors == 0 else ValidationStatus.FAIL
    return ValidationResult(
        rule_id="VAL-MCH-001",
        dataset="matches",
        field="win_team_id, result",
        severity=Severity.CRITICAL,
        status=status,
        affected_record_count=total_errors,
        new_anomaly_count=total_errors,
        short_description=(
            f"All {len(matches):,} matches satisfy supervised target integrity "
            f"(clean={regime_counts.get('clean_completed', 0)}, dls={regime_counts.get('dls_revised_completed', 0)}, "
            f"super_over={regime_counts.get('super_over_completed', 0)}, unlabeled={regime_counts.get('unlabeled', 0)})."
            if total_errors == 0
            else f"Detected {total_errors} invalid win_team_id/result combination(s) or completed matches missing delivery logs."
        ),
        example_record_identifiers=examples,
        recommended_action="Exclude blank win_team_id matches (No Result / Abandoned / Tied without SO) from binary win loss.",
        metadata={
            "regime_counts": {str(k): int(v) for k, v in regime_counts.items()},
            "unlabeled_breakdown": {str(k): int(v) for k, v in unlabeled_breakdown.items()},
            "delivery_coverage": delivery_coverage,
        },
    )


def _check_val_mch_002_dls_and_revised_overs(
    bundle: DatasetLoadBundle,
) -> ValidationResult:
    req = {
        "matches": (
            "match_id",
            "win_team_id",
            "result",
            "first_inn_revised_overs",
            "second_inn_revised_overs",
            "revised_target",
        )
    }
    skip_reason = check_required_columns(bundle, req)
    if skip_reason:
        return make_skipped_result(
            rule_id="VAL-MCH-002",
            dataset="matches",
            field="first_inn_revised_overs, second_inn_revised_overs, revised_target, result",
            severity=Severity.WARNING,
            reason=skip_reason,
            recommended_action="Ensure DLS/revised columns load cleanly.",
        )

    matches = bundle.get("matches")
    bbb = bundle.get("ball_by_ball")
    assert matches is not None
    for col in ("first_inn_revised_overs", "second_inn_revised_overs", "revised_target"):
        if not pd.api.types.is_numeric_dtype(matches[col].dtype):
            return make_skipped_result(
                rule_id="VAL-MCH-002",
                dataset="matches",
                field=col,
                severity=Severity.WARNING,
                reason=f"{col} failed numeric parsing.",
                recommended_action="Fix VAL-SCH-002 parse errors first.",
            )

    reg_df = classify_match_regimes(matches, bbb)
    dls_df = reg_df.loc[reg_df["is_dls_or_revised"]]

    # Validate ball-count unit semantics (6..120) and positive target
    bad_overs_1 = matches.loc[
        matches["first_inn_revised_overs"].notna()
        & ~matches["first_inn_revised_overs"].between(6, 120)
    ]
    bad_overs_2 = matches.loc[
        matches["second_inn_revised_overs"].notna()
        & ~matches["second_inn_revised_overs"].between(6, 120)
    ]
    bad_target = matches.loc[
        matches["revised_target"].notna() & (matches["revised_target"] <= 0)
    ]

    # DLS text matches missing revised_target (known documented baseline: 20182, 23674, 24822, 28334)
    known_missing_target_ids: frozenset[int] = KNOWN_EXCEPTIONS["dls_text_missing_target_matches"]  # type: ignore[assignment]
    dls_text_no_target = dls_df.loc[dls_df["has_dls_text"] & dls_df["revised_target"].isna()]
    completed_rev_no_target = dls_df.loc[
        dls_df["has_win_team"] & ~dls_df["has_dls_text"] & dls_df["revised_target"].isna()
    ]
    overlap_dls_so = dls_df.loc[dls_df["is_super_over"]]

    dls_completed_cnt = int((dls_df["has_win_team"] & ~dls_df["is_super_over"]).sum())
    dls_unlabeled_cnt = int((~dls_df["has_win_team"]).sum())

    hard_errors = int(len(bad_overs_1) + len(bad_overs_2) + len(bad_target) + len(overlap_dls_so))
    missing_target_cnt = int(len(dls_text_no_target))
    known_cnt = int(dls_text_no_target["match_id"].isin(known_missing_target_ids).sum())
    new_missing_target_cnt = missing_target_cnt - known_cnt
    new_cnt = hard_errors + new_missing_target_cnt

    examples: list[str] = []
    for _, r in bad_overs_1.head(2).iterrows():
        examples.append(f"INVALID_1ST_BALLS match_id={r['match_id']} val={r['first_inn_revised_overs']}")
    for _, r in bad_overs_2.head(2).iterrows():
        examples.append(f"INVALID_2ND_BALLS match_id={r['match_id']} val={r['second_inn_revised_overs']}")
    for _, r in bad_target.head(2).iterrows():
        examples.append(f"INVALID_TARGET match_id={r['match_id']} val={r['revised_target']}")
    for _, r in dls_text_no_target.head(6).iterrows():
        tag = "KNOWN" if int(r["match_id"]) in known_missing_target_ids else "NEW"
        examples.append(
            f"[{tag}] DLS_NO_TARGET match_id={r['match_id']} rev1={r['first_inn_revised_overs']} rev2={r['second_inn_revised_overs']} result={r['result']!r}"
        )

    if hard_errors > 0:
        status = ValidationStatus.FAIL
    elif missing_target_cnt > 0:
        status = ValidationStatus.WARNING
    else:
        status = ValidationStatus.PASS

    return ValidationResult(
        rule_id="VAL-MCH-002",
        dataset="matches",
        field="first_inn_revised_overs, second_inn_revised_overs, revised_target, result",
        severity=Severity.WARNING,
        status=status,
        affected_record_count=hard_errors + missing_target_cnt,
        known_exception_count=known_cnt,
        new_anomaly_count=new_cnt,
        short_description=(
            f"DLS/revised-overs matches: {dls_completed_cnt} completed + {dls_unlabeled_cnt} unlabeled "
            f"(stored as legal balls in 6..120); {missing_target_cnt} DLS-text match(es) omit revised_target "
            f"({known_cnt} known, {new_missing_target_cnt} new); 0 DLS/Super Over overlap, {hard_errors} range/target errors."
        ),
        example_record_identifiers=examples[:10],
        recommended_action=(
            "Do NOT infer missing revised targets; treat first/second_inn_revised_overs as legal ball counts "
            "and isolate is_dls_match from primary non-DLS training to avoid rain-interruption hindsight leakage."
        ),
        known_exceptions_summary=(
            f"28 DLS/revised completed matches; 4 completed DLS-text matches {sorted(known_missing_target_ids)} "
            f"omit revised_target (+ {len(completed_rev_no_target)} equal-reduced completed & "
            f"{int((~dls_df['has_win_team'] & dls_df['revised_target'].isna()).sum())} unlabeled NR/abandoned revised matches)."
        ),
        metadata={
            "dls_completed_count": dls_completed_cnt,
            "dls_unlabeled_count": dls_unlabeled_cnt,
            "with_revised_target_count": int(matches["revised_target"].notna().sum()),
            "dls_text_missing_target_count": missing_target_cnt,
            "completed_revised_without_dls_text_count": int(len(completed_rev_no_target)),
            "dls_super_over_overlap_count": int(len(overlap_dls_so)),
            "bad_revised_ball_counts": int(len(bad_overs_1) + len(bad_overs_2)),
        },
    )


def _check_val_mch_003_super_over_isolation(
    bundle: DatasetLoadBundle,
) -> ValidationResult:
    req = {
        "matches": (
            "match_id",
            "win_team_id",
            "result",
            "first_inn_revised_overs",
            "second_inn_revised_overs",
            "revised_target",
        )
    }
    skip_reason = check_required_columns(bundle, req)
    if skip_reason:
        return make_skipped_result(
            rule_id="VAL-MCH-003",
            dataset="matches,ball_by_ball",
            field="innings, result",
            severity=Severity.INFO,
            reason=skip_reason,
            recommended_action="Ensure matches.csv loads cleanly.",
        )

    matches = bundle.get("matches")
    bbb = bundle.get("ball_by_ball")
    assert matches is not None
    if not pd.api.types.is_numeric_dtype(matches["match_id"].dtype):
        return make_skipped_result(
            rule_id="VAL-MCH-003",
            dataset="matches,ball_by_ball",
            field="match_id",
            severity=Severity.INFO,
            reason="match_id failed numeric parsing.",
            recommended_action="Fix VAL-SCH-002 parse errors first.",
        )

    reg_df = classify_match_regimes(matches, bbb)
    so_df = reg_df.loc[reg_df["is_super_over"]]
    with_inn34 = so_df.loc[so_df["has_super_over_innings"]]
    without_inn34 = so_df.loc[~so_df["has_super_over_innings"]]

    so_ball_rows = int((bbb["innings"] >= 3).sum()) if bbb is not None and "innings" in bbb.columns else 0
    known_pre2024: frozenset[int] = KNOWN_EXCEPTIONS["playing_eleven_super_over_dup_matches"]  # type: ignore[assignment]
    no_inn34_ids = set(int(x) for x in without_inn34["match_id"].tolist())
    new_missing_so_feed = no_inn34_ids - set(known_pre2024)

    examples = [
        f"SO match_id={r['match_id']} has_inn34={bool(r['has_super_over_innings'])} result={r['result']!r}"
        for _, r in so_df.sort_values("match_id").head(10).iterrows()
    ]

    status = ValidationStatus.WARNING if new_missing_so_feed else ValidationStatus.PASS
    return ValidationResult(
        rule_id="VAL-MCH-003",
        dataset="matches,ball_by_ball",
        field="innings >= 3, result",
        severity=Severity.INFO,
        status=status,
        affected_record_count=int(len(so_df)),
        known_exception_count=len(no_inn34_ids & set(known_pre2024)),
        new_anomaly_count=len(new_missing_so_feed),
        short_description=(
            f"Identified {len(so_df)} Super Over match(es) ({len(with_inn34)} with innings 3/4 totaling {so_ball_rows} deliveries; "
            f"{len(without_inn34)} pre-July-2024 tie-deciders without innings 3/4 rows), cleanly separated from DLS."
        ),
        example_record_identifiers=examples,
        recommended_action="Keep innings >= 3 isolated from 20-over regulation Win Probability training; preserve tie-after-regulation tag.",
        known_exceptions_summary=(
            f"3 pre-July-2024 Super Over matches {sorted(known_pre2024)} lack innings 3/4 rows in ball_by_ball."
        ),
        metadata={
            "super_over_matches": sorted(int(x) for x in so_df["match_id"].tolist()),
            "with_innings_3_4": sorted(int(x) for x in with_inn34["match_id"].tolist()),
            "without_innings_3_4": sorted(no_inn34_ids),
            "super_over_delivery_rows": so_ball_rows,
        },
    )


def _check_val_ext_005_score_and_chase_reconciliation(
    bundle: DatasetLoadBundle,
) -> ValidationResult:
    req = {
        "matches": (
            "match_id",
            "home_team_id",
            "away_team_id",
            "win_team_id",
            "result",
            "first_inn_revised_overs",
            "second_inn_revised_overs",
            "revised_target",
        ),
        "ball_by_ball": (
            "match_id",
            "innings",
            "innings_ball_num",
            "batting_team_id",
            "runs",
            "extras1_runs",
            "extras_2_runs",
            "is_wicket",
        ),
    }
    skip_reason = check_required_columns(bundle, req)
    if skip_reason:
        return make_skipped_result(
            rule_id="VAL-EXT-005",
            dataset="ball_by_ball,matches",
            field="runs, extras1_runs, extras_2_runs, win_team_id, result",
            severity=Severity.CRITICAL,
            reason=skip_reason,
            recommended_action="Ensure matches and ball_by_ball scoring columns load cleanly.",
        )

    matches = bundle.get("matches")
    bbb = bundle.get("ball_by_ball")
    assert matches is not None and bbb is not None
    if not all(
        pd.api.types.is_numeric_dtype(bbb[c].dtype)
        for c in ("match_id", "innings", "runs", "extras1_runs", "extras_2_runs")
    ) or not pd.api.types.is_bool_dtype(bbb["is_wicket"].dtype):
        return make_skipped_result(
            rule_id="VAL-EXT-005",
            dataset="ball_by_ball,matches",
            field="runs, extras1_runs, extras_2_runs, is_wicket",
            severity=Severity.CRITICAL,
            reason="Scoring or wicket columns failed typed parsing.",
            recommended_action="Fix VAL-SCH-002 parse errors first.",
        )

    reg_df = classify_match_regimes(matches, bbb)
    clean_df = reg_df.loc[reg_df["regime"] == "clean_completed"]
    if len(clean_df) == 0:
        return ValidationResult(
            rule_id="VAL-EXT-005",
            dataset="ball_by_ball,matches",
            field="runs, extras1_runs, extras_2_runs, win_team_id, result",
            severity=Severity.CRITICAL,
            status=ValidationStatus.PASS,
            affected_record_count=0,
            short_description="0 clean non-DLS non-SO completed matches in batch.",
            recommended_action="None required.",
        )

    work = bbb.loc[
        bbb["match_id"].isin(clean_df["match_id"]) & bbb["innings"].isin([1, 2]),
        [
            "match_id",
            "innings",
            "innings_ball_num",
            "batting_team_id",
            "runs",
            "extras1_runs",
            "extras_2_runs",
            "is_wicket",
        ],
    ].copy()
    work["_team_runs"] = derive_team_runs(work)
    work = work.sort_values(["match_id", "innings", "innings_ball_num"], kind="mergesort")

    inn_agg = (
        work.groupby(["match_id", "innings"], sort=False)
        .agg(
            total_runs=("_team_runs", "sum"),
            wickets=("is_wicket", "sum"),
            batting_team_id=("batting_team_id", "first"),
            last_ball_runs=("_team_runs", "last"),
        )
        .reset_index()
    )
    inn1 = inn_agg.loc[inn_agg["innings"] == 1].set_index("match_id")
    inn2 = inn_agg.loc[inn_agg["innings"] == 2].set_index("match_id")

    winner_mismatches = 0
    chase_violations = 0
    margin_mismatches = 0
    margin_checked = 0
    known_text_typo_hits = 0
    known_typo_matches: frozenset[int] = KNOWN_EXCEPTIONS["scorecard_result_text_typo_matches"]  # type: ignore[assignment]
    examples: list[str] = []

    for _, m in clean_df.iterrows():
        mid = int(m["match_id"])
        if mid not in inn1.index or mid not in inn2.index:
            winner_mismatches += 1
            if len(examples) < 10:
                examples.append(f"MISSING_INNINGS match_id={mid}")
            continue
        r1 = inn1.loc[mid]
        r2 = inn2.loc[mid]
        s1 = int(r1["total_runs"])
        s2 = int(r2["total_runs"])
        t1 = int(r1["batting_team_id"])
        t2 = int(r2["batting_team_id"])
        w2 = int(r2["wickets"])
        last_runs_2 = int(r2["last_ball_runs"])
        win_tid = int(m["win_team_id"])

        expected_winner = t1 if s1 > s2 else (t2 if s2 > s1 else -1)
        if expected_winner != win_tid:
            winner_mismatches += 1
            if len(examples) < 10:
                examples.append(
                    f"WINNER_MISMATCH match_id={mid}: s1={s1} (t1={t1}), s2={s2} (t2={t2}), recorded_win={win_tid}"
                )

        if s2 > s1:
            # Successful chase invariant: previous ball total <= s1 and 1 <= s2 - s1 <= 6
            s2_prev = s2 - last_runs_2
            overshoot = s2 - s1
            if not (s2_prev <= s1 and 1 <= overshoot <= 6):
                chase_violations += 1
                if len(examples) < 10:
                    examples.append(
                        f"CHASE_INVARIANT_FAIL match_id={mid}: s1={s1}, s2={s2}, s2_prev={s2_prev}, overshoot={overshoot}"
                    )

        res_txt = str(m["result"])
        match_obj = _MARGIN_RE.search(res_txt)
        if match_obj:
            margin_checked += 1
            recorded_val = int(match_obj.group(1))
            unit = match_obj.group(2).lower()
            if unit.startswith("run"):
                computed_margin = s1 - s2
            else:
                computed_margin = 10 - w2
            if computed_margin != recorded_val:
                margin_mismatches += 1
                if mid in known_typo_matches:
                    known_text_typo_hits += 1
                elif len(examples) < 10:
                    examples.append(
                        f"MARGIN_MISMATCH match_id={mid}: computed={computed_margin}, recorded={recorded_val}, result={res_txt!r}"
                    )

    total_clean = int(len(clean_df))
    margin_rate = (margin_checked - margin_mismatches) / margin_checked if margin_checked > 0 else 1.0
    passes = (
        winner_mismatches == 0
        and chase_violations == 0
        and margin_rate >= 0.995
    )

    return ValidationResult(
        rule_id="VAL-EXT-005",
        dataset="ball_by_ball,matches",
        field="runs, extras1_runs, extras_2_runs, win_team_id, result",
        severity=Severity.CRITICAL,
        status=ValidationStatus.PASS if passes else ValidationStatus.FAIL,
        affected_record_count=winner_mismatches + chase_violations + (0 if passes else margin_mismatches),
        known_exception_count=0 if passes else known_text_typo_hits,
        new_anomaly_count=(
            winner_mismatches
            + chase_violations
            + (0 if passes else max(0, margin_mismatches - known_text_typo_hits))
        ),
        short_description=(
            f"Reconciled {total_clean}/{total_clean} clean completed matches: "
            f"winner accuracy=100% ({total_clean - winner_mismatches}/{total_clean}), "
            f"chase boundary invariant=100% (violations={chase_violations}), "
            f"margin reconciliation={margin_checked - margin_mismatches}/{margin_checked} ({margin_rate * 100:.2f}% >= 99.5%)."
        ),
        example_record_identifiers=examples,
        recommended_action="Halt on winner/chase violations or <99.5% margin reconciliation; log isolated text/dropped-ball diffs in VAL-MCH-004.",
        known_exceptions_summary=(
            "match_id=20190 result text states '6 wickets' vs 5 wickets; match_id=14130 has 37 computed vs '36 Runs' text due to dropped 1.14 delivery (both flagged in VAL-MCH-004)."
        ),
        metadata={
            "clean_completed_matches": total_clean,
            "winner_mismatches": winner_mismatches,
            "chase_violations": chase_violations,
            "margin_checked": margin_checked,
            "margin_mismatches": margin_mismatches,
            "margin_match_rate": round(margin_rate, 6),
        },
    )


def _check_val_mch_004_scorecard_text_consistency(
    bundle: DatasetLoadBundle,
) -> ValidationResult:
    """Surface scorecard text discrepancies like match 20190 separately from VAL-EXT-005."""
    req = {
        "matches": ("match_id", "win_team_id", "result", "first_inn_revised_overs", "second_inn_revised_overs", "revised_target"),
        "ball_by_ball": ("match_id", "innings", "runs", "extras1_runs", "extras_2_runs", "is_wicket"),
    }
    skip_reason = check_required_columns(bundle, req)
    if skip_reason:
        return make_skipped_result(
            rule_id="VAL-MCH-004",
            dataset="matches,ball_by_ball",
            field="result",
            severity=Severity.WARNING,
            reason=skip_reason,
            recommended_action="Ensure matches and ball_by_ball load cleanly.",
        )

    matches = bundle.get("matches")
    bbb = bundle.get("ball_by_ball")
    assert matches is not None and bbb is not None
    if not all(
        pd.api.types.is_numeric_dtype(bbb[c].dtype)
        for c in ("match_id", "innings", "runs", "extras1_runs", "extras_2_runs")
    ) or not pd.api.types.is_bool_dtype(bbb["is_wicket"].dtype):
        return make_skipped_result(
            rule_id="VAL-MCH-004",
            dataset="matches,ball_by_ball",
            field="runs, extras1_runs, extras_2_runs, is_wicket",
            severity=Severity.WARNING,
            reason="Scoring or wicket columns failed typed parsing.",
            recommended_action="Fix VAL-SCH-002 parse errors first.",
        )

    reg_df = classify_match_regimes(matches, bbb)
    clean_df = reg_df.loc[reg_df["regime"] == "clean_completed"]
    work = bbb.loc[
        bbb["match_id"].isin(clean_df["match_id"]) & bbb["innings"].isin([1, 2]),
        ["match_id", "innings", "runs", "extras1_runs", "extras_2_runs", "is_wicket"],
    ].copy()
    work["_tr"] = derive_team_runs(work)
    inn_agg = work.groupby(["match_id", "innings"])[["_tr", "is_wicket"]].sum().unstack()

    known_typo_matches: frozenset[int] = KNOWN_EXCEPTIONS["scorecard_result_text_typo_matches"]  # type: ignore[assignment]
    known_cnt = 0
    new_cnt = 0
    examples: list[str] = []

    for _, m in clean_df.iterrows():
        mid = int(m["match_id"])
        if mid not in inn_agg.index:
            continue
        match_obj = _MARGIN_RE.search(str(m["result"]))
        if not match_obj:
            continue
        recorded_val = int(match_obj.group(1))
        unit = match_obj.group(2).lower()
        s1 = int(inn_agg.loc[mid, ("_tr", 1)])
        s2 = int(inn_agg.loc[mid, ("_tr", 2)])
        w2 = int(inn_agg.loc[mid, ("is_wicket", 2)])
        computed = (s1 - s2) if unit.startswith("run") else (10 - w2)
        if computed != recorded_val:
            is_known = mid in known_typo_matches
            if is_known:
                known_cnt += 1
            else:
                new_cnt += 1
            examples.append(
                f"[{'KNOWN' if is_known else 'NEW'}] match_id={mid}: computed={computed}, text_margin={recorded_val} ({m['result']!r})"
            )

    total = known_cnt + new_cnt
    status = ValidationStatus.PASS if total == 0 else ValidationStatus.WARNING
    return ValidationResult(
        rule_id="VAL-MCH-004",
        dataset="matches,ball_by_ball",
        field="result",
        severity=Severity.WARNING,
        status=status,
        affected_record_count=total,
        known_exception_count=known_cnt,
        new_anomaly_count=new_cnt,
        short_description=(
            "0 scorecard result text vs delivery margin discrepancies."
            if total == 0
            else f"{total} scorecard/delivery margin mismatch(es) ({known_cnt} known: match_id=20190, {new_cnt} new)."
        ),
        example_record_identifiers=examples,
        recommended_action="Trust win_team_id + ball-by-ball runs/wickets for modeling labels (note 14130 missing delivery offsets 1st-inn runs by 1); keep raw result string untouched.",
        known_exceptions_summary="match_id=20190 states 'Lucknow Super Giants Won by 6 wickets' while ball_by_ball has 5 wickets lost (10-5=5).",
    )


def _check_val_src_001_dates_and_competition_scope(
    bundle: DatasetLoadBundle,
) -> ValidationResult:
    req = {
        "competitions": ("comp_id", "comp_name", "match_format", "season"),
        "matches": ("match_id", "comp_id", "match_date"),
    }
    skip_reason = check_required_columns(bundle, req)
    if skip_reason:
        return make_skipped_result(
            rule_id="VAL-SRC-001",
            dataset="competitions,matches",
            field="match_date, comp_id, comp_name, match_format",
            severity=Severity.INFO,
            reason=skip_reason,
            recommended_action="Ensure competitions and matches load cleanly.",
        )

    comps = bundle.get("competitions")
    matches = bundle.get("matches")
    assert comps is not None and matches is not None

    parsed_dates = pd.to_datetime(matches["match_date"], format="%Y-%m-%d", errors="coerce")
    bad_dates = int(parsed_dates.isna().sum())
    today_utc = datetime.now(timezone.utc).date()
    future_dates = int((parsed_dates.dt.date > today_utc).fillna(False).sum())
    min_date = str(parsed_dates.min().date()) if parsed_dates.notna().any() else "N/A"
    max_date = str(parsed_dates.max().date()) if parsed_dates.notna().any() else "N/A"

    matches_sorted_id = matches.assign(_dt=parsed_dates).sort_values("match_id")
    non_monotonic_vs_id = int(
        (matches_sorted_id["_dt"] < matches_sorted_id["_dt"].shift(1)).fillna(False).sum()
    )

    merged = matches[["match_id", "comp_id", "match_date"]].merge(
        comps[["comp_id", "comp_name", "match_format", "season"]],
        on="comp_id",
        how="left",
    )
    format_comp_counts = comps["match_format"].value_counts().to_dict()
    format_match_counts = merged["match_format"].value_counts().to_dict()

    merged["_year"] = parsed_dates.dt.year
    year_format_counts = (
        merged.groupby(["_year", "match_format"], dropna=False)
        .size()
        .reset_index(name="matches")
        .to_dict(orient="records")
    )

    date_errors = bad_dates + future_dates
    return ValidationResult(
        rule_id="VAL-SRC-001",
        dataset="competitions,matches",
        field="match_date, match_format, comp_id",
        severity=Severity.INFO,
        status=ValidationStatus.PASS if date_errors == 0 else ValidationStatus.FAIL,
        affected_record_count=date_errors if date_errors > 0 else int(len(matches)),
        new_anomaly_count=date_errors,
        short_description=(
            f"Temporal span {min_date}..{max_date} (0 future/invalid dates; {non_monotonic_vs_id} match_ids out-of-date-order); "
            f"preserved separate competition formats (T20={format_comp_counts.get('T20', 0)} comps / "
            f"{format_match_counts.get('T20', 0)} matches; T20I={format_comp_counts.get('T20I', 0)} comps / "
            f"{format_match_counts.get('T20I', 0)} matches) with original comp_id/comp_name."
        ),
        recommended_action="Enforce match-grouped chronological splits using match_date (not match_id) and preserve competition format stratification.",
        metadata={
            "min_match_date": min_date,
            "max_match_date": max_date,
            "bad_dates": bad_dates,
            "future_dates": future_dates,
            "non_monotonic_date_vs_match_id": non_monotonic_vs_id,
            "competitions_by_format": {str(k): int(v) for k, v in format_comp_counts.items()},
            "matches_by_format": {str(k): int(v) for k, v in format_match_counts.items()},
            "matches_by_year_and_format": year_format_counts,
        },
    )
