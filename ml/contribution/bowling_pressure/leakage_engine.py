"""Stage B7.5 Run Leakage Penalty Engine."""

from __future__ import annotations

import numpy as np
import pandas as pd


class LeakageEngine:
    """Evaluates run leakage penalty when unexpected boundaries or extras relieve pressure."""

    def __init__(self, exp_runs_baseline: float = 1.25) -> None:
        self.exp_runs_baseline = exp_runs_baseline

    def evaluate_leakage(
        self,
        runs_conceded: np.ndarray | pd.Series,
        leverage: np.ndarray | pd.Series,
        exp_runs: np.ndarray | pd.Series | None = None,
    ) -> np.ndarray:
        """Compute delivery-level Run Leakage Penalty.
        
        Formula:
            Leakage = max(0, RunsConceded - ExpRuns) * Leverage
        """
        runs = np.asarray(runs_conceded, dtype=float)
        lev = np.asarray(leverage, dtype=float)

        if exp_runs is not None:
            baseline = np.asarray(exp_runs, dtype=float)
        else:
            baseline = np.full_like(runs, self.exp_runs_baseline)

        excess_runs = np.maximum(0.0, runs - baseline)
        leakage = excess_runs * lev
        return leakage
