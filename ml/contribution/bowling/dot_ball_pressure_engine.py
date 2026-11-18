"""Stage B4 Dot-Ball Pressure Engine for Bowling Contribution Model."""
from __future__ import annotations

from typing import Any, Final

import numpy as np
import pandas as pd

from ml.contribution.bowling.config import load_bowling_config

# Baseline empirical dot probabilities conditioned on (innings, phase)
EMPIRICAL_DOT_PROBS: Final[dict[tuple[int, str], float]] = {
    (1, "powerplay"): 0.4594,
    (1, "middle"): 0.3124,
    (1, "death"): 0.2825,
    (2, "powerplay"): 0.4605,
    (2, "middle"): 0.3207,
    (2, "death"): 0.3236,
}
GLOBAL_DOT_PROB: Final[float] = 0.3575


class DotBallPressureEngine:
    """Evaluates dot-ball occurrences, sequential dot pressure, and residuals."""

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        self.config = config or load_bowling_config()
        self.empirical_dot_probs = EMPIRICAL_DOT_PROBS
        self.global_dot_prob = GLOBAL_DOT_PROB

    def get_expected_dot_prob(self, innings: int, phase: str) -> float:
        """Look up expected dot probability for given innings and phase."""
        key = (innings, str(phase).lower())
        return self.empirical_dot_probs.get(key, self.global_dot_prob)

    def evaluate_delivery(
        self,
        is_legal: bool,
        bowler_runs: int,
        is_non_bowler_extra: bool,
        consecutive_dots_before: int,
        innings: int,
        phase: str,
    ) -> tuple[bool, float, float, int, float]:
        """Compute dot ball status, residual, updated consecutive dots, and pressure index for a single ball.

        Returns:
            (is_dot, exp_dot_prob, dot_residual, consecutive_dots_after, dot_pressure_index)
        """
        # Under standard rules, a dot is a legal delivery with 0 bowler runs
        # Non-bowler extras (e.g. byes/leg-byes) without bowler runs are not genuine bowler dots
        is_dot = bool(is_legal and (bowler_runs == 0) and not is_non_bowler_extra)

        exp_prob = self.get_expected_dot_prob(innings, phase)
        residual = (1.0 if is_dot else 0.0) - exp_prob

        consecutive_after = (consecutive_dots_before + 1) if is_dot else 0
        pressure_index = consecutive_after * (1.0 - exp_prob)

        return is_dot, exp_prob, residual, consecutive_after, pressure_index

    def evaluate_dataframe(
        self, df: pd.DataFrame
    ) -> tuple[pd.Series, pd.Series, pd.Series, pd.Series, pd.Series, pd.Series]:
        """Process an entire dataframe to causally track consecutive dots and compute diagnostics.

        Assumes dataframe is sorted or will be grouped by match_id and bowler_id.
        Returns:
            (dot_ball, exp_dot_prob, dot_residual, consecutive_dots_before, consecutive_dots_after, dot_pressure_index)
        """
        n = len(df)
        dot_ball = np.zeros(n, dtype=bool)
        exp_dot_prob = np.zeros(n, dtype=float)
        dot_residual = np.zeros(n, dtype=float)
        dots_before = np.zeros(n, dtype=int)
        dots_after = np.zeros(n, dtype=int)
        pressure_idx = np.zeros(n, dtype=float)

        # Precompute is_dot and exp_prob
        is_legal = df["is_legal_delivery"].to_numpy(dtype=bool)
        bowler_runs = df["bowler_runs"].to_numpy(dtype=int) if "bowler_runs" in df else np.zeros(n, dtype=int)
        
        # Check non_bowler_extra
        if "is_non_bowler_extra" in df:
            non_bowler_extra = df["is_non_bowler_extra"].to_numpy(dtype=bool)
        elif "extras_type" in df:
            non_bowler_extra = df["extras_type"].isin(["byes", "legbyes", "Penalty"]).to_numpy(dtype=bool)
        else:
            non_bowler_extra = np.zeros(n, dtype=bool)

        dots = is_legal & (bowler_runs == 0) & (~non_bowler_extra)
        dot_ball[:] = dots

        inns = pd.to_numeric(df["innings"], errors="coerce").fillna(1).to_numpy(dtype=int)
        phases = df["innings_phase"].fillna("middle").astype(str).str.lower().to_numpy()

        for i in range(n):
            key = (inns[i], phases[i])
            exp_dot_prob[i] = self.empirical_dot_probs.get(key, self.global_dot_prob)

        dot_residual[:] = dot_ball.astype(float) - exp_dot_prob

        # Group-wise causal sequential tracking by (match_id, bowler_id)
        # Note: preserve original order
        match_ids = df["match_id"].to_numpy()
        bowler_ids = df["bowler_id"].to_numpy()

        # Track consecutive dots per bowler within match
        tracker: dict[tuple[Any, Any], int] = {}
        for i in range(n):
            key = (match_ids[i], bowler_ids[i])
            current_streak = tracker.get(key, 0)
            dots_before[i] = current_streak
            if dots[i]:
                new_streak = current_streak + 1
            else:
                new_streak = 0
            dots_after[i] = new_streak
            tracker[key] = new_streak
            pressure_idx[i] = new_streak * (1.0 - exp_dot_prob[i])

        idx = df.index
        return (
            pd.Series(dot_ball, index=idx, name="dot_ball"),
            pd.Series(exp_dot_prob, index=idx, name="exp_dot_prob"),
            pd.Series(dot_residual, index=idx, name="dot_residual"),
            pd.Series(dots_before, index=idx, name="consecutive_dots_before"),
            pd.Series(dots_after, index=idx, name="consecutive_dots_after"),
            pd.Series(pressure_idx, index=idx, name="dot_pressure_index"),
        )
