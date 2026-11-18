"""Stage B7.5 Second-Innings Dynamic Chase Capacity & Margin Engine."""

from __future__ import annotations

import numpy as np
import pandas as pd

from ml.contribution.bowling_pressure.causal_features import calculate_resource_percentage


class SecondInningsPressureEngine:
    """Evaluates unconstrained chase capacity, chase margin (M_chase), and structural loss."""

    def __init__(self, alpha_res: float = 0.55) -> None:
        self.alpha_res = alpha_res

    def predict_unconstrained_chase_capacity(
        self,
        balls_remaining: np.ndarray | float,
        wickets_remaining: np.ndarray | float,
        current_run_rate: np.ndarray | float,
        required_run_rate: np.ndarray | float,
        runs_required: np.ndarray | float,
    ) -> np.ndarray:
        """Calculate unconstrained chase capacity without artificial target score truncation."""
        b_rem = np.asarray(balls_remaining, dtype=float)
        w_rem = np.asarray(wickets_remaining, dtype=float)
        crr = np.asarray(current_run_rate, dtype=float)
        rrr = np.asarray(required_run_rate, dtype=float)
        runs_req = np.asarray(runs_required, dtype=float)

        # Chase pace: balanced blend of required rate and current momentum
        crr_safe = np.clip(crr, 4.0, 16.0)
        rrr_safe = np.clip(rrr, 4.0, 24.0)
        rr_pace = 0.50 * crr_safe + 0.50 * rrr_safe

        # Compute resource percentage
        res_pct = np.array([
            calculate_resource_percentage(w, b) for w, b in zip(w_rem.ravel(), b_rem.ravel())
        ]).reshape(w_rem.shape)

        res_factor = np.power(np.clip(res_pct / 100.0, 0.0, 1.0), self.alpha_res)

        # Capacity is 0 if match already concluded (runs_req <= 0 or w_rem <= 0 or b_rem <= 0)
        unc_runs = b_rem * (rr_pace / 6.0) * res_factor
        unc_runs = np.where((runs_req <= 0) | (w_rem <= 0) | (b_rem <= 0), 0.0, unc_runs)

        return np.maximum(0.0, unc_runs)

    def evaluate_wicket_loss(
        self,
        balls_remaining: np.ndarray | pd.Series,
        wickets_remaining: np.ndarray | pd.Series,
        current_run_rate: np.ndarray | pd.Series,
        required_run_rate: np.ndarray | pd.Series,
        runs_required: np.ndarray | pd.Series,
    ) -> np.ndarray:
        """Calculate structural chase capacity drop from losing 1 wicket (Delta M_wkt)."""
        b_rem = np.asarray(balls_remaining, dtype=float)
        w_rem = np.asarray(wickets_remaining, dtype=float)
        crr = np.asarray(current_run_rate, dtype=float)
        rrr = np.asarray(required_run_rate, dtype=float)
        runs_req = np.asarray(runs_required, dtype=float)

        # Baseline capacity
        cap_before = self.predict_unconstrained_chase_capacity(b_rem, w_rem, crr, rrr, runs_req)

        # Counterfactual capacity with (w_rem - 1)
        w_after = np.maximum(0.0, w_rem - 1.0)
        cap_after = self.predict_unconstrained_chase_capacity(b_rem, w_after, crr, rrr, runs_req)

        delta_m = cap_before - cap_after
        return np.maximum(0.0, delta_m)
