"""CricImpact Phase 2 — High Pressure Player (HPP) Engine.

Production implementation of the Stage 7C High Pressure Player evaluation engine,
measuring contextual delivery-level pressure, situational expected runs,
Runs Above Expectation (RAE), and High Pressure Contribution (HPC) with
asymmetric crisis leverage.

Strictly causal, pre-delivery information only, zero forward-looking leakage.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# Model Hyperparameters and Frozen Empirical Constants
# ---------------------------------------------------------------------------

# First-Innings Empirical Phase Base Rates (runs per legal ball)
BASE_RATE_I1_POWERPLAY: float = 1.3390
BASE_RATE_I1_MIDDLE: float = 1.3230
BASE_RATE_I1_DEATH: float = 1.6445

# Second-Innings Empirical Phase Base Rates (runs per legal ball)
BASE_RATE_I2_POWERPLAY: float = 1.3667
BASE_RATE_I2_MIDDLE: float = 1.3247
BASE_RATE_I2_DEATH: float = 1.5246

# Tail Wicket Degradation Factor (kappa)
TAIL_FACTORS: Dict[int, float] = {
    0: 1.00,
    1: 1.00,
    2: 1.00,
    3: 1.00,
    4: 1.00,
    5: 1.00,
    6: 0.98,
    7: 0.92,
    8: 0.88,
    9: 0.75,
}

# Population Ground Par Benchmark (Historical Corpus Median)
CORPUS_MEDIAN_TOTAL: float = 173.8
FALLBACK_EXPECTED_TOTAL: float = 177.5

# Pressure Tiers
TIER_LOW: str = "Low"
TIER_MEDIUM: str = "Medium"
TIER_HIGH: str = "High"
TIER_EXTREME: str = "Extreme"


# ---------------------------------------------------------------------------
# Core Mathematical Formulations
# ---------------------------------------------------------------------------

def calculate_par_wickets(legal_balls_before: Union[int, float]) -> float:
    """Calculate historical cumulative par wickets lost at ball b.

    Formula: w_par(b) = 6.0 * (b / 120.0) ** 0.85
    """
    if legal_balls_before <= 0:
        return 0.0
    return float(6.0 * ((float(legal_balls_before) / 120.0) ** 0.85))


def calculate_delivery_pressure(
    innings: int,
    legal_balls_before: int,
    wickets_before: int,
    score_before: int,
    bench_total: float,
    required_run_rate: Optional[float] = None,
    legal_balls_remaining_before: Optional[int] = None,
) -> float:
    """Calculate delivery-level Pressure Score P(t) in [0.0, 100.0].

    Strictly uses causal pre-delivery state variables.
    """
    w_before = int(min(9, max(0, wickets_before)))
    b_before = int(max(0, legal_balls_before))
    score = int(score_before)

    if innings == 1:
        # 1. Wicket Component (0 to 55)
        w_par = calculate_par_wickets(b_before)
        w_excess = max(0.0, float(w_before) - w_par)
        p_w_base = (float(w_before) / 9.0) * 35.0
        p_w_excess = float(np.clip(w_excess * 7.0, 0.0, 20.0))
        p_w = p_w_base + p_w_excess

        # 2. Scoreboard Deficit Component (-9 to 30)
        expected_bench = float(bench_total) if bench_total > 0 else FALLBACK_EXPECTED_TOTAL
        par_score = expected_bench * (float(b_before) / 120.0)
        deficit = par_score - float(score)
        p_def = float(np.clip(deficit / 25.0, -0.3, 1.0)) * 30.0

        # 3. Phase Urgency (0 to 15)
        if b_before >= 90:
            p_urgency = ((float(b_before) - 90.0) / 30.0) * 15.0
        else:
            p_urgency = 0.0

        p_total = float(np.clip(p_w + p_def + p_urgency, 0.0, 100.0))
        return p_total

    else:
        # Innings 2 (Target Chase)
        if required_run_rate is None or pd.isna(required_run_rate):
            rrr = 8.0
        else:
            try:
                rrr_val = float(required_run_rate)
                rrr = 8.0 if (np.isnan(rrr_val) or rrr_val < 0) else rrr_val
            except (ValueError, TypeError):
                rrr = 8.0

        if legal_balls_remaining_before is None or pd.isna(legal_balls_remaining_before):
            b_rem = float(120 - b_before)
        else:
            try:
                b_rem_val = float(legal_balls_remaining_before)
                b_rem = float(120 - b_before) if np.isnan(b_rem_val) else b_rem_val
            except (ValueError, TypeError):
                b_rem = float(120 - b_before)

        # 1. Required Run Rate Component (0 to 60)
        p_rrr = float(np.clip((rrr - 4.0) / 12.0, 0.0, 1.0)) * 60.0

        # 2. Wicket Component (0 to 30)
        p_w = (float(w_before) / 9.0) * 30.0

        # 3. Endgame Urgency / Leverage (-10 to 10)
        urgency_weight = (120.0 - b_rem) / 120.0
        if rrr > 8.0:
            p_urg = urgency_weight * min(10.0, (rrr - 8.0) * 2.0)
        else:
            p_urg = - urgency_weight * min(10.0, (8.0 - rrr) * 2.0)

        p_total = float(np.clip(p_rrr + p_w + p_urg, 0.0, 100.0))
        return p_total


def calculate_delivery_expected_runs(
    innings: int,
    phase: str,
    wickets_before: int,
    bench_total: float,
    required_run_rate: Optional[float] = None,
) -> float:
    """Calculate expected runs e(s) off an individual delivery.

    Conditioned on innings, phase, wickets down, venue benchmark, and RRR.
    """
    w = min(9, max(0, int(wickets_before)))
    phase_str = str(phase).lower()

    if innings == 1:
        if phase_str == "powerplay":
            base_r = BASE_RATE_I1_POWERPLAY
        elif phase_str == "middle":
            base_r = BASE_RATE_I1_MIDDLE
        else:
            base_r = BASE_RATE_I1_DEATH

        g_target = float(bench_total) if bench_total > 0 else FALLBACK_EXPECTED_TOTAL
        gamma_g = g_target / CORPUS_MEDIAN_TOTAL
        kappa_w = TAIL_FACTORS.get(w, 1.0)
        return float(base_r * kappa_w * gamma_g)

    else:
        if phase_str == "powerplay":
            base_r = BASE_RATE_I2_POWERPLAY
        elif phase_str == "middle":
            base_r = BASE_RATE_I2_MIDDLE
        else:
            base_r = BASE_RATE_I2_DEATH

        if required_run_rate is None or pd.isna(required_run_rate):
            rrr = 8.0
        else:
            try:
                rrr_val = float(required_run_rate)
                rrr = 8.0 if (np.isnan(rrr_val) or rrr_val < 0) else rrr_val
            except (ValueError, TypeError):
                rrr = 8.0
        # RRR demand factor: clip((RRR - 8.0) * 0.02, -0.15, 0.20)
        rrr_factor = 1.0 + float(np.clip((rrr - 8.0) * 0.02, -0.15, 0.20))
        kappa_w = TAIL_FACTORS.get(w, 1.0)
        return float(base_r * kappa_w * rrr_factor)


def calculate_hpc(rae: float, mean_pressure: float) -> float:
    """Calculate High Pressure Contribution (HPC).

    Audited Asymmetric Formulation:
    - If RAE >= 0:
        leverage = 1.0 + clip((mean_p - 50.0) / 50.0, -0.5, 1.0)
        HPC = RAE * leverage
    - If RAE < 0:
        mitigation = 1.0 - clip((mean_p - 50.0) / 100.0, 0.0, 0.4)
        HPC = RAE * mitigation

    Mathematical Invariants:
    - Sign preservation: sign(HPC) == sign(RAE)
    - Zero preservation: RAE == 0 -> HPC == 0
    - Continuity: At P=50, HPC = RAE
    - Non-inversion: Negative performances are softened in crisis, never made positive.
    """
    if pd.isna(rae) or pd.isna(mean_pressure):
        return np.nan

    if rae == 0.0:
        return 0.0

    p = float(np.clip(mean_pressure, 0.0, 100.0))

    if rae > 0.0:
        leverage = 1.0 + float(np.clip((p - 50.0) / 50.0, -0.5, 1.0))
        return float(rae * leverage)
    else:
        mitigation = 1.0 - float(np.clip((p - 50.0) / 100.0, 0.0, 0.4))
        return float(rae * mitigation)


def get_pressure_tier(pressure: float) -> str:
    """Classify continuous Pressure Score into operational tiers."""
    if pd.isna(pressure):
        return "Unknown"
    p = float(pressure)
    if p < 25.0:
        return TIER_LOW
    elif p < 50.0:
        return TIER_MEDIUM
    elif p < 75.0:
        return TIER_HIGH
    else:
        return TIER_EXTREME


# ---------------------------------------------------------------------------
# High-Level Evaluation Pipeline
# ---------------------------------------------------------------------------

def evaluate_batter_stints(
    match_states_df: pd.DataFrame,
    ground_benchmark_map: Optional[Dict[int, float]] = None,
    player_names_map: Optional[Dict[int, str]] = None,
    matches_df: Optional[pd.DataFrame] = None,
    stints_metadata_df: Optional[pd.DataFrame] = None,
) -> pd.DataFrame:
    """Evaluate all batter stints across match states with full HPP metrics.

    Parameters
    ----------
    match_states_df : pd.DataFrame
        Delivery transitions from match_states_standard_t20_v1.pkl.gz.
    ground_benchmark_map : Optional[Dict[int, float]]
        Mapping of match_id -> expected first innings total (arch3_shrink_m5_total).
    player_names_map : Optional[Dict[int, str]]
        Mapping of striker_id -> player name.
    matches_df : Optional[pd.DataFrame]
        Matches dataframe containing win_team_id for outcome analysis.
    stints_metadata_df : Optional[pd.DataFrame]
        Metadata from batter_stints_v1.pkl.gz for dismissal status and DNB tracking.

    Returns
    -------
    pd.DataFrame
        Evaluated stints table containing actual runs, expected runs, RAE,
        pressure trajectory, HPC, pressure tiers, and dismissal types.
    """
    # 1. Filter to legal, non-super-over deliveries
    df = match_states_df[
        (~match_states_df["is_super_over_delivery"]) & (match_states_df["is_legal_delivery"])
    ].copy()

    # 2. Attach ground benchmark and names
    if ground_benchmark_map is not None:
        df["bench_total"] = df["match_id"].map(ground_benchmark_map).fillna(FALLBACK_EXPECTED_TOTAL)
    else:
        df["bench_total"] = FALLBACK_EXPECTED_TOTAL

    if player_names_map is not None:
        df["striker_name"] = df["striker_id"].map(player_names_map)
    else:
        df["striker_name"] = "Player " + df["striker_id"].astype(str)

    if matches_df is not None:
        win_map = dict(zip(matches_df["match_id"], matches_df["win_team_id"]))
        df["team_won"] = df["batting_team_id"] == df["match_id"].map(win_map)
    else:
        df["team_won"] = False

    # 3. Vectorized / Row-wise delivery pressure and expectation
    print("Computing delivery-level Pressure Scores and Expected Runs...")

    def _row_pressure(row):
        return calculate_delivery_pressure(
            innings=int(row["innings"]),
            legal_balls_before=int(row["legal_balls_completed_before"]),
            wickets_before=int(row["wickets_lost_before"]),
            score_before=int(row["score_before"]),
            bench_total=float(row["bench_total"]),
            required_run_rate=row.get("required_run_rate", None),
            legal_balls_remaining_before=row.get("legal_balls_remaining_before", None),
        )

    def _row_expected(row):
        return calculate_delivery_expected_runs(
            innings=int(row["innings"]),
            phase=str(row["innings_phase"]),
            wickets_before=int(row["wickets_lost_before"]),
            bench_total=float(row["bench_total"]),
            required_run_rate=row.get("required_run_rate", None),
        )

    df["delivery_pressure"] = df.apply(_row_pressure, axis=1)
    df["delivery_expected_runs"] = df.apply(_row_expected, axis=1)

    # 4. Aggregate by (match_id, innings, striker_id)
    # This naturally unifies retired-hurt returnees into their single innings stint.
    print("Aggregating unique batter innings stints...")

    # Build dismissal lookup if metadata provided
    dismissal_map: Dict[Tuple[int, int, int], Dict[str, Any]] = {}
    if stints_metadata_df is not None:
        for _, srow in stints_metadata_df.iterrows():
            key = (int(srow["match_id"]), int(srow["innings"]), int(srow["player_id"]))
            dismissal_map[key] = {
                "dismissal_status": srow.get("dismissal_status", "not out"),
                "dismissal_type_canonical": srow.get("dismissal_type_canonical", None),
                "is_out": bool(srow.get("is_out", False)),
                "is_not_out": bool(srow.get("is_not_out", True)),
                "is_dnb": bool(srow.get("is_dnb", False)),
                "batting_order": srow.get("batting_order", np.nan),
            }

    stint_records = []
    grouped = df.groupby(["match_id", "innings", "striker_id"], sort=False)

    for (mid, inn, sid), grp in grouped:
        sname = grp["striker_name"].iloc[0]
        team_won = grp["team_won"].iloc[0]
        bat_team = grp["batting_team_id"].iloc[0]
        bowl_team = grp["bowling_team_id"].iloc[0]
        m_date = grp["match_date"].iloc[0]
        season = grp["season"].iloc[0]
        comp = grp["competition_category"].iloc[0]

        b_faced = len(grp)
        actual_runs = int(grp["batter_runs"].sum())
        fours = int(grp["is_boundary_four"].sum())
        sixes = int(grp["is_boundary_six"].sum())
        dots = int((grp["batter_runs"] == 0).sum())

        entry_ball = int(grp["innings_ball_num"].iloc[0])
        entry_over = float(grp["overid"].iloc[0])
        entry_w = int(grp["wickets_lost_before"].iloc[0])
        entry_score = int(grp["score_before"].iloc[0])

        entry_p = float(grp["delivery_pressure"].iloc[0])
        exit_p = float(grp["delivery_pressure"].iloc[-1])
        mean_p = float(grp["delivery_pressure"].mean())
        peak_p = float(grp["delivery_pressure"].max())

        e_runs = float(grp["delivery_expected_runs"].sum())
        rae = float(actual_runs - e_runs)

        hpc = calculate_hpc(rae=rae, mean_pressure=mean_p)
        tier = get_pressure_tier(mean_p)

        # Lookup dismissal info
        d_info = dismissal_map.get((int(mid), int(inn), int(sid)), {})
        dismissal_status = d_info.get("dismissal_status", "not out" if grp["wickets_lost_before"].iloc[-1] == entry_w else "out")
        dismissal_type = d_info.get("dismissal_type_canonical", None)
        is_out = d_info.get("is_out", dismissal_status == "out")
        is_not_out = d_info.get("is_not_out", dismissal_status == "not out")
        batting_order = d_info.get("batting_order", np.nan)

        stint_records.append({
            "match_id": int(mid),
            "innings": int(inn),
            "player_id": int(sid),
            "striker_id": int(sid),
            "batter_name": str(sname),
            "match_date": str(m_date),
            "season": str(season),
            "competition_category": str(comp),
            "batting_team_id": int(bat_team),
            "bowling_team_id": int(bowl_team),
            "team_won": bool(team_won),
            "batting_order": batting_order,
            "balls_faced": int(b_faced),
            "actual_runs": int(actual_runs),
            "fours": int(fours),
            "sixes": int(sixes),
            "dots": int(dots),
            "entry_ball": entry_ball,
            "entry_over": entry_over,
            "entry_wickets": entry_w,
            "entry_score": entry_score,
            "entry_pressure": entry_p,
            "exit_pressure": exit_p,
            "mean_pressure": mean_p,
            "peak_pressure": peak_p,
            "pressure_tier": tier,
            "expected_runs": e_runs,
            "rae": rae,
            "hpc": hpc,
            "dismissal_status": dismissal_status,
            "dismissal_type_canonical": dismissal_type,
            "is_out": is_out,
            "is_not_out": is_not_out,
            "is_dnb": False,
        })

    # 5. Add explicit DNB and 0-ball records if metadata provided
    # Ensuring DNB records have explicit NaN for contribution and pressure, never 0.0!
    if stints_metadata_df is not None:
        seen_keys = set(df.groupby(["match_id", "innings", "striker_id"]).groups.keys())
        for _, srow in stints_metadata_df.iterrows():
            key = (int(srow["match_id"]), int(srow["innings"]), int(srow["player_id"]))
            if key not in seen_keys:
                mid, inn, pid = key
                sname = player_names_map.get(pid, f"Player {pid}") if player_names_map else f"Player {pid}"
                stint_records.append({
                    "match_id": mid,
                    "innings": inn,
                    "player_id": pid,
                    "striker_id": pid,
                    "batter_name": str(sname),
                    "match_date": str(srow.get("match_date", "")),
                    "season": str(srow.get("season", "")),
                    "competition_category": str(srow.get("competition_category", "")),
                    "batting_team_id": int(srow.get("team_id", -1)),
                    "bowling_team_id": int(srow.get("opponent_team_id", -1)),
                    "team_won": False,
                    "batting_order": srow.get("batting_order", np.nan),
                    "balls_faced": 0,
                    "actual_runs": 0,
                    "fours": 0,
                    "sixes": 0,
                    "dots": 0,
                    "entry_ball": np.nan,
                    "entry_over": np.nan,
                    "entry_wickets": np.nan,
                    "entry_score": np.nan,
                    "entry_pressure": np.nan,
                    "exit_pressure": np.nan,
                    "mean_pressure": np.nan,
                    "peak_pressure": np.nan,
                    "pressure_tier": "DNB",
                    "expected_runs": np.nan,
                    "rae": np.nan,
                    "hpc": np.nan,
                    "dismissal_status": srow.get("dismissal_status", "DNB"),
                    "dismissal_type_canonical": srow.get("dismissal_type_canonical", None),
                    "is_out": bool(srow.get("is_out", False)),
                    "is_not_out": bool(srow.get("is_not_out", True)),
                    "is_dnb": True,
                })

    df_out = pd.DataFrame(stint_records)
    print(f"Total evaluated records created: {len(df_out)} (Active Batting Stints: {len(df_out[~df_out['is_dnb']])})")
    return df_out
