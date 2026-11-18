"""Stage B7.5 Partnership Threat Index (PTI) Engine."""

from __future__ import annotations

import numpy as np
import pandas as pd


class PartnershipThreatEngine:
    """Evaluates continuous partnership danger using scoring velocity, acceleration, and batter threat."""

    def __init__(self, min_stand_ramp: float = 15.0) -> None:
        self.min_stand_ramp = min_stand_ramp

    def evaluate_pti(
        self,
        partnership_runs: np.ndarray | pd.Series,
        partnership_run_rate: np.ndarray | pd.Series,
        reference_run_rate: np.ndarray | pd.Series,
        phi_acc: np.ndarray | pd.Series,
        phi_bat: np.ndarray | pd.Series,
    ) -> np.ndarray:
        """Compute Partnership Threat Index (PTI).
        
        Formula:
            PTI = Runs_ptnr * (RR_ptnr / RR_ref) * Phi_acc * Phi_bat * Ramp
        """
        p_runs = np.asarray(partnership_runs, dtype=float)
        p_rr = np.asarray(partnership_run_rate, dtype=float)
        r_rr = np.asarray(reference_run_rate, dtype=float)
        p_acc = np.asarray(phi_acc, dtype=float)
        p_bat = np.asarray(phi_bat, dtype=float)

        # Safe reference run rate: clip to avoid division by zero or extreme spikes
        r_safe = np.clip(r_rr, 5.0, 18.0)
        p_safe = np.clip(p_rr, 2.0, 24.0)

        # Velocity ratio: how fast the stand is scoring relative to required / expected trajectory
        vel_ratio = np.clip(p_safe / r_safe, 0.40, 2.50)

        # Small stand dampening ramp (< 15 runs)
        ramp = np.clip(p_runs / self.min_stand_ramp, 0.0, 1.0)

        raw_pti = p_runs * vel_ratio * p_acc * p_bat * ramp
        return np.maximum(0.0, raw_pti)
