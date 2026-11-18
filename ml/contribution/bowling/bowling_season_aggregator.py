"""Stage B4 Bowling Career and Season Aggregator with Empirical Bayes Shrinkage."""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from ml.contribution.bowling.config import load_bowling_config


class BowlingCareerSeasonAggregator:
    """Aggregates bowler match spells into Career and Season summaries.

    Applies Empirical Bayes shrinkage (M0 = 48 balls / 8 overs) to stabilize
    small-sample rate estimates and prevent short-sample flukes from dominating leaderboards.
    """

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        self.config = config or load_bowling_config()
        params = self.config.get("parameters", {})
        self.m0_shrinkage: float = float(params.get("career_season_shrinkage_m0", 48.0))

    def aggregate_career(self, spells_df: pd.DataFrame) -> pd.DataFrame:
        """Aggregate match spells into career records per bowler."""
        grp = spells_df.groupby("bowler_id", as_index=False)
        career = grp.agg(
            bowler_name=("bowler_name", "first"),
            matches=("match_id", "nunique"),
            spells=("match_id", "count"),
            legal_balls=("legal_balls", "sum"),
            bowler_runs=("bowler_runs", "sum"),
            wickets=("wickets", "sum"),
            maidens=("maidens", "sum"),
            dot_balls=("dot_balls", "sum"),
            boundaries=("boundaries", "sum"),
            total_erp=("total_erp", "sum"),
            total_bcs=("total_bcs", "sum"),
            total_bwpa=("total_bwpa", "sum"),
            mean_leverage=("mean_leverage", "mean"),
            mean_wqm=("mean_wqm", lambda s: float(s.mean())),
            first_inns_restriction=("first_inns_restriction", "sum"),
        )

        # Overs notation
        complete_overs = career["legal_balls"] // 6
        partial_balls = career["legal_balls"] % 6
        career["overs"] = complete_overs + (partial_balls / 10.0)

        # Standard metrics
        career["economy"] = np.where(
            career["legal_balls"] > 0,
            (career["bowler_runs"] * 6.0) / career["legal_balls"],
            0.0,
        )
        career["dot_pct"] = np.where(
            career["legal_balls"] > 0,
            (career["dot_balls"] / career["legal_balls"]) * 100.0,
            0.0,
        )
        career["boundary_pct"] = np.where(
            career["legal_balls"] > 0,
            (career["boundaries"] / career["legal_balls"]) * 100.0,
            0.0,
        )
        career["strike_rate"] = np.where(
            career["wickets"] > 0,
            career["legal_balls"] / career["wickets"],
            np.nan,
        )
        career["bowling_average"] = np.where(
            career["wickets"] > 0,
            career["bowler_runs"] / career["wickets"],
            np.nan,
        )

        # Empirical Bayes shrinkage on BCS per ball
        total_pop_bcs = career["total_bcs"].sum()
        total_pop_balls = career["legal_balls"].sum()
        pop_mean_rate = total_pop_bcs / total_pop_balls if total_pop_balls > 0 else 0.0

        balls = career["legal_balls"].to_numpy(dtype=float)
        bcs = career["total_bcs"].to_numpy(dtype=float)
        sample_rate = np.where(balls > 0, bcs / balls, 0.0)

        shrunk_rate = (balls / (balls + self.m0_shrinkage)) * sample_rate + (
            self.m0_shrinkage / (balls + self.m0_shrinkage)
        ) * pop_mean_rate

        career["bcs_per_over"] = (sample_rate * 6.0).round(2)
        career["shrunk_bcs_per_over"] = (shrunk_rate * 6.0).round(2)
        career["total_bcs_shrunk"] = (shrunk_rate * balls).round(2)

        # Rounding
        career["economy"] = career["economy"].round(2)
        career["dot_pct"] = career["dot_pct"].round(1)
        career["boundary_pct"] = career["boundary_pct"].round(1)
        career["strike_rate"] = career["strike_rate"].round(1)
        career["bowling_average"] = career["bowling_average"].round(2)
        career["total_erp"] = career["total_erp"].round(2)
        career["total_bcs"] = career["total_bcs"].round(2)
        career["total_bwpa"] = career["total_bwpa"].round(4)
        career["mean_leverage"] = career["mean_leverage"].round(3)
        career["mean_wqm"] = career["mean_wqm"].round(3)
        career["first_inns_restriction"] = career["first_inns_restriction"].round(2)

        # Rank by total_bcs_shrunk descending
        career = career.sort_values("total_bcs_shrunk", ascending=False).reset_index(drop=True)
        career["rank"] = career.index + 1

        return career

    def aggregate_season(self, spells_df: pd.DataFrame) -> pd.DataFrame:
        """Aggregate match spells into season records per bowler and season."""
        grp = spells_df.groupby(["season", "bowler_id"], as_index=False)
        season_df = grp.agg(
            bowler_name=("bowler_name", "first"),
            matches=("match_id", "nunique"),
            spells=("match_id", "count"),
            legal_balls=("legal_balls", "sum"),
            bowler_runs=("bowler_runs", "sum"),
            wickets=("wickets", "sum"),
            maidens=("maidens", "sum"),
            dot_balls=("dot_balls", "sum"),
            boundaries=("boundaries", "sum"),
            total_erp=("total_erp", "sum"),
            total_bcs=("total_bcs", "sum"),
            total_bwpa=("total_bwpa", "sum"),
            mean_leverage=("mean_leverage", "mean"),
            mean_wqm=("mean_wqm", lambda s: float(s.mean())),
            first_inns_restriction=("first_inns_restriction", "sum"),
        )

        # Overs notation
        complete_overs = season_df["legal_balls"] // 6
        partial_balls = season_df["legal_balls"] % 6
        season_df["overs"] = complete_overs + (partial_balls / 10.0)

        # Standard metrics
        season_df["economy"] = np.where(
            season_df["legal_balls"] > 0,
            (season_df["bowler_runs"] * 6.0) / season_df["legal_balls"],
            0.0,
        )
        season_df["dot_pct"] = np.where(
            season_df["legal_balls"] > 0,
            (season_df["dot_balls"] / season_df["legal_balls"]) * 100.0,
            0.0,
        )
        season_df["boundary_pct"] = np.where(
            season_df["legal_balls"] > 0,
            (season_df["boundaries"] / season_df["legal_balls"]) * 100.0,
            0.0,
        )
        season_df["strike_rate"] = np.where(
            season_df["wickets"] > 0,
            season_df["legal_balls"] / season_df["wickets"],
            np.nan,
        )
        season_df["bowling_average"] = np.where(
            season_df["wickets"] > 0,
            season_df["bowler_runs"] / season_df["wickets"],
            np.nan,
        )

        # Empirical Bayes shrinkage per season
        shrunk_totals = np.zeros(len(season_df), dtype=float)
        shrunk_rates = np.zeros(len(season_df), dtype=float)
        raw_rates = np.zeros(len(season_df), dtype=float)

        for s_val in season_df["season"].unique():
            s_mask = (season_df["season"] == s_val).values
            s_bcs = season_df.loc[s_mask, "total_bcs"].values.astype(float)
            s_balls = season_df.loc[s_mask, "legal_balls"].values.astype(float)

            tot_bcs = s_bcs.sum()
            tot_balls = s_balls.sum()
            pop_rate = tot_bcs / tot_balls if tot_balls > 0 else 0.0

            sample_rate = np.where(s_balls > 0, s_bcs / s_balls, 0.0)
            shrunk_r = (s_balls / (s_balls + self.m0_shrinkage)) * sample_rate + (
                self.m0_shrinkage / (s_balls + self.m0_shrinkage)
            ) * pop_rate

            raw_rates[s_mask] = sample_rate * 6.0
            shrunk_rates[s_mask] = shrunk_r * 6.0
            shrunk_totals[s_mask] = shrunk_r * s_balls

        season_df["bcs_per_over"] = np.round(raw_rates, 2)
        season_df["shrunk_bcs_per_over"] = np.round(shrunk_rates, 2)
        season_df["total_bcs_shrunk"] = np.round(shrunk_totals, 2)

        # Rounding
        season_df["economy"] = season_df["economy"].round(2)
        season_df["dot_pct"] = season_df["dot_pct"].round(1)
        season_df["boundary_pct"] = season_df["boundary_pct"].round(1)
        season_df["strike_rate"] = season_df["strike_rate"].round(1)
        season_df["bowling_average"] = season_df["bowling_average"].round(2)
        season_df["total_erp"] = season_df["total_erp"].round(2)
        season_df["total_bcs"] = season_df["total_bcs"].round(2)
        season_df["total_bwpa"] = season_df["total_bwpa"].round(4)
        season_df["mean_leverage"] = season_df["mean_leverage"].round(3)
        season_df["mean_wqm"] = season_df["mean_wqm"].round(3)
        season_df["first_inns_restriction"] = season_df["first_inns_restriction"].round(2)

        season_df = season_df.sort_values(
            ["season", "total_bcs_shrunk"], ascending=[True, False]
        ).reset_index(drop=True)

        return season_df
