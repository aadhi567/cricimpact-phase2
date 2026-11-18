"""Stage 5C Aggregation Engine.

Provides:
1. Retrospective season and competition aggregations (View A & View B) for Track A.
   - Implements locked ABC rules:
     - ABC-R01: contribution_per_batting_opportunity = tot_pos_raw / n.
     - ABC-R02: death_over_contribution = (entry >= 16.0) | (exit >= 16.0).
     - Strict DNB non-dilution (DNBs never enter ABC denominator).
2. Strictly causal walk-forward pre-match player ABC features for Track B (future Stage 6 WP).
   - Enforces source.match_date < target.match_date everywhere (zero same-match / future leakage).
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd

from ml.contribution.schema import TRACK_A_TAG, TRACK_B_TAG

logger = logging.getLogger(__name__)


def build_season_competition_metrics(
    scored_match_df: pd.DataFrame, engine_name: str
) -> pd.DataFrame:
    """Builds season & competition aggregation tables for View A and View B (Track A).

    Parameters
    ----------
    scored_match_df : pd.DataFrame
        Scored batter-match records (including DNBs).
    engine_name : str
        Identifier of the scoring engine used.

    Returns
    -------
    pd.DataFrame
        Aggregated metrics per (player_id, season, competition_category, team_id).
    """
    df = scored_match_df.copy()

    # Pre-calculate team positive raw totals per (season, competition_category, team_id)
    batted_only = df[~df["is_dnb"] & df["raw_contribution"].notna()].copy()
    batted_only["pos_raw"] = batted_only["raw_contribution"].clip(lower=0.0)

    team_totals = (
        batted_only.groupby(
            ["season", "competition_category", "team_id"]
        )["pos_raw"]
        .sum()
        .to_dict()
    )

    records: list[dict[str, Any]] = []

    grouped = df.groupby(
        ["player_id", "season", "competition_category", "team_id"],
        sort=False,
    )

    for (p_id, seas, comp_cat, t_id), g in grouped:
        m_played = int(len(g))
        b_inns = g[~g["is_dnb"] & g["contribution_score"].notna()]
        n_batted = int(len(b_inns))
        dnb_m = m_played - n_batted

        if n_batted > 0:
            cs_vals = b_inns["contribution_score"].astype(float).values
            raw_vals = b_inns["raw_contribution"].astype(float).values
            pos_raw_vals = np.clip(raw_vals, 0.0, None)

            abc = round(float(np.mean(cs_vals)), 2)
            tot_raw = round(float(np.sum(raw_vals)), 4)
            tot_pos_raw = round(float(np.sum(pos_raw_vals)), 4)
            pos_rate = round(float(np.sum(cs_vals > 50.0) / n_batted * 100.0), 2)

            # ABC-R01: tot_pos_raw / n_batted
            contrib_per_opp = round(float(tot_pos_raw / n_batted), 4)

            # Team contribution share
            team_pos_tot = team_totals.get((seas, comp_cat, t_id), 0.0)
            team_share = (
                round(float(tot_pos_raw / team_pos_tot * 100.0), 2)
                if team_pos_tot > 0
                else 0.0
            )

            # Contextual splits
            inn1_cs = b_inns[b_inns["innings"] == 1]["contribution_score"]
            inn1_avg = (
                round(float(inn1_cs.mean()), 2) if len(inn1_cs) > 0 else None
            )

            inn2_cs = b_inns[b_inns["innings"] == 2]["contribution_score"]
            inn2_avg = (
                round(float(inn2_cs.mean()), 2) if len(inn2_cs) > 0 else None
            )

            pp_cs = b_inns[b_inns["entry_over_notation"] < 6.0]["contribution_score"]
            pp_avg = round(float(pp_cs.mean()), 2) if len(pp_cs) > 0 else None

            mid_cs = b_inns[
                (b_inns["entry_over_notation"] < 16.0)
                & (b_inns["exit_over_notation"] >= 6.0)
            ]["contribution_score"]
            mid_avg = round(float(mid_cs.mean()), 2) if len(mid_cs) > 0 else None

            # ABC-R02: (entry >= 16.0) | (exit >= 16.0)
            death_cs = b_inns[
                (b_inns["entry_over_notation"] >= 16.0)
                | (b_inns["exit_over_notation"] >= 16.0)
            ]["contribution_score"]
            death_avg = (
                round(float(death_cs.mean()), 2) if len(death_cs) > 0 else None
            )

            press_cs = b_inns[b_inns["c_eff"] >= 60.0]["contribution_score"]
            press_avg = (
                round(float(press_cs.mean()), 2) if len(press_cs) > 0 else None
            )

            # Qualified View B (excluding small cameo opportunities: <=2 balls & <=2 runs if not out)
            qual_mask = ~(
                (b_inns["balls_faced"] <= 2)
                & (b_inns["actual_runs"] <= 2)
                & (b_inns["is_not_out"])
            )
            qual_inns = b_inns[qual_mask]
            n_qual = int(len(qual_inns))
            if n_qual > 0:
                qual_cs = qual_inns["contribution_score"].astype(float).values
                qual_abc = round(float(np.mean(qual_cs)), 2)
                qual_pos_raw = round(
                    float(np.sum(np.clip(qual_inns["raw_contribution"].values, 0.0, None))), 4
                )
            else:
                qual_abc = None
                qual_pos_raw = 0.0

        else:
            # Pure DNB: strict NULL for all score metrics
            abc = None
            tot_raw = 0.0
            tot_pos_raw = 0.0
            pos_rate = None
            contrib_per_opp = None
            team_share = None
            inn1_avg = None
            inn2_avg = None
            pp_avg = None
            mid_avg = None
            death_avg = None
            press_avg = None
            n_qual = 0
            qual_abc = None
            qual_pos_raw = 0.0

        records.append(
            {
                "player_id": p_id,
                "season": seas,
                "competition_category": comp_cat,
                "team_id": t_id,
                "engine_name": engine_name,
                "track_tag": TRACK_A_TAG,
                "matches_played": m_played,
                "batting_innings": n_batted,
                "did_not_bat_matches": dnb_m,
                "average_contribution_score": abc,
                "total_raw_contribution": tot_raw,
                "total_positive_raw_contribution": tot_pos_raw,
                "positive_contribution_rate": pos_rate,
                "contribution_per_batting_opportunity": contrib_per_opp,
                "season_team_contribution_share": team_share,
                "first_innings_contribution": inn1_avg,
                "chase_contribution": inn2_avg,
                "powerplay_contribution": pp_avg,
                "middle_over_contribution": mid_avg,
                "death_over_contribution": death_avg,
                "high_pressure_contribution": press_avg,
                "qualified_batting_innings": n_qual,
                "qualified_average_contribution_score": qual_abc,
                "qualified_positive_raw_contribution": qual_pos_raw,
            }
        )

    res_df = pd.DataFrame(records)
    return res_df.sort_values(
        ["season", "competition_category", "team_id", "batting_innings"],
        ascending=[True, True, True, False],
    ).reset_index(drop=True)


def build_pre_match_causal_abc_features(
    scored_match_df: pd.DataFrame,
    engine_name: str,
) -> pd.DataFrame:
    """Builds strictly causal pre-match player ABC features for Track B (future WP models).

    Enforces calendar inequality: source.match_date < target.match_date.
    Zero same-match or future information is ever leaked.

    Parameters
    ----------
    scored_match_df : pd.DataFrame
        Scored batter-match records (with match_id, match_date, player_id, team_id, contribution_score, is_dnb).
    engine_name : str
        Name of the source engine used to score the matches.

    Returns
    -------
    pd.DataFrame
        Pre-match causal player ABC features.
    """
    df = scored_match_df.copy()

    # Pre-extract unique fixtures ordered by (match_date, match_id)
    fixtures = (
        df[["match_id", "competition_category", "season", "match_date"]]
        .drop_duplicates(subset=["match_id"])
        .sort_values(["match_date", "match_id"])
        .reset_index(drop=True)
    )

    # Filter to valid scored batting appearances for prior lookup
    batted_df = df[~df["is_dnb"] & df["contribution_score"].notna()].copy()
    batted_df = batted_df.sort_values(["match_date", "match_id"]).reset_index(
        drop=True
    )

    # Build historical index by player_id
    player_history: dict[int, list[dict[str, Any]]] = {}
    for row in batted_df.to_dict(orient="records"):
        p_id = int(row["player_id"])
        if p_id not in player_history:
            player_history[p_id] = []
        player_history[p_id].append(
            {
                "match_id": int(row["match_id"]),
                "match_date": str(row["match_date"])[:10],
                "competition_category": str(row["competition_category"]),
                "cs": float(row["contribution_score"]),
                "raw": float(row["raw_contribution"]) if row["raw_contribution"] is not None else 0.0,
            }
        )

    # For every player row in df, compute features strictly using match_date < current_match_date
    features_list: list[dict[str, Any]] = []

    for row in df.to_dict(orient="records"):
        m_id = int(row["match_id"])
        p_id = int(row["player_id"])
        t_id = int(row["team_id"])
        cat = str(row["competition_category"])
        m_date = str(row["match_date"])[:10]

        # Prior batting innings strictly before this match's date
        p_inns = player_history.get(p_id, [])
        prior_all = [x for x in p_inns if x["match_date"] < m_date]
        prior_cat = [x for x in prior_all if x["competition_category"] == cat]

        n_all = len(prior_all)
        n_cat = len(prior_cat)

        if n_all > 0:
            all_cs = [x["cs"] for x in prior_all]
            all_raw = [x["raw"] for x in prior_all]
            abc_all_mean = round(float(np.mean(all_cs)), 2)
            abc_all_std = (
                round(float(np.std(all_cs)), 2) if n_all >= 2 else None
            )

            # Last-k
            last10 = all_cs[-10:]
            abc_last10_mean = round(float(np.mean(last10)), 2)
            last5 = all_cs[-5:]
            abc_last5_mean = round(float(np.mean(last5)), 2)

            # Bayesian shrinkage toward 50.0 (m0 = 5)
            abc_shrunk = round(
                float((n_all * abc_all_mean + 5.0 * 50.0) / (n_all + 5.0)), 2
            )

            pos_rate = round(
                float(sum(1 for s in all_cs if s > 50.0) / n_all * 100.0), 2
            )
            pos_raw_sum = sum(max(0.0, r) for r in all_raw)
            pos_raw_per_opp = round(float(pos_raw_sum / n_all), 4)
            is_cold_start = False
        else:
            abc_all_mean = None
            abc_all_std = None
            abc_last10_mean = None
            abc_last5_mean = None
            abc_shrunk = 50.0  # prior anchor when n=0
            pos_rate = None
            pos_raw_per_opp = None
            is_cold_start = True

        if n_cat > 0:
            cat_cs = [x["cs"] for x in prior_cat]
            abc_cat_mean = round(float(np.mean(cat_cs)), 2)
            abc_cat_std = (
                round(float(np.std(cat_cs)), 2) if n_cat >= 2 else None
            )
        else:
            abc_cat_mean = None
            abc_cat_std = None

        features_list.append(
            {
                "match_id": m_id,
                "match_date": m_date,
                "player_id": p_id,
                "team_id": t_id,
                "competition_category": cat,
                "engine_name": engine_name,
                "track_tag": TRACK_B_TAG,
                "batted_inns_prior_all": n_all,
                "batted_inns_prior_cat": n_cat,
                "abc_prior_all_mean": abc_all_mean,
                "abc_prior_all_std": abc_all_std,
                "abc_prior_cat_mean": abc_cat_mean,
                "abc_prior_cat_std": abc_cat_std,
                "abc_prior_all_last10_mean": abc_last10_mean,
                "abc_prior_all_last5_mean": abc_last5_mean,
                "abc_prior_shrunk": abc_shrunk,
                "pos_contrib_rate_prior": pos_rate,
                "pos_raw_per_opp_prior": pos_raw_per_opp,
                "is_abc_cold_start": is_cold_start,
            }
        )

    res_df = pd.DataFrame(features_list)
    return res_df.sort_values(
        ["match_date", "match_id", "team_id", "player_id"]
    ).reset_index(drop=True)
