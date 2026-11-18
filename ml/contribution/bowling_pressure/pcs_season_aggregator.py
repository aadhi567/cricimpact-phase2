"""Stage B7.5 Season Pressure Aggregator with Empirical Bayes Shrinkage."""

from __future__ import annotations

from typing import Any
import numpy as np
import pandas as pd

from ml.contribution.bowling_pressure.config import load_pcs_config
from ml.contribution.bowling_pressure.schema import M0_SHRINKAGE_BALLS, POPULATION_NEUTRAL_PCS


class PCSSeasonAggregator:
    """Aggregates match spells into season records with Empirical Bayes shrinkage (M0 = 48 balls)."""

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        self.config = config or load_pcs_config()
        self.m0_balls = float(self.config["parameters"].get("m0_shrinkage_balls", M0_SHRINKAGE_BALLS))
        self.prior_pcs = POPULATION_NEUTRAL_PCS

    def aggregate_seasons(self, spells_df: pd.DataFrame) -> pd.DataFrame:
        """Aggregate match spells into season summaries per bowler."""
        df = spells_df.copy()
        df["pcs_x_balls"] = df["pcs_spell"] * df["legal_balls"]

        grp = df.groupby(["season", "bowler_id"], as_index=False)

        seasons = grp.agg(
            matches=("match_id", "nunique"),
            spells=("match_id", "count"),
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
        balls_sum = seasons["legal_balls"].to_numpy(dtype=float)
        pcs_prod_sum = seasons["pcs_x_balls_sum"].to_numpy(dtype=float)
        weighted_mean = np.where(balls_sum > 0, pcs_prod_sum / balls_sum, seasons["raw_pcs_mean"].to_numpy(dtype=float))
        seasons["weighted_pcs_mean"] = weighted_mean
        seasons = seasons.drop(columns=["pcs_x_balls_sum"])

        # Standard metrics
        seasons["overs"] = (seasons["legal_balls"] // 6) + ((seasons["legal_balls"] % 6) / 10.0)
        seasons["economy"] = np.where(
            seasons["legal_balls"] > 0,
            (seasons["bowler_runs"] * 6.0) / seasons["legal_balls"],
            0.0,
        ).round(2)
        seasons["strike_rate"] = np.where(
            seasons["wickets"] > 0,
            seasons["legal_balls"] / seasons["wickets"],
            np.nan,
        ).round(1)

        # Empirical Bayes shrinkage based on legal balls (M0 = 48 legal balls = 8 overs = 2 spells)
        balls = seasons["legal_balls"].to_numpy(dtype=float)
        w = balls / (balls + self.m0_balls)
        shrunk_pcs = w * seasons["weighted_pcs_mean"].to_numpy(dtype=float) + (1.0 - w) * self.prior_pcs

        seasons["shrinkage_weight"] = w.round(3)
        seasons["pcs_season_raw"] = seasons["weighted_pcs_mean"].round(2)
        seasons["pcs_season_shrunk"] = shrunk_pcs.round(2)

        return seasons
