"""Stage B4: Wicket Quality Multiplier (WQM) Engine.

Evaluates the batter dismissed across:
1. Historical Quality: Q_hist = abc_prior_shrunk / 50.0
2. Recent Form: F_recent = 1.0 + clip((last5 - shrunk)/50.0, -0.40, 0.40)
3. In-Match Threat: theta_match,t-1 = tanh(runs / 25.0) * sqrt(clip(SR, 80.0, 250.0) / 130.0)
4. Composite Multiplier:
   Q_base = 0.70 * Q_hist + 0.30 * F_recent
   WQM = clip(Q_base * (1.0 + 0.50 * theta_match,t-1), 0.40, 2.50)
"""
from __future__ import annotations

import math
from typing import Any, Final

import numpy as np
import pandas as pd

from ml.contribution.bowling.config import load_bowling_config


class WicketQualityMultiplierEngine:
    """Computes context-aware Wicket Quality Multipliers for dismissed batters."""

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        self.config = config or load_bowling_config()
        p = self.config["parameters"]
        self.hist_weight: float = float(p["historical_quality_weight"])
        self.form_weight: float = float(p["recent_form_weight"])
        self.threat_coef: float = float(p["threat_coefficient"])
        self.wqm_min: float = float(p["wqm_min"])
        self.wqm_max: float = float(p["wqm_max"])
        self.form_delta_min: float = float(p["form_delta_min"])
        self.form_delta_max: float = float(p["form_delta_max"])
        self.cold_start_threshold: int = int(p["cold_start_innings_threshold"])
        self.threat_runs_scale: float = float(p["threat_runs_scale"])
        self.threat_sr_baseline: float = float(p["threat_sr_baseline"])
        self.threat_sr_min: float = float(p["threat_sr_min"])
        self.threat_sr_max: float = float(p["threat_sr_max"])

    def compute_historical_quality(self, abc_prior_shrunk: float | None) -> float:
        """Historical quality normalized around neutral 50.0."""
        if abc_prior_shrunk is None or math.isnan(abc_prior_shrunk):
            return 1.0
        return float(abc_prior_shrunk / 50.0)

    def compute_recent_form(
        self,
        abc_prior_shrunk: float | None,
        abc_prior_all_last5_mean: float | None,
        batted_inns_prior_all: int | None,
    ) -> float:
        """Recent form factor with cold-start protection."""
        if (
            batted_inns_prior_all is None
            or batted_inns_prior_all < self.cold_start_threshold
            or abc_prior_shrunk is None
            or abc_prior_all_last5_mean is None
            or math.isnan(abc_prior_shrunk)
            or math.isnan(abc_prior_all_last5_mean)
        ):
            return 1.0

        delta_form = (abc_prior_all_last5_mean - abc_prior_shrunk) / 50.0
        delta_clipped = float(np.clip(delta_form, self.form_delta_min, self.form_delta_max))
        return 1.0 + delta_clipped

    def compute_in_match_threat(
        self,
        runs_before: int,
        balls_before: int,
    ) -> float:
        """Calculate in-match threat immediately before delivery t."""
        if balls_before <= 0 or runs_before <= 0:
            return 0.0

        sr = 100.0 * float(runs_before) / float(balls_before)
        sr_clipped = float(np.clip(sr, self.threat_sr_min, self.threat_sr_max))
        volatility = math.sqrt(sr_clipped / self.threat_sr_baseline)
        accumulation = math.tanh(float(runs_before) / self.threat_runs_scale)
        return float(accumulation * volatility)

    def calculate_wqm(
        self,
        abc_prior_shrunk: float | None,
        abc_prior_all_last5_mean: float | None,
        batted_inns_prior_all: int | None,
        runs_before: int = 0,
        balls_before: int = 0,
    ) -> float:
        """Calculate single delivery WQM for a dismissed batter."""
        q_hist = self.compute_historical_quality(abc_prior_shrunk)
        f_recent = self.compute_recent_form(
            abc_prior_shrunk=abc_prior_shrunk,
            abc_prior_all_last5_mean=abc_prior_all_last5_mean,
            batted_inns_prior_all=batted_inns_prior_all,
        )
        theta_match = self.compute_in_match_threat(runs_before, balls_before)

        q_base = self.hist_weight * q_hist + self.form_weight * f_recent
        raw_wqm = q_base * (1.0 + self.threat_coef * theta_match)
        return float(np.clip(raw_wqm, self.wqm_min, self.wqm_max))

    def evaluate_dataframe(
        self,
        df: pd.DataFrame,
        causal_features_df: pd.DataFrame | None = None,
    ) -> pd.DataFrame:
        """Vectorized evaluation of WQM across a match states dataframe.

        Merges causal features if provided, reconstructs pre-delivery striker state,
        and computes WQM column.
        """
        res = df.copy()

        if causal_features_df is not None:
            # Merge pre-match causal features
            causal_sub = causal_features_df[
                [
                    "match_id",
                    "player_id",
                    "abc_prior_shrunk",
                    "abc_prior_all_last5_mean",
                    "batted_inns_prior_all",
                ]
            ].rename(columns={"player_id": "striker_id"})
            res = res.merge(causal_sub, on=["match_id", "striker_id"], how="left")

        # Fallback for missing causal features
        res["abc_prior_shrunk"] = res["abc_prior_shrunk"].fillna(50.0)
        res["abc_prior_all_last5_mean"] = res["abc_prior_all_last5_mean"].fillna(50.0)
        res["batted_inns_prior_all"] = res["batted_inns_prior_all"].fillna(0)

        # Historical Quality
        res["Q_hist"] = res["abc_prior_shrunk"] / 50.0

        # Recent Form
        has_min_inns = res["batted_inns_prior_all"] >= self.cold_start_threshold
        delta_form = (res["abc_prior_all_last5_mean"] - res["abc_prior_shrunk"]) / 50.0
        delta_clipped = delta_form.clip(self.form_delta_min, self.form_delta_max)
        res["F_recent"] = np.where(has_min_inns, 1.0 + delta_clipped, 1.0)

        # In-match threat reconstruction (strictly pre-delivery t-1)
        res = res.sort_values(["match_id", "innings", "innings_ball_num"]).reset_index(drop=True)
        res["is_legal_int"] = res["is_legal_delivery"].astype(int)

        # Shift(1) within match, innings, and striker
        striker_legal_ball = (
            res.groupby(["match_id", "innings", "striker_id"])["is_legal_int"]
            .shift(1)
            .fillna(0)
        )
        striker_ball_runs = (
            res.groupby(["match_id", "innings", "striker_id"])["batter_runs"]
            .shift(1)
            .fillna(0)
        )

        res["striker_cum_balls"] = (
            striker_legal_ball.groupby([res["match_id"], res["innings"], res["striker_id"]]).cumsum()
        )
        res["striker_cum_runs"] = (
            striker_ball_runs.groupby([res["match_id"], res["innings"], res["striker_id"]]).cumsum()
        )

        sr = np.where(
            res["striker_cum_balls"] > 0,
            100.0 * res["striker_cum_runs"] / res["striker_cum_balls"],
            100.0,
        )
        sr_clipped = np.clip(sr, self.threat_sr_min, self.threat_sr_max)
        accumulation = np.tanh(res["striker_cum_runs"] / self.threat_runs_scale)
        volatility = np.sqrt(sr_clipped / self.threat_sr_baseline)
        res["theta_match"] = accumulation * volatility

        # Composite WQM
        q_base = self.hist_weight * res["Q_hist"] + self.form_weight * res["F_recent"]
        raw_wqm = q_base * (1.0 + self.threat_coef * res["theta_match"])
        res["WQM"] = np.clip(raw_wqm, self.wqm_min, self.wqm_max)

        return res

