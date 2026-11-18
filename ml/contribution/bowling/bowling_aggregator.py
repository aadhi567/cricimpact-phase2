"""Stage B4 Bowling Match Spell Aggregator."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from ml.contribution.bowling.config import load_bowling_config


class BowlingSpellAggregator:
    """Aggregates delivery-level contribution results into bowler match spells."""

    def __init__(
        self,
        config: dict[str, Any] | None = None,
        player_mapping_path: Path | str | None = None,
    ) -> None:
        self.config = config or load_bowling_config()
        self.player_map: dict[int, str] = {}
        self.team_map: dict[int, str] = {}
        self._load_mappings(player_mapping_path)

    def _load_mappings(self, mapping_path: Path | str | None) -> None:
        cfg_paths = self.config.get("paths", {})
        path = Path(mapping_path) if mapping_path else Path(cfg_paths.get("player_mapping_csv", "data/raw/competition_team_player_mapping.csv"))
        if path.exists():
            df = pd.read_csv(path)
            if "player_id" in df.columns and "player_name" in df.columns:
                self.player_map = dict(zip(df["player_id"], df["player_name"]))
            if "team_id" in df.columns and "team_name" in df.columns:
                self.team_map = dict(zip(df["team_id"], df["team_name"]))

    def aggregate_spells(self, deliveries_df: pd.DataFrame) -> pd.DataFrame:
        """Aggregate delivery records into bowler match spells.

        Computes standard figures (O-M-R-W), advanced contribution totals (BCS, bWPA, ERP),
        ratios, and pressure summaries.
        """
        df = deliveries_df.copy()

        # Ensure required boolean/numerical flags exist
        if "is_legal_delivery" not in df.columns:
            df["is_legal_delivery"] = True
        df["is_legal"] = df["is_legal_delivery"].astype(bool)

        if "boundaries" not in df.columns:
            is_four = df.get("is_boundary_four", pd.Series(False, index=df.index)).fillna(False).astype(bool)
            is_six = df.get("is_boundary_six", pd.Series(False, index=df.index)).fillna(False).astype(bool)
            df["boundaries"] = (is_four | is_six).astype(int)

        # 1. Compute maidens at over level
        over_grp = df.groupby(["match_id", "innings", "bowler_id", "overid"], as_index=False).agg(
            over_legal_balls=("is_legal", "sum"),
            over_runs=("bowler_runs", "sum"),
        )
        over_grp["is_maiden"] = (over_grp["over_legal_balls"] >= 6) & (over_grp["over_runs"] == 0)
        maidens_series = (
            over_grp.groupby(["match_id", "innings", "bowler_id"])["is_maiden"]
            .sum()
            .rename("maidens")
        )

        # 2. Compute max consecutive dots per spell
        max_dots_series = (
            df.groupby(["match_id", "innings", "bowler_id"])["consecutive_dots_after"]
            .max()
            .fillna(0)
            .astype(int)
            .rename("max_consecutive_dots")
        )

        # 3. Main group aggregation
        grp = df.groupby(["match_id", "innings", "bowler_id"], as_index=False)
        spells = grp.agg(
            match_date=("match_date", "first"),
            season=("season", "first"),
            competition_category=("competition_category", "first"),
            venue=("venue_country", "first") if "venue_country" in df else ("venue_id", "first"),
            bowling_team_id=("bowling_team_id", "first"),
            batting_team_id=("batting_team_id", "first"),
            legal_balls=("is_legal", "sum"),
            bowler_runs=("bowler_runs", "sum"),
            wickets=("is_bowler_wkt", "sum"),
            dot_balls=("dot_ball", "sum"),
            boundaries=("boundaries", "sum"),
            total_erp=("erp", "sum"),
            total_bcs=("bcs", "sum"),
            total_bwpa=("bwpa", "sum"),
            mean_leverage=("leverage", "mean"),
            mean_dot_pressure=("dot_pressure_index", "mean"),
            mean_rrr_pressure=("rrr_pressure_index", "mean"),
            first_inns_restriction=("first_inns_scoring_restriction", "sum"),
        )

        # Merge maidens and max consecutive dots
        spells = spells.merge(maidens_series, on=["match_id", "innings", "bowler_id"], how="left")
        spells["maidens"] = spells["maidens"].fillna(0).astype(int)

        spells = spells.merge(max_dots_series, on=["match_id", "innings", "bowler_id"], how="left")
        spells["max_consecutive_dots"] = spells["max_consecutive_dots"].fillna(0).astype(int)

        # Compute total_wkt_impact and mean_wqm on dismissals
        wkt_df = df[df["is_bowler_wkt"] == True]
        if not wkt_df.empty:
            wkt_agg = wkt_df.groupby(["match_id", "innings", "bowler_id"]).agg(
                total_wkt_impact=("unweighted_run_impact", lambda s: float((df.loc[s.index, "wqm"] * df.loc[s.index, "v_wkt"]).sum())),
                mean_wqm=("wqm", "mean"),
            )
            spells = spells.merge(wkt_agg, on=["match_id", "innings", "bowler_id"], how="left")
            spells["total_wkt_impact"] = spells["total_wkt_impact"].fillna(0.0)
            spells["mean_wqm"] = spells["mean_wqm"].fillna(1.0)
        else:
            spells["total_wkt_impact"] = 0.0
            spells["mean_wqm"] = 1.0

        # Names & metadata
        spells["bowler_name"] = spells["bowler_id"].map(self.player_map).fillna(spells["bowler_id"].astype(str))
        spells["team"] = spells["bowling_team_id"].map(self.team_map).fillna(spells["bowling_team_id"].astype(str))
        spells["opponent"] = spells["batting_team_id"].map(self.team_map).fillna(spells["batting_team_id"].astype(str))

        # Overs notation and rates
        complete_overs = spells["legal_balls"] // 6
        partial_balls = spells["legal_balls"] % 6
        spells["overs"] = complete_overs + (partial_balls / 10.0)

        # Economy & percentages
        spells["economy"] = np.where(
            spells["legal_balls"] > 0,
            (spells["bowler_runs"] * 6.0) / spells["legal_balls"],
            0.0,
        )
        spells["dot_pct"] = np.where(
            spells["legal_balls"] > 0,
            (spells["dot_balls"] / spells["legal_balls"]) * 100.0,
            0.0,
        )
        spells["boundary_pct"] = np.where(
            spells["legal_balls"] > 0,
            (spells["boundaries"] / spells["legal_balls"]) * 100.0,
            0.0,
        )

        # Rounding for clean presentation
        spells["economy"] = spells["economy"].round(2)
        spells["total_erp"] = spells["total_erp"].round(2)
        spells["total_wkt_impact"] = spells["total_wkt_impact"].round(2)
        spells["total_bcs"] = spells["total_bcs"].round(2)
        spells["total_bwpa"] = spells["total_bwpa"].round(4)
        spells["mean_wqm"] = spells["mean_wqm"].round(3)
        spells["mean_leverage"] = spells["mean_leverage"].round(3)
        spells["dot_pct"] = spells["dot_pct"].round(1)
        spells["boundary_pct"] = spells["boundary_pct"].round(1)
        spells["mean_dot_pressure"] = pd.to_numeric(spells["mean_dot_pressure"], errors="coerce").round(2)
        spells["mean_rrr_pressure"] = pd.to_numeric(spells["mean_rrr_pressure"], errors="coerce").round(2)
        spells["first_inns_restriction"] = pd.to_numeric(spells["first_inns_restriction"], errors="coerce").round(2)

        # Sort chronologically by match_date, match_id, innings, total_bcs descending
        spells = spells.sort_values(
            ["match_date", "match_id", "innings", "total_bcs"], ascending=[True, True, True, False]
        ).reset_index(drop=True)

        return spells
