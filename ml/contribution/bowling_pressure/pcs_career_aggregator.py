"""Stage B7.5 Career Pressure Aggregator with Empirical Bayes Shrinkage."""

from __future__ import annotations

from typing import Any
import numpy as np
import pandas as pd

from ml.contribution.bowling_pressure.config import load_pcs_config
from ml.contribution.bowling_pressure.schema import M0_SHRINKAGE_BALLS, POPULATION_NEUTRAL_PCS


class PCSCareerAggregator:
    """Aggregates match spells into career records with Empirical Bayes shrinkage (M0 = 48 balls)."""

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        self.config = config or load_pcs_config()
        self.m0_balls = float(self.config["parameters"].get("m0_shrinkage_balls", M0_SHRINKAGE_BALLS))
        self.prior_pcs = POPULATION_NEUTRAL_PCS

    def aggregate_career(self, spells_df: pd.DataFrame) -> pd.DataFrame:
        """Aggregate match spells into career summaries per bowler."""
        df = spells_df.copy()
        df["pcs_x_balls"] = df["pcs_spell"] * df["legal_balls"]

        grp = df.groupby("bowler_id", as_index=False)

        career = grp.agg(
            matches=("match_id", "nunique"),
            spells=("match_id", "count"),
            seasons_active=("season", "nunique"),
            legal_balls=("legal_balls", "sum"),
            bowler_runs=("bowler_runs", "sum"),
            wickets=("wickets", "sum"),
            dot_balls=("dot_balls", "sum"),
            boundaries=("boundaries", "sum"),
            mean_leverage=("mean_leverage", "mean"),
            total_rpe=("total_rpe", "sum"),
            raw_pcs_mean=("pcs_spell", "mean"),
            pcs_x_balls_sum=("pcs_x_balls", "sum"),
        )

        # Weighted PCS Mean across balls
        balls_sum = career["legal_balls"].to_numpy(dtype=float)
        pcs_prod_sum = career["pcs_x_balls_sum"].to_numpy(dtype=float)
        weighted_mean = np.where(balls_sum > 0, pcs_prod_sum / balls_sum, career["raw_pcs_mean"].to_numpy(dtype=float))
        career["weighted_pcs_mean"] = weighted_mean
        career = career.drop(columns=["pcs_x_balls_sum"])

        # Standard metrics
        career["overs"] = (career["legal_balls"] // 6) + ((career["legal_balls"] % 6) / 10.0)
        career["economy"] = np.where(
            career["legal_balls"] > 0,
            (career["bowler_runs"] * 6.0) / career["legal_balls"],
            0.0,
        ).round(2)
        career["strike_rate"] = np.where(
            career["wickets"] > 0,
            career["legal_balls"] / career["wickets"],
            np.nan,
        ).round(1)

        # Empirical Bayes shrinkage based on career legal balls (M0 = 48 legal balls)
        balls = career["legal_balls"].to_numpy(dtype=float)
        w = balls / (balls + self.m0_balls)
        shrunk_pcs = w * career["weighted_pcs_mean"].to_numpy(dtype=float) + (1.0 - w) * self.prior_pcs

        career["shrinkage_weight"] = w.round(3)
        career["pcs_career_raw"] = career["weighted_pcs_mean"].round(2)
        career["pcs_career_shrunk"] = shrunk_pcs.round(2)

        return career
