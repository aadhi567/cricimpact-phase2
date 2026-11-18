"""Stage B7.5 Batter Threat & Strike-Starvation Engine."""

from __future__ import annotations

import numpy as np
import pandas as pd


class BatterThreatEngine:
    """Evaluates striker and non-striker threat multipliers and composite threat."""

    def __init__(
        self,
        w_striker: float = 0.60,
        w_non_striker: float = 0.40,
        starve_weight: float = 0.25,
    ) -> None:
        self.w_striker = w_striker
        self.w_non_striker = w_non_striker
        self.starve_weight = starve_weight

    def evaluate_batter_threat(
        self,
        abc_rating: float | np.ndarray,
        runs_current: float | np.ndarray,
        balls_current: float | np.ndarray,
    ) -> np.ndarray:
        """Compute individual batter dynamic threat multiplier.
        
        Blends historical quality (ABC) with match establishment and scoring velocity.
        """
        abc = np.asarray(abc_rating, dtype=float)
        runs = np.asarray(runs_current, dtype=float)
        balls = np.asarray(balls_current, dtype=float)

        # Baseline ABC multiplier (normalized around 1.0, typically in [0.60, 2.20])
        # If abc is NaN or 0, fallback to 1.00. If on 0-100 scale (e.g. > 10), divide by 50.0.
        abc_safe = np.where(np.isnan(abc) | (abc <= 0), 1.00, abc)
        abc_norm = np.where(abc_safe > 10.0, abc_safe / 50.0, abc_safe)
        q_factor = np.clip(abc_norm, 0.60, 2.20)

        # Establishment factor: batters with 15+ balls are established and more dangerous
        est_factor = 1.0 + 0.25 * np.clip(balls / 20.0, 0.0, 1.0)

        # Current match velocity: strike rate factor
        sr_current = np.divide(
            runs * 100.0,
            balls,
            out=np.full_like(balls, 125.0, dtype=float),
            where=(balls > 0),
        )
        vel_factor = np.clip(sr_current / 135.0, 0.60, 1.80)

        # Combined threat multiplier (bounded in [0.50, 2.50])
        threat = q_factor * (0.60 * est_factor + 0.40 * vel_factor)
        return np.clip(threat, 0.50, 2.50)

    def evaluate_composite_threat(
        self,
        striker_threat: np.ndarray | float,
        non_striker_threat: np.ndarray | float,
    ) -> tuple[np.ndarray, np.ndarray]:
        """Compute composite threat and non-striker strike-starvation multiplier.
        
        Returns:
            (phi_bat, starvation_mult)
        """
        s_threat = np.asarray(striker_threat, dtype=float)
        ns_threat = np.asarray(non_striker_threat, dtype=float)

        # Composite threat: 60% striker, 40% non-striker
        phi_bat = self.w_striker * s_threat + self.w_non_striker * ns_threat

        # Strike-starvation multiplier: rewards keeping an elite non-striker off strike
        # Starvation bonus applies when non-striker threat exceeds striker threat
        diff = np.maximum(0.0, ns_threat - s_threat)
        starvation_mult = 1.0 + self.starve_weight * np.clip(diff, 0.0, 1.5)

        return phi_bat, starvation_mult
