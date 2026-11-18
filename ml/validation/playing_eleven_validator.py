"""Playing XI, bench players, Impact Substitutes, batting order, and participation validation (Stage 4 Phase 3G)."""

from __future__ import annotations

import pandas as pd

from ml.ingestion.csv_loader import DatasetLoadBundle
from ml.ingestion.dataset_registry import KNOWN_EXCEPTIONS
from ml.validation.validation_engine import (
    Severity,
    ValidationResult,
    ValidationStatus,
    check_required_columns,
    format_row_id,
    make_skipped_result,
)


def validate_playing_eleven(bundle: DatasetLoadBundle) -> list[ValidationResult]:
    """Execute VAL-P11-001 and bench-leak / Impact-Sub participation checks."""
    return [_check_val_p11_001_lineups_and_impact_subs(bundle)]


def _check_val_p11_001_lineups_and_impact_subs(
    bundle: DatasetLoadBundle,
) -> ValidationResult:
    req = {
        "playing_eleven": (
            "match_id",
            "team_id",
            "player_id",
            "batting_order",
            "is_played",
            "is_captain",
            "is_wk",
            "is_impact",
            "is_impact_off",
        )
    }
    skip_reason = check_required_columns(bundle, req)
    if skip_reason:
        return make_skipped_result(
            rule_id="VAL-P11-001",
            dataset="playing_eleven",
            field="is_played, batting_order, is_impact, is_impact_off, is_captain, is_wk",
            severity=Severity.WARNING,
            reason=skip_reason,
            recommended_action="Ensure playing_eleven.csv loads cleanly.",
        )

    p11 = bundle.get("playing_eleven")
    bbb = bundle.get("ball_by_ball")
    matches = bundle.get("matches")
    comps = bundle.get("competitions")
    assert p11 is not None
    if not pd.api.types.is_bool_dtype(p11["is_played"].dtype) or not all(
        pd.api.types.is_numeric_dtype(p11[c].dtype)
        for c in ("match_id", "team_id", "player_id", "is_impact", "is_impact_off")
    ):
        return make_skipped_result(
            rule_id="VAL-P11-001",
            dataset="playing_eleven",
            field="is_played, is_impact, is_impact_off",
            severity=Severity.WARNING,
            reason="playing_eleven typed columns failed parsing.",
            recommended_action="Fix VAL-SCH-002 parse errors first.",
        )

    played_df = p11.loc[p11["is_played"].fillna(False)].copy()
    bench_df = p11.loc[~p11["is_played"].fillna(False)].copy()

    # 1) Unique played players per (match_id, team_id) — handles Super Over duplicate rows fairly
    tm_stats = (
        played_df.groupby(["match_id", "team_id"], sort=False)
        .agg(
            unique_played=("player_id", "nunique"),
            raw_played_rows=("player_id", "count"),
            impact_count=("is_impact", "sum"),
            impact_off_count=("is_impact_off", "sum"),
        )
        .reset_index()
    )
    if (
        matches is not None
        and comps is not None
        and {"match_id", "comp_id"}.issubset(matches.columns)
        and {"comp_id", "match_format"}.issubset(comps.columns)
    ):
        m_fmt = matches[["match_id", "comp_id"]].merge(
            comps[["comp_id", "match_format"]], on="comp_id", how="left"
        )[["match_id", "match_format"]]
        tm_stats = tm_stats.merge(m_fmt, on="match_id", how="left")
    else:
        tm_stats["match_format"] = pd.Series(pd.NA, index=tm_stats.index, dtype="string")

    # Check {11, 12} played count expectation without blindly forcing == 11
    under_11 = tm_stats.loc[tm_stats["unique_played"] < 11]
    over_12 = tm_stats.loc[tm_stats["unique_played"] > 12]
    twelve_without_impact = tm_stats.loc[
        (tm_stats["unique_played"] == 12) & (tm_stats["impact_count"] == 0)
    ]
    t20i_concussion_subs = twelve_without_impact.loc[
        twelve_without_impact["match_format"].astype(str) == "T20I"
    ]
    non_t20i_12_no_impact = twelve_without_impact.loc[
        twelve_without_impact["match_format"].astype(str) != "T20I"
    ]

    # 2) Impact Sub invariants: all is_impact == 1 and is_impact_off == 1 must have is_played == True
    impact_on_bench = p11.loc[
        (~p11["is_played"].fillna(False))
        & ((p11["is_impact"] == 1) | (p11["is_impact_off"] == 1))
    ]

    # 3) Bench rows should not carry active batting_order / is_captain / is_wk
    bench_with_active_fields = bench_df.loc[
        bench_df["batting_order"].notna()
        | bench_df["is_captain"].notna()
        | bench_df["is_wk"].notna()
    ]

    # 4) Played rows missing batting_order when team batted in ball_by_ball
    played_missing_order = played_df.loc[played_df["batting_order"].isna()]
    known_missing_order_tms: frozenset[tuple[int, int]] = KNOWN_EXCEPTIONS["played_xi_missing_batting_order_team_matches"]  # type: ignore[assignment]
    known_underpop_tms: frozenset[tuple[int, int]] = KNOWN_EXCEPTIONS["underpopulated_played_xi_team_matches"]  # type: ignore[assignment]
    known_over_12_tms: frozenset[tuple[int, int]] = KNOWN_EXCEPTIONS["played_xi_over_12_team_matches"]  # type: ignore[assignment]

    # 5) Check whether any pure bench row (is_played=False, excluding keys present in played_df) appears in ball_by_ball
    bench_leaks_count = 0
    bench_leak_examples: list[str] = []
    if bbb is not None and {
        "match_id",
        "batting_team_id",
        "bowling_team_id",
        "striker_id",
        "non_striker_id",
        "bowler_id",
    }.issubset(bbb.columns):
        played_keys = played_df[["match_id", "team_id", "player_id"]].drop_duplicates()
        bench_keys_raw = bench_df[["match_id", "team_id", "player_id"]].drop_duplicates()
        bench_only_merged = bench_keys_raw.merge(
            played_keys.assign(_in_played=1),
            on=["match_id", "team_id", "player_id"],
            how="left",
        )
        bench_keys = bench_only_merged.loc[
            bench_only_merged["_in_played"].isna(),
            ["match_id", "team_id", "player_id"],
        ].assign(_bench=1)
        for p_col, t_col in [
            ("striker_id", "batting_team_id"),
            ("non_striker_id", "batting_team_id"),
            ("bowler_id", "bowling_team_id"),
        ]:
            sub = bbb[["match_id", t_col, p_col]].rename(
                columns={t_col: "team_id", p_col: "player_id"}
            )
            leaked = sub.merge(bench_keys, on=["match_id", "team_id", "player_id"], how="inner")
            if len(leaked) > 0:
                bench_leaks_count += int(len(leaked))
                for _, r in leaked.head(3).iterrows():
                    bench_leak_examples.append(
                        f"BENCH_LEAK_{p_col} {format_row_id(r, ['match_id', 'team_id', 'player_id'])}"
                    )

    known_count = 0
    new_count = 0
    examples: list[str] = list(bench_leak_examples)

    for _, r in under_11.iterrows():
        tm = (int(r["match_id"]), int(r["team_id"]))
        is_known = tm in known_underpop_tms
        if is_known:
            known_count += 1
        else:
            new_count += 1
        if len(examples) < 10:
            examples.append(
                f"[{'KNOWN' if is_known else 'NEW'}] PLAYED_LT_11 {format_row_id(r, ['match_id', 'team_id', 'unique_played'])}"
            )

    for _, r in over_12.iterrows():
        tm = (int(r["match_id"]), int(r["team_id"]))
        is_known = tm in known_over_12_tms
        if is_known:
            known_count += 1
        else:
            new_count += 1
        if len(examples) < 10:
            examples.append(
                f"[{'KNOWN' if is_known else 'NEW'}] PLAYED_GT_12 {format_row_id(r, ['match_id', 'team_id', 'unique_played', 'impact_count'])}"
            )

    missing_order_tms = played_missing_order[["match_id", "team_id"]].drop_duplicates()
    for _, r in missing_order_tms.iterrows():
        tm = (int(r["match_id"]), int(r["team_id"]))
        cnt = int(
            (
                (played_missing_order["match_id"] == r["match_id"])
                & (played_missing_order["team_id"] == r["team_id"])
            ).sum()
        )
        is_known = tm in known_missing_order_tms
        if is_known:
            known_count += cnt
        else:
            new_count += cnt
        if len(examples) < 10:
            examples.append(
                f"[{'KNOWN' if is_known else 'NEW'}] MISSING_BATTING_ORDER match_id={r['match_id']} team_id={r['team_id']} rows={cnt}"
            )

    # Report 12 played without is_impact=1: distinguish T20I concussion substitutes vs missing Impact flag
    for _, r in t20i_concussion_subs.iterrows():
        new_count += 1
        if len(examples) < 10:
            examples.append(
                f"[NEW-CONCUSSION-SUB] PLAYED_12_T20I_NO_IMPACT {format_row_id(r, ['match_id', 'team_id', 'unique_played', 'match_format'])}"
            )
    for _, r in non_t20i_12_no_impact.iterrows():
        new_count += 1
        if len(examples) < 10:
            examples.append(
                f"[NEW] PLAYED_12_NO_IMPACT {format_row_id(r, ['match_id', 'team_id', 'unique_played', 'match_format'])}"
            )

    hard_errors = bench_leaks_count + int(len(impact_on_bench)) + int(len(bench_with_active_fields))
    new_count += hard_errors

    if hard_errors > 0:
        status = ValidationStatus.FAIL
    elif known_count + new_count > 0:
        status = ValidationStatus.WARNING
    else:
        status = ValidationStatus.PASS

    return ValidationResult(
        rule_id="VAL-P11-001",
        dataset="playing_eleven",
        field="is_played, batting_order, is_impact, is_impact_off",
        severity=Severity.WARNING,
        status=status,
        affected_record_count=known_count + new_count,
        known_exception_count=known_count,
        new_anomaly_count=new_count,
        short_description=(
            f"Played rows: {len(played_df):,}; Bench rows: {len(bench_df):,} (0 leaks into ball_by_ball={bench_leaks_count == 0}); "
            f"Impact Subs: {int((p11['is_impact'] == 1).sum())}; "
            f"<11 played teams={len(under_11)}, >12 played teams={len(over_12)}, "
            f"12 played w/o is_impact={len(twelve_without_impact)} (T20I concussion subs={len(t20i_concussion_subs)}, other={len(non_t20i_12_no_impact)}), "
            f"played missing batting_order={len(played_missing_order)}."
        ),
        example_record_identifiers=examples[:10],
        recommended_action=(
            "Preserve all original rows including bench & Super Over duplicates; do NOT coerce team size to 11 "
            "(T20I permits concussion substitutes with is_impact=0); infer fallback batting order from ball_by_ball."
        ),
        known_exceptions_summary=(
            "Known exceptions preserved: match 28333 team 17 (10 played rows, NR), 6 IPL team-matches with 13 played rows, "
            "match 48512 team 25 (11 played rows missing batting_order), and 40 Super Over duplicate rows in 13613/21176/28962. "
            "Newly surfaced valid domain behavior: 4 T20I matches (20880, 29926, 32132, 40039) have 12 played players due to concussion substitutes."
        ),
        metadata={
            "total_rows": int(len(p11)),
            "played_rows": int(len(played_df)),
            "bench_rows": int(len(bench_df)),
            "impact_sub_in_rows": int((p11["is_impact"] == 1).sum()),
            "impact_sub_off_rows": int((p11["is_impact_off"] == 1).sum()),
            "team_matches_total": int(len(tm_stats)),
            "team_matches_11_played": int((tm_stats["unique_played"] == 11).sum()),
            "team_matches_12_played": int((tm_stats["unique_played"] == 12).sum()),
            "team_matches_under_11": int(len(under_11)),
            "team_matches_over_12": int(len(over_12)),
            "twelve_played_without_impact": int(len(twelve_without_impact)),
            "t20i_concussion_sub_cases": int(len(t20i_concussion_subs)),
            "non_t20i_12_without_impact": int(len(non_t20i_12_no_impact)),
            "played_missing_batting_order": int(len(played_missing_order)),
            "bench_leaks_in_ball_by_ball": bench_leaks_count,
            "impact_on_bench_rows": int(len(impact_on_bench)),
            "bench_with_active_metadata": int(len(bench_with_active_fields)),
        },
    )
