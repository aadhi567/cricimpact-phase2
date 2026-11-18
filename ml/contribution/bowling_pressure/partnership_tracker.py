"""Stage B7.5 Dynamic Partnership Tracker & State Engine."""

from __future__ import annotations

import numpy as np
import pandas as pd


class PartnershipTracker:
    """Tracks active partnership metrics, resetting upon wicket dismissals."""

    def __init__(self) -> None:
        pass

    def track_partnerships(self, df: pd.DataFrame) -> pd.DataFrame:
        """Compute delivery-level active partnership metrics across dataframe."""
        df_work = df.copy()

        # Sort chronologically
        df_work = df_work.sort_values(["match_id", "innings", "innings_ball_num"]).reset_index(drop=True)

        # Use existing partnership metrics if already provided (e.g. single delivery evaluations)
        if "partnership_runs_current" in df_work.columns and "partnership_balls_current" in df_work.columns:
            ptnr_runs = df_work["partnership_runs_current"].fillna(0).astype(int)
            ptnr_balls = df_work["partnership_balls_current"].fillna(0).astype(int)
        else:
            # Vectorized partnership calculations using wickets_lost_before group key
            # A partnership is uniquely identified by (match_id, innings, wickets_lost_before)
            ptnr_keys = ["match_id", "innings", "wickets_lost_before"]

            # Partnership start score and start legal balls
            start_scores = df_work.groupby(ptnr_keys)["score_before"].transform("min")
            start_balls = df_work.groupby(ptnr_keys)["legal_balls_completed_before"].transform("min")

            ptnr_runs = (df_work["score_before"] - start_scores).clip(lower=0).astype(int)
            ptnr_balls = (df_work["legal_balls_completed_before"] - start_balls).clip(lower=0).astype(int)

        # Partnership run rate (fall back to current run rate if 0 balls)
        crr = df_work["current_run_rate_before"].to_numpy(dtype=float)
        p_runs_arr = ptnr_runs.to_numpy(dtype=float)
        p_balls_arr = ptnr_balls.to_numpy(dtype=float)

        ptnr_rr = np.divide(
            p_runs_arr * 6.0,
            p_balls_arr,
            out=crr.copy(),
            where=(p_balls_arr > 0),
        )

        df_work["partnership_runs_current"] = ptnr_runs
        df_work["partnership_balls_current"] = ptnr_balls
        df_work["partnership_run_rate"] = ptnr_rr

        return df_work
