"""Stage B4 Bowler Win Probability Added (bWPA) Engine."""
from __future__ import annotations

import gzip
import pickle
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from ml.contribution.bowling.config import load_bowling_config
from ml.contribution.bowling.schema import BOWLER_CREDITED_DISMISSALS, NON_BOWLER_EXTRAS


class _SafeStringArray(pd.arrays.StringArray):
    """Custom StringArray unpickler shim for pandas cross-version compatibility."""

    def __setstate__(self, state: Any) -> None:
        if isinstance(state, tuple) and len(state) == 2:
            super().__init__(state[1])
            return
        super().__setstate__(state)


def _patched_unpickle(cls: Any, magic: Any, state: Any) -> Any:
    if cls == pd.arrays.StringArray:
        return _SafeStringArray.__new__(_SafeStringArray)
    return object.__new__(cls)


class _CustomUnpickler(pickle.Unpickler):
    def find_class(self, module: str, name: str) -> Any:
        if name == "__pyx_unpickle_NDArrayBacked":
            return _patched_unpickle
        return super().find_class(module, name)


class BowlerWinProbabilityAddedEngine:
    """Computes delivery-level Bowler Win Probability Added (bWPA).

    Calculates:
        Delta WP_bowl = P(bowl_win | S_t+1) - P(bowl_win | S_t)
                     = P(bat_win | S_t) - P(bat_win | S_t+1)
        bWPA = alpha_attr * Delta WP_bowl

    Attribution filter:
        alpha_attr = 1.0 for bowler deliveries and bowler credited dismissals
        alpha_attr = 0.0 for pure non-bowler extras (byes/leg-byes) and non-bowler wickets (run-outs)

    CRITICAL INVARIANT:
        bWPA is strictly evaluated in probability space and is NEVER added to BCS.
    """

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        self.config = config or load_bowling_config()
        self.calibrated_cache: pd.DataFrame | None = None

    def load_calibrated_probabilities(
        self, base_dir: Path | str | None = None
    ) -> pd.DataFrame:
        """Load and concatenate the three frozen calibrated probability sets."""
        if self.calibrated_cache is not None:
            return self.calibrated_cache

        cfg_paths = self.config.get("paths", {})
        cal_dir = Path(base_dir) if base_dir else Path(cfg_paths.get("calibrated_predictions_dir", "data/processed/calibration"))

        splits = [
            "train_2022_2024_oof",
            "val_2025",
            "test_2026",
        ]
        dfs = []
        for name in splits:
            file_path = cal_dir / f"{name}_calibrated_predictions_v1.pkl.gz"
            if not file_path.exists():
                raise FileNotFoundError(f"Calibrated predictions file missing: {file_path}")
            with gzip.open(file_path, "rb") as f:
                dfs.append(_CustomUnpickler(f).load())

        combined = pd.concat(dfs, ignore_index=True)
        # Select key columns
        cols = [
            "match_id",
            "innings",
            "innings_ball_num",
            "calibrated_probability",
            "target_batting_team_win",
        ]
        available_cols = [c for c in cols if c in combined.columns]
        self.calibrated_cache = combined[available_cols].copy()
        return self.calibrated_cache

    def evaluate_delivery(
        self,
        p_bat_current: float,
        p_bat_next: float,
        alpha_attr: float = 1.0,
    ) -> tuple[float, float]:
        """Compute delta WP and bWPA for a single delivery.

        Returns:
            (bwpa, delta_wp_bowl)
        """
        delta_wp_bowl = float(p_bat_current - p_bat_next)
        bwpa = float(alpha_attr * delta_wp_bowl)
        return bwpa, delta_wp_bowl

    def evaluate_dataframe(
        self,
        df: pd.DataFrame,
        cal_df: pd.DataFrame | None = None,
    ) -> tuple[pd.Series, pd.Series]:
        """Compute delivery-level bWPA and Delta WP_bowl across dataframe.

        Returns:
            (bwpa_series, delta_wp_bowl_series)
        """
        if "calibrated_probability" not in df.columns:
            if cal_df is None:
                cal_df = self.load_calibrated_probabilities()
            merged = pd.merge(
                df,
                cal_df[["match_id", "innings", "innings_ball_num", "calibrated_probability"]],
                on=["match_id", "innings", "innings_ball_num"],
                how="left",
            )
        else:
            merged = df.copy()

        # Compute next ball probability within each match and innings
        # Preserve original index for output series
        original_idx = df.index
        temp_df = merged[["match_id", "innings", "innings_ball_num", "calibrated_probability"]].copy()
        temp_df["orig_order"] = np.arange(len(temp_df))
        temp_df = temp_df.sort_values(["match_id", "innings", "innings_ball_num"]).reset_index(drop=True)

        next_p = temp_df.groupby(["match_id", "innings"])["calibrated_probability"].shift(-1)

        # Handle terminal delivery in 2nd innings
        inn2_last = (temp_df["innings"] == 2) & next_p.isna()
        if "target_batting_team_win" in df.columns:
            target_win = pd.to_numeric(
                temp_df.get("target_batting_team_win", pd.Series(0, index=temp_df.index)), errors="coerce"
            ).fillna(0).to_numpy(dtype=float)
            next_p = np.where(inn2_last, target_win, next_p)
        else:
            # Fallback if target_win is not present: use current prob so delta is 0
            next_p = np.where(inn2_last, temp_df["calibrated_probability"], next_p)

        # Handle terminal delivery in 1st innings
        next_p = np.where(pd.isna(next_p), temp_df["calibrated_probability"], next_p)

        delta_wp_bowl_sorted = temp_df["calibrated_probability"].to_numpy(dtype=float) - next_p.astype(float)

        # Re-sort to original order
        sort_back_idx = np.empty_like(temp_df["orig_order"].values)
        sort_back_idx[temp_df["orig_order"].values] = np.arange(len(temp_df))
        delta_wp_bowl = delta_wp_bowl_sorted[sort_back_idx]

        # Attribution factor
        if "alpha_attr" in df.columns:
            alpha = df["alpha_attr"].to_numpy(dtype=float)
        else:
            is_non_bowler_extra = df["extras_type"].isin(NON_BOWLER_EXTRAS).to_numpy(dtype=bool)
            canonical_dismissal = (
                df["dismissal_type_canonical"].fillna("").astype(str).str.strip().str.lower().to_numpy()
            )
            is_wkt = df["is_wicket_event"].to_numpy(dtype=bool)
            bowler_credited_lower = [d.lower() for d in BOWLER_CREDITED_DISMISSALS]
            is_bowler_wkt = is_wkt & np.isin(canonical_dismissal, bowler_credited_lower)
            is_non_bowler_wkt = is_wkt & (~is_bowler_wkt)
            alpha = np.where(is_non_bowler_extra | is_non_bowler_wkt, 0.0, 1.0)

        bwpa = alpha * delta_wp_bowl

        return (
            pd.Series(bwpa, index=original_idx, name="bwpa"),
            pd.Series(delta_wp_bowl, index=original_idx, name="delta_wp_bowl"),
        )
