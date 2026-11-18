"""Stage 5B causal feature, verified innings-limit, chase, and target derivation."""

from __future__ import annotations

import pandas as pd

from ml.match_state.schema import (
    UNRESOLVED_50407_EXCLUSION_REASON,
    UNRESOLVED_50407_MATCH_ID,
    enforce_schema_dtypes,
)


def derive_match_state_features(
    state_df: pd.DataFrame,
    match_eligibility_df: pd.DataFrame,
) -> pd.DataFrame:
    """Attach context, verified innings limits, rates, chase metrics, and targets.

    Implements every Stage 5A Revision 1.1 rule:
    - Never infers innings_ball_limit from observed deliveries or defaults null limits to 0/120.
    - Leaves legal_balls_remaining un-clamped and flags negative differences via
      is_legal_balls_remaining_negative.
    - Keeps all chase-only features strictly pd.NA in Innings 1 and Super Overs.
    - Enforces zero-division and unverified-limit guards on required_run_rate and CRR.
    - Preserves original competition metadata verbatim alongside competition_category.
    """
    if len(state_df) == 0:
        raise ValueError("Cannot derive features from an empty delivery state table.")

    match_cols = [
        "match_id",
        "comp_id",
        "comp_name",
        "match_format",
        "competition_category",
        "season",
        "match_date",
        "match_number",
        "stage",
        "knock_out",
        "venue_id",
        "venue_country",
        "home_team_id",
        "away_team_id",
        "toss_win_team_id",
        "toss_opted",
        "first_inn_revised_overs",
        "second_inn_revised_overs",
        "revised_target",
        "win_team_id_raw",
        "inn1_runs",
        "match_regime",
        "has_dls_or_revised_meta",
        "has_unrecorded_over_reduction",
        "is_tied_after_regulation",
        "has_super_over_innings",
        "has_missing_super_over_feed",
        "has_sequence_anomaly",
        "has_extras_anomaly",
        "has_margin_text_mismatch",
        "has_uae_split_player_id",
        "has_deliveries",
        "_is_50407_unresolved",
        "_is_completed_injury_closure_inn2",
    ]
    df = state_df.merge(
        match_eligibility_df[match_cols],
        on="match_id",
        how="left",
        validate="many_to_one",
    )
    if bool(df["match_regime"].isna().any()):
        orphan_mids = sorted(int(x) for x in df.loc[df["match_regime"].isna(), "match_id"].unique())
        raise ValueError(f"Delivery rows reference match_id(s) absent from matches: {orphan_mids}")

    idx = df.index
    inn = df["innings"]
    reg = df["match_regime"]

    # 1. Pre-match causal toss alignment (switches when teams swap innings)
    toss_known = df["toss_win_team_id"].notna()
    is_bat_toss = pd.Series(pd.NA, index=idx, dtype="boolean")
    is_bat_toss.loc[toss_known] = (
        df.loc[toss_known, "batting_team_id"] == df.loc[toss_known, "toss_win_team_id"]
    ).astype("boolean")
    df["is_batting_team_toss_winner"] = is_bat_toss

    # 2. Verified innings_ball_limit (Issue B: NEVER substitute 0/120 or infer from observed balls)
    rev1 = df["first_inn_revised_overs"]
    rev2 = df["second_inn_revised_overs"]

    ball_limit = pd.Series(pd.NA, index=idx, dtype="Int64")
    limit_source = pd.Series("unavailable", index=idx, dtype="string")

    so_mask = (inn >= 3).fillna(False)
    std_or_so_reg_mask = reg.isin(["STANDARD_T20", "SUPER_OVER"]) & inn.isin([1, 2])
    if bool(std_or_so_reg_mask.any()):
        bad_fmt = std_or_so_reg_mask & ~df["match_format"].isin(["T20", "T20I"])
        if bool(bad_fmt.any()):
            raise ValueError("Cannot apply 120-ball T20 format rule to unsupported match_format.")

    explicit_rev1_mask = (~so_mask) & (~std_or_so_reg_mask) & (inn == 1) & rev1.notna()
    explicit_rev2_mask = (~so_mask) & (~std_or_so_reg_mask) & (inn == 2) & rev2.notna()

    ball_limit.loc[std_or_so_reg_mask] = 120
    limit_source.loc[std_or_so_reg_mask] = "standard_t20_format_rule"

    ball_limit.loc[explicit_rev1_mask] = rev1.loc[explicit_rev1_mask].astype("Int64")
    limit_source.loc[explicit_rev1_mask] = "first_inn_revised_overs"

    ball_limit.loc[explicit_rev2_mask] = rev2.loc[explicit_rev2_mask].astype("Int64")
    limit_source.loc[explicit_rev2_mask] = "second_inn_revised_overs"

    # Super Over mini-innings (>= 3) take precedence as 6-ball regulation
    ball_limit.loc[so_mask] = 6
    limit_source.loc[so_mask] = "super_over_regulation_6_balls"

    is_limit_verified = ball_limit.notna().astype("boolean")

    # Structured unavailability reason whenever is_innings_limit_verified == False
    unavail_reason = pd.Series(pd.NA, index=idx, dtype="string")
    unver_mask = ~is_limit_verified.fillna(False)
    if bool(unver_mask.any()):
        unavail_reason.loc[unver_mask] = "matches_revised_overs_null_in_dls_or_halted_regime"
        unavail_reason.loc[
            unver_mask & df["has_unrecorded_over_reduction"].fillna(False)
        ] = "unflagged_over_reduction_missing_revised_overs"
        unavail_reason.loc[unver_mask & (reg == "TIED")] = "rain_tied_missing_revised_overs"
        unavail_reason.loc[
            unver_mask & (reg == "INCOMPLETE_OR_UNRESOLVED")
        ] = "sequence_anomaly_unverified_limit"
        unavail_reason.loc[
            unver_mask & df["_is_50407_unresolved"].fillna(False)
        ] = UNRESOLVED_50407_EXCLUSION_REASON

    df["innings_ball_limit"] = ball_limit
    df["is_innings_limit_verified"] = is_limit_verified
    df["innings_limit_source"] = limit_source
    df["innings_limit_unavailable_reason"] = unavail_reason

    # 3. Legal balls remaining (UN-CLAMPED; negative values retained and flagged)
    l_before = df["legal_balls_completed_before"]
    l_after = df["legal_balls_completed_after"]

    rem_before = pd.Series(pd.NA, index=idx, dtype="Int64")
    rem_after = pd.Series(pd.NA, index=idx, dtype="Int64")
    ver_bool = is_limit_verified.fillna(False)
    rem_before.loc[ver_bool] = (
        ball_limit.loc[ver_bool].astype("int64") - l_before.loc[ver_bool].astype("int64")
    )
    rem_after.loc[ver_bool] = (
        ball_limit.loc[ver_bool].astype("int64") - l_after.loc[ver_bool].astype("int64")
    )

    is_neg_rem = pd.Series(False, index=idx, dtype="boolean")
    is_neg_rem.loc[ver_bool] = (rem_after.loc[ver_bool] < 0).astype("boolean")

    df["legal_balls_remaining_before"] = rem_before
    df["legal_balls_remaining"] = rem_after
    df["is_legal_balls_remaining_negative"] = is_neg_rem

    # 4. Overs, CRR, Tactical Phase, Progress
    l_after_i64 = l_after.astype("int64")
    df["overs_completed_decimal"] = pd.Series(
        l_after_i64.to_numpy(dtype="float64") / 6.0, index=idx, dtype="Float64"
    )
    df["overs_completed_notation"] = pd.Series(
        (l_after_i64 // 6).to_numpy(dtype="float64")
        + (l_after_i64 % 6).to_numpy(dtype="float64") / 10.0,
        index=idx,
        dtype="Float64",
    )

    has_legal = (l_after_i64 > 0).astype("boolean")
    df["has_legal_balls_completed"] = has_legal

    crr = pd.Series(0.0, index=idx, dtype="Float64")
    pos_legal = l_after_i64 > 0
    crr.loc[pos_legal] = (
        6.0 * df.loc[pos_legal, "score_after"].astype("float64")
        / l_after_i64.loc[pos_legal].astype("float64")
    )
    df["current_run_rate"] = crr

    phase = pd.Series("revised_or_unverified", index=idx, dtype="string")
    std_120_mask = ver_bool & (ball_limit == 120).fillna(False) & (~so_mask)
    phase.loc[std_120_mask & (l_after_i64 <= 36)] = "powerplay"
    phase.loc[std_120_mask & (l_after_i64 >= 37) & (l_after_i64 <= 90)] = "middle"
    phase.loc[std_120_mask & (l_after_i64 >= 91)] = "death"
    phase.loc[so_mask] = "super_over"
    df["innings_phase"] = phase

    prog = pd.Series(pd.NA, index=idx, dtype="Float64")
    prog_mask = ver_bool & (ball_limit > 0).fillna(False)
    prog.loc[prog_mask] = (
        l_after_i64.loc[prog_mask].astype("float64")
        / ball_limit.loc[prog_mask].astype("float64")
    )
    df["innings_progress_pct"] = prog

    # 5. Second-innings chase features (strictly pd.NA in Innings 1 and Super Overs)
    inn2_mask = (inn == 2).fillna(False)
    inn1_total = pd.Series(pd.NA, index=idx, dtype="Int64")
    inn1_total.loc[inn2_mask] = df.loc[inn2_mask, "inn1_runs"].astype("Int64")
    df["innings1_total_score"] = inn1_total

    target_runs = pd.Series(pd.NA, index=idx, dtype="Int64")
    target_source = pd.Series("not_applicable_inn1", index=idx, dtype="string")
    target_source.loc[so_mask] = "super_over_isolated"
    target_source.loc[inn2_mask] = "missing_dls_target"

    # Standard / unflagged equal-reduced inn1 + 1 chase target
    std_chase_mask = (
        inn2_mask
        & df["revised_target"].isna()
        & (~df["has_dls_or_revised_meta"].fillna(False))
        & (reg != "TIED")
        & inn1_total.notna()
    )
    target_runs.loc[std_chase_mask] = inn1_total.loc[std_chase_mask].astype("int64") + 1
    target_source.loc[std_chase_mask] = "inn1_plus_1"

    # Populated DLS revised_target takes priority
    dls_chase_mask = inn2_mask & df["revised_target"].notna()
    target_runs.loc[dls_chase_mask] = df.loc[dls_chase_mask, "revised_target"].astype("Int64")
    target_source.loc[dls_chase_mask] = "dls_revised_target"

    is_target_known = (inn2_mask & target_runs.notna()).astype("boolean")
    df["target_runs"] = target_runs
    df["is_target_known"] = is_target_known
    df["target_source"] = target_source

    req_before = pd.Series(pd.NA, index=idx, dtype="Int64")
    req_after = pd.Series(pd.NA, index=idx, dtype="Int64")
    tk_bool = is_target_known.fillna(False)
    req_before.loc[tk_bool] = (
        target_runs.loc[tk_bool].astype("int64") - df.loc[tk_bool, "score_before"].astype("int64")
    ).clip(lower=0)
    req_after.loc[tk_bool] = (
        target_runs.loc[tk_bool].astype("int64") - df.loc[tk_bool, "score_after"].astype("int64")
    ).clip(lower=0)

    df["runs_required_before"] = req_before
    df["runs_required_after"] = req_after

    # Required Run Rate with strict limit-verification and zero-division guards
    rrr = pd.Series(pd.NA, index=idx, dtype="Float64")
    rrr_eligible = inn2_mask & tk_bool & ver_bool
    rrr_zero = rrr_eligible & (req_after == 0).fillna(False)
    rrr_pos = rrr_eligible & (req_after > 0).fillna(False) & (rem_after > 0).fillna(False)
    rrr.loc[rrr_zero] = 0.0
    rrr.loc[rrr_pos] = (
        6.0 * req_after.loc[rrr_pos].astype("float64")
        / rem_after.loc[rrr_pos].astype("float64")
    )
    df["required_run_rate"] = rrr
    df["is_rrr_undefined"] = rrr.isna().astype("boolean")

    rrr_diff = pd.Series(pd.NA, index=idx, dtype="Float64")
    diff_valid = rrr.notna() & has_legal.fillna(False)
    rrr_diff.loc[diff_valid] = (
        rrr.loc[diff_valid].astype("float64") - crr.loc[diff_valid].astype("float64")
    )
    df["rrr_minus_crr"] = rrr_diff

    # 6. Causal innings_completion_status_at_ball & chase_completion_status
    inn_status = pd.Series("in_progress", index=idx, dtype="string")
    inn_status.loc[ver_bool & (rem_after <= 0).fillna(False)] = "max_balls_reached"
    inn_status.loc[(df["wickets_lost_after"] >= 10).fillna(False)] = "all_out_10"
    inn_status.loc[
        inn2_mask & tk_bool & (df["score_after"] >= target_runs).fillna(False)
    ] = "target_achieved"
    df["innings_completion_status_at_ball"] = inn_status

    chase_status = pd.Series("not_chase", index=idx, dtype="string")
    chase_status.loc[inn2_mask & (~tk_bool)] = "target_unknown"
    inn2_known = inn2_mask & tk_bool
    chase_status.loc[inn2_known] = "in_progress"
    chase_status.loc[
        inn2_known & ver_bool & (rem_after <= 0).fillna(False) & (req_after >= 2).fillna(False)
    ] = "balls_exhausted_lost"
    chase_status.loc[
        inn2_known & ver_bool & (rem_after <= 0).fillna(False) & (req_after == 1).fillna(False)
    ] = "tied_regulation"
    chase_status.loc[inn2_known & (df["wickets_lost_after"] >= 10).fillna(False)] = "all_out_lost"
    chase_status.loc[inn2_known & (req_after == 0).fillna(False)] = "target_achieved"
    df["chase_completion_status"] = chase_status

    # Audit-only terminal innings closure label (strictly non-predictive metadata)
    term_status = pd.Series("normal_balls_or_all_out_or_chase", index=idx, dtype="string")
    term_status.loc[
        inn2_mask & df["_is_completed_injury_closure_inn2"].fillna(False)
    ] = "completed_all_out_injury"
    term_status.loc[df["has_unrecorded_over_reduction"].fillna(False)] = (
        "completed_unrecorded_curtailment"
    )
    term_status.loc[reg.isin(["ABANDONED", "NO_RESULT"])] = "halted_nr_abandoned"
    term_status.loc[
        df["_is_50407_unresolved"].fillna(False) | (df["match_id"] == UNRESOLVED_50407_MATCH_ID)
    ] = "unresolved_50407"
    df["terminal_innings_status_audit"] = term_status

    # 7. Targets & Delivery-level eligibility gates (§7)
    win_raw = df["win_team_id_raw"]
    has_win = win_raw.notna()
    t_bat = pd.Series(pd.NA, index=idx, dtype="Int64")
    t_home = pd.Series(pd.NA, index=idx, dtype="Int64")
    t_bat.loc[has_win] = (
        df.loc[has_win, "batting_team_id"] == win_raw.loc[has_win]
    ).astype("int64")
    t_home.loc[has_win] = (
        df.loc[has_win, "home_team_id"] == win_raw.loc[has_win]
    ).astype("int64")
    df["target_batting_team_win"] = t_bat
    df["target_home_team_win"] = t_home

    is_primary = (
        (reg == "STANDARD_T20")
        & inn.isin([1, 2])
        & ver_bool
        & t_bat.notna()
        & (~is_neg_rem.fillna(False))
    ).astype("boolean")
    is_dls_eval = (
        (reg == "REVISED_OVERS_DLS") & inn.isin([1, 2]) & t_bat.notna()
    ).astype("boolean")
    df["is_primary_wp_train_eligible"] = is_primary
    df["is_dls_eval_slice_eligible"] = is_dls_eval

    excl = pd.Series(pd.NA, index=idx, dtype="string")
    not_elig = ~is_primary.fillna(False)
    if bool(not_elig.any()):
        excl.loc[not_elig] = "sequence_or_termination_anomaly"
        excl.loc[
            not_elig
            & (df["_is_50407_unresolved"].fillna(False) | (df["match_id"] == UNRESOLVED_50407_MATCH_ID))
        ] = UNRESOLVED_50407_EXCLUSION_REASON
        excl.loc[not_elig & (reg == "REVISED_OVERS_DLS")] = "dls_or_revised_overs"
        excl.loc[not_elig & (reg == "SUPER_OVER") & inn.isin([1, 2])] = "tied_after_regulation"
        excl.loc[not_elig & (reg == "SUPER_OVER") & so_mask] = "super_over_innings"
        excl.loc[not_elig & (reg == "TIED")] = "tied_no_winner"
        excl.loc[not_elig & (reg == "NO_RESULT")] = "no_result_null_winner"
        excl.loc[not_elig & (reg == "ABANDONED")] = "abandoned_null_winner"
    df["eligibility_exclusion_reason"] = excl

    temp_cols = [
        "first_inn_revised_overs",
        "second_inn_revised_overs",
        "revised_target",
        "inn1_runs",
        "_is_50407_unresolved",
        "_is_completed_injury_closure_inn2",
    ]
    df = df.drop(columns=temp_cols)
    return enforce_schema_dtypes(df)

