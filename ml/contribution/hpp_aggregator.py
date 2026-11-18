"""CricImpact Phase 2 — High Pressure Player (HPP) Aggregator Engine.

Provides multi-level aggregation of player contributions:
- Match-level contribution summaries
- Season-level performance trajectories
- Career-level ratings and crisis resilience indices

Strictly enforces:
- DNB mathematical exclusion from rate denominators
- Innings 1 vs Innings 2 separation
- Pressure tier distribution breakdowns
- Outcome invariance verification (evaluating performance independent of team win/loss)
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd

from ml.contribution.hpp_engine import (
    TIER_EXTREME,
    TIER_HIGH,
    TIER_LOW,
    TIER_MEDIUM,
)


def aggregate_player_match(df_stints: pd.DataFrame) -> pd.DataFrame:
    """Aggregate stint evaluations to player-match summaries.

    Parameters
    ----------
    df_stints : pd.DataFrame
        Table of evaluated stints.

    Returns
    -------
    pd.DataFrame
        Match-level player contributions.
    """
    records = []
    # Group by match_id, player_id
    grouped = df_stints.groupby(["match_id", "player_id"], sort=False)

    for (mid, pid), grp in grouped:
        batted_stints = grp[~grp["is_dnb"]]
        sname = grp["batter_name"].iloc[0]
        mdate = grp["match_date"].iloc[0]
        season = grp["season"].iloc[0]
        comp = grp["competition_category"].iloc[0]
        team_won = grp["team_won"].iloc[0]

        if len(batted_stints) == 0:
            # Player Did Not Bat
            records.append({
                "match_id": mid,
                "player_id": pid,
                "batter_name": sname,
                "match_date": mdate,
                "season": season,
                "competition_category": comp,
                "team_won": team_won,
                "innings_count": 0,
                "is_dnb": True,
                "balls_faced": 0,
                "actual_runs": 0,
                "expected_runs": np.nan,
                "total_rae": np.nan,
                "total_hpc": np.nan,
                "mean_pressure": np.nan,
                "peak_pressure": np.nan,
                "pressure_tier": "DNB",
                "dismissal_status": "DNB",
            })
        else:
            b_faced = int(batted_stints["balls_faced"].sum())
            actual_r = int(batted_stints["actual_runs"].sum())
            exp_r = float(batted_stints["expected_runs"].sum())
            tot_rae = float(batted_stints["rae"].sum())
            tot_hpc = float(batted_stints["hpc"].sum())

            # Weighted mean pressure by balls faced
            if b_faced > 0:
                mean_p = float(np.average(batted_stints["mean_pressure"], weights=batted_stints["balls_faced"]))
            else:
                mean_p = float(batted_stints["mean_pressure"].mean())

            peak_p = float(batted_stints["peak_pressure"].max())
            tier = batted_stints["pressure_tier"].iloc[-1]
            dismissal = batted_stints["dismissal_status"].iloc[-1]

            records.append({
                "match_id": mid,
                "player_id": pid,
                "batter_name": sname,
                "match_date": mdate,
                "season": season,
                "competition_category": comp,
                "team_won": team_won,
                "innings_count": len(batted_stints),
                "is_dnb": False,
                "balls_faced": b_faced,
                "actual_runs": actual_r,
                "expected_runs": exp_r,
                "total_rae": tot_rae,
                "total_hpc": tot_hpc,
                "mean_pressure": mean_p,
                "peak_pressure": peak_p,
                "pressure_tier": tier,
                "dismissal_status": dismissal,
            })

    return pd.DataFrame(records)


def aggregate_player_season(df_stints: pd.DataFrame) -> pd.DataFrame:
    """Aggregate player performances across seasons.

    Strictly excludes DNB records from innings denominators.
    """
    records = []
    # Filter to active stints for rate calculations
    grouped = df_stints.groupby(["player_id", "season"], sort=False)

    for (pid, season), grp in grouped:
        sname = grp["batter_name"].iloc[0]
        batted = grp[~grp["is_dnb"]]
        dnb_count = int(grp["is_dnb"].sum())
        total_matches = grp["match_id"].nunique()
        innings_batted = len(batted)

        if innings_batted == 0:
            continue

        b_faced = int(batted["balls_faced"].sum())
        actual_r = int(batted["actual_runs"].sum())
        exp_r = float(batted["expected_runs"].sum())
        tot_rae = float(batted["rae"].sum())
        tot_hpc = float(batted["hpc"].sum())

        mean_rae = float(tot_rae / innings_batted)
        mean_hpc = float(tot_hpc / innings_batted)

        # Positive and negative totals
        pos_hpc = float(batted[batted["hpc"] > 0]["hpc"].sum())
        neg_hpc = float(batted[batted["hpc"] < 0]["hpc"].sum())

        # Innings splits
        i1 = batted[batted["innings"] == 1]
        i2 = batted[batted["innings"] == 2]

        i1_innings = len(i1)
        i1_hpc = float(i1["hpc"].sum()) if i1_innings > 0 else 0.0
        i1_avg_hpc = float(i1_hpc / i1_innings) if i1_innings > 0 else np.nan

        i2_innings = len(i2)
        i2_hpc = float(i2["hpc"].sum()) if i2_innings > 0 else 0.0
        i2_avg_hpc = float(i2_hpc / i2_innings) if i2_innings > 0 else np.nan

        # Pressure tier splits
        p_low = batted[batted["pressure_tier"] == TIER_LOW]
        p_med = batted[batted["pressure_tier"] == TIER_MEDIUM]
        p_high = batted[batted["pressure_tier"] == TIER_HIGH]
        p_ext = batted[batted["pressure_tier"] == TIER_EXTREME]

        records.append({
            "player_id": pid,
            "batter_name": sname,
            "season": season,
            "total_matches": total_matches,
            "innings_batted": innings_batted,
            "dnb_count": dnb_count,
            "balls_faced": b_faced,
            "actual_runs": actual_r,
            "expected_runs": exp_r,
            "strike_rate": float(actual_r / b_faced * 100.0) if b_faced > 0 else 0.0,
            "total_rae": tot_rae,
            "mean_rae": mean_rae,
            "total_hpc": tot_hpc,
            "mean_hpc": mean_hpc,
            "pos_hpc_sum": pos_hpc,
            "neg_hpc_sum": neg_hpc,
            "i1_innings": i1_innings,
            "i1_total_hpc": i1_hpc,
            "i1_mean_hpc": i1_avg_hpc,
            "i2_innings": i2_innings,
            "i2_total_hpc": i2_hpc,
            "i2_mean_hpc": i2_avg_hpc,
            "low_p_innings": len(p_low),
            "low_p_hpc": float(p_low["hpc"].sum()),
            "med_p_innings": len(p_med),
            "med_p_hpc": float(p_med["hpc"].sum()),
            "high_p_innings": len(p_high),
            "high_p_hpc": float(p_high["hpc"].sum()),
            "ext_p_innings": len(p_ext),
            "ext_p_hpc": float(p_ext["hpc"].sum()),
        })

    df_res = pd.DataFrame(records)
    if len(df_res) > 0:
        df_res = df_res.sort_values("total_hpc", ascending=False).reset_index(drop=True)
    return df_res


def aggregate_player_career(df_stints: pd.DataFrame) -> pd.DataFrame:
    """Aggregate career-level HPP metrics.

    Calculates:
    - Career Total and Mean HPC (strictly excluding DNB)
    - Crisis Performance (High & Extreme Pressure HPC)
    - Outcome Invariance Verification (HPC in team Wins vs Losses)
    - Dismissal and Not-Out conversion
    """
    records = []
    grouped = df_stints.groupby("player_id", sort=False)

    for pid, grp in grouped:
        sname = grp["batter_name"].iloc[0]
        batted = grp[~grp["is_dnb"]]
        dnb_count = int(grp["is_dnb"].sum())
        total_matches = grp["match_id"].nunique()
        innings_batted = len(batted)

        if innings_batted == 0:
            continue

        b_faced = int(batted["balls_faced"].sum())
        actual_r = int(batted["actual_runs"].sum())
        exp_r = float(batted["expected_runs"].sum())
        tot_rae = float(batted["rae"].sum())
        tot_hpc = float(batted["hpc"].sum())

        mean_rae = float(tot_rae / innings_batted)
        mean_hpc = float(tot_hpc / innings_batted)

        pos_hpc = float(batted[batted["hpc"] > 0]["hpc"].sum())
        neg_hpc = float(batted[batted["hpc"] < 0]["hpc"].sum())

        outs = int(batted["is_out"].sum())
        not_outs = int(batted["is_not_out"].sum())

        # Average pressure faced across career
        avg_pressure = float(np.average(batted["mean_pressure"], weights=batted["balls_faced"])) if b_faced > 0 else float(batted["mean_pressure"].mean())

        # Innings splits
        i1 = batted[batted["innings"] == 1]
        i2 = batted[batted["innings"] == 2]

        i1_innings = len(i1)
        i1_hpc = float(i1["hpc"].sum()) if i1_innings > 0 else 0.0
        i1_avg_hpc = float(i1_hpc / i1_innings) if i1_innings > 0 else np.nan

        i2_innings = len(i2)
        i2_hpc = float(i2["hpc"].sum()) if i2_innings > 0 else 0.0
        i2_avg_hpc = float(i2_hpc / i2_innings) if i2_innings > 0 else np.nan

        # Pressure tier splits
        p_low = batted[batted["pressure_tier"] == TIER_LOW]
        p_med = batted[batted["pressure_tier"] == TIER_MEDIUM]
        p_high = batted[batted["pressure_tier"] == TIER_HIGH]
        p_ext = batted[batted["pressure_tier"] == TIER_EXTREME]

        crisis_innings = len(p_high) + len(p_ext)
        crisis_hpc = float(p_high["hpc"].sum() + p_ext["hpc"].sum())
        crisis_avg_hpc = float(crisis_hpc / crisis_innings) if crisis_innings > 0 else np.nan

        # Outcome Invariance (Win vs Loss)
        wins = batted[batted["team_won"]]
        losses = batted[~batted["team_won"]]

        win_innings = len(wins)
        win_hpc = float(wins["hpc"].sum()) if win_innings > 0 else 0.0
        win_avg_hpc = float(win_hpc / win_innings) if win_innings > 0 else np.nan

        loss_innings = len(losses)
        loss_hpc = float(losses["hpc"].sum()) if loss_innings > 0 else 0.0
        loss_avg_hpc = float(loss_hpc / loss_innings) if loss_innings > 0 else np.nan

        records.append({
            "player_id": pid,
            "batter_name": sname,
            "total_matches": total_matches,
            "innings_batted": innings_batted,
            "dnb_count": dnb_count,
            "balls_faced": b_faced,
            "actual_runs": actual_r,
            "expected_runs": exp_r,
            "strike_rate": float(actual_r / b_faced * 100.0) if b_faced > 0 else 0.0,
            "outs": outs,
            "not_outs": not_outs,
            "avg_pressure_faced": avg_pressure,
            "total_rae": tot_rae,
            "mean_rae": mean_rae,
            "total_hpc": tot_hpc,
            "mean_hpc": mean_hpc,
            "pos_hpc_sum": pos_hpc,
            "neg_hpc_sum": neg_hpc,
            "crisis_innings": crisis_innings,
            "crisis_total_hpc": crisis_hpc,
            "crisis_mean_hpc": crisis_avg_hpc,
            "i1_innings": i1_innings,
            "i1_total_hpc": i1_hpc,
            "i1_mean_hpc": i1_avg_hpc,
            "i2_innings": i2_innings,
            "i2_total_hpc": i2_hpc,
            "i2_mean_hpc": i2_avg_hpc,
            "win_innings": win_innings,
            "win_total_hpc": win_hpc,
            "win_mean_hpc": win_avg_hpc,
            "loss_innings": loss_innings,
            "loss_total_hpc": loss_hpc,
            "loss_mean_hpc": loss_avg_hpc,
            "low_p_innings": len(p_low),
            "low_p_hpc": float(p_low["hpc"].sum()),
            "med_p_innings": len(p_med),
            "med_p_hpc": float(p_med["hpc"].sum()),
            "high_p_innings": len(p_high),
            "high_p_hpc": float(p_high["hpc"].sum()),
            "ext_p_innings": len(p_ext),
            "ext_p_hpc": float(p_ext["hpc"].sum()),
        })

    df_career = pd.DataFrame(records)
    if len(df_career) > 0:
        df_career = df_career.sort_values("total_hpc", ascending=False).reset_index(drop=True)
    return df_career

