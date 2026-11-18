"""Stage 5B delivery continuity audit and full-dataset validation rules."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd

from ml.ingestion.dataset_registry import VALID_EXTRAS_TYPES
from ml.match_state.schema import (
    COLUMN_SPEC_MAP,
    COLUMN_SPECS,
    EXPECTED_COLUMN_ORDER,
    MODEL_FEATURE_COLUMNS,
    REGIME_AUDIT_COLUMNS,
    TARGET_COLUMNS,
    TRANSITION_KEY_COLUMNS,
    UNRESOLVED_50407_AUDIT_STATUS,
    UNRESOLVED_50407_EXCLUSION_REASON,
    UNRESOLVED_50407_MATCH_ID,
)
from ml.validation.extras_validator import derive_is_legal_delivery, derive_team_runs
from ml.validation.validation_engine import Severity, ValidationResult, ValidationStatus


CONTINUITY_AUDIT_COLUMNS: tuple[str, ...] = (
    "match_id",
    "innings",
    "delivery_identifier",
    "field_affected",
    "previous_after_state",
    "current_before_state",
    "discrepancy",
    "classification",
    "resolution_status",
)


@dataclass
class ContinuityAuditOutcome:
    """Structured result of the delivery-by-delivery state continuity audit."""

    audit_df: pd.DataFrame
    total_rows_checked: int
    total_innings_groups: int
    unexpected_break_count: int
    documented_discontinuity_count: int
    step_equation_violation_count: int
    initial_state_violation_count: int
    key_sequence_gap_count: int
    mid_over_anomaly_count: int
    unresolved_termination_count: int


def _fmt_delivery_id(
    match_id: int,
    innings: int,
    overid: int,
    over_ball_num: int,
    innings_ball_num: int,
    prev_ib: int | None = None,
) -> str:
    base = f"match={match_id} inn={innings} ov={overid}.{over_ball_num} ib={innings_ball_num}"
    if prev_ib is not None:
        return f"{base} (prev_ib={prev_ib})"
    return base


def run_continuity_audit(
    states_df: pd.DataFrame,
    eligibility_df: pd.DataFrame | None = None,
) -> ContinuityAuditOutcome:
    """Validate intra-innings transition continuity without repairing source data.

    Checks across every sorted `(match_id, innings)` stream:
    1. Initial-row invariant (`before[first] == 0`, etc.).
    2. Consecutive transition continuity (`before[k] == after[k-1]`) for:
       - `score` (`score_before` vs prev `score_after`)
       - `wickets_lost` (`wickets_lost_before` vs prev `wickets_lost_after`)
       - `legal_balls_completed` (`legal_balls_completed_before` vs prev `legal_balls_completed_after`)
       - `retired_hurt_count` (`retired_hurt_count_before` vs prev `retired_hurt_count_after`)
       - `legal_balls_remaining` (when both rows have `is_innings_limit_verified == True`)
       - `runs_required` (in `innings == 2` when `is_target_known == True`)
    3. Step transition equation invariant (`after[k] == before[k] + delta[k]`).
    4. Contiguous `innings_ball_num` sequence (`starts at 1` and `diff == 1`).
    5. Documented source over-length sequence discontinuities (`overid < max_overid & over_legal != 6`)
       and premature unresolved termination (`50407`), audited transparently without mutation.
    """
    required_cols = {
        "match_id",
        "innings",
        "overid",
        "over_ball_num",
        "innings_ball_num",
        "score_before",
        "score_after",
        "wickets_lost_before",
        "wickets_lost_after",
        "legal_balls_completed_before",
        "legal_balls_completed_after",
        "retired_hurt_count_before",
        "retired_hurt_count_after",
        "legal_balls_remaining_before",
        "legal_balls_remaining",
        "innings_ball_limit",
        "is_innings_limit_verified",
        "target_runs",
        "is_target_known",
        "runs_required_before",
        "runs_required_after",
        "team_runs",
        "is_wicket_event",
        "is_legal_delivery",
        "is_retired_hurt_event",
        "match_regime",
    }
    missing = sorted(required_cols - set(states_df.columns))
    if missing:
        raise KeyError(f"states_df missing required continuity audit columns: {missing}")

    if len(states_df) == 0:
        empty_df = pd.DataFrame(columns=list(CONTINUITY_AUDIT_COLUMNS))
        return ContinuityAuditOutcome(
            audit_df=empty_df,
            total_rows_checked=0,
            total_innings_groups=0,
            unexpected_break_count=0,
            documented_discontinuity_count=0,
            step_equation_violation_count=0,
            initial_state_violation_count=0,
            key_sequence_gap_count=0,
            mid_over_anomaly_count=0,
            unresolved_termination_count=0,
        )

    df = states_df.sort_values(list(TRANSITION_KEY_COLUMNS), kind="mergesort").reset_index(drop=True)
    records: list[dict[str, Any]] = []

    grp = df.groupby(["match_id", "innings"], sort=False)
    total_innings_groups = int(grp.ngroups)

    same_group = (df["match_id"] == df["match_id"].shift(1)) & (
        df["innings"] == df["innings"].shift(1)
    )
    first_in_group = ~same_group

    unexpected_breaks = 0
    step_violations = 0
    initial_violations = 0
    key_gaps = 0
    documented_count = 0
    mid_over_count = 0
    unresolved_term_count = 0

    def _emit_row(
        idx_pos: int,
        *,
        field_affected: str,
        prev_val: Any,
        curr_val: Any,
        discrepancy: Any,
        classification: str,
        resolution_status: str,
        include_prev_ib: bool = False,
    ) -> None:
        r = df.iloc[idx_pos]
        prev_ib = int(df.iloc[idx_pos - 1]["innings_ball_num"]) if include_prev_ib and idx_pos > 0 else None
        records.append(
            {
                "match_id": int(r["match_id"]),
                "innings": int(r["innings"]),
                "delivery_identifier": _fmt_delivery_id(
                    int(r["match_id"]),
                    int(r["innings"]),
                    int(r["overid"]),
                    int(r["over_ball_num"]),
                    int(r["innings_ball_num"]),
                    prev_ib=prev_ib,
                ),
                "field_affected": field_affected,
                "previous_after_state": str(prev_val),
                "current_before_state": str(curr_val),
                "discrepancy": str(discrepancy),
                "classification": classification,
                "resolution_status": resolution_status,
            }
        )

    # 1. Initial state checks (first delivery of each innings)
    for col_name, label in (
        ("score_before", "score_before[first]"),
        ("wickets_lost_before", "wickets_lost_before[first]"),
        ("legal_balls_completed_before", "legal_balls_completed_before[first]"),
        ("retired_hurt_count_before", "retired_hurt_count_before[first]"),
    ):
        bad_init = first_in_group & (df[col_name].fillna(-999999) != 0)
        for pos in df.index[bad_init].tolist():
            initial_violations += 1
            unexpected_breaks += 1
            curr_val = df.at[pos, col_name]
            _emit_row(
                int(pos),
                field_affected=label,
                prev_val="0 (expected_innings_start)",
                curr_val=curr_val,
                discrepancy=int(curr_val) if pd.notna(curr_val) else "NA",
                classification="INITIAL_STATE_VIOLATION",
                resolution_status="CRITICAL_FAIL",
            )

    init_rem_bad = (
        first_in_group
        & df["is_innings_limit_verified"].fillna(False)
        & (df["legal_balls_remaining_before"] != df["innings_ball_limit"]).fillna(True)
    )
    for pos in df.index[init_rem_bad].tolist():
        initial_violations += 1
        unexpected_breaks += 1
        exp_lim = df.at[pos, "innings_ball_limit"]
        cur_rem = df.at[pos, "legal_balls_remaining_before"]
        diff = (int(cur_rem) - int(exp_lim)) if pd.notna(cur_rem) and pd.notna(exp_lim) else "NA_MISMATCH"
        _emit_row(
            int(pos),
            field_affected="legal_balls_remaining_before[first]",
            prev_val=exp_lim,
            curr_val=cur_rem,
            discrepancy=diff,
            classification="INITIAL_STATE_VIOLATION",
            resolution_status="CRITICAL_FAIL",
        )

    init_req_bad = (
        first_in_group
        & (df["innings"] == 2)
        & df["is_target_known"].fillna(False)
        & (df["runs_required_before"] != df["target_runs"]).fillna(True)
    )
    for pos in df.index[init_req_bad].tolist():
        initial_violations += 1
        unexpected_breaks += 1
        exp_tgt = df.at[pos, "target_runs"]
        cur_req = df.at[pos, "runs_required_before"]
        diff = (int(cur_req) - int(exp_tgt)) if pd.notna(cur_req) and pd.notna(exp_tgt) else "NA_MISMATCH"
        _emit_row(
            int(pos),
            field_affected="runs_required_before[first]",
            prev_val=exp_tgt,
            curr_val=cur_req,
            discrepancy=diff,
            classification="INITIAL_STATE_VIOLATION",
            resolution_status="CRITICAL_FAIL",
        )

    # 2. Consecutive state continuity checks: state_before[k] == state_after[k - 1]
    continuity_pairs: tuple[tuple[str, str, str, pd.Series | None], ...] = (
        ("score", "score_after", "score_before", None),
        ("wickets_lost", "wickets_lost_after", "wickets_lost_before", None),
        (
            "legal_balls_completed",
            "legal_balls_completed_after",
            "legal_balls_completed_before",
            None,
        ),
        ("retired_hurt_count", "retired_hurt_count_after", "retired_hurt_count_before", None),
        (
            "legal_balls_remaining",
            "legal_balls_remaining",
            "legal_balls_remaining_before",
            df["is_innings_limit_verified"].fillna(False)
            & df["is_innings_limit_verified"].shift(1).fillna(False),
        ),
        (
            "runs_required",
            "runs_required_after",
            "runs_required_before",
            (df["innings"] == 2) & df["is_target_known"].fillna(False),
        ),
    )

    for field_label, after_col, before_col, extra_mask in continuity_pairs:
        prev_after = df[after_col].shift(1)
        curr_before = df[before_col]
        mask = same_group
        if extra_mask is not None:
            mask = mask & extra_mask
        mismatch = mask & (
            (curr_before.isna() != prev_after.isna())
            | (
                curr_before.notna()
                & prev_after.notna()
                & (curr_before != prev_after)
            )
        )
        for pos in df.index[mismatch.fillna(False)].tolist():
            unexpected_breaks += 1
            pv = prev_after.iloc[pos]
            cb = curr_before.iloc[pos]
            diff = (int(cb) - int(pv)) if pd.notna(cb) and pd.notna(pv) else "NA_MISMATCH"
            _emit_row(
                int(pos),
                field_affected=field_label,
                prev_val=pv,
                curr_val=cb,
                discrepancy=diff,
                classification="UNEXPECTED_CONTINUITY_BREAK",
                resolution_status="CRITICAL_FAIL",
                include_prev_ib=True,
            )

    # 3. Step transition equations: after[k] == before[k] + delta[k]
    step_checks: tuple[tuple[str, pd.Series, pd.Series, pd.Series], ...] = (
        ("score_step", df["score_after"], df["score_before"], df["team_runs"]),
        (
            "wickets_step",
            df["wickets_lost_after"],
            df["wickets_lost_before"],
            df["is_wicket_event"].astype("Int64"),
        ),
        (
            "legal_balls_step",
            df["legal_balls_completed_after"],
            df["legal_balls_completed_before"],
            df["is_legal_delivery"].astype("Int64"),
        ),
        (
            "retired_hurt_step",
            df["retired_hurt_count_after"],
            df["retired_hurt_count_before"],
            df["is_retired_hurt_event"].astype("Int64"),
        ),
    )
    for label, after_s, before_s, delta_s in step_checks:
        expected_after = before_s + delta_s
        bad_step = (after_s != expected_after).fillna(True)
        for pos in df.index[bad_step].tolist():
            step_violations += 1
            unexpected_breaks += 1
            ea = expected_after.iloc[pos]
            af = after_s.iloc[pos]
            diff = (int(af) - int(ea)) if pd.notna(af) and pd.notna(ea) else "NA_MISMATCH"
            _emit_row(
                int(pos),
                field_affected=label,
                prev_val=ea,
                curr_val=af,
                discrepancy=diff,
                classification="STEP_EQUATION_VIOLATION",
                resolution_status="CRITICAL_FAIL",
            )

    # 4. Contiguous innings_ball_num sequence check (1, 2, 3, ...)
    init_ib_bad = first_in_group & (df["innings_ball_num"] != 1)
    for pos in df.index[init_ib_bad].tolist():
        key_gaps += 1
        unexpected_breaks += 1
        _emit_row(
            int(pos),
            field_affected="innings_ball_num[first]",
            prev_val="1 (expected_start)",
            curr_val=int(df.at[pos, "innings_ball_num"]),
            discrepancy=int(df.at[pos, "innings_ball_num"]) - 1,
            classification="UNEXPECTED_SEQUENCE_START_GAP",
            resolution_status="CRITICAL_FAIL",
        )

    ib_gap = same_group & ((df["innings_ball_num"] - df["innings_ball_num"].shift(1)) != 1)
    for pos in df.index[ib_gap.fillna(False)].tolist():
        key_gaps += 1
        unexpected_breaks += 1
        prev_ib_v = int(df.iloc[pos - 1]["innings_ball_num"])
        curr_ib_v = int(df.iloc[pos]["innings_ball_num"])
        _emit_row(
            int(pos),
            field_affected="innings_ball_num_gap",
            prev_val=prev_ib_v,
            curr_val=curr_ib_v,
            discrepancy=curr_ib_v - prev_ib_v - 1,
            classification="UNEXPECTED_INNINGS_BALL_GAP",
            resolution_status="CRITICAL_FAIL",
            include_prev_ib=True,
        )

    # 5. Documented feed/over sequence discontinuities in regulation innings (read-only audit)
    reg_df = df.loc[df["innings"].isin([1, 2])].copy()
    if len(reg_df) > 0:
        reg_df["_legal_int"] = reg_df["is_legal_delivery"].astype("int64")
        ov_agg = (
            reg_df.groupby(["match_id", "innings", "overid"], sort=False)
            .agg(
                over_legal=("_legal_int", "sum"),
                last_over_ball=("over_ball_num", "max"),
                last_ib=("innings_ball_num", "max"),
                match_regime=("match_regime", "first"),
            )
            .reset_index()
        )
        max_ov = (
            ov_agg.groupby(["match_id", "innings"], sort=False)["overid"]
            .max()
            .reset_index(name="max_overid")
        )
        ov_chk = ov_agg.merge(max_ov, on=["match_id", "innings"], how="left")
        mid_anom = ov_chk.loc[(ov_chk["overid"] < ov_chk["max_overid"]) & (ov_chk["over_legal"] != 6)]
        for _, r in mid_anom.iterrows():
            is_quarantined = str(r["match_regime"]) == "INCOMPLETE_OR_UNRESOLVED"
            documented_count += 1
            mid_over_count += 1
            if not is_quarantined:
                unexpected_breaks += 1
            records.append(
                {
                    "match_id": int(r["match_id"]),
                    "innings": int(r["innings"]),
                    "delivery_identifier": f"match={int(r['match_id'])} inn={int(r['innings'])} ov={int(r['overid'])} (up to ob={int(r['last_over_ball'])}, ib={int(r['last_ib'])})",
                    "field_affected": "over_legal_ball_count",
                    "previous_after_state": "6 legal_balls_expected_mid_over",
                    "current_before_state": f"{int(r['over_legal'])} legal_balls_recorded",
                    "discrepancy": str(int(r["over_legal"]) - 6),
                    "classification": (
                        "DOCUMENTED_SOURCE_SEQUENCE_ANOMALY"
                        if is_quarantined
                        else "UNEXPECTED_MID_OVER_ANOMALY"
                    ),
                    "resolution_status": (
                        "QUARANTINED_IN_INCOMPLETE_OR_UNRESOLVED (excluded from primary dataset; raw rows unaltered)"
                        if is_quarantined
                        else "CRITICAL_FAIL"
                    ),
                }
            )

    # 6. Documented premature unresolved termination (50407 / INCOMPLETE_OR_UNRESOLVED)
    unresolved_rows = df.loc[
        (df["match_regime"] == "INCOMPLETE_OR_UNRESOLVED")
        & (df["innings"] == 2)
        & (df["match_id"] == UNRESOLVED_50407_MATCH_ID)
    ]
    if len(unresolved_rows) > 0:
        last_50407 = unresolved_rows.iloc[-1]
        documented_count += 1
        unresolved_term_count += 1
        records.append(
            {
                "match_id": int(last_50407["match_id"]),
                "innings": int(last_50407["innings"]),
                "delivery_identifier": _fmt_delivery_id(
                    int(last_50407["match_id"]),
                    int(last_50407["innings"]),
                    int(last_50407["overid"]),
                    int(last_50407["over_ball_num"]),
                    int(last_50407["innings_ball_num"]),
                ),
                "field_affected": "innings_termination_legal_balls",
                "previous_after_state": (
                    f"score={int(last_50407['score_after'])}/{int(last_50407['wickets_lost_after'])} "
                    f"in {int(last_50407['legal_balls_completed_after'])}b"
                ),
                "current_before_state": "match_ended_no_further_deliveries (expected 120b or 10th wkt or chase)",
                "discrepancy": f"{int(last_50407['legal_balls_completed_after']) - 120} legal_balls (stops at 20.5 wide-5)",
                "classification": "DOCUMENTED_UNRESOLVED_TERMINATION",
                "resolution_status": UNRESOLVED_50407_AUDIT_STATUS,
            }
        )

    audit_df = (
        pd.DataFrame(records, columns=list(CONTINUITY_AUDIT_COLUMNS))
        if records
        else pd.DataFrame(columns=list(CONTINUITY_AUDIT_COLUMNS))
    )
    return ContinuityAuditOutcome(
        audit_df=audit_df,
        total_rows_checked=int(len(df)),
        total_innings_groups=total_innings_groups,
        unexpected_break_count=unexpected_breaks,
        documented_discontinuity_count=documented_count,
        step_equation_violation_count=step_violations,
        initial_state_violation_count=initial_violations,
        key_sequence_gap_count=key_gaps,
        mid_over_anomaly_count=mid_over_count,
        unresolved_termination_count=unresolved_term_count,
    )


def validate_match_state_dataset(
    *,
    all_states_df: pd.DataFrame,
    primary_states_df: pd.DataFrame,
    eligibility_df: pd.DataFrame,
    raw_ball_by_ball: pd.DataFrame,
    raw_matches: pd.DataFrame,
    raw_competitions: pd.DataFrame,
) -> dict[str, Any]:
    """Execute full Stage 5B §17 validation suite across all 13 categories.

    Returns a structured dictionary containing `ValidationResult` entries, exact category metrics,
    continuity audit outcome, status counts, and `has_critical_failure`.
    """
    results: list[ValidationResult] = []
    continuity = run_continuity_audit(all_states_df, eligibility_df)

    # 1. VAL-5B-KEY-001: Unique transition key, zero duplicates, strict sort order
    key_cols = list(TRANSITION_KEY_COLUMNS)
    null_keys_all = int(all_states_df[key_cols].isna().any(axis=1).sum())
    dup_all = int(all_states_df.duplicated(subset=key_cols, keep=False).sum())
    dup_pri = int(primary_states_df.duplicated(subset=key_cols, keep=False).sum())
    expected_pri_rows = int(all_states_df["is_primary_wp_train_eligible"].fillna(False).sum())
    pri_row_diff = abs(len(primary_states_df) - expected_pri_rows)

    sorted_pri = primary_states_df[key_cols].sort_values(key_cols, kind="mergesort")
    unsorted_pri = not sorted_pri.index.equals(primary_states_df.index)
    sorted_all = all_states_df[key_cols].sort_values(key_cols, kind="mergesort")
    unsorted_all = not sorted_all.index.equals(all_states_df.index)
    key_errs = null_keys_all + dup_all + dup_pri + pri_row_diff + int(unsorted_pri) + int(unsorted_all)
    results.append(
        ValidationResult(
            rule_id="VAL-5B-KEY-001",
            dataset="match_states_all,match_states_primary",
            field="match_id, innings, innings_ball_num",
            severity=Severity.CRITICAL,
            status=ValidationStatus.PASS if key_errs == 0 else ValidationStatus.FAIL,
            affected_record_count=key_errs,
            new_anomaly_count=key_errs,
            short_description=(
                f"Unique non-null transition key verified cleanly across {len(all_states_df):,} total "
                f"and {len(primary_states_df):,} primary rows (0 duplicates, strictly sorted)."
                if key_errs == 0
                else f"Detected {key_errs} transition-key / ordering / row-partition violation(s)."
            ),
            recommended_action="Sort strictly by (match_id, innings, innings_ball_num) and enforce unique delivery keys.",
            metadata={
                "all_rows": int(len(all_states_df)),
                "primary_rows": int(len(primary_states_df)),
                "null_keys_all": null_keys_all,
                "duplicate_rows_all": dup_all,
                "duplicate_rows_primary": dup_pri,
                "row_partition_diff": pri_row_diff,
            },
        )
    )

    # 2. VAL-5B-ELG-001: Included match eligibility & exclusion reason completeness
    bad_pri_regime = int((primary_states_df["match_regime"] != "STANDARD_T20").sum())
    bad_pri_inn = int((~primary_states_df["innings"].isin([1, 2])).sum())
    bad_pri_lim = int((~primary_states_df["is_innings_limit_verified"].fillna(False)).sum())
    bad_pri_tgt = int(primary_states_df["target_batting_team_win"].isna().sum())
    bad_pri_excl = int(primary_states_df["eligibility_exclusion_reason"].notna().sum())
    leak_50407 = int((primary_states_df["match_id"] == UNRESOLVED_50407_MATCH_ID).sum())

    excl_elg = eligibility_df.loc[~eligibility_df["is_primary_wp_train_eligible"].fillna(False)]
    missing_excl_reason = int(excl_elg["eligibility_exclusion_reason"].isna().sum())
    elig_elg = eligibility_df.loc[eligibility_df["is_primary_wp_train_eligible"].fillna(False)]
    unexpected_elig_reason = int(elig_elg["eligibility_exclusion_reason"].notna().sum())
    elg_50407 = eligibility_df.loc[eligibility_df["match_id"] == UNRESOLVED_50407_MATCH_ID]
    bad_50407_reason = 0
    if len(elg_50407) > 0:
        if (
            bool(elg_50407["is_primary_wp_train_eligible"].iloc[0])
            or str(elg_50407["eligibility_exclusion_reason"].iloc[0]) != UNRESOLVED_50407_EXCLUSION_REASON
        ):
            bad_50407_reason = 1

    elg_errs = (
        bad_pri_regime
        + bad_pri_inn
        + bad_pri_lim
        + bad_pri_tgt
        + bad_pri_excl
        + leak_50407
        + missing_excl_reason
        + unexpected_elig_reason
        + bad_50407_reason
    )
    results.append(
        ValidationResult(
            rule_id="VAL-5B-ELG-001",
            dataset="match_eligibility,match_states_primary",
            field="match_regime, is_primary_wp_train_eligible, eligibility_exclusion_reason",
            severity=Severity.CRITICAL,
            status=ValidationStatus.PASS if elg_errs == 0 else ValidationStatus.FAIL,
            affected_record_count=elg_errs,
            new_anomaly_count=elg_errs,
            short_description=(
                f"Primary dataset strictly contains {int(elig_elg['match_id'].nunique())} STANDARD_T20 matches; "
                f"all {len(excl_elg)} excluded matches (incl. 50407) retain non-null exclusion reasons."
                if elg_errs == 0
                else f"Detected {elg_errs} eligibility gate or quarantine violation(s)."
            ),
            recommended_action="Ensure only verified STANDARD_T20 regulation innings enter primary dataset.",
            metadata={
                "total_matches": int(len(eligibility_df)),
                "primary_included_matches": int(primary_states_df["match_id"].nunique()),
                "excluded_matches": int(len(excl_elg)),
                "leak_50407_rows": leak_50407,
                "missing_exclusion_reasons": missing_excl_reason,
            },
        )
    )

    # 3. VAL-5B-SCR-001: Score reconciliation vs raw ball_by_ball & chase outcome invariants
    raw_tr = derive_team_runs(raw_ball_by_ball)
    tr_mismatch = int(
        (
            all_states_df["team_runs"]
            != (
                all_states_df["batter_runs"]
                + all_states_df["extras1_runs"]
                + all_states_df["extras_2_runs"]
            )
        ).sum()
    )
    raw_grp = (
        raw_ball_by_ball.assign(_tr=raw_tr)
        .groupby(["match_id", "innings"], sort=False)["_tr"]
        .sum()
    )
    state_grp = (
        all_states_df.groupby(["match_id", "innings"], sort=False)["score_after"]
        .max()
    )
    reconcile_score = raw_grp.align(state_grp, join="outer", fill_value=-1)
    score_inn_diff = int((reconcile_score[0] != reconcile_score[1]).sum())

    # Check primary chase winner and overshoot invariant
    pri_inn_final = (
        primary_states_df.groupby(["match_id", "innings"], sort=False)
        .agg(
            runs=("score_after", "max"),
            batting_team_id=("batting_team_id", "first"),
            last_runs=("team_runs", "last"),
            win_team_id=("win_team_id_raw", "first"),
        )
        .reset_index()
    )
    p1 = pri_inn_final.loc[pri_inn_final["innings"] == 1].set_index("match_id")
    p2 = pri_inn_final.loc[pri_inn_final["innings"] == 2].set_index("match_id")
    win_fail = 0
    chase_fail = 0
    for mid in p1.index:
        if mid not in p2.index:
            win_fail += 1
            continue
        s1 = int(p1.at[mid, "runs"])
        s2 = int(p2.at[mid, "runs"])
        t1 = int(p1.at[mid, "batting_team_id"])
        t2 = int(p2.at[mid, "batting_team_id"])
        wt = int(p1.at[mid, "win_team_id"])
        exp_w = t1 if s1 > s2 else (t2 if s2 > s1 else -1)
        if exp_w != wt:
            win_fail += 1
        if s2 > s1:
            ov = s2 - s1
            if not ((s2 - int(p2.at[mid, "last_runs"])) <= s1 and 1 <= ov <= 6):
                chase_fail += 1

    scr_errs = tr_mismatch + score_inn_diff + win_fail + chase_fail
    ext_anom_rows = int(all_states_df["has_extras_anomaly"].fillna(False).sum())
    results.append(
        ValidationResult(
            rule_id="VAL-5B-SCR-001",
            dataset="match_states_all,match_states_primary",
            field="team_runs, score_before, score_after",
            severity=Severity.CRITICAL,
            status=ValidationStatus.PASS if scr_errs == 0 else ValidationStatus.FAIL,
            affected_record_count=scr_errs,
            new_anomaly_count=scr_errs,
            short_description=(
                f"100% score reconciliation verified across {len(raw_grp):,} innings "
                f"(total runs={int(raw_tr.sum()):,}; {len(p1)}/{len(p1)} primary winners & chase bounds match)."
                if scr_errs == 0
                else f"Detected {scr_errs} score or chase reconciliation mismatch(es)."
            ),
            recommended_action="Ensure cumulative score_after = cumsum(runs + extras1_runs + extras_2_runs).",
            metadata={
                "raw_total_runs": int(raw_tr.sum()),
                "innings_checked": int(len(raw_grp)),
                "team_runs_formula_mismatches": tr_mismatch,
                "innings_total_mismatches": score_inn_diff,
                "primary_winner_mismatches": win_fail,
                "primary_chase_invariant_failures": chase_fail,
                "rows_in_extras_anomaly_matches": ext_anom_rows,
            },
        )
    )

    # 4. VAL-5B-WKT-001: Wicket reconciliation (Retired Hurt vs Retire Out vs 40709)
    raw_wkt_sum = int(raw_ball_by_ball["is_wicket"].sum())
    state_wkt_sum = int(all_states_df["is_wicket_event"].sum())
    rh_cnt = int(all_states_df["is_retired_hurt_event"].sum())
    ro_cnt = int(all_states_df["is_retire_out_event"].sum())
    rh_wkt_leak = int(
        (all_states_df["is_retired_hurt_event"] & all_states_df["is_wicket_event"]).sum()
    )
    non_mono_wkt = int(
        (
            all_states_df.groupby(["match_id", "innings"], sort=False)["wickets_lost_after"]
            .diff()
            .fillna(0)
            < 0
        ).sum()
    )
    out_range_wkt = int((~all_states_df["wickets_lost_after"].between(0, 10)).sum())
    # Ensure missing dismissed_player_id is NEVER fabricated
    fab_dis = int(
        (
            all_states_df["dismissed_player_id_raw"].isna()
            & all_states_df["resolved_dismissed_player_id"].notna()
        ).sum()
    )
    r40709 = all_states_df.loc[
        (all_states_df["match_id"] == 40709)
        & (all_states_df["innings"] == 2)
        & (all_states_df["overid"] == 19)
        & (all_states_df["over_ball_num"] == 5)
    ]
    bad_40709 = 0
    if len(r40709) > 0:
        row40 = r40709.iloc[0]
        if (
            not bool(row40["is_wicket_event"])
            or not bool(row40["is_retire_out_event"])
            or not bool(row40["is_dismissed_player_unresolved"])
            or pd.notna(row40["resolved_dismissed_player_id"])
        ):
            bad_40709 = 1

    raw_grp_wkt = (
        raw_ball_by_ball.groupby(["match_id", "innings"], sort=False)["is_wicket"].sum()
    )
    st_grp_wkt = (
        all_states_df.groupby(["match_id", "innings"], sort=False)["wickets_lost_after"].max()
    )
    rw1, sw1 = raw_grp_wkt.align(st_grp_wkt, join="outer", fill_value=-1)
    inn_wkt_diff = int((rw1 != sw1).sum())

    wkt_errs = (
        abs(raw_wkt_sum - state_wkt_sum)
        + rh_wkt_leak
        + non_mono_wkt
        + out_range_wkt
        + fab_dis
        + bad_40709
        + inn_wkt_diff
    )
    results.append(
        ValidationResult(
            rule_id="VAL-5B-WKT-001",
            dataset="match_states_all",
            field="is_wicket_event, wickets_lost_after, is_retired_hurt_event, is_retire_out_event",
            severity=Severity.CRITICAL,
            status=ValidationStatus.PASS if wkt_errs == 0 else ValidationStatus.FAIL,
            affected_record_count=wkt_errs,
            new_anomaly_count=wkt_errs,
            short_description=(
                f"100% wicket reconciliation across {raw_wkt_sum:,} official wickets "
                f"(Retired Hurt={rh_cnt} adds +0; Retire Out={ro_cnt} adds +1; 0 fabricated IDs)."
                if wkt_errs == 0
                else f"Detected {wkt_errs} wicket/retirement reconciliation violation(s)."
            ),
            recommended_action="Track wickets strictly via is_wicket; never fabricate missing dismissed_player_id.",
            metadata={
                "official_wickets_total": raw_wkt_sum,
                "retired_hurt_count": rh_cnt,
                "retire_out_count": ro_cnt,
                "unresolved_dismissed_player_count": int(
                    all_states_df["is_dismissed_player_unresolved"].sum()
                ),
                "obstructing_typos_normalized_in_canonical": int(
                    (all_states_df["dismissal_type_raw"] == "Obstracting the field").fillna(False).sum()
                ),
            },
        )
    )

    # 5. VAL-5B-LGL-001: Legal-ball reconciliation
    raw_legal = derive_is_legal_delivery(raw_ball_by_ball)
    raw_legal_sum = int(raw_legal.sum())
    state_legal_sum = int(all_states_df["is_legal_delivery"].sum())
    bad_wide_legal = int(
        (all_states_df["is_wide"] & all_states_df["is_legal_delivery"]).sum()
    )
    bad_nb_legal = int(
        (all_states_df["is_no_ball"] & all_states_df["is_legal_delivery"]).sum()
    )
    raw_grp_leg = (
        raw_ball_by_ball.assign(_leg=raw_legal)
        .groupby(["match_id", "innings"], sort=False)["_leg"]
        .sum()
    )
    st_grp_leg = (
        all_states_df.groupby(["match_id", "innings"], sort=False)["legal_balls_completed_after"].max()
    )
    rl1, sl1 = raw_grp_leg.align(st_grp_leg, join="outer", fill_value=-1)
    inn_leg_diff = int((rl1 != sl1).sum())
    lgl_errs = abs(raw_legal_sum - state_legal_sum) + bad_wide_legal + bad_nb_legal + inn_leg_diff
    results.append(
        ValidationResult(
            rule_id="VAL-5B-LGL-001",
            dataset="match_states_all",
            field="is_legal_delivery, legal_balls_completed_after",
            severity=Severity.CRITICAL,
            status=ValidationStatus.PASS if lgl_errs == 0 else ValidationStatus.FAIL,
            affected_record_count=lgl_errs,
            new_anomaly_count=lgl_errs,
            short_description=(
                f"100% legal-ball reconciliation ({raw_legal_sum:,} legal, "
                f"{len(raw_legal) - raw_legal_sum:,} non-legal wide/Overstep/other deliveries)."
                if lgl_errs == 0
                else f"Detected {lgl_errs} legal-ball calculation mismatch(es)."
            ),
            recommended_action="Apply exact Stage 5A legal rule: extras_type not in {'wide', 'Overstep', 'other'}.",
            metadata={
                "legal_deliveries_total": raw_legal_sum,
                "illegal_deliveries_total": int(len(raw_legal) - raw_legal_sum),
                "wide_rows": int(all_states_df["is_wide"].sum()),
                "no_ball_rows": int(all_states_df["is_no_ball"].sum()),
            },
        )
    )

    # 6. VAL-5B-LIM-001: Innings limit verification & un-clamped negative-balls guard (CRITICAL)
    ver = all_states_df["is_innings_limit_verified"].fillna(False)
    unver = ~ver
    bad_unver_cols = int(
        (
            (unver & all_states_df["innings_ball_limit"].notna())
            | (unver & all_states_df["legal_balls_remaining"].notna())
            | (unver & all_states_df["legal_balls_remaining_before"].notna())
            | (unver & all_states_df["innings_progress_pct"].notna())
            | (unver & all_states_df["required_run_rate"].notna())
            | (unver & all_states_df["innings_limit_unavailable_reason"].isna())
        ).sum()
    )
    bad_ver_cols = int(
        (
            (ver & all_states_df["innings_ball_limit"].isna())
            | (ver & all_states_df["legal_balls_remaining"].isna())
            | (ver & all_states_df["legal_balls_remaining_before"].isna())
            | (ver & all_states_df["innings_limit_unavailable_reason"].notna())
        ).sum()
    )
    # Check un-clamped exact equation where verified
    exp_rem = all_states_df.loc[ver, "innings_ball_limit"] - all_states_df.loc[ver, "legal_balls_completed_after"]
    bad_rem_eq = int((all_states_df.loc[ver, "legal_balls_remaining"] != exp_rem).sum())
    neg_rem_all = int(all_states_df["is_legal_balls_remaining_negative"].fillna(False).sum())
    neg_rem_pri = int(primary_states_df["is_legal_balls_remaining_negative"].fillna(False).sum())
    lim_errs = bad_unver_cols + bad_ver_cols + bad_rem_eq + neg_rem_all + neg_rem_pri

    ver_rows_all = int(ver.sum())
    unver_rows_all = int(unver.sum())
    inn_lim_summary = (
        all_states_df.groupby(["match_id", "innings"], sort=False)
        .agg(
            verified=("is_innings_limit_verified", "first"),
            limit=("innings_ball_limit", "first"),
            source=("innings_limit_source", "first"),
        )
        .reset_index()
    )
    ver_inn_cnt = int(inn_lim_summary["verified"].fillna(False).sum())
    unver_inn_cnt = int((~inn_lim_summary["verified"].fillna(False)).sum())

    results.append(
        ValidationResult(
            rule_id="VAL-5B-LIM-001",
            dataset="match_states_all,match_states_primary",
            field="innings_ball_limit, is_innings_limit_verified, legal_balls_remaining, is_legal_balls_remaining_negative",
            severity=Severity.CRITICAL,
            status=ValidationStatus.PASS if lim_errs == 0 else ValidationStatus.FAIL,
            affected_record_count=lim_errs,
            new_anomaly_count=lim_errs,
            short_description=(
                f"Verified innings limits across {ver_inn_cnt:,}/{len(inn_lim_summary):,} innings "
                f"({ver_rows_all:,}/{len(all_states_df):,} deliveries); {unver_inn_cnt} missing-metadata "
                f"innings kept strictly pd.NA ({unver_rows_all:,} deliveries); {neg_rem_all} negative remaining-ball rows."
                if lim_errs == 0
                else f"Detected {lim_errs} innings-limit contract violation(s) (neg_rem={neg_rem_all}, unver_leak={bad_unver_cols})."
            ),
            recommended_action="Never substitute 0/120 or infer limits when metadata missing; never clamp negative remaining balls.",
            metadata={
                "verified_innings": ver_inn_cnt,
                "unverified_innings": unver_inn_cnt,
                "verified_deliveries_all": ver_rows_all,
                "unverified_deliveries_all": unver_rows_all,
                "verified_deliveries_primary": int(primary_states_df["is_innings_limit_verified"].sum()),
                "negative_legal_balls_remaining_all": neg_rem_all,
                "negative_legal_balls_remaining_primary": neg_rem_pri,
                "limit_source_counts_all": {
                    str(k): int(v)
                    for k, v in all_states_df["innings_limit_source"].value_counts(dropna=False).items()
                },
            },
        )
    )

    # 7. VAL-5B-CHS-001: Chase & RRR/CRR calculation validity
    not_inn2 = all_states_df["innings"] != 2
    chase_leak_non_inn2 = int(
        (
            (not_inn2 & all_states_df["innings1_total_score"].notna())
            | (not_inn2 & all_states_df["target_runs"].notna())
            | (not_inn2 & all_states_df["runs_required_before"].notna())
            | (not_inn2 & all_states_df["runs_required_after"].notna())
            | (not_inn2 & all_states_df["required_run_rate"].notna())
            | (not_inn2 & all_states_df["rrr_minus_crr"].notna())
            | (not_inn2 & all_states_df["is_target_known"].fillna(False))
        ).sum()
    )
    bad_rrr_zero_div = int(
        (
            all_states_df["is_innings_limit_verified"].fillna(False)
            & (all_states_df["legal_balls_remaining"].fillna(1) <= 0)
            & (all_states_df["runs_required_after"].fillna(0) > 0)
            & all_states_df["required_run_rate"].notna()
        ).sum()
    )
    bad_rrr_achieved = int(
        (
            (all_states_df["innings"] == 2)
            & all_states_df["is_target_known"].fillna(False)
            & all_states_df["is_innings_limit_verified"].fillna(False)
            & (all_states_df["runs_required_after"] == 0).fillna(False)
            & (all_states_df["required_run_rate"].fillna(-1.0) != 0.0)
        ).sum()
    )
    bad_crr_zero = int(
        (
            (all_states_df["legal_balls_completed_after"] == 0)
            & (all_states_df["current_run_rate"] != 0.0)
        ).sum()
    )
    chs_errs = chase_leak_non_inn2 + bad_rrr_zero_div + bad_rrr_achieved + bad_crr_zero
    results.append(
        ValidationResult(
            rule_id="VAL-5B-CHS-001",
            dataset="match_states_all,match_states_primary",
            field="innings1_total_score, target_runs, runs_required_after, required_run_rate, current_run_rate",
            severity=Severity.CRITICAL,
            status=ValidationStatus.PASS if chs_errs == 0 else ValidationStatus.FAIL,
            affected_record_count=chs_errs,
            new_anomaly_count=chs_errs,
            short_description=(
                f"Zero Innings 1 chase-field leakage; CRR/RRR zero-division and target-achieved guards verified."
                if chs_errs == 0
                else f"Detected {chs_errs} chase or run-rate guard violation(s)."
            ),
            recommended_action="Keep all chase fields strictly pd.NA outside Innings 2 and guard RRR when unverified or rem <= 0.",
            metadata={
                "chase_leak_non_inn2": chase_leak_non_inn2,
                "bad_rrr_zero_div": bad_rrr_zero_div,
                "bad_rrr_achieved": bad_rrr_achieved,
                "bad_crr_zero": bad_crr_zero,
                "inn2_known_target_rows_all": int(all_states_df["is_target_known"].sum()),
                "rrr_defined_rows_all": int((~all_states_df["is_rrr_undefined"]).sum()),
            },
        )
    )

    # 8. VAL-5B-CNT-001: State continuity (CRITICAL fail on unexpected breaks; WARNING on documented quarantined discontinuities)
    cnt_crit = continuity.unexpected_break_count
    cnt_doc = continuity.documented_discontinuity_count
    cnt_status = (
        ValidationStatus.FAIL
        if cnt_crit > 0
        else (ValidationStatus.WARNING if cnt_doc > 0 else ValidationStatus.PASS)
    )
    cnt_sev = Severity.CRITICAL if cnt_crit > 0 else Severity.WARNING
    results.append(
        ValidationResult(
            rule_id="VAL-5B-CNT-001",
            dataset="match_states_all",
            field="score_before/after, wickets_lost_before/after, legal_balls_completed_before/after",
            severity=cnt_sev,
            status=cnt_status,
            affected_record_count=cnt_crit + cnt_doc,
            known_exception_count=cnt_doc if cnt_crit == 0 else 0,
            new_anomaly_count=cnt_crit,
            short_description=(
                f"0 unexpected state continuity breaks across {continuity.total_rows_checked:,} transitions "
                f"({continuity.total_innings_groups:,} innings); {cnt_doc} documented source sequence/termination "
                f"discontinuity record(s) logged in quarantined INCOMPLETE_OR_UNRESOLVED matches."
                if cnt_crit == 0
                else f"CRITICAL: Detected {cnt_crit} unexpected continuity / step / initial-state break(s)!"
            ),
            example_record_identifiers=(
                continuity.audit_df["delivery_identifier"].head(6).tolist()
                if len(continuity.audit_df) > 0
                else []
            ),
            recommended_action="Investigate unexpected breaks immediately; keep documented 14130/14164/41509/50407 discontinuities quarantined.",
            known_exceptions_summary=(
                "Documented sequence discontinuities in 14130 (inn1/2 ov14), 14164 (inn1 ov14), 41509 (inn1 ov12), "
                "and premature termination in 50407 (inn2 20.5) are quarantined out of primary training."
                if cnt_doc > 0
                else None
            ),
            metadata={
                "total_rows_checked": continuity.total_rows_checked,
                "total_innings_groups": continuity.total_innings_groups,
                "unexpected_break_count": cnt_crit,
                "documented_discontinuity_count": cnt_doc,
                "step_equation_violations": continuity.step_equation_violation_count,
                "initial_state_violations": continuity.initial_state_violation_count,
                "key_sequence_gaps": continuity.key_sequence_gap_count,
            },
        )
    )

    # 9. VAL-5B-NUL-001: Null semantics, literal 'None' preservation & 101-column dtype contract
    bad_cols = 0 if tuple(primary_states_df.columns) == EXPECTED_COLUMN_ORDER else 1
    bad_cols_all = 0 if tuple(all_states_df.columns) == EXPECTED_COLUMN_ORDER else 1
    null_extras = int(all_states_df["extras_type"].isna().sum())
    bad_extras_dom = int((~all_states_df["extras_type"].isin(VALID_EXTRAS_TYPES)).sum())
    nonnull_contract_fails = 0
    for spec in COLUMN_SPECS:
        if not spec.nullable:
            nonnull_contract_fails += int(all_states_df[spec.name].isna().sum())
        if str(all_states_df[spec.name].dtype) != spec.dtype:
            bad_cols_all += 1
        if str(primary_states_df[spec.name].dtype) != spec.dtype:
            bad_cols += 1

    nul_errs = bad_cols + bad_cols_all + null_extras + bad_extras_dom + nonnull_contract_fails
    literal_none_cnt = int((all_states_df["extras_type"] == "None").sum())
    results.append(
        ValidationResult(
            rule_id="VAL-5B-NUL-001",
            dataset="match_states_all,match_states_primary",
            field="101-column schema, extras_type",
            severity=Severity.CRITICAL,
            status=ValidationStatus.PASS if nul_errs == 0 else ValidationStatus.FAIL,
            affected_record_count=nul_errs,
            new_anomaly_count=nul_errs,
            short_description=(
                f"All {len(EXPECTED_COLUMN_ORDER)} columns conform exactly to Stage 5A Revision 1.1 dtypes and "
                f"nullability contracts; literal 'None' extras_type preserved ({literal_none_cnt:,} rows)."
                if nul_errs == 0
                else f"Detected {nul_errs} dtype, nullability, or literal-'None' preservation violation(s)."
            ),
            recommended_action="Preserve nullable extension dtypes (Int64/Float64/boolean/string) and literal 'None' extras_type.",
            metadata={
                "column_count": len(EXPECTED_COLUMN_ORDER),
                "literal_none_extras_type_rows": literal_none_cnt,
                "nonnull_contract_violations": nonnull_contract_fails,
            },
        )
    )

    # 10. VAL-5B-CMP-001: Competition metadata preservation & taxonomy integrity
    comp_map = raw_competitions.set_index("comp_id")[["comp_name", "match_format", "season"]]
    st_comp = all_states_df[["match_id", "comp_id", "comp_name", "match_format", "season", "competition_category"]].drop_duplicates("match_id")
    joined_comp = st_comp.merge(comp_map, on="comp_id", how="left", suffixes=("", "_raw"))
    comp_mismatch = int(
        (
            joined_comp["comp_name_raw"].isna()
            | (joined_comp["comp_name"] != joined_comp["comp_name_raw"])
            | (joined_comp["match_format"] != joined_comp["match_format_raw"])
            | (joined_comp["season"] != joined_comp["season_raw"])
            | (~joined_comp["competition_category"].isin(["IPL", "OTHER_T20", "T20I"]))
            | ((joined_comp["match_format"] == "T20I") & (joined_comp["competition_category"] != "T20I"))
            | (
                (joined_comp["match_format"] == "T20")
                & joined_comp["comp_name"].str.startswith("IPL", na=False)
                & (joined_comp["competition_category"] != "IPL")
            )
        ).sum()
    )
    results.append(
        ValidationResult(
            rule_id="VAL-5B-CMP-001",
            dataset="match_states_all,competitions",
            field="comp_id, comp_name, match_format, competition_category, season",
            severity=Severity.CRITICAL,
            status=ValidationStatus.PASS if comp_mismatch == 0 else ValidationStatus.FAIL,
            affected_record_count=comp_mismatch,
            new_anomaly_count=comp_mismatch,
            short_description=(
                f"Original competition metadata preserved 100% verbatim alongside verified competition_category "
                f"across {len(st_comp):,} played matches."
                if comp_mismatch == 0
                else f"Detected {comp_mismatch} competition metadata or category derivation violation(s)."
            ),
            recommended_action="Derive competition_category strictly from competitions.match_format + comp_name.",
            metadata={
                "primary_matches_by_category": {
                    str(k): int(v)
                    for k, v in eligibility_df.loc[
                        eligibility_df["is_primary_wp_train_eligible"].fillna(False),
                        "competition_category",
                    ]
                    .value_counts()
                    .items()
                },
                "all_matches_by_category": {
                    str(k): int(v)
                    for k, v in eligibility_df["competition_category"].value_counts().items()
                },
            },
        )
    )

    # 11. VAL-5B-TGT-001: Target correctness & leakage role separation
    overlap_roles = set(MODEL_FEATURE_COLUMNS) & (set(TARGET_COLUMNS) | set(REGIME_AUDIT_COLUMNS))
    unlabeled_mask = all_states_df["match_regime"].isin(["ABANDONED", "NO_RESULT", "TIED"])
    bad_unlabeled_tgt = int(
        (
            (unlabeled_mask & all_states_df["target_batting_team_win"].notna())
            | (unlabeled_mask & all_states_df["target_home_team_win"].notna())
        ).sum()
    )
    bad_pri_tgt_vals = int(
        (~primary_states_df["target_batting_team_win"].isin([0, 1])).fillna(True).sum()
    )
    bad_tgt_vals_home = int(
        (~primary_states_df["target_home_team_win"].isin([0, 1])).fillna(True).sum()
    )
    missing_date = int(all_states_df["match_date"].isna().sum())
    tgt_errs = len(overlap_roles) + bad_unlabeled_tgt + bad_pri_tgt_vals + bad_tgt_vals_home + missing_date
    results.append(
        ValidationResult(
            rule_id="VAL-5B-TGT-001",
            dataset="match_states_all,match_states_primary",
            field="target_batting_team_win, target_home_team_win, MODEL_FEATURE_COLUMNS",
            severity=Severity.CRITICAL,
            status=ValidationStatus.PASS if tgt_errs == 0 else ValidationStatus.FAIL,
            affected_record_count=tgt_errs,
            new_anomaly_count=tgt_errs,
            short_description=(
                f"Strict separation of {len(MODEL_FEATURE_COLUMNS)} model features from {len(TARGET_COLUMNS)} targets and "
                f"{len(REGIME_AUDIT_COLUMNS)} audit/pre-state columns; binary targets verified on primary dataset and pd.NA on unlabeled matches."
                if tgt_errs == 0
                else f"Detected {tgt_errs} target or leakage-role separation violation(s)."
            ),
            recommended_action="Never mix targets or post-match audit columns into model feature sets.",
            metadata={
                "model_feature_count": len(MODEL_FEATURE_COLUMNS),
                "regime_audit_count": len(REGIME_AUDIT_COLUMNS),
                "target_count": len(TARGET_COLUMNS),
                "primary_target_positive_rate": round(
                    float(primary_states_df["target_batting_team_win"].mean()), 6
                )
                if len(primary_states_df) > 0
                else None,
            },
        )
    )

    # 12. VAL-5B-WRN-001: Transparent preservation of known source anomalies & quarantine items (never suppressed!)
    quarantined_matches = int((eligibility_df["match_regime"] == "INCOMPLETE_OR_UNRESOLVED").sum())
    ext2_rows = int(all_states_df["is_extras_2_subtype_unresolved"].sum())
    unres_wkt_rows = int(all_states_df["is_dismissed_player_unresolved"].sum())
    uae_rows = int(all_states_df["has_uae_split_player_id"].sum())
    margin_mm_rows = int(all_states_df["has_margin_text_mismatch"].sum())
    zero_ball_abandoned = int((~eligibility_df["has_deliveries"].fillna(True)).sum())
    warning_items = quarantined_matches + ext2_rows + unres_wkt_rows + uae_rows + margin_mm_rows + zero_ball_abandoned
    results.append(
        ValidationResult(
            rule_id="VAL-5B-WRN-001",
            dataset="match_states_all,match_eligibility",
            field="quarantined_50407, is_dismissed_player_unresolved, has_uae_split_player_id, extras_2_runs",
            severity=Severity.WARNING,
            status=ValidationStatus.WARNING if warning_items > 0 else ValidationStatus.PASS,
            affected_record_count=warning_items,
            known_exception_count=warning_items,
            new_anomaly_count=0,
            short_description=(
                f"Preserved all known source anomalies/warnings without silent alteration: "
                f"quarantined_incomplete={quarantined_matches} (incl. 50407 UNRESOLVED), "
                f"unresolved_dismissed_id={unres_wkt_rows} (40709 2.19.5), extras_2_runs={ext2_rows}, "
                f"uae_split_rows={uae_rows}, margin_text_mismatch_rows={margin_mm_rows}, "
                f"zero_ball_abandoned={zero_ball_abandoned}."
            ),
            recommended_action="Retain flags as audit metadata; never fabricate missing IDs or repair raw values.",
            metadata={
                "quarantined_incomplete_matches": quarantined_matches,
                "extras_2_subtype_unresolved_rows": ext2_rows,
                "unresolved_dismissed_player_rows": unres_wkt_rows,
                "uae_split_delivery_rows": uae_rows,
                "margin_text_mismatch_rows": margin_mm_rows,
                "zero_ball_abandoned_matches": zero_ball_abandoned,
            },
        )
    )

    status_counts = {s.value: 0 for s in ValidationStatus}
    severity_counts = {sev.value: 0 for sev in Severity}
    has_critical_failure = False
    for r in results:
        status_counts[r.status.value] = status_counts.get(r.status.value, 0) + 1
        severity_counts[r.severity.value] = severity_counts.get(r.severity.value, 0) + 1
        if r.severity == Severity.CRITICAL and r.status == ValidationStatus.FAIL:
            has_critical_failure = True

    return {
        "results": results,
        "status_counts": status_counts,
        "severity_counts": severity_counts,
        "has_critical_failure": has_critical_failure,
        "continuity": continuity,
    }
