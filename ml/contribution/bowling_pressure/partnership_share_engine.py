"""Stage B7.5 Individual Batter Partnership Contribution Share Engine."""

from __future__ import annotations

import numpy as np
import pandas as pd


class PartnershipShareEngine:
    """Evaluates individual batter run and velocity share within the active partnership."""

    def __init__(self, regularization_threshold: float = 15.0) -> None:
        self.regularization_threshold = regularization_threshold

    def evaluate_contribution_share(
        self,
        striker_runs_in_ptnr: np.ndarray | pd.Series,
        partnership_runs: np.ndarray | pd.Series,
    ) -> np.ndarray:
        """Calculate regularized striker contribution share in [0.0, 1.0].
        
        For small partnerships (< 15 runs), regularizes towards 0.50 to avoid
        extreme 100%/0% artifacts from small sample noise.
        """
        s_runs = np.asarray(striker_runs_in_ptnr, dtype=float)
        p_runs = np.asarray(partnership_runs, dtype=float)

        raw_share = np.divide(
            s_runs,
            p_runs,
            out=np.full_like(s_runs, 0.50),
            where=(p_runs > 0),
        )
        raw_share = np.clip(raw_share, 0.0, 1.0)

        # Linear shrinkage towards 0.50 when partnership runs < 15
        ramp = np.clip(p_runs / self.regularization_threshold, 0.0, 1.0)
        reg_share = (1.0 - ramp) * 0.50 + ramp * raw_share

        return np.clip(reg_share, 0.05, 0.95)
