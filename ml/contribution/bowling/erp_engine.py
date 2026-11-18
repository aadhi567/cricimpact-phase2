"""Stage B4: Expected Runs Prevented (ERP) Engine.

Evaluates:
    ERP_t = E[BowlerRuns | S_t] - ActualBowlerRuns_t
using the calibrated Hierarchical Bayesian Shrinkage Model (M=20.0).
Preserves the audited B1/B3.1 extras safeguard.
"""
from __future__ import annotations

from typing import Any, Final

import numpy as np
import pandas as pd

from ml.contribution.bowling.config import load_bowling_config
from ml.contribution.bowling.schema import (
    BOWLER_CHARGED_EXTRAS,
    NON_BOWLER_EXTRAS,
)


class ExpectedRunsPreventedEngine:
    """Computes expected bowler runs and expected runs prevented per delivery."""

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        self.config = config or load_bowling_config()
        erp_cfg = self.config["erp_model"]
        self.global_mean: float = float(erp_cfg["global_mean"])
        self.phase_priors: dict[str, float] = {
            str(k): float(v) for k, v in erp_cfg["phase_priors"].items()
        }
        self.hierarchical_table: dict[str, float] = {
            str(k): float(v) for k, v in erp_cfg["hierarchical_shrunk_table"].items()
        }
        self.shrinkage_m: float = float(self.config["parameters"]["erp_shrinkage_m"])
        self.safeguard_zero_erp: bool = bool(
            self.config["safeguards"]["extras_safeguard_zero_erp"]
        )

    @staticmethod
    def get_over_group(overid: int) -> str:
        """Map overid (1-20) to standard over groups."""
        if overid <= 2:
            return "1-2"
        elif overid <= 4:
            return "3-4"
        elif overid <= 6:
            return "5-6"
        elif overid <= 10:
            return "7-10"
        elif overid <= 15:
            return "11-15"
        elif overid <= 17:
            return "16-17"
        else:
            return "18-20"

    @staticmethod
    def get_wkt_bucket(wickets_lost_before: int) -> str:
        """Map wickets lost before delivery (0-10) to standard wicket bucket."""
        if wickets_lost_before <= 1:
            return "0-1"
        elif wickets_lost_before <= 3:
            return "2-3"
        elif wickets_lost_before <= 5:
            return "4-5"
        elif wickets_lost_before <= 7:
            return "6-7"
        else:
            return "8+"

    def predict_expected_bowler_runs(
        self,
        innings: int,
        innings_phase: str,
        overid: int,
        wickets_lost_before: int,
    ) -> float:
        """Predict expected bowler runs for a single pre-delivery state."""
        wkt_bucket = self.get_wkt_bucket(wickets_lost_before)
        over_group = self.get_over_group(overid)
        key = f"inn_{innings}_{innings_phase}_{wkt_bucket}_{over_group}"

        if key in self.hierarchical_table:
            return self.hierarchical_table[key]

        # Hierarchical fallback: phase prior -> global mean
        return self.phase_priors.get(innings_phase, self.global_mean)

    @staticmethod
    def calculate_bowler_runs(
        batter_runs: int,
        extras_type: str | None,
        extras1_runs: int,
    ) -> int:
        """Calculate runs charged to the bowler under MCC rules."""
        charged_extras = 0
        if extras_type in BOWLER_CHARGED_EXTRAS:
            charged_extras = int(extras1_runs)
        return int(batter_runs) + charged_extras

    def evaluate_delivery(
        self,
        innings: int,
        innings_phase: str,
        overid: int,
        wickets_lost_before: int,
        batter_runs: int,
        extras_type: str | None,
        extras1_runs: int,
    ) -> tuple[float, int, float]:
        """Evaluate a single delivery.

        Returns:
            (exp_bowler_runs, bowler_runs, erp)
        """
        exp_runs = self.predict_expected_bowler_runs(
            innings=innings,
            innings_phase=innings_phase,
            overid=overid,
            wickets_lost_before=wickets_lost_before,
        )
        bowler_runs = self.calculate_bowler_runs(
            batter_runs=batter_runs,
            extras_type=extras_type,
            extras1_runs=extras1_runs,
        )

        is_non_bowler_extra = extras_type in NON_BOWLER_EXTRAS
        if self.safeguard_zero_erp and is_non_bowler_extra and batter_runs == 0:
            erp = 0.0
        else:
            erp = exp_runs - float(bowler_runs)

        return float(exp_runs), bowler_runs, float(erp)

    def evaluate_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """Vectorized evaluation of an entire deliveries dataframe.

        Adds columns:
            - bowler_runs
            - exp_bowler_runs
            - erp
        """
        res = df.copy()

        # Bowler runs
        bowler_extra_mask = res["extras_type"].isin(BOWLER_CHARGED_EXTRAS)
        charged_extras = np.where(bowler_extra_mask, res["extras1_runs"].fillna(0).astype(int), 0)
        res["bowler_runs"] = res["batter_runs"].fillna(0).astype(int) + charged_extras

        # State grouping
        over_groups = res["overid"].apply(self.get_over_group)
        wkt_buckets = res["wickets_lost_before"].apply(self.get_wkt_bucket)

        keys = [
            f"inn_{inn}_{phase}_{wkt}_{ov}"
            for inn, phase, wkt, ov in zip(
                res["innings"], res["innings_phase"], wkt_buckets, over_groups
            )
        ]

        # Table lookup with phase fallback
        exp_vals = np.empty(len(res), dtype=float)
        for i, (k, phase) in enumerate(zip(keys, res["innings_phase"])):
            if k in self.hierarchical_table:
                exp_vals[i] = self.hierarchical_table[k]
            else:
                exp_vals[i] = self.phase_priors.get(phase, self.global_mean)

        res["exp_bowler_runs"] = exp_vals
        res["erp"] = res["exp_bowler_runs"] - res["bowler_runs"].astype(float)

        # Safeguard: pure non-bowler extras (byes, leg-byes with 0 batter runs) -> ERP = 0.0
        if self.safeguard_zero_erp:
            non_bowler_mask = (
                res["extras_type"].isin(NON_BOWLER_EXTRAS) & (res["batter_runs"] == 0)
            )
            res.loc[non_bowler_mask, "erp"] = 0.0

        return res

