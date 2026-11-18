"""Stage B7.5 Partnership Acceleration Engine (12-Ball Primary, 18-Ball Diagnostic)."""

from __future__ import annotations

import numpy as np
import pandas as pd


class AccelerationEngine:
    """Evaluates short-window partnership scoring rate surges against base stand rate."""

    def __init__(
        self,
        primary_window: int = 12,
        sensitivity_window: int = 18,
        clip_lower: float = -0.30,
        clip_upper: float = 0.60,
    ) -> None:
        self.primary_window = primary_window
        self.sensitivity_window = sensitivity_window
        self.clip_lower = clip_lower
        self.clip_upper = clip_upper

    def evaluate_acceleration(
        self,
        runs_last_12: np.ndarray | pd.Series,
        runs_last_18: np.ndarray | pd.Series,
        partnership_run_rate: np.ndarray | pd.Series,
        legal_balls_in_stand: np.ndarray | pd.Series,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Compute primary acceleration factor (Phi_acc), Acc_12 RPO, and Acc_18 RPO.
        
        Returns:
            (phi_acc, acc_12_rpo, acc_18_rpo)
        """
        r12 = np.asarray(runs_last_12, dtype=float)
        r18 = np.asarray(runs_last_18, dtype=float)
        base_rr = np.asarray(partnership_run_rate, dtype=float)
        stand_balls = np.asarray(legal_balls_in_stand, dtype=float)

        # Implied run rates over recent windows (normalized to 6-ball RPO)
        rr_12 = (r12 / float(self.primary_window)) * 6.0
        rr_18 = (r18 / float(self.sensitivity_window)) * 6.0

        # Acceleration in RPO
        acc_12 = rr_12 - base_rr
        acc_18 = rr_18 - base_rr

        # Raw acceleration scaling
        acc_scale = acc_12 / 6.0
        phi_raw = 1.0 + np.clip(acc_scale, self.clip_lower, self.clip_upper)

        # Confidence ramp when partnership is very young (< 6 balls)
        young_ramp = np.clip(stand_balls / 6.0, 0.0, 1.0)
        phi_acc = (1.0 - young_ramp) * 1.00 + young_ramp * phi_raw

        return np.clip(phi_acc, 0.70, 1.60), acc_12, acc_18
