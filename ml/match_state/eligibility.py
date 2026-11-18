"""Stage 5B match regime classification and training eligibility gates (Stage 5A Revision 1.1)."""

from __future__ import annotations

import pandas as pd

from ml.match_state.schema import (
    UNRESOLVED_50407_AUDIT_STATUS,
    UNRESOLVED_50407_EXCLUSION_REASON,
    UNRESOLVED_50407_MATCH_ID,
)
from ml.validation.extras_validator import derive_is_legal_delivery, derive_team_runs
from ml.validation.match_validator import _DLS_TEXT_RE, _MARGIN_RE, _SO_TEXT_RE


def derive_competition_category(competitions: pd.DataFrame) -> pd.Series:
    """Derive additive competition_category strictly from competitions metadata (never team names)."""
    if not {"match_format", "comp_name"}.issubset(competitions.columns):
        raise KeyError("competitions table must contain 'match_format' and 'comp_name'.")

    fmt = competitions["match_format"].astype("string")
    name = competitions["comp_name"].astype("string")

    bad_fmt = fmt.isna() | ~fmt.isin(["T20", "T20I"])
    if bool(bad_fmt.any()):
        bad_vals = sorted(str(x) for x in fmt.loc[bad_fmt].dropna().unique())
        raise ValueError(f"Unsupported match_format value(s) in competitions: {bad_vals}")

    category = pd.Series("OTHER_T20", index=competitions.index, dtype="string")
    category = category.where(fmt != "T20I", "T20I")
    ipl_mask = (fmt == "T20") & name.str.startswith("IPL", na=False)
    category = category.where(~ipl_mask, "IPL")
    return category


def _empty_int_map(match_ids: pd.Series, fill: int = 0) -> pd.Series:
    return pd.Series(fill, index=match_ids, dtype="int64")


