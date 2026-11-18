"""Stage B7.5 Situational Wicket Importance (SWI) Engine."""

from __future__ import annotations

import numpy as np
import pandas as pd

from ml.contribution.bowling.wicket_value_engine import ContextWicketValueEngine


class SituationalWicketEngine:
    """Evaluates objective structural damage inflicted by bowler-credited dismissals."""

    def __init__(self, alpha_res: float = 0.55) -> None:
        self.alpha_res = alpha_res
        self.wkt_value_engine = ContextWicketValueEngine()

    def evaluate_swi(
        self,
        innings: np.ndarray | pd.Series,
        is_bowler_wicket: np.ndarray | pd.Series,
        leverage: np.ndarray | pd.Series,
        score_before: np.ndarray | pd.Series,
        balls_remaining: np.ndarray | pd.Series,
        wickets_remaining: np.ndarray | pd.Series,
        current_run_rate: np.ndarray | pd.Series,
        required_run_rate: np.ndarray | pd.Series,
        runs_required: np.ndarray | pd.Series,
        venue_avg_first_inn_score: np.ndarray | pd.Series,
        v_wkt: np.ndarray | pd.Series | None = None,
        overid: np.ndarray | pd.Series | None = None,
        wickets_lost_before: np.ndarray | pd.Series | None = None,
        partnership_run_rate: np.ndarray | pd.Series | None = None,
    ) -> np.ndarray:
        """Compute delivery-level Situational Wicket Importance (SWI).
        
        Formula:
            SWI_1st = Delta EFS_wkt * Leverage
            SWI_2nd = Delta M_wkt * Leverage
        """
        inn = np.asarray(innings, dtype=int)
        is_bwkt = np.asarray(is_bowler_wicket, dtype=bool)
        lev = np.asarray(leverage, dtype=float)
        b_rem = np.asarray(balls_remaining, dtype=float)
        runs_req = np.asarray(runs_required, dtype=float)
        rrr = np.asarray(required_run_rate, dtype=float)
        par = np.asarray(venue_avg_first_inn_score, dtype=float)
        par_rr = np.clip(par / 20.0, 6.0, 11.0)

        # Retrieve base physical wicket run drop V_wkt
        if v_wkt is not None:
            base_v_wkt = np.asarray(v_wkt, dtype=float)
        else:
            ov = np.asarray(overid, dtype=int) if overid is not None else np.clip((120 - b_rem) // 6 + 1, 1, 20).astype(int)
            w_lost = np.asarray(wickets_lost_before, dtype=int) if wickets_lost_before is not None else (10 - np.asarray(wickets_remaining, dtype=int))
            base_v_wkt = np.array([
                self.wkt_value_engine.get_wicket_value(int(o), int(w))
                for o, w in zip(ov, w_lost)
            ])

        # Stand run rate adjustment factor
        if partnership_run_rate is not None:
            ptnr_rr = np.asarray(partnership_run_rate, dtype=float)
        else:
            ptnr_rr = np.asarray(current_run_rate, dtype=float)

        swi = np.zeros(len(inn), dtype=float)

        # Innings 1 evaluation: Delta EFS_wkt = V_wkt * StandVelocityAdjustment
        mask1 = (inn == 1) & is_bwkt
        if np.any(mask1):
            vel_diff = ptnr_rr[mask1] - par_rr[mask1]
            stand_factor = 1.0 + 0.15 * np.clip(vel_diff / 6.0, -0.30, 0.60)
            delta_efs = base_v_wkt[mask1] * stand_factor
            swi[mask1] = delta_efs * lev[mask1]

        # Innings 2 evaluation: Delta M_wkt = V_wkt * ChaseUrgency * StandVelocityAdjustment
        # If runs_required <= 0, target already reached -> 0.0
        mask2 = (inn == 2) & is_bwkt & (runs_req > 0)
        if np.any(mask2):
            urgency = 0.75 + 0.25 * np.clip(rrr[mask2] / 8.0, 0.50, 2.00)
            vel_diff2 = ptnr_rr[mask2] - np.clip(rrr[mask2], 6.0, 16.0)
            stand_factor2 = 1.0 + 0.15 * np.clip(vel_diff2 / 6.0, -0.30, 0.60)
            delta_m = base_v_wkt[mask2] * urgency * stand_factor2
            swi[mask2] = delta_m * lev[mask2]

        return np.maximum(0.0, swi)
