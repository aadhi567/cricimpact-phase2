"""Stage 5C Comprehensive Evaluation & Comparison Suite.

Evaluates and compares Phase 7U vs Universal Strategy 4 across all 10 criteria
and 4 sensitivity audits, separately for IPL, T20I, and OTHER_T20.
"""

from __future__ import annotations

import json
import logging
from typing import Any

import numpy as np
import pandas as pd
from scipy.stats import kendalltau, pearsonr, pointbiserialr, spearmanr

logger = logging.getLogger(__name__)


def compute_distribution_summary(series: pd.Series) -> dict[str, Any]:
    """Computes summary statistics for a numeric series."""
    valid = series.dropna().astype(float)
    if len(valid) == 0:
        return {"count": 0}
    vals = valid.values
    p05, p25, p50, p75, p90, p95, p99 = np.percentile(
        vals, [5, 25, 50, 75, 90, 95, 99]
    )
    return {
        "count": int(len(vals)),
        "mean": round(float(np.mean(vals)), 2),
        "std": round(float(np.std(vals)), 2),
        "median": round(float(p50), 2),
        "iqr": round(float(p75 - p25), 2),
        "min": round(float(np.min(vals)), 2),
        "max": round(float(np.max(vals)), 2),
        "p05": round(float(p05), 2),
        "p25": round(float(p25), 2),
        "p50": round(float(p50), 2),
        "p75": round(float(p75), 2),
        "p90": round(float(p90), 2),
        "p95": round(float(p95), 2),
        "p99": round(float(p99), 2),
        "pct_gte_95": round(float(np.sum(vals >= 95.0) / len(vals) * 100.0), 2),
        "pct_lte_5": round(float(np.sum(vals <= 5.0) / len(vals) * 100.0), 2),
        "pct_gt_50": round(float(np.sum(vals > 50.0) / len(vals) * 100.0), 2),
    }


