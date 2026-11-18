"""Stage B4: Context-Dependent Wicket Value Engine.

Implements Approach D: Leverage-Modulated Shared Resource Curve.
Provides 2D Over x Wickets-Lost Bayesian Shrinkage lookup V_wkt(S_t) (M=15.0).
Double-leverage safeguard: The returned values are purely physical run drops,
never pre-multiplied by match leverage.
"""
from __future__ import annotations

from typing import Any, Final

import numpy as np
import pandas as pd

from ml.contribution.bowling.config import load_bowling_config


class ContextWicketValueEngine:
    """Evaluates physical marginal wicket value based on over and wickets lost."""

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        self.config = config or load_bowling_config()
        wkt_cfg = self.config["wicket_value_model"]
        self.phase_baselines: dict[str, float] = {
            str(k): float(v) for k, v in wkt_cfg["phase_baselines"].items()
        }
        self.shrunk_2d_table: dict[str, float] = {
            str(k): float(v) for k, v in wkt_cfg["shrunk_2d_table"].items()
        }
        self.global_baseline: float = float(
            self.phase_baselines.get("global", 8.90955)
        )

    def get_wicket_value(
        self,
        overid: int,
        wickets_lost_before: int,
        innings_phase: str | None = None,
    ) -> float:
        """Retrieve physical wicket value V_wkt(S_t) for a state.

        Args:
            overid: 1 to 20
            wickets_lost_before: 0 to 9
            innings_phase: 'powerplay', 'middle', 'death' (optional fallback)

        Returns:
            Physical wicket run-drop value (strictly non-negative).
        """
        key = f"ov_{int(overid)}_wkt_{int(wickets_lost_before)}"
        if key in self.shrunk_2d_table:
            return self.shrunk_2d_table[key]

        # Phase fallback
        if innings_phase and innings_phase in self.phase_baselines:
            return self.phase_baselines[innings_phase]

        # Derive phase from overid if phase not provided
        if overid <= 6:
            return self.phase_baselines.get("powerplay", 14.30)
        elif overid <= 15:
            return self.phase_baselines.get("middle", 10.09)
        else:
            return self.phase_baselines.get("death", 3.21)

    def evaluate_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """Vectorized evaluation of V_wkt across a match states dataframe.

        Adds column:
            - V_wkt
        """
        res = df.copy()
        keys = [
            f"ov_{int(ov)}_wkt_{int(w)}"
            for ov, w in zip(res["overid"], res["wickets_lost_before"])
        ]

        vals = np.empty(len(res), dtype=float)
        for i, (k, phase, ov) in enumerate(zip(keys, res["innings_phase"], res["overid"])):
            if k in self.shrunk_2d_table:
                vals[i] = self.shrunk_2d_table[k]
            else:
                vals[i] = self.get_wicket_value(ov, 0, phase)

        res["V_wkt"] = vals
        return res

