"""Stage B7.5 Bipolar Logistic Normalizer Module."""

from __future__ import annotations

import numpy as np
import pandas as pd

from ml.contribution.bowling_pressure.schema import (
    K_SIGMOID_SLOPE,
    PCS_SCALE_MAX,
    PCS_SCALE_MIN,
    PCS_SCALE_NEUTRAL,
    SIGMA_REF_1ST,
    SIGMA_REF_2ND,
)


class PCSNormalizer:
    """Transforms raw spell and stint pressure effects (RPE) into standardized 0-100 bipolar PCS."""

    def __init__(
        self,
        k_slope: float = K_SIGMOID_SLOPE,
        sigma_ref_1st: float = SIGMA_REF_1ST,
        sigma_ref_2nd: float = SIGMA_REF_2ND,
    ) -> None:
        self.k_slope = k_slope
        self.sigma_ref_1st = sigma_ref_1st
        self.sigma_ref_2nd = sigma_ref_2nd

    def normalize(
        self,
        rpe: float | np.ndarray | pd.Series,
        innings: int | np.ndarray | pd.Series = 1,
    ) -> np.ndarray:
        """Apply bipolar logistic transformation: PCS = 100 / (1 + exp(-k * z)).
        
        Guarantees:
            RPE = 0.0 -> PCS = 50.00 (Neutral Tour Par)
            RPE > 0.0 -> PCS in (50, 100]
            RPE < 0.0 -> PCS in [0, 50)
        """
        is_scalar = np.isscalar(rpe)
        rpe_arr = np.atleast_1d(np.asarray(rpe, dtype=float))
        inn_arr = np.atleast_1d(np.asarray(innings, dtype=int))
        if len(inn_arr) == 1 and len(rpe_arr) > 1:
            inn_arr = np.full_like(rpe_arr, inn_arr[0], dtype=int)

        sigma = np.where(inn_arr == 2, self.sigma_ref_2nd, self.sigma_ref_1st)
        z = rpe_arr / sigma

        # Logistic transformation with numerical clipping on logits
        z_clipped = np.clip(z, -8.0, 8.0)
        pcs = 100.0 / (1.0 + np.exp(-self.k_slope * z_clipped))
        pcs = np.clip(pcs, PCS_SCALE_MIN, PCS_SCALE_MAX)

        return pcs
