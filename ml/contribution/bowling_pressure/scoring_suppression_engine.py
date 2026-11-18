"""Stage B7.5 Scoring Rate Divergence & Suppression Engine."""

from __future__ import annotations

import numpy as np
import pandas as pd


class ScoringSuppressionEngine:
    """Evaluates multi-ball rate escalation (Sup) when batting teams fall behind pace."""

    def __init__(self) -> None:
        pass

    def evaluate_suppression(
        self,
        innings: np.ndarray | pd.Series,
        is_legal_delivery: np.ndarray | pd.Series,
        runs_conceded: np.ndarray | pd.Series,
        leverage: np.ndarray | pd.Series,
        required_run_rate_before: np.ndarray | pd.Series,
        legal_balls_remaining_before: np.ndarray | pd.Series,
        runs_required_before: np.ndarray | pd.Series,
    ) -> np.ndarray:
        """Compute delivery-level scoring suppression (Sup).
        
        In Innings 2, evaluates the required run rate climb when bowler concedes fewer
        runs than required to maintain the required rate.
        In Innings 1, evaluates containment relative to expected rate.
        """
        inn = np.asarray(innings, dtype=int)
        legal = np.asarray(is_legal_delivery, dtype=bool)
        runs = np.asarray(runs_conceded, dtype=float)
        lev = np.asarray(leverage, dtype=float)
        rrr_before = np.asarray(required_run_rate_before, dtype=float)
        b_rem = np.asarray(legal_balls_remaining_before, dtype=float)
        runs_req = np.asarray(runs_required_before, dtype=float)

        sup = np.zeros(len(inn), dtype=float)

        # Innings 2 Suppression: Required run rate escalation
        # If ball is legal, b_rem decreases by 1, and runs_req decreases by runs conceded.
        mask2 = (inn == 2) & legal & (b_rem > 1) & (runs_req > runs)
        if np.any(mask2):
            b_after = b_rem[mask2] - 1.0
            r_after = runs_req[mask2] - runs[mask2]
            rrr_after = (r_after / b_after) * 6.0
            delta_rrr = rrr_after - rrr_before[mask2]

            # Positive delta RRR means required rate escalated (bowler squeezed batting team)
            # Scaled so that +0.50 RPO climb = +1.0 run of pressure, capped at 2.50
            climb = np.clip(delta_rrr / 0.50, 0.0, 2.50)
            sup[mask2] = climb * lev[mask2]

        # Innings 1 Suppression: Delivery-level containment below par pace
        # If conceded 0 or 1 run on legal delivery, awards small trajectory suppression
        mask1 = (inn == 1) & legal & (runs <= 1.0)
        if np.any(mask1):
            contain_val = np.where(runs[mask1] == 0.0, 0.40, 0.15)
            sup[mask1] = contain_val * lev[mask1]

        return np.maximum(0.0, sup)
