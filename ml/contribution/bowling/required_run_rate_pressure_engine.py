"""Stage B4 Required Run Rate Pressure Engine for Bowling Contribution Model."""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from ml.contribution.bowling.config import load_bowling_config


class RequiredRunRatePressureEngine:
    """Evaluates chase RRR dynamics, bowler running economy, and RRR pressure indices.

    Strictly returns NaN for first innings deliveries as RRR does not exist.
    """

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        self.config = config or load_bowling_config()

    def evaluate_delivery(
        self,
        innings: int,
        required_run_rate: float | None,
        bowler_cum_runs: int,
        bowler_cum_legal_balls: int,
    ) -> tuple[float | None, float | None, float | None]:
        """Compute RRR pressure diagnostics for a single delivery.

        Returns:
            (rrr_before, bowler_econ_current, rrr_pressure_index)
            All are None if innings != 2 or RRR is undefined.
        """
        if innings != 2 or required_run_rate is None or pd.isna(required_run_rate):
            return None, None, None

        rrr = float(required_run_rate)
        if bowler_cum_legal_balls > 0:
            bowler_econ = (bowler_cum_runs * 6.0) / bowler_cum_legal_balls
        else:
            # Baseline expectation before bowling first ball
            bowler_econ = 8.0

        pressure_index = float(np.clip(rrr - bowler_econ, -10.0, 15.0))
        return rrr, bowler_econ, pressure_index

    def evaluate_dataframe(
        self, df: pd.DataFrame
    ) -> tuple[pd.Series, pd.Series, pd.Series]:
        """Compute chase RRR pressure diagnostics across a dataframe.

        Returns:
            (rrr_before, bowler_econ_current, rrr_pressure_index)
            Values are NaN for 1st innings rows.
        """
        n = len(df)
        rrr_before = np.full(n, np.nan, dtype=float)
        bowler_econ = np.full(n, np.nan, dtype=float)
        pressure_idx = np.full(n, np.nan, dtype=float)

        inn = pd.to_numeric(df["innings"], errors="coerce").fillna(1).to_numpy(dtype=int)
        raw_rrr = pd.to_numeric(df.get("required_run_rate", pd.Series(np.nan, index=df.index)), errors="coerce").to_numpy(dtype=float)

        # We also compute causal cumulative bowler runs and legal balls per match and bowler
        match_ids = df["match_id"].to_numpy()
        bowler_ids = df["bowler_id"].to_numpy()
        is_legal = df["is_legal_delivery"].to_numpy(dtype=bool)
        bowler_runs = df["bowler_runs"].to_numpy(dtype=int) if "bowler_runs" in df else np.zeros(n, dtype=int)

        # Causal tracker per (match_id, bowler_id)
        runs_tracker: dict[tuple[Any, Any], int] = {}
        balls_tracker: dict[tuple[Any, Any], int] = {}

        for i in range(n):
            if inn[i] == 2 and not np.isnan(raw_rrr[i]):
                key = (match_ids[i], bowler_ids[i])
                cum_runs = runs_tracker.get(key, 0)
                cum_balls = balls_tracker.get(key, 0)

                rrr_before[i] = raw_rrr[i]
                if cum_balls > 0:
                    econ = (cum_runs * 6.0) / cum_balls
                else:
                    econ = 8.0
                bowler_econ[i] = econ
                pressure_idx[i] = np.clip(raw_rrr[i] - econ, -10.0, 15.0)

            # Update running totals after recording pre-delivery state
            key = (match_ids[i], bowler_ids[i])
            runs_tracker[key] = runs_tracker.get(key, 0) + bowler_runs[i]
            if is_legal[i]:
                balls_tracker[key] = balls_tracker.get(key, 0) + 1

        idx = df.index
        return (
            pd.Series(rrr_before, index=idx, name="rrr_before"),
            pd.Series(bowler_econ, index=idx, name="bowler_econ_current"),
            pd.Series(pressure_idx, index=idx, name="rrr_pressure_index"),
        )