def run_10_criteria_evaluation(
    df_p7u: pd.DataFrame,
    df_s4: pd.DataFrame,
    df_s4_opt1c: pd.DataFrame | None = None,
    df_p7u_causal_gap: pd.DataFrame | None = None,
    df_s4_personal_diss: pd.DataFrame | None = None,
    target_match_states_df: pd.DataFrame | None = None,
) -> dict[str, Any]:
    """Runs the full 10-criterion generalisation evaluation and sensitivity analyses."""
    results: dict[str, Any] = {
        "evaluation_scope": "798 STANDARD_T20 matches (18,106 player-match records)",
        "categories": {},
        "sensitivity_audits": {},
    }

    # Filter to valid scored appearances
    batted_p7u = df_p7u[~df_p7u["is_dnb"] & df_p7u["contribution_score"].notna()]
    batted_s4 = df_s4[~df_s4["is_dnb"] & df_s4["contribution_score"].notna()]

    categories = ["IPL", "T20I", "OTHER_T20"]

    for cat in categories:
        cat_p7u = batted_p7u[batted_p7u["competition_category"] == cat]
        cat_s4 = batted_s4[batted_s4["competition_category"] == cat]

        # 1. Distributions of P1, P2, P3, and CS
        dist_p7u_cs = compute_distribution_summary(cat_p7u["contribution_score"])
        dist_s4_cs = compute_distribution_summary(cat_s4["contribution_score"])
        dist_p7u_p2 = compute_distribution_summary(cat_p7u["p2_score"])
        dist_s4_p2 = compute_distribution_summary(cat_s4["p2_score"])
        dist_p7u_p3 = compute_distribution_summary(cat_p7u["p3_score"])
        dist_s4_p3 = compute_distribution_summary(cat_s4["p3_score"])
        dist_p7u_lev = compute_distribution_summary(cat_p7u["leverage_l"])
        dist_s4_lev = compute_distribution_summary(cat_s4["leverage_l"])

        # 2. Innings 1 vs Innings 2 score balance
        inn1_p7u = cat_p7u[cat_p7u["innings"] == 1]["contribution_score"].values
        inn2_p7u = cat_p7u[cat_p7u["innings"] == 2]["contribution_score"].values
        inn1_s4 = cat_s4[cat_s4["innings"] == 1]["contribution_score"].values
        inn2_s4 = cat_s4[cat_s4["innings"] == 2]["contribution_score"].values

        p7u_inn_gap = round(float(abs(np.mean(inn1_p7u) - np.mean(inn2_p7u))), 2) if len(inn1_p7u) > 0 and len(inn2_p7u) > 0 else None
        s4_inn_gap = round(float(abs(np.mean(inn1_s4) - np.mean(inn2_s4))), 2) if len(inn1_s4) > 0 and len(inn2_s4) > 0 else None

        # 3. Collapse Protection: multi-wicket collapses (wkts_lost_during_stay >= 2)
        collapse_p7u = cat_p7u[cat_p7u["wickets_lost_during_stay"] >= 2]
        collapse_s4 = cat_s4[cat_s4["wickets_lost_during_stay"] >= 2]
        col_p7u_mean = round(float(collapse_p7u["contribution_score"].mean()), 2) if len(collapse_p7u) > 0 else None
        col_s4_mean = round(float(collapse_s4["contribution_score"].mean()), 2) if len(collapse_s4) > 0 else None

        # 4. Low-ball and cameo knocks (1..5 balls)
        cameos_p7u = cat_p7u[cat_p7u["balls_faced"].between(1, 5)]
        cameos_s4 = cat_s4[cat_s4["balls_faced"].between(1, 5)]
        cameo_p7u_mean = round(float(cameos_p7u["contribution_score"].mean()), 2) if len(cameos_p7u) > 0 else None
        cameo_s4_mean = round(float(cameos_s4["contribution_score"].mean()), 2) if len(cameos_s4) > 0 else None

        # Extreme knocks: runs >= 70
        extreme_p7u = cat_p7u[cat_p7u["actual_runs"] >= 70]
        extreme_s4 = cat_s4[cat_s4["actual_runs"] >= 70]
        ext_p7u_mean = round(float(extreme_p7u["contribution_score"].mean()), 2) if len(extreme_p7u) > 0 else None
        ext_s4_mean = round(float(extreme_s4["contribution_score"].mean()), 2) if len(extreme_s4) > 0 else None

        # 5. Era / Season Stability across 2022-2026
        seasons = sorted(cat_p7u["season"].unique())
        season_stability = {}
        for s in seasons:
            s_p7u = cat_p7u[cat_p7u["season"] == s]["contribution_score"]
            s_s4 = cat_s4[cat_s4["season"] == s]["contribution_score"]
            season_stability[s] = {
                "matches": int(len(cat_p7u[cat_p7u["season"] == s]["match_id"].unique())),
                "p7u_mean": round(float(s_p7u.mean()), 2),
                "s4_mean": round(float(s_s4.mean()), 2),
                "p7u_pos_rate": round(float((s_p7u > 50.0).mean() * 100.0), 2),
                "s4_pos_rate": round(float((s_s4 > 50.0).mean() * 100.0), 2),
            }

        # 6. DNB Exclusion Integrity in this category
        all_cat_p7u = df_p7u[df_p7u["competition_category"] == cat]
        dnb_cat = all_cat_p7u[all_cat_p7u["is_dnb"]]
        dnb_null_count = int(dnb_cat["contribution_score"].isna().sum())
        dnb_intact = (dnb_null_count == len(dnb_cat))

        # 7. Rank Stability between engines
        # Align by (match_id, innings, player_id)
        merged = pd.merge(
            cat_p7u[["match_id", "innings", "player_id", "contribution_score", "actual_runs"]],
            cat_s4[["match_id", "innings", "player_id", "contribution_score"]],
            on=["match_id", "innings", "player_id"],
            suffixes=("_p7u", "_s4"),
        )
        if len(merged) >= 5:
            sp_rho, _ = spearmanr(merged["contribution_score_p7u"], merged["contribution_score_s4"])
            kd_tau, _ = kendalltau(merged["contribution_score_p7u"], merged["contribution_score_s4"])
            diffs = merged["contribution_score_s4"] - merged["contribution_score_p7u"]
            mean_diff = round(float(diffs.mean()), 2)
            max_abs_diff = round(float(diffs.abs().max()), 2)
        else:
            sp_rho = kd_tau = mean_diff = max_abs_diff = None

        # 8. Tournament-specific diagnostics for OTHER_T20 (comp_id 2670 and 3289)
        tourn_diag = {}
        if cat == "OTHER_T20":
            for comp_id in [2670, 3289]:
                # find match_ids for this comp
                if target_match_states_df is not None:
                    c_mids = set(target_match_states_df[target_match_states_df["comp_id"] == comp_id]["match_id"].unique())
                else:
                    c_mids = set()
                c_p7u = cat_p7u[cat_p7u["match_id"].isin(c_mids)]
                c_s4 = cat_s4[cat_s4["match_id"].isin(c_mids)]
                tourn_diag[str(comp_id)] = {
                    "matches": len(c_mids),
                    "p7u_mean": round(float(c_p7u["contribution_score"].mean()), 2) if len(c_p7u) > 0 else None,
                    "s4_mean": round(float(c_s4["contribution_score"].mean()), 2) if len(c_s4) > 0 else None,
                    "provenance": "LOW_SAMPLE_EXPLORATORY_NO_ML",
                }

        results["categories"][cat] = {
            "n_matches": int(len(cat_p7u["match_id"].unique())),
            "n_batted_inns": int(len(cat_p7u)),
            "criterion_1_distributions": {
                "phase7u_cs": dist_p7u_cs,
                "strategy4_cs": dist_s4_cs,
                "phase7u_p2": dist_p7u_p2,
                "strategy4_p2": dist_s4_p2,
                "phase7u_p3": dist_p7u_p3,
                "strategy4_p3": dist_s4_p3,
                "phase7u_leverage": dist_p7u_lev,
                "strategy4_leverage": dist_s4_lev,
            },
            "criterion_2_innings_balance": {
                "p7u_inn1_mean": round(float(np.mean(inn1_p7u)), 2) if len(inn1_p7u) > 0 else None,
                "p7u_inn2_mean": round(float(np.mean(inn2_p7u)), 2) if len(inn2_p7u) > 0 else None,
                "p7u_inn_gap": p7u_inn_gap,
                "s4_inn1_mean": round(float(np.mean(inn1_s4)), 2) if len(inn1_s4) > 0 else None,
                "s4_inn2_mean": round(float(np.mean(inn2_s4)), 2) if len(inn2_s4) > 0 else None,
                "s4_inn_gap": s4_inn_gap,
            },
            "criterion_3_collapse_protection": {
                "collapse_inns_count": int(len(collapse_p7u)),
                "p7u_collapse_mean": col_p7u_mean,
                "s4_collapse_mean": col_s4_mean,
            },
            "criterion_4_outlier_stability": {
                "cameos_1_to_5_balls": {
                    "count": int(len(cameos_p7u)),
                    "p7u_mean": cameo_p7u_mean,
                    "s4_mean": cameo_s4_mean,
                },
                "extreme_knocks_70_plus_runs": {
                    "count": int(len(extreme_p7u)),
                    "p7u_mean": ext_p7u_mean,
                    "s4_mean": ext_s4_mean,
                },
            },
            "criterion_5_season_stability": season_stability,
            "criterion_6_dnb_integrity": {
                "dnb_rows": int(len(dnb_cat)),
                "dnb_null_scores": dnb_null_count,
                "dnb_intact": dnb_intact,
            },
            "criterion_7_rank_stability": {
                "spearman_rho": round(float(sp_rho), 4) if sp_rho is not None else None,
                "kendall_tau": round(float(kd_tau), 4) if kd_tau is not None else None,
                "mean_delta_s4_minus_p7u": mean_diff,
                "max_abs_delta": max_abs_diff,
            },
            "criterion_9_tournament_subgroups": tourn_diag if cat == "OTHER_T20" else None,
        }

    # 10. Match-level plausibility & outcome alignment audit (post-hoc point-biserial check)
    if target_match_states_df is not None:
        target_map = (
            target_match_states_df[["match_id", "target_batting_team_win"]]
            .drop_duplicates(subset=["match_id"])
            .set_index("match_id")["target_batting_team_win"]
            .to_dict()
        )
        batted_s4_copy = batted_s4.copy()
        batted_s4_copy["win"] = batted_s4_copy["match_id"].map(target_map)
        valid_win = batted_s4_copy.dropna(subset=["win", "contribution_score"])
        if len(valid_win) > 30:
            pb_corr, pb_pval = pointbiserialr(valid_win["win"].astype(int), valid_win["contribution_score"].astype(float))
            win_mean = round(float(valid_win[valid_win["win"] == 1]["contribution_score"].mean()), 2)
            loss_mean = round(float(valid_win[valid_win["win"] == 0]["contribution_score"].mean()), 2)
            results["criterion_10_outcome_alignment"] = {
                "point_biserial_corr": round(float(pb_corr), 4),
                "p_value": float(pb_pval),
                "winner_batter_mean_cs": win_mean,
                "loser_batter_mean_cs": loss_mean,
                "separation": round(win_mean - loss_mean, 2),
            }

    # -------------------------------------------------------------
    # SENSITIVITY AUDITS
    # -------------------------------------------------------------
    # Audit S1: S_res Partner Wicket vs Personal Dismissal
    if df_s4_personal_diss is not None:
        merged_s1 = pd.merge(
            batted_s4[["match_id", "innings", "player_id", "is_not_out", "wickets_lost_during_stay", "contribution_score"]],
            df_s4_personal_diss[["match_id", "innings", "player_id", "contribution_score"]],
            on=["match_id", "innings", "player_id"],
            suffixes=("_partner_wkt", "_personal_diss"),
        )
        not_out_with_partner_wkt = merged_s1[
            merged_s1["is_not_out"] & (merged_s1["wickets_lost_during_stay"] > 0)
        ]
        diff_s1 = (
            not_out_with_partner_wkt["contribution_score_personal_diss"]
            - not_out_with_partner_wkt["contribution_score_partner_wkt"]
        )
        results["sensitivity_audits"]["audit_s1_partner_vs_personal_dismissal"] = {
            "affected_not_out_inns": int(len(not_out_with_partner_wkt)),
            "mean_delta_on_not_out_batters": round(float(diff_s1.mean()), 2) if len(diff_s1) > 0 else 0.0,
            "max_delta": round(float(diff_s1.max()), 2) if len(diff_s1) > 0 else 0.0,
            "explanation": "Evaluates impact of Phase 1 S_res quirk on not-out batters when a partner fell during stay.",
        }

    # Audit S2: rr_gap_entry wired vs 0.0 in C_chase
    if df_p7u_causal_gap is not None:
        merged_s2 = pd.merge(
            df_p7u[df_p7u["innings"] == 2][["match_id", "innings", "player_id", "contribution_score", "c_chase"]],
            df_p7u_causal_gap[df_p7u_causal_gap["innings"] == 2][["match_id", "innings", "player_id", "contribution_score", "c_chase"]],
            on=["match_id", "innings", "player_id"],
            suffixes=("_gap0", "_causal_gap"),
        ).dropna()
        cs_diff = merged_s2["contribution_score_causal_gap"] - merged_s2["contribution_score_gap0"]
        c_chase_diff = merged_s2["c_chase_causal_gap"] - merged_s2["c_chase_gap0"]
        results["sensitivity_audits"]["audit_s2_rr_gap_wired_vs_zero"] = {
            "chase_inns_evaluated": int(len(merged_s2)),
            "c_chase_mean_delta": round(float(c_chase_diff.mean()), 2),
            "c_chase_max_abs_delta": round(float(c_chase_diff.abs().max()), 2),
            "cs_mean_delta": round(float(cs_diff.mean()), 2),
            "cs_max_abs_delta": round(float(cs_diff.abs().max()), 2),
            "explanation": "Compares Phase 1 baseline rr_gap=0.0 against actual causal rr_gap_entry in C_chase.",
        }

    # Audit S4: Option 1C Chase f_res Variant
    if df_s4_opt1c is not None:
        merged_s4 = pd.merge(
            batted_s4[batted_s4["innings"] == 2][["match_id", "innings", "player_id", "contribution_score"]],
            df_s4_opt1c[df_s4_opt1c["innings"] == 2][["match_id", "innings", "player_id", "contribution_score"]],
            on=["match_id", "innings", "player_id"],
            suffixes=("_opt1b", "_opt1c"),
        ).dropna()
        opt_diff = merged_s4["contribution_score_opt1c"] - merged_s4["contribution_score_opt1b"]
        results["sensitivity_audits"]["audit_s4_option_1c_f_res_chase"] = {
            "chase_inns_evaluated": int(len(merged_s4)),
            "mean_delta_opt1c_minus_opt1b": round(float(opt_diff.mean()), 2),
            "max_abs_delta": round(float(opt_diff.abs().max()), 2),
            "explanation": "Compares Option 1B primary chase model against Option 1C crease resource depletion f_res variant.",
        }

    return results

