"""Stage B7.5 First-Innings Dynamic Trajectory & EFS Pressure Engine."""

from __future__ import annotations

import numpy as np
import pandas as pd

from ml.contribution.bowling_pressure.causal_features import calculate_resource_percentage


class FirstInningsPressureEngine:
    """Evaluates dynamic Expected Final Score (EFS) trajectories and structural wicket loss."""

    def __init__(self, alpha_res: float = 0.55) -> None:
        self.alpha_res = alpha_res

    def predict_remaining_runs(
        self,
        balls_remaining: np.ndarray | float,
        wickets_remaining: np.ndarray | float,
        current_run_rate: np.ndarray | float,
        venue_avg_first_inn_score: np.ndarray | float,
    ) -> np.ndarray:
        """Calculate expected remaining runs via resource-adjusted baseline run rate."""
        b_rem = np.asarray(balls_remaining, dtype=float)
        w_rem = np.asarray(wickets_remaining, dtype=float)
        crr = np.asarray(current_run_rate, dtype=float)
        par = np.asarray(venue_avg_first_inn_score, dtype=float)

        # Baseline run rate: blend of current run rate and venue par
        par_rr = np.clip(par / 20.0, 6.0, 11.0)
        crr_safe = np.clip(crr, 4.0, 15.0)

        # Weight transitions from par-dominated early to CRR-dominated as innings progresses
        progress = np.clip((120.0 - b_rem) / 120.0, 0.0, 1.0)
        w_crr = 0.30 + 0.50 * progress
        rr_base = (1.0 - w_crr) * par_rr + w_crr * crr_safe

        # Compute resource percentage
        res_pct = np.array([
            calculate_resource_percentage(w, b) for w, b in zip(w_rem.ravel(), b_rem.ravel())
        ]).reshape(w_rem.shape)

        res_factor = np.power(np.clip(res_pct / 100.0, 0.0, 1.0), self.alpha_res)

        rem_runs = b_rem * (rr_base / 6.0) * res_factor
        return np.maximum(0.0, rem_runs)

    def evaluate_efs(
        self,
        score_before: np.ndarray | pd.Series,
        balls_remaining: np.ndarray | pd.Series,
        wickets_remaining: np.ndarray | pd.Series,
        current_run_rate: np.ndarray | pd.Series,
        venue_avg_first_inn_score: np.ndarray | pd.Series,
    ) -> tuple[np.ndarray, np.ndarray]:
        """Compute dynamic EFS and implied remaining required rate.
        
        Returns:
            (efs, rr_exp_rem)
        """
        score = np.asarray(score_before, dtype=float)
        b_rem = np.asarray(balls_remaining, dtype=float)
        w_rem = np.asarray(wickets_remaining, dtype=float)
        crr = np.asarray(current_run_rate, dtype=float)
        par = np.asarray(venue_avg_first_inn_score, dtype=float)

        rem_runs = self.predict_remaining_runs(b_rem, w_rem, crr, par)
        efs = score + rem_runs

        # Implied expected rate over remaining balls
        rr_exp_rem = np.where(b_rem > 0, (rem_runs / b_rem) * 6.0, crr)

        return efs, rr_exp_rem

    def evaluate_wicket_loss(
        self,
        score_before: np.ndarray | pd.Series,
        balls_remaining: np.ndarray | pd.Series,
        wickets_remaining: np.ndarray | pd.Series,
        current_run_rate: np.ndarray | pd.Series,
        venue_avg_first_inn_score: np.ndarray | pd.Series,
    ) -> np.ndarray:
        """Calculate structural expected runs drop from losing 1 wicket (Delta EFS_wkt)."""
        b_rem = np.asarray(balls_remaining, dtype=float)
        w_rem = np.asarray(wickets_remaining, dtype=float)
        crr = np.asarray(current_run_rate, dtype=float)
        par = np.asarray(venue_avg_first_inn_score, dtype=float)

        # Baseline remaining runs
        rem_before = self.predict_remaining_runs(b_rem, w_rem, crr, par)

        # Counterfactual remaining runs with (w_rem - 1)
        w_after = np.maximum(0.0, w_rem - 1.0)
        rem_after = self.predict_remaining_runs(b_rem, w_after, crr, par)

        delta_efs = rem_before - rem_after
        return np.maximum(0.0, delta_efs)
