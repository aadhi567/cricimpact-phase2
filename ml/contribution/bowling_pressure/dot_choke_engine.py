"""Stage B7.5 Dot Choke Index (DCI) Engine."""

from __future__ import annotations

import numpy as np
import pandas as pd


class DotChokeEngine:
    """Evaluates dot-ball choke pressure, dot clustering, and non-striker starvation."""

    def __init__(
        self,
        base_dot_val: float = 0.75,
        cluster_weight: float = 0.35,
    ) -> None:
        self.base_dot_val = base_dot_val
        self.cluster_weight = cluster_weight

    def evaluate_dci(
        self,
        is_dot_ball: np.ndarray | pd.Series,
        dots_last_12: np.ndarray | pd.Series,
        leverage: np.ndarray | pd.Series,
        starvation_mult: np.ndarray | pd.Series,
    ) -> np.ndarray:
        """Compute delivery-level Dot Choke Index (DCI).
        
        Formula:
            DCI = [I(dot) * 0.75 + 0.35 * Dots_last_12] * Leverage * StarvationMult
            (Only awarded if current delivery is a dot ball)
        """
        dot = np.asarray(is_dot_ball, dtype=bool)
        dots_12 = np.asarray(dots_last_12, dtype=float)
        lev = np.asarray(leverage, dtype=float)
        starve = np.asarray(starvation_mult, dtype=float)

        # Cluster density component (capped at 12 dots)
        density = np.clip(dots_12 / 12.0, 0.0, 1.0)
        cluster_val = self.cluster_weight * density * 2.0  # Up to +0.70 runs for full 12 dots

        # Raw DCI
        raw_dci = (self.base_dot_val + cluster_val) * lev * starve

        # Zero if not a dot ball
        dci = np.where(dot, raw_dci, 0.0)
        return np.maximum(0.0, dci)
