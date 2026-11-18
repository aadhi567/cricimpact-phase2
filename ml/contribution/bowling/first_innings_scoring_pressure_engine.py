"""Stage B4 First-Innings Scoring Pressure Engine for Bowling Contribution Model."""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from ml.contribution.bowling.config import load_bowling_config


class FirstInningsScoringPressureEngine:
    """Evaluates run restriction and scoring containment in the first innings.

    Strictly returns NaN for second-innings deliveries where chase RRR applies instead.
    """

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        self.config = config or load_bowling_config()

    def evaluate_delivery(
        self,
        innings: int,
        exp_bowler_runs: float,
        bowler_runs: int,
        is_non_bowler_extra: bool = False,
    ) -> float | None:
        """Compute first innings scoring restriction for a single delivery.

        Returns:
            exp_bowler_runs - bowler_runs (or 0.0 if non-bowler extra).
            None if innings != 1.
        """
        if innings != 1:
            return None

        if is_non_bowler_extra:
            return 0.0

        return float(exp_bowler_runs - bowler_runs)

    def evaluate_dataframe(
        self,
        df: pd.DataFrame,
        exp_bowler_runs: pd.Series | np.ndarray,
        bowler_runs: pd.Series | np.ndarray,
        is_non_bowler_extra: pd.Series | np.ndarray,
    ) -> pd.Series:
        """Compute first innings scoring restriction across a dataframe.

        Returns:
            pd.Series with values for 1st innings deliveries and NaN for 2nd innings.
        """
        n = len(df)
        restriction = np.full(n, np.nan, dtype=float)

        inn = pd.to_numeric(df["innings"], errors="coerce").fillna(1).to_numpy(dtype=int)
        exp_r = np.asarray(exp_bowler_runs, dtype=float)
        b_runs = np.asarray(bowler_runs, dtype=int)
        nb_extra = np.asarray(is_non_bowler_extra, dtype=bool)

        mask1 = inn == 1
        res = np.where(nb_extra, 0.0, exp_r - b_runs)
        restriction = np.where(mask1, res, np.nan)

        return pd.Series(restriction, index=df.index, name="first_inns_scoring_restriction")
