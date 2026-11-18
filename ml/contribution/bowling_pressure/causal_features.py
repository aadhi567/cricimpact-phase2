"""Stage B7.5 Causal Feature Extraction & Pre-Delivery State Pipeline."""

from __future__ import annotations

import numpy as np
import pandas as pd

from ml.contribution.bowling_pressure.schema import validate_causal_timing


def calculate_resource_percentage(wickets_remaining: int | float, balls_remaining: int | float) -> float:
    """Calculate non-linear remaining batting resources percentage in [0.0, 100.0]."""
    w = float(wickets_remaining)
    b = float(balls_remaining)
    if w <= 0.0 or b <= 0.0:
        return 0.0
    exponent = -(b / 120.0) * (0.20 + 0.08 * w)
    val = 100.0 * (1.0 - np.exp(exponent)) / (1.0 - np.exp(-1.0))
    return float(np.clip(val, 0.0, 100.0))


class CausalFeatureExtractor:
    """Engineers strictly causal, pre-delivery rolling features with zero lookahead."""

    def __init__(self) -> None:
        pass

    def extract_delivery_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Extract delivery-grain features across dataframe.
        
        Guarantees that rolling windows only use deliveries strictly prior to ball t.
        """
        df_work = df.copy()

        # Sort chronologically by match, innings, and delivery sequence
        df_work = df_work.sort_values(["match_id", "innings", "innings_ball_num"]).reset_index(drop=True)

        # 1. Clean event fields for lag-1 shifting
        team_runs_f = df_work["team_runs"].astype(float).fillna(0.0).to_numpy()
        is_wkt_f = df_work["is_wicket_event"].astype(float).fillna(0.0).to_numpy()
        
        # Dot ball definition: team runs == 0 and legal delivery
        is_legal = df_work["is_legal_delivery"].astype(bool).to_numpy()
        is_dot = (team_runs_f == 0.0) & is_legal
        is_dot_f = is_dot.astype(float)

        # Group keys
        m_id = df_work["match_id"].to_numpy()
        inns = df_work["innings"].to_numpy()

        # Vectorized lag-1 shift within (match_id, innings)
        # Identify group boundaries
        boundary = np.empty(len(df_work), dtype=bool)
        boundary[0] = True
        boundary[1:] = (m_id[1:] != m_id[:-1]) | (inns[1:] != inns[:-1])

        runs_prev = np.zeros(len(df_work), dtype=float)
        wkts_prev = np.zeros(len(df_work), dtype=float)
        dots_prev = np.zeros(len(df_work), dtype=float)

        runs_prev[1:] = np.where(boundary[1:], 0.0, team_runs_f[:-1])
        wkts_prev[1:] = np.where(boundary[1:], 0.0, is_wkt_f[:-1])
        dots_prev[1:] = np.where(boundary[1:], 0.0, is_dot_f[:-1])

        df_work["runs_prev"] = runs_prev
        df_work["wkts_prev"] = wkts_prev
        df_work["dots_prev"] = dots_prev

        # 2. Rolling 12-ball and 18-ball causal windows
        grp = df_work.groupby(["match_id", "innings"])
        df_work["runs_last_12_balls"] = (
            grp["runs_prev"].transform(lambda s: s.rolling(12, min_periods=1).sum()).astype(int)
        )
        df_work["dots_last_12_balls"] = (
            grp["dots_prev"].transform(lambda s: s.rolling(12, min_periods=1).sum()).astype(int)
        )
        df_work["runs_last_18_balls"] = (
            grp["runs_prev"].transform(lambda s: s.rolling(18, min_periods=1).sum()).astype(int)
        )
        df_work["dots_last_18_balls"] = (
            grp["dots_prev"].transform(lambda s: s.rolling(18, min_periods=1).sum()).astype(int)
        )

        # 3. Non-linear resource percentage remaining
        w_rem = df_work["wickets_remaining_before"].to_numpy() if "wickets_remaining_before" in df_work.columns else (10 - df_work["wickets_lost_before"].to_numpy())
        b_rem = df_work["legal_balls_remaining_before"].to_numpy()
        df_work["resource_pct_remaining"] = [
            calculate_resource_percentage(w, b) for w, b in zip(w_rem, b_rem)
        ]

        # 4. Clean required run rate and current run rate
        crr = df_work["current_run_rate"].fillna(0.0).clip(0.0, 36.0)
        df_work["current_run_rate_before"] = crr

        if "required_run_rate" in df_work.columns:
            rrr = pd.to_numeric(df_work["required_run_rate"], errors="coerce").fillna(0.0).clip(0.0, 99.0)
            df_work["required_run_rate_before"] = rrr
        else:
            df_work["required_run_rate_before"] = 0.0

        # Drop temporary lag columns
        df_work = df_work.drop(columns=["runs_prev", "wkts_prev", "dots_prev"])

        return df_work
