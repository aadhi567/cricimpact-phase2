"""Stage 5C Stint and Roster Builder.

Transforms delivery-grain match states (190,575 rows across 798 STANDARD_T20 matches)
and playing_eleven.csv into:
1. Continuous crease tenures (stints).
2. Batter-match appearances (aggregating multi-stint batters cleanly).
3. Roster union including Did-Not-Bat (DNB) rows (total 18,106 player-match records).
"""

from __future__ import annotations

import logging
from dataclasses import asdict
from typing import Any

import numpy as np
import pandas as pd

from ml.contribution.schema import (
    EXPECTED_BATTER_MATCH_RECORDS,
    EXPECTED_STANDARD_T20_MATCHES,
    BatterStint,
)

logger = logging.getLogger(__name__)


def build_batter_stints_and_roster(
    match_states_df: pd.DataFrame,
    playing_eleven_df: pd.DataFrame,
    competitions_df: pd.DataFrame | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Constructs batter stints and complete batter-match roster records.

    Parameters
    ----------
    match_states_df : pd.DataFrame
        Stage 5B primary dataset (match_states_standard_t20_v1.pkl.gz).
    playing_eleven_df : pd.DataFrame
        Raw playing_eleven.csv.
    competitions_df : pd.DataFrame, optional
        Raw competitions.csv.

    Returns
    -------
    tuple[pd.DataFrame, pd.DataFrame]
        stints_df : All continuous crease stints.
        batter_match_df : Exactly 18,106 player-match records (batted + DNB).
    """
    # 1. Filter match_states_df to primary Standard T20 matches
    df = match_states_df[match_states_df["is_primary_wp_train_eligible"] == True].copy()
    match_ids = sorted(df["match_id"].unique())
    if len(match_ids) != EXPECTED_STANDARD_T20_MATCHES:
        logger.warning(
            "Expected %d STANDARD_T20 matches, found %d",
            EXPECTED_STANDARD_T20_MATCHES,
            len(match_ids),
        )

    # 2. Build match metadata lookup
    match_meta = (
        df[
            [
                "match_id",
                "comp_id",
                "comp_name",
                "competition_category",
                "season",
                "match_date",
                "home_team_id",
                "away_team_id",
            ]
        ]
        .drop_duplicates(subset=["match_id"])
        .set_index("match_id")
    )
    match_meta_dict = match_meta.to_dict(orient="index")

    # 3. Reconstruct continuous crease stints for every (match_id, innings)
    stints_list: list[dict[str, Any]] = []

    # Group deliveries by (match_id, innings)
    grouped = df.groupby(["match_id", "innings"], sort=False)

    for (match_id, innings), inn_df in grouped:
        inn_df = inn_df.sort_values("innings_ball_num").reset_index(drop=True)
        meta = match_meta_dict[match_id]
        comp_cat = str(meta["competition_category"])
        season = str(meta["season"])
        m_date = str(meta["match_date"])[:10]
        batting_team_id = int(inn_df["batting_team_id"].iloc[0])
        bowling_team_id = int(inn_df["bowling_team_id"].iloc[0])

        # Identify all players who appeared on crease
        strikers = inn_df["striker_id"].values
        non_strikers = inn_df["non_striker_id"].values
        crease_players = set(strikers) | set(non_strikers)

        # Pre-extract arrays for fast delivery iteration
        ib_nums = inn_df["innings_ball_num"].values
        legal_before = inn_df["legal_balls_completed_before"].values
        legal_after = inn_df["legal_balls_completed_after"].values
        score_before = inn_df["score_before"].values
        score_after = inn_df["score_after"].values
        wkts_before = inn_df["wickets_lost_before"].values
        wkts_after = inn_df["wickets_lost_after"].values
        batter_runs_arr = inn_df["batter_runs"].values
        team_runs_arr = inn_df["team_runs"].values
        is_wide_arr = inn_df["is_wide"].values
        is_wicket_arr = inn_df["is_wicket_event"].values
        is_rh_arr = inn_df["is_retired_hurt_event"].values
        is_ro_arr = inn_df["is_retire_out_event"].values
        resolved_diss_arr = inn_df["resolved_dismissed_player_id"].values
        diss_canon_arr = inn_df["dismissal_type_canonical"].values
        batting_order_arr = inn_df["batting_order"].values

        # Innings 2 chase arrays
        is_inn2 = int(innings) == 2
        if is_inn2:
            target_runs_arr = inn_df["target_runs"].values
            runs_req_before_arr = inn_df["runs_required_before"].values
            runs_req_after_arr = inn_df["runs_required_after"].values
            rrr_after_arr = inn_df["required_run_rate"].values
        else:
            target_runs_arr = None
            runs_req_before_arr = None
            runs_req_after_arr = None
            rrr_after_arr = None

        n_balls = len(inn_df)

        for p in crease_players:
            p = int(p)
            # Find delivery indices where player p is on crease
            on_crease = (strikers == p) | (non_strikers == p)
            on_crease_indices = np.where(on_crease)[0]
            if len(on_crease_indices) == 0:
                continue

            # Detect contiguous stints (breaks happen if index difference > 1, e.g. Retired Hurt hiatus)
            stint_splits = np.where(np.diff(on_crease_indices) > 1)[0]
            stint_starts = np.insert(stint_splits + 1, 0, 0)
            stint_ends = np.append(stint_splits, len(on_crease_indices) - 1)

            # Determine player's earliest batting order
            first_idx = on_crease_indices[0]
            # If player was striker at first appearance, batting_order is direct; else find first striker appearance or default
            p_striker_idx = np.where(strikers == p)[0]
            if len(p_striker_idx) > 0:
                p_bat_order = int(batting_order_arr[p_striker_idx[0]])
            else:
                # Non-striker only: batting order is at least non_striker entry order
                p_bat_order = int(batting_order_arr[first_idx])

            for stint_id, (s_start_idx, s_end_idx) in enumerate(
                zip(stint_starts, stint_ends), start=1
            ):
                d_start = on_crease_indices[s_start_idx]
                d_end = on_crease_indices[s_end_idx]

                # Entry state immediately BEFORE delivery d_start
                entry_ib = int(ib_nums[d_start])
                entry_legal = int(legal_before[d_start])
                entry_over_notation = float(
                    (entry_legal // 6) + (entry_legal % 6) / 10.0
                )
                entry_over_decimal = float(entry_legal / 6.0)
                entry_score = int(score_before[d_start])
                entry_wkts = int(wkts_before[d_start])
                entry_wkts_rem = max(10 - entry_wkts, 0)
                entry_balls_rem = 120 - entry_legal
                entry_trr = (
                    float(entry_score * 6.0 / entry_legal) if entry_legal > 0 else 0.0
                )

                # Exit state immediately AFTER delivery d_end
                exit_ib = int(ib_nums[d_end])
                exit_legal = int(legal_after[d_end])
                exit_over_notation = float((exit_legal // 6) + (exit_legal % 6) / 10.0)
                exit_over_decimal = float(exit_legal / 6.0)
                exit_score = int(score_after[d_end])
                exit_wkts = int(wkts_after[d_end])
                exit_wkts_rem = max(10 - exit_wkts, 0)
                exit_balls_rem = 120 - exit_legal
                overs_spent = float((exit_legal - entry_legal) / 6.0)
                team_runs_added = int(exit_score - entry_score)
                window_trr = (
                    float(team_runs_added / overs_spent) if overs_spent > 0 else 0.0
                )
                wkts_lost_during_stay = int(exit_wkts - entry_wkts)

                # Stint batting stats: deliveries where player is STRIKER in range [d_start, d_end]
                stint_range = np.arange(d_start, d_end + 1)
                is_striker_here = strikers[stint_range] == p

                # balls_faced excludes wides (~is_wide)
                striker_wide = is_wide_arr[stint_range][is_striker_here]
                balls_faced = int(np.sum(~striker_wide))

                striker_batter_runs = batter_runs_arr[stint_range][is_striker_here]
                actual_runs = int(np.sum(striker_batter_runs))
                actual_sr = (
                    float(actual_runs / balls_faced * 100.0) if balls_faced > 0 else 0.0
                )
                fours = int(np.sum(striker_batter_runs == 4))
                sixes = int(np.sum(striker_batter_runs == 6))
                bnd_pct = (
                    float((4 * fours + 6 * sixes) / actual_runs * 100.0)
                    if actual_runs > 0
                    else 0.0
                )

                striker_team_runs = team_runs_arr[stint_range][is_striker_here]
                dot_balls = int(np.sum(striker_team_runs == 0))
                dot_ball_pct = (
                    float(dot_balls / balls_faced * 100.0) if balls_faced > 0 else 0.0
                )

                # Dismissal evaluation at d_end
                is_out = False
                is_not_out = True
                is_rh = False
                is_ro = False
                diss_status = "not out"
                diss_canon = None
                has_unresolved_40709 = False

                is_diss_p = (
                    pd.notna(resolved_diss_arr[d_end])
                    and resolved_diss_arr[d_end] == p
                )

                if bool(is_rh_arr[d_end]) and is_diss_p:
                    is_rh = True
                    diss_status = "not out"
                elif bool(is_wicket_arr[d_end]) and is_diss_p:
                    is_out = True
                    is_not_out = False
                    if bool(is_ro_arr[d_end]):
                        is_ro = True
                        diss_status = "out"
                        diss_canon = "Retire Out"
                    else:
                        diss_status = "out"
                        diss_canon = str(diss_canon_arr[d_end])
                elif match_id == 40709 and innings == 2 and exit_ib == 117:
                    # Match 40709 2.19.5 Retire Out edge case
                    has_unresolved_40709 = True
                    diss_status = "not out"
                    is_out = False
                    is_not_out = True

                # Innings 2 chase metrics
                if is_inn2:
                    tgt = (
                        int(target_runs_arr[d_start])
                        if pd.notna(target_runs_arr[d_start])
                        else None
                    )
                    rq_before = (
                        int(runs_req_before_arr[d_start])
                        if pd.notna(runs_req_before_arr[d_start])
                        else None
                    )
                    rq_after = (
                        int(runs_req_after_arr[d_end])
                        if pd.notna(runs_req_after_arr[d_end])
                        else None
                    )
                    if rq_before is not None and rq_before <= 0:
                        rrr_en = 0.0
                    elif rq_before is not None and entry_balls_rem > 0:
                        rrr_en = float(rq_before * 6.0 / entry_balls_rem)
                    else:
                        rrr_en = None

                    rrr_ex = (
                        float(rrr_after_arr[d_end])
                        if pd.notna(rrr_after_arr[d_end])
                        else None
                    )
                    rrr_chg = (
                        float(rrr_en - rrr_ex)
                        if (rrr_en is not None and rrr_ex is not None)
                        else None
                    )
                    rr_gap_en = (
                        float(rrr_en - entry_trr) if rrr_en is not None else None
                    )
                    exit_trr = (
                        float(exit_score * 6.0 / exit_legal) if exit_legal > 0 else 0.0
                    )
                    rr_gap_ex = (
                        float(rrr_ex - exit_trr) if rrr_ex is not None else None
                    )
                    rr_gap_chg = (
                        float(rr_gap_en - rr_gap_ex)
                        if (rr_gap_en is not None and rr_gap_ex is not None)
                        else None
                    )
                    t_prog_chg = (
                        float((rq_before - rq_after) / tgt)
                        if (tgt and rq_before is not None and rq_after is not None)
                        else None
                    )
                else:
                    tgt = None
                    rq_before = None
                    rq_after = None
                    rrr_en = None
                    rrr_ex = None
                    rrr_chg = None
                    rr_gap_en = None
                    rr_gap_ex = None
                    rr_gap_chg = None
                    t_prog_chg = None

                # Is this stint a pure DNB-equivalent (0 balls faced, 0 runs, not out)?
                is_stint_dnb = (
                    balls_faced == 0 and actual_runs == 0 and diss_status != "out"
                )

                # UAE split player flag
                is_uae = match_id in (37087, 37092, 37095) and p in (36153, 39444)

                stints_list.append(
                    {
                        "match_id": match_id,
                        "innings": innings,
                        "stint_id": stint_id,
                        "player_id": p,
                        "team_id": batting_team_id,
                        "opponent_team_id": bowling_team_id,
                        "competition_category": comp_cat,
                        "season": season,
                        "match_date": m_date,
                        "batting_order": p_bat_order,
                        "entry_innings_ball_num": entry_ib,
                        "exit_innings_ball_num": exit_ib,
                        "entry_legal_balls": entry_legal,
                        "entry_over_notation": entry_over_notation,
                        "entry_over_decimal": entry_over_decimal,
                        "entry_team_score": entry_score,
                        "entry_wickets_lost": entry_wkts,
                        "entry_wickets_remaining": entry_wkts_rem,
                        "entry_balls_remaining": entry_balls_rem,
                        "entry_team_rr": entry_trr,
                        "exit_legal_balls": exit_legal,
                        "exit_over_notation": exit_over_notation,
                        "exit_over_decimal": exit_over_decimal,
                        "exit_team_score": exit_score,
                        "exit_wickets_lost": exit_wkts,
                        "exit_wickets_remaining": exit_wkts_rem,
                        "exit_balls_remaining": exit_balls_rem,
                        "overs_spent": overs_spent,
                        "team_runs_added": team_runs_added,
                        "window_team_rr": window_trr,
                        "wickets_lost_during_stay": wkts_lost_during_stay,
                        "actual_runs": actual_runs,
                        "balls_faced": balls_faced,
                        "actual_sr": actual_sr,
                        "fours": fours,
                        "sixes": sixes,
                        "boundary_pct": bnd_pct,
                        "dot_balls": dot_balls,
                        "dot_ball_pct": dot_ball_pct,
                        "dismissal_status": diss_status,
                        "dismissal_type_canonical": diss_canon,
                        "is_out": is_out,
                        "is_not_out": is_not_out,
                        "is_retired_hurt": is_rh,
                        "is_retire_out": is_ro,
                        "is_dnb": is_stint_dnb,
                        "is_impact": False,  # Will be enriched from playing_eleven
                        "is_roster_missing_uae_split": is_uae,
                        "has_unresolved_dismissal_in_match": has_unresolved_40709,
                        "target_runs": tgt,
                        "runs_required_entry": rq_before,
                        "runs_required_exit": rq_after,
                        "required_rr_entry": rrr_en,
                        "required_rr_exit": rrr_ex,
                        "required_rr_change": rrr_chg,
                        "rr_gap_entry": rr_gap_en,
                        "rr_gap_exit": rr_gap_ex,
                        "rr_gap_change": rr_gap_chg,
                        "target_progress_change": t_prog_chg,
                    }
                )

    stints_df = pd.DataFrame(stints_list)

    # 4. Multi-Stint Aggregation into Batter-Match Records
    # Group stints by (match_id, innings, player_id)
    aggregated_stints: list[dict[str, Any]] = []
    stint_grouped = stints_df.groupby(
        ["match_id", "innings", "player_id"], sort=False
    )

    for (m_id, inn, p_id), g in stint_grouped:
        g = g.sort_values("stint_id").reset_index(drop=True)
        first_s = g.iloc[0]
        last_s = g.iloc[-1]

        # Multi-stint aggregation (covers returning Retired Hurt stints cleanly)
        tot_runs = int(g["actual_runs"].sum())
        tot_balls = int(g["balls_faced"].sum())
        tot_fours = int(g["fours"].sum())
        tot_sixes = int(g["sixes"].sum())
        tot_dots = int(g["dot_balls"].sum())
        tot_overs_spent = float(g["overs_spent"].sum())
        tot_team_runs = int(g["team_runs_added"].sum())
        tot_wkts_during_stay = int(g["wickets_lost_during_stay"].sum())

        sr = float(tot_runs / tot_balls * 100.0) if tot_balls > 0 else 0.0
        bnd_pct = (
            float((4 * tot_fours + 6 * tot_sixes) / tot_runs * 100.0)
            if tot_runs > 0
            else 0.0
        )
        dot_pct = float(tot_dots / tot_balls * 100.0) if tot_balls > 0 else 0.0
        win_trr = (
            float(tot_team_runs / tot_overs_spent) if tot_overs_spent > 0 else 0.0
        )

        diss_stat = str(last_s["dismissal_status"])
        is_dnb_final = (
            tot_balls == 0 and tot_runs == 0 and diss_stat != "out"
        )

        record = {
            "match_id": m_id,
            "innings": inn,
            "player_id": p_id,
            "team_id": int(first_s["team_id"]),
            "opponent_team_id": int(first_s["opponent_team_id"]),
            "competition_category": str(first_s["competition_category"]),
            "season": str(first_s["season"]),
            "match_date": str(first_s["match_date"]),
            "batting_order": int(first_s["batting_order"]),
            "entry_innings_ball_num": int(first_s["entry_innings_ball_num"]),
            "exit_innings_ball_num": int(last_s["exit_innings_ball_num"]),
            "entry_legal_balls": int(first_s["entry_legal_balls"]),
            "entry_over_notation": float(first_s["entry_over_notation"]),
            "entry_over_decimal": float(first_s["entry_over_decimal"]),
            "entry_team_score": int(first_s["entry_team_score"]),
            "entry_wickets_lost": int(first_s["entry_wickets_lost"]),
            "entry_wickets_remaining": int(first_s["entry_wickets_remaining"]),
            "entry_balls_remaining": int(first_s["entry_balls_remaining"]),
            "entry_team_rr": float(first_s["entry_team_rr"]),
            "exit_legal_balls": int(last_s["exit_legal_balls"]),
            "exit_over_notation": float(last_s["exit_over_notation"]),
            "exit_over_decimal": float(last_s["exit_over_decimal"]),
            "exit_team_score": int(last_s["exit_team_score"]),
            "exit_wickets_lost": int(last_s["exit_wickets_lost"]),
            "exit_wickets_remaining": int(last_s["exit_wickets_remaining"]),
            "exit_balls_remaining": int(last_s["exit_balls_remaining"]),
            "overs_spent": tot_overs_spent,
            "team_runs_added": tot_team_runs,
            "window_team_rr": win_trr,
            "wickets_lost_during_stay": tot_wkts_during_stay,
            "actual_runs": tot_runs,
            "balls_faced": tot_balls,
            "actual_sr": sr,
            "fours": tot_fours,
            "sixes": tot_sixes,
            "boundary_pct": bnd_pct,
            "dot_balls": tot_dots,
            "dot_ball_pct": dot_pct,
            "dismissal_status": diss_stat,
            "dismissal_type_canonical": last_s["dismissal_type_canonical"],
            "is_out": bool(last_s["is_out"]),
            "is_not_out": bool(last_s["is_not_out"]),
            "is_retired_hurt": bool(last_s["is_retired_hurt"]),
            "is_retire_out": bool(last_s["is_retire_out"]),
            "is_dnb": is_dnb_final,
            "is_impact": False,
            "is_roster_missing_uae_split": bool(first_s["is_roster_missing_uae_split"]),
            "has_unresolved_dismissal_in_match": bool(
                first_s["has_unresolved_dismissal_in_match"]
            ),
            "target_runs": first_s["target_runs"],
            "runs_required_entry": first_s["runs_required_entry"],
            "runs_required_exit": last_s["runs_required_exit"],
            "required_rr_entry": first_s["required_rr_entry"],
            "required_rr_exit": last_s["required_rr_exit"],
            "required_rr_change": first_s["required_rr_change"],
            "rr_gap_entry": first_s["rr_gap_entry"],
            "rr_gap_exit": last_s["rr_gap_exit"],
            "rr_gap_change": first_s["rr_gap_change"],
            "target_progress_change": first_s["target_progress_change"],
        }
        aggregated_stints.append(record)

    batted_df = pd.DataFrame(aggregated_stints)

    # 5. Join playing_eleven to construct DNB rows and enrich is_impact
    p11_std = playing_eleven_df[
        (playing_eleven_df["match_id"].isin(match_ids))
        & (playing_eleven_df["is_played"] == 1)
    ].copy()

    # Pre-map is_impact from p11
    impact_map = dict(
        zip(
            zip(p11_std["match_id"].astype(int), p11_std["player_id"].astype(int)),
            p11_std["is_impact"].astype(int) == 1,
        )
    )

    # Enrich is_impact on batted_df
    batted_df["is_impact"] = [
        impact_map.get((int(m), int(p)), False)
        for m, p in zip(batted_df["match_id"], batted_df["player_id"])
    ]
    stints_df["is_impact"] = [
        impact_map.get((int(m), int(p)), False)
        for m, p in zip(stints_df["match_id"], stints_df["player_id"])
    ]

    # Find who batted in which match & innings
    batted_set = set(
        zip(batted_df["match_id"].astype(int), batted_df["player_id"].astype(int))
    )

    # Build DNB records for rostered players who did NOT bat
    dnb_records: list[dict[str, Any]] = []

    # Map team innings: for each match, who batted in innings 1 and 2?
    inn_teams_df = df[
        ["match_id", "innings", "batting_team_id", "bowling_team_id"]
    ].drop_duplicates()
    inn_teams_dict = {
        (int(m), int(bt)): (int(inn), int(bwt))
        for m, bt, inn, bwt in zip(
            inn_teams_df["match_id"],
            inn_teams_df["batting_team_id"],
            inn_teams_df["innings"],
            inn_teams_df["bowling_team_id"],
        )
    }

    p11_m_ids = p11_std["match_id"].astype(int).values
    p11_p_ids = p11_std["player_id"].astype(int).values
    p11_t_ids = p11_std["team_id"].astype(int).values
    p11_imp = (p11_std["is_impact"].astype(int) == 1).values

    for m_id, p_id, t_id, is_imp in zip(p11_m_ids, p11_p_ids, p11_t_ids, p11_imp):
        if (m_id, p_id) not in batted_set:
            # Player never came to crease in this match -> DNB
            meta = match_meta_dict[m_id]
            comp_cat = str(meta["competition_category"])
            season = str(meta["season"])
            m_date = str(meta["match_date"])[:10]

            # Determine which innings this player's team batted
            if (m_id, t_id) in inn_teams_dict:
                p_inn, opp_id = inn_teams_dict[(m_id, t_id)]
            else:
                p_inn = 1
                opp_id = int(
                    meta["away_team_id"]
                    if t_id == meta["home_team_id"]
                    else meta["home_team_id"]
                )

            dnb_records.append(
                {
                    "match_id": m_id,
                    "innings": p_inn,
                    "player_id": p_id,
                    "team_id": t_id,
                    "opponent_team_id": opp_id,
                    "competition_category": comp_cat,
                    "season": season,
                    "match_date": m_date,
                    "batting_order": 99,
                    "entry_innings_ball_num": None,
                    "exit_innings_ball_num": None,
                    "entry_legal_balls": None,
                    "entry_over_notation": None,
                    "entry_over_decimal": None,
                    "entry_team_score": None,
                    "entry_wickets_lost": None,
                    "entry_wickets_remaining": None,
                    "entry_balls_remaining": None,
                    "entry_team_rr": None,
                    "exit_legal_balls": None,
                    "exit_over_notation": None,
                    "exit_over_decimal": None,
                    "exit_team_score": None,
                    "exit_wickets_lost": None,
                    "exit_wickets_remaining": None,
                    "exit_balls_remaining": None,
                    "overs_spent": 0.0,
                    "team_runs_added": 0,
                    "window_team_rr": 0.0,
                    "wickets_lost_during_stay": 0,
                    "actual_runs": 0,
                    "balls_faced": 0,
                    "actual_sr": 0.0,
                    "fours": 0,
                    "sixes": 0,
                    "boundary_pct": 0.0,
                    "dot_balls": 0,
                    "dot_ball_pct": 0.0,
                    "dismissal_status": "dnb",
                    "dismissal_type_canonical": None,
                    "is_out": False,
                    "is_not_out": False,
                    "is_retired_hurt": False,
                    "is_retire_out": False,
                    "is_dnb": True,
                    "is_impact": is_imp,
                    "is_roster_missing_uae_split": False,
                    "has_unresolved_dismissal_in_match": False,
                    "target_runs": None,
                    "runs_required_entry": None,
                    "runs_required_exit": None,
                    "required_rr_entry": None,
                    "required_rr_exit": None,
                    "required_rr_change": None,
                    "rr_gap_entry": None,
                    "rr_gap_exit": None,
                    "rr_gap_change": None,
                    "target_progress_change": None,
                }
            )

    dnb_df = pd.DataFrame(dnb_records)
    batter_match_df = pd.concat([batted_df, dnb_df], ignore_index=True)

    # Sort deterministically by (match_date, match_id, innings, batting_order, player_id)
    batter_match_df = batter_match_df.sort_values(
        ["match_date", "match_id", "innings", "batting_order", "player_id"]
    ).reset_index(drop=True)

    stints_df = stints_df.sort_values(
        ["match_date", "match_id", "innings", "entry_innings_ball_num", "player_id"]
    ).reset_index(drop=True)

    logger.info(
        "Built %d stints and %d batter-match records (batted=%d, dnb=%d)",
        len(stints_df),
        len(batter_match_df),
        len(batted_df),
        len(dnb_df),
    )

    return stints_df, batter_match_df
