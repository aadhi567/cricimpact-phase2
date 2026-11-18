"""Stage B7.5 Match Spell Pressure Aggregator Module."""

from __future__ import annotations

from typing import Any
import numpy as np
import pandas as pd

from ml.contribution.bowling_pressure.config import load_pcs_config
from ml.contribution.bowling_pressure.pcs_normalizer import PCSNormalizer


class PCSSpellAggregator:
    """Aggregates delivery-level pressure effects into bowler match spells."""

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        self.config = config or load_pcs_config()
        self.normalizer = PCSNormalizer(
            k_slope=float(self.config["parameters"]["k_sigmoid_slope"]),
            sigma_ref_1st=float(self.config["parameters"]["sigma_ref_1st"]),
            sigma_ref_2nd=float(self.config["parameters"]["sigma_ref_2nd"]),
        )

    def aggregate_spells(self, df_deliveries: pd.DataFrame) -> pd.DataFrame:
        """Aggregate delivery-level records into match spells per bowler."""
        # Ensure legal delivery indicator
        is_legal = df_deliveries["is_legal_delivery"].fillna(True).astype(bool)
        is_bwkt = df_deliveries["is_bowler_wkt"].fillna(False).astype(bool)
        is_dot = df_deliveries.get("is_dot_ball", pd.Series(False, index=df_deliveries.index)).astype(bool)

        df = df_deliveries.copy()
        df["legal_ball_count"] = is_legal.astype(int)
        df["bowler_wkt_count"] = is_bwkt.astype(int)
        df["dot_ball_count"] = is_dot.astype(int)
        df["boundary_count"] = (df["is_boundary_four"] | df["is_boundary_six"]).astype(int)
        df["bowler_runs_count"] = df.get("bowler_runs", df["team_runs"]).fillna(0).astype(int)

        grp_keys = ["match_id", "innings", "bowler_id"]
        grp = df.groupby(grp_keys, as_index=False)

        spells = grp.agg(
            season=("season", "first"),
            match_date=("match_date", "first"),
            competition_category=("competition_category", "first"),
            venue_id=("venue_id", "first"),
            bowling_team_id=("bowling_team_id", "first"),
            batting_team_id=("batting_team_id", "first"),
            legal_balls=("legal_ball_count", "sum"),
            total_deliveries=("innings_ball_num", "count"),
            bowler_runs=("bowler_runs_count", "sum"),
            wickets=("bowler_wkt_count", "sum"),
            dot_balls=("dot_ball_count", "sum"),
            boundaries=("boundary_count", "sum"),
            mean_leverage=("leverage", "mean"),
            total_swi=("swi", "sum"),
            total_dci=("dci", "sum"),
            total_sup=("sup", "sum"),
            total_leakage=("leakage", "sum"),
            total_rpe=("rpe", "sum"),
        )

        # Overs notation
        c_overs = spells["legal_balls"] // 6
        p_balls = spells["legal_balls"] % 6
        spells["overs"] = c_overs + (p_balls / 10.0)

        # Economy rate
        spells["economy"] = np.where(
            spells["legal_balls"] > 0,
            (spells["bowler_runs"] * 6.0) / spells["legal_balls"],
            0.0,
        ).round(2)

        # Bipolar PCS Normalization
        pcs = self.normalizer.normalize(
            rpe=spells["total_rpe"].to_numpy(),
            innings=spells["innings"].to_numpy(),
        )
        spells["pcs_spell"] = pcs.round(2)

        return spells