def classify_match_eligibility(
    matches: pd.DataFrame,
    competitions: pd.DataFrame,
    ball_by_ball: pd.DataFrame,
    playing_eleven: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Classify all matches into the 7 Stage 5A Revision 1.1 regimes with full eligibility metadata.

    Does not mutate input DataFrames or alter raw CSV values.
    """
    m = matches.copy()
    comps = competitions.copy()
    bbb = ball_by_ball.copy()

    comps["competition_category"] = derive_competition_category(comps)

    # Preserve original competition metadata verbatim alongside competition_category
    merged = m.merge(
        comps[["comp_id", "comp_name", "match_format", "competition_category", "season"]],
        on="comp_id",
        how="left",
        validate="many_to_one",
    )
    if bool(merged["comp_name"].isna().any()):
        orphan_cids = sorted(int(x) for x in merged.loc[merged["comp_name"].isna(), "comp_id"].unique())
        raise ValueError(f"Orphan comp_id(s) in matches missing from competitions: {orphan_cids}")

    # Delivery aggregates (strictly ordered by match_id, innings, innings_ball_num)
    if len(bbb) > 0:
        bbb_work = bbb.sort_values(
            ["match_id", "innings", "innings_ball_num"], kind="mergesort"
        ).copy()
        bbb_work["_team_runs"] = derive_team_runs(bbb_work)
        bbb_work["_is_legal"] = derive_is_legal_delivery(bbb_work)
        bbb_work["_is_rh"] = (~bbb_work["is_wicket"].fillna(False)) & bbb_work[
            "dismissed_player_id"
        ].notna()

        # Extras anomalies (VAL-EXT-004 structural patterns)
        bbb_work["_has_ext_anom"] = (
            (
                ((bbb_work["extras_type"] == "None") & (bbb_work["extras1_runs"] > 0))
                | ((bbb_work["extras_type"] == "None") & (bbb_work["extras_2_runs"] > 0))
                | ((bbb_work["extras_type"] == "legbyes") & (bbb_work["runs"] > 0))
            )
            .fillna(False)
            .astype(bool)
        )
        bbb_work["_is_so"] = (bbb_work["innings"] >= 3).fillna(False).astype(bool)

        match_agg = (
            bbb_work.groupby("match_id", sort=False)
            .agg(
                deliveries_count=("innings_ball_num", "count"),
                has_super_over_innings=("_is_so", "any"),
                has_raw_extras_anom=("_has_ext_anom", "any"),
            )
            .reset_index()
        )

        inn_agg = (
            bbb_work.groupby(["match_id", "innings"], sort=False)
            .agg(
                deliveries=("innings_ball_num", "count"),
                legal_balls=("_is_legal", "sum"),
                runs=("_team_runs", "sum"),
                wickets=("is_wicket", "sum"),
                retired_hurts=("_is_rh", "sum"),
                max_overid=("overid", "max"),
                batting_team_id=("batting_team_id", "first"),
                last_ball_runs=("_team_runs", "last"),
                last_ball_is_wicket=("is_wicket", "last"),
            )
            .reset_index()
        )

        # Mid-over sequence anomalies in regulation innings (overid < max_overid and legal_balls != 6)
        reg_bbb = bbb_work.loc[bbb_work["innings"].isin([1, 2])].copy()
        if len(reg_bbb) > 0:
            over_agg = (
                reg_bbb.groupby(["match_id", "innings", "overid"], sort=False)["_is_legal"]
                .sum()
                .reset_index(name="over_legal")
            )
            inn_max = inn_agg.loc[
                inn_agg["innings"].isin([1, 2]), ["match_id", "innings", "max_overid"]
            ]
            over_chk = over_agg.merge(inn_max, on=["match_id", "innings"], how="left")
            mid_seq_rows = over_chk.loc[
                (over_chk["overid"] < over_chk["max_overid"])
                & (over_chk["over_legal"] != 6)
            ]
            mid_seq_mids = set(int(x) for x in mid_seq_rows["match_id"].unique())
            incomplete_mid_14_mids = set(
                int(x)
                for x in mid_seq_rows.loc[
                    mid_seq_rows["over_legal"] < 6, "match_id"
                ].unique()
            )
        else:
            mid_seq_mids = set()
            incomplete_mid_14_mids = set()

        # Optional p11 player join audit (detects UAE split IDs dynamically)
        uae_split_mids: set[int] = set()
        if playing_eleven is not None and len(playing_eleven) > 0:
            valid_p11 = playing_eleven[
                ["match_id", "team_id", "player_id"]
            ].drop_duplicates()
            valid_p11 = valid_p11.assign(_in_p11=True)
            for p_col, t_col in (
                ("striker_id", "batting_team_id"),
                ("non_striker_id", "batting_team_id"),
                ("bowler_id", "bowling_team_id"),
                ("dismissed_player_id", "batting_team_id"),
            ):
                sub = bbb_work.loc[
                    bbb_work[p_col].notna(), ["match_id", t_col, p_col]
                ].rename(columns={t_col: "team_id", p_col: "player_id"})
                joined = sub.merge(
                    valid_p11, on=["match_id", "team_id", "player_id"], how="left"
                )
                miss_mids = joined.loc[joined["_in_p11"].isna(), "match_id"].dropna().unique()
                uae_split_mids.update(int(x) for x in miss_mids)
    else:
        match_agg = pd.DataFrame(
            columns=["match_id", "deliveries_count", "has_super_over_innings", "has_raw_extras_anom"]
        )
        inn_agg = pd.DataFrame(
            columns=[
                "match_id",
                "innings",
                "deliveries",
                "legal_balls",
                "runs",
                "wickets",
                "retired_hurts",
                "max_overid",
                "batting_team_id",
                "last_ball_runs",
                "last_ball_is_wicket",
            ]
        )
        mid_seq_mids = set()
        incomplete_mid_14_mids = set()
        uae_split_mids = set()

    inn1 = inn_agg.loc[inn_agg["innings"] == 1].set_index("match_id")
    inn2 = inn_agg.loc[inn_agg["innings"] == 2].set_index("match_id")
    so_counts = (
        bbb.loc[bbb["innings"] >= 3].groupby("match_id").size().to_dict()
        if len(bbb) > 0
        else {}
    )

    merged = merged.merge(match_agg, on="match_id", how="left")
    merged["deliveries_count"] = merged["deliveries_count"].fillna(0).astype("int64")
    merged["has_deliveries"] = merged["deliveries_count"] > 0
    merged["has_super_over_innings"] = (
        merged["has_super_over_innings"].astype("boolean").fillna(False).astype(bool)
    )
    merged["has_raw_extras_anom"] = (
        merged["has_raw_extras_anom"].astype("boolean").fillna(False).astype(bool)
    )

    records: list[dict[str, object]] = []
    for _, row in merged.iterrows():
        mid = int(row["match_id"])
        res_str = "" if pd.isna(row["result"]) else str(row["result"])
        win_tid = row["win_team_id"]
        has_win = pd.notna(win_tid)

        r1 = inn1.loc[mid] if mid in inn1.index else None
        r2 = inn2.loc[mid] if mid in inn2.index else None

        inn1_deliv = int(r1["deliveries"]) if r1 is not None else 0
        inn1_legal = int(r1["legal_balls"]) if r1 is not None else 0
        inn1_runs = int(r1["runs"]) if r1 is not None else pd.NA
        inn1_wkts = int(r1["wickets"]) if r1 is not None else 0
        inn1_max_ov = int(r1["max_overid"]) if r1 is not None else 0
        inn1_team = int(r1["batting_team_id"]) if r1 is not None else pd.NA

        inn2_deliv = int(r2["deliveries"]) if r2 is not None else 0
        inn2_legal = int(r2["legal_balls"]) if r2 is not None else 0
        inn2_runs = int(r2["runs"]) if r2 is not None else pd.NA
        inn2_wkts = int(r2["wickets"]) if r2 is not None else 0
        inn2_max_ov = int(r2["max_overid"]) if r2 is not None else 0
        inn2_team = int(r2["batting_team_id"]) if r2 is not None else pd.NA
        inn2_last_runs = int(r2["last_ball_runs"]) if r2 is not None else 0
        inn2_last_is_wkt = bool(r2["last_ball_is_wicket"]) if r2 is not None else False

        so_deliv = int(so_counts.get(mid, 0))

        has_dls_text = bool(_DLS_TEXT_RE.search(res_str))
        has_rev_cols = bool(
            pd.notna(row["first_inn_revised_overs"])
            or pd.notna(row["second_inn_revised_overs"])
            or pd.notna(row["revised_target"])
        )
        has_dls_or_revised_meta = has_dls_text or has_rev_cols

        has_so_inn = bool(row["has_super_over_innings"])
        has_so_text = bool(_SO_TEXT_RE.search(res_str))
        reg_scores_equal = (
            r1 is not None
            and r2 is not None
            and int(inn1_runs) == int(inn2_runs)
            and not has_dls_or_revised_meta
        )
        is_super_over = has_win and (has_so_inn or has_so_text or reg_scores_equal)

        is_abandoned = res_str == "Match Abandoned"
        is_no_result = res_str == "No Result"
        is_tied_no_winner = (not is_abandoned) and (not is_no_result) and (
            (not has_win) or (res_str == "Match Tied")
        )

        # Unflagged equal-reduced parity match (15795, 31278, 48514) or curtailed rain tie (18532)
        completed_unrec_red = bool(
            has_win
            and (not is_abandoned)
            and (not is_no_result)
            and (not is_tied_no_winner)
            and (not is_super_over)
            and (not has_dls_or_revised_meta)
            and r1 is not None
            and inn1_max_ov < 20
            and inn1_wkts < 10
        )
        tied_unrec_red = bool(
            is_tied_no_winner
            and (not has_dls_or_revised_meta)
            and r2 is not None
            and inn2_max_ov < 20
            and inn2_wkts < 10
        )
        has_unrecorded_over_reduction = completed_unrec_red or tied_unrec_red

        # Structural sequence/termination/reconciliation checks on completed non-DLS, non-SO, non-reduced matches
        in_standard_path = (
            has_win
            and (not is_abandoned)
            and (not is_no_result)
            and (not is_tied_no_winner)
            and (not is_super_over)
            and (not has_dls_or_revised_meta)
            and (not has_unrecorded_over_reduction)
        )

        fails_reconciliation = False
        has_margin_text_mismatch = False
        is_injury_closure_inn2 = False
        is_unresolved_termination = False
        mid_over_seq_anom = mid in mid_seq_mids

        if in_standard_path:
            if r1 is None or r2 is None:
                fails_reconciliation = True
            else:
                s1 = int(inn1_runs)
                s2 = int(inn2_runs)
                expected_win = int(inn1_team) if s1 > s2 else (int(inn2_team) if s2 > s1 else -1)
                if expected_win != int(win_tid):
                    fails_reconciliation = True
                if s2 > s1:
                    s2_prev = s2 - inn2_last_runs
                    overshoot = s2 - s1
                    if not (s2_prev <= s1 and 1 <= overshoot <= 6):
                        fails_reconciliation = True

                # Check margin text discrepancy (audit flag only; matches 20190 & 14130)
                m_obj = _MARGIN_RE.search(res_str)
                if m_obj:
                    rec_val = int(m_obj.group(1))
                    unit = m_obj.group(2).lower()
                    comp_val = (s1 - s2) if unit.startswith("run") else (10 - inn2_wkts)
                    if comp_val != rec_val:
                        has_margin_text_mismatch = True

                # Incomplete Innings 1 at over 20 without 10 wickets (e.g., 14130, 14164)
                incomplete_inn1_ov20 = (inn1_legal < 120) and (inn1_wkts < 10)
                # Premature losing Innings 2 chase (< 120 balls, < 10 wickets, s2 < s1)
                if s2 < s1 and inn2_legal < 120 and inn2_wkts < 10:
                    if inn2_last_is_wkt and inn2_wkts == 9 and (not mid_over_seq_anom):
                        # Verified injured/absent-batter 9-wicket closure (15409, 17627, 29983, 42743, 48917)
                        is_injury_closure_inn2 = True
                    else:
                        # Unresolved premature termination (e.g., 50407 ending 20.5 without wicket)
                        is_unresolved_termination = True
                elif incomplete_inn1_ov20 and not mid_over_seq_anom:
                    mid_over_seq_anom = True

        has_sequence_anomaly = bool(
            mid_over_seq_anom or is_unresolved_termination or fails_reconciliation
        )
        # Documented extras anomalies include raw VAL-EXT-004 rows + 14130 incomplete mid-match over
        has_extras_anomaly = bool(
            bool(row["has_raw_extras_anom"]) or (mid in incomplete_mid_14_mids)
        )

        # Mutually exclusive 7-class match_regime precedence tree (Stage 5A Revision 1.1 §3)
        if is_abandoned:
            match_regime = "ABANDONED"
        elif is_no_result:
            match_regime = "NO_RESULT"
        elif is_tied_no_winner:
            match_regime = "TIED"
        elif is_super_over:
            match_regime = "SUPER_OVER"
        elif has_dls_or_revised_meta or has_unrecorded_over_reduction:
            match_regime = "REVISED_OVERS_DLS"
        elif has_sequence_anomaly or fails_reconciliation:
            match_regime = "INCOMPLETE_OR_UNRESOLVED"
        else:
            match_regime = "STANDARD_T20"

        is_tied_after_regulation = match_regime in ("SUPER_OVER", "TIED")
        has_missing_super_over_feed = (match_regime == "SUPER_OVER") and (not has_so_inn)
        is_50407_unresolved = mid == UNRESOLVED_50407_MATCH_ID
        has_unresolved_termination_reason = is_50407_unresolved or (
            match_regime == "INCOMPLETE_OR_UNRESOLVED" and is_unresolved_termination and not mid_over_seq_anom
        )

        # Match-level primary WP eligibility & deterministic exclusion reason
        is_primary_eligible = (match_regime == "STANDARD_T20") and has_win and (r1 is not None) and (r2 is not None)
        is_dls_eval_eligible = (match_regime == "REVISED_OVERS_DLS") and has_win
        if is_primary_eligible:
            excl_reason: object = pd.NA
        elif match_regime == "ABANDONED":
            excl_reason = "abandoned_null_winner"
        elif match_regime == "NO_RESULT":
            excl_reason = "no_result_null_winner"
        elif match_regime == "TIED":
            excl_reason = "tied_no_winner"
        elif match_regime == "SUPER_OVER":
            excl_reason = "tied_after_regulation"
        elif match_regime == "REVISED_OVERS_DLS":
            excl_reason = "dls_or_revised_overs"
        elif is_50407_unresolved:
            excl_reason = UNRESOLVED_50407_EXCLUSION_REASON
        else:
            excl_reason = "sequence_or_termination_anomaly"

        audit_note = (
            UNRESOLVED_50407_AUDIT_STATUS
            if has_unresolved_termination_reason
            else (
                "Completed all-out injury closure at 9 wickets in Innings 2."
                if is_injury_closure_inn2
                else (
                    "Zero deliveries in ball_by_ball.csv (ABANDONED)."
                    if int(row["deliveries_count"]) == 0
                    else "Classified cleanly via Stage 5A Revision 1.1 rules."
                )
            )
        )

        records.append(
            {
                "match_id": mid,
                "comp_id": int(row["comp_id"]),
                "comp_name": str(row["comp_name"]),
                "match_format": str(row["match_format"]),
                "competition_category": str(row["competition_category"]),
                "season": str(row["season"]),
                "match_date": row["match_date"],
                "match_number": int(row["match_number"]),
                "stage": str(row["stage"]),
                "knock_out": bool(pd.notna(row["knock_out"]) and int(row["knock_out"]) == 1),
                "venue_id": int(row["venue_id"]),
                "venue_country": str(row["venue_country"]),
                "home_team_id": int(row["home_team_id"]),
                "away_team_id": int(row["away_team_id"]),
                "toss_win_team_id": row["toss_win_team_id"],
                "toss_opted": row["toss_opted"],
                "first_inn_revised_overs": row["first_inn_revised_overs"],
                "second_inn_revised_overs": row["second_inn_revised_overs"],
                "revised_target": row["revised_target"],
                "win_team_id_raw": win_tid,
                "result_raw": res_str,
                "deliveries_count": int(row["deliveries_count"]),
                "inn1_deliveries": inn1_deliv,
                "inn2_deliveries": inn2_deliv,
                "so_deliveries": so_deliv,
                "inn1_runs": inn1_runs,
                "inn1_wickets": inn1_wkts,
                "inn1_legal_balls": inn1_legal,
                "inn1_max_overid": inn1_max_ov,
                "inn2_runs": inn2_runs,
                "inn2_wickets": inn2_wkts,
                "inn2_legal_balls": inn2_legal,
                "inn2_max_overid": inn2_max_ov,
                "match_regime": match_regime,
                "has_dls_or_revised_meta": has_dls_or_revised_meta,
                "has_unrecorded_over_reduction": has_unrecorded_over_reduction,
                "is_tied_after_regulation": is_tied_after_regulation,
                "has_super_over_innings": has_so_inn,
                "has_missing_super_over_feed": has_missing_super_over_feed,
                "has_sequence_anomaly": has_sequence_anomaly,
                "has_extras_anomaly": has_extras_anomaly,
                "has_margin_text_mismatch": has_margin_text_mismatch,
                "has_uae_split_player_id": mid in uae_split_mids,
                "has_deliveries": bool(row["has_deliveries"]),
                "_is_50407_unresolved": is_50407_unresolved,
                "_is_completed_injury_closure_inn2": is_injury_closure_inn2,
                "_fails_reconciliation": fails_reconciliation,
                "is_primary_wp_train_eligible": is_primary_eligible,
                "is_dls_eval_slice_eligible": is_dls_eval_eligible,
                "eligibility_exclusion_reason": excl_reason,
                "audit_status_note": audit_note,
            }
        )

    out = pd.DataFrame(records)
    for col in (
        "match_id",
        "comp_id",
        "match_number",
        "venue_id",
        "home_team_id",
        "away_team_id",
        "toss_win_team_id",
        "first_inn_revised_overs",
        "second_inn_revised_overs",
        "revised_target",
        "win_team_id_raw",
        "inn1_runs",
        "inn2_runs",
    ):
        out[col] = pd.array(out[col], dtype="Int64")
    for col in (
        "comp_name",
        "match_format",
        "competition_category",
        "season",
        "stage",
        "venue_country",
        "toss_opted",
        "result_raw",
        "match_regime",
        "eligibility_exclusion_reason",
        "audit_status_note",
    ):
        out[col] = pd.Series(out[col], index=out.index, dtype="string")
    for col in (
        "knock_out",
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
        "_fails_reconciliation",
        "is_primary_wp_train_eligible",
        "is_dls_eval_slice_eligible",
    ):
        out[col] = pd.array(out[col], dtype="boolean")
    out["match_date"] = pd.to_datetime(out["match_date"], format="%Y-%m-%d", errors="raise").astype("datetime64[ns]")
    return out.sort_values("match_id", kind="mergesort").reset_index(drop=True)
