"""Stage B4 Match Leverage Engine for Bowling Contribution Model."""
from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd

from ml.contribution.bowling.config import load_bowling_config


class MatchLeverageEngine:
    """Computes bounded, context-normalized match leverage multipliers."""

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        cfg = config or load_bowling_config()
        params = cfg.get("parameters", {})
        self.normalizer: float = float(params.get("leverage_normalizer", 1.1199))
        self.min_leverage: float = float(params.get("leverage_min", 0.50))
        self.max_leverage: float = float(params.get("leverage_max", 2.00))

    def evaluate_delivery(
        self,
        innings: int,
        phase: str,
        wickets_lost_before: int,
        required_run_rate: float | None = None,
        legal_balls_remaining_before: int | None = None,
    ) -> float:
        """Calculate the calibrated match leverage multiplier for a single delivery."""
        phase_str = str(phase).lower()
        wkts = float(wickets_lost_before)

        if innings == 2:
            if (
                required_run_rate is None
                or pd.isna(required_run_rate)
                or legal_balls_remaining_before is None
                or legal_balls_remaining_before <= 0
            ):
                return self.min_leverage

            rrr = float(required_run_rate)
            closeness = math.exp(-0.5 * ((rrr - 9.0) / 4.0) ** 2)
            phase_mult = 1.40 if phase_str == "death" else (1.00 if phase_str == "middle" else 0.85)
            wkt_factor = 1.0 + 0.08 * max(0.0, wkts - 3.0)
            raw = closeness * phase_mult * wkt_factor * 1.50
        else:
            phase_mult = 1.30 if phase_str == "death" else (0.95 if phase_str == "middle" else 1.10)
            wkt_factor = 1.0 + 0.05 * wkts
            raw = phase_mult * wkt_factor * 0.90

        leverage = raw / self.normalizer
        return float(np.clip(leverage, self.min_leverage, self.max_leverage))

    def evaluate_dataframe(self, df: pd.DataFrame) -> np.ndarray:
        """Vectorized computation of match leverage multiplier across delivery dataframe."""
        inn = pd.to_numeric(df["innings"], errors="coerce").fillna(1).to_numpy(dtype=int)
        phase = df["innings_phase"].fillna("middle").astype(str).str.lower().to_numpy()
        wkts = pd.to_numeric(df["wickets_lost_before"], errors="coerce").fillna(0).to_numpy(dtype=float)

        rrr_series = pd.to_numeric(df.get("required_run_rate", pd.Series(np.nan, index=df.index)), errors="coerce")
        rrr = rrr_series.to_numpy(dtype=float)

        rem_balls_series = pd.to_numeric(
            df.get("legal_balls_remaining_before", pd.Series(0, index=df.index)), errors="coerce"
        ).fillna(0)
        rem_balls = rem_balls_series.to_numpy(dtype=float)

        mask2 = inn == 2
        valid2 = mask2 & (~rrr_series.isna().to_numpy()) & (rem_balls > 0)

        # Innings 2 calculation
        rrr_clean = np.where(valid2, rrr, 9.0)
        closeness = np.exp(-0.5 * ((rrr_clean - 9.0) / 4.0) ** 2)
        phase2 = np.where(phase == "death", 1.40, np.where(phase == "middle", 1.00, 0.85))
        wkt2 = 1.0 + 0.08 * np.maximum(0.0, wkts - 3.0)
        raw2 = np.where(valid2, closeness * phase2 * wkt2 * 1.50, self.min_leverage * self.normalizer)

        # Innings 1 calculation
        phase1 = np.where(phase == "death", 1.30, np.where(phase == "middle", 0.95, 1.10))
        wkt1 = 1.0 + 0.05 * wkts
        raw1 = phase1 * wkt1 * 0.90

        raw = np.where(mask2, raw2, raw1)
        return np.clip(raw / self.normalizer, self.min_leverage, self.max_leverage)
