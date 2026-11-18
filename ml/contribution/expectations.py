"""Stage 5C Competition-Aware Causal Expectations Engine.

Provides walk-forward, competition-isolated expectations:
1. Par_20(b) cumulative 1st-innings par curve.
2. w_hist(b) cumulative wicket loss curve.
3. ExpectedScoreRFModel (EFS) for 1st-innings entry/exit.
4. ExpectedRunsRFModel and ExpectedSRRFModel for batter entry.
5. Deterministic COLD_START_FALLBACK (N_prior < 30).
6. Non-ML empirical shrinkage for OTHER_T20 (comp_id 2670 and 3289).
7. Phase 7U heuristic baselines (1.25 * B, 125.0, NaN).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor

from ml.contribution.schema import (
    FALLBACK_EXPECTED_SR,
    FALLBACK_RUN_RATE_PAR,
    IPL_HISTORICAL_PAR_TOTAL,
    MIN_MATCHES_FOR_EXPECTATIONS,
    REGIME_COLD_START,
    REGIME_LOW_SAMPLE_NO_ML,
    REGIME_PHASE7U_HEURISTIC,
    REGIME_WALK_FORWARD_RF,
)

logger = logging.getLogger(__name__)

# Phase 1 historical wicket loss curve (derived from 1,217 IPL 1st innings)
PHASE1_HISTORICAL_WICKET_LOSS_CURVE: dict[int, float] = {
    0: 0.00,
    6: 0.22,
    12: 0.44,
    18: 0.67,
    24: 0.90,
    30: 1.14,
    36: 1.39,
    42: 1.62,
    48: 1.86,
    54: 2.11,
    60: 2.37,
    66: 2.64,
    72: 2.92,
    78: 3.20,
    84: 3.49,
    90: 3.63,
    96: 4.10,
    102: 4.47,
    108: 4.88,
    114: 5.38,
    120: 5.93,
}


def interpolate_w_hist(b: int, w_curve: dict[int, float] | None = None) -> float:
    """Linearly interpolates historical wickets lost at legal ball b in [0, 120]."""
    if w_curve is None:
        w_curve = PHASE1_HISTORICAL_WICKET_LOSS_CURVE
    b_clamped = max(0, min(120, int(b)))
    grid_points = sorted(w_curve.keys())
    if b_clamped in w_curve:
        return float(w_curve[b_clamped])
    # Find surrounding points
    lower = max(k for k in grid_points if k <= b_clamped)
    upper = min(k for k in grid_points if k >= b_clamped)
    if lower == upper:
        return float(w_curve[lower])
    frac = (b_clamped - lower) / float(upper - lower)
    return float(w_curve[lower] + frac * (w_curve[upper] - w_curve[lower]))


@dataclass
class WindowExpectationModels:
    """Holds fitted or fallback models for one walk-forward window."""

    category: str
    regime: str
    n_prior_matches: int
    par_total: float
    par_curve: np.ndarray  # 121-element array for b=0..120
    w_curve: dict[int, float]
    efs_model: RandomForestRegressor | None = None
    runs_model: RandomForestRegressor | None = None
    sr_model: RandomForestRegressor | None = None
    # Category normalization anchors
    target_center: float = 165.0
    rrr_center: float = 8.25
    p2_runs_mean: float = 19.8
    p2_runs_std: float = 21.6
    p2_sr_mean: float = 125.0
    p2_sr_std: float = 50.0
    p2_norm_mean: float = -0.068
    p2_norm_std: float = 1.029
    p3_norm_mean: float = 0.159
    p3_norm_std: float = 1.513


class CausalExpectationManager:
    """Manages chronologically safe walk-forward expectation models."""

    def __init__(self, match_states_df: pd.DataFrame, stints_df: pd.DataFrame):
        self.match_states_df = match_states_df[
            match_states_df["is_primary_wp_train_eligible"] == True
        ].copy()
        self.stints_df = stints_df.copy()

        # Cache of window models: key is (category, refit_date)
        self.window_cache: dict[tuple[str, str], WindowExpectationModels] = {}
        self.last_rf_models: dict[str, WindowExpectationModels] = {}
        self.last_rf_n_prior: dict[str, int] = {}
        self.last_rf_season: dict[str, str] = {}

        # Extract unique matches sorted by (match_date, match_id)
        self.matches_meta = (
            self.match_states_df[
                ["match_id", "competition_category", "season", "match_date"]
            ]
            .drop_duplicates(subset=["match_id"])
            .sort_values(["match_date", "match_id"])
            .reset_index(drop=True)
        )

    def get_models_for_match(
        self,
        match_id: int,
        comp_category: str,
        match_date: str,
        season: str,
    ) -> WindowExpectationModels:
        """Returns expectation models trained strictly on past matches (date < match_date)."""
        cache_key = (comp_category, match_date)
        if cache_key in self.window_cache:
            return self.window_cache[cache_key]

        # Prior matches strictly before match_date in same category
        prior_matches = self.matches_meta[
            (self.matches_meta["competition_category"] == comp_category)
            & (self.matches_meta["match_date"] < match_date)
        ]
        n_prior = len(prior_matches)
        prior_mids = set(prior_matches["match_id"].unique())

        # Decision 3: OTHER_T20 NEVER fits Random Forest
        if comp_category == "OTHER_T20":
            models = self._build_other_t20_models(n_prior, prior_mids, season)
            self.window_cache[cache_key] = models
            return models

        # Decision 2: Cold start if n_prior < 30
        if n_prior < MIN_MATCHES_FOR_EXPECTATIONS:
            models = self._build_cold_start_models(comp_category, n_prior)
            self.window_cache[cache_key] = models
            return models

        # Walk-forward RF models for IPL and T20I (n_prior >= 30)
        # Expand RF window every 15 prior matches or upon new season to maintain strict causality with high performance
        need_refit = (
            comp_category not in self.last_rf_models
            or (n_prior - self.last_rf_n_prior.get(comp_category, 0)) >= 15
            or season != self.last_rf_season.get(comp_category, "")
        )
        if need_refit:
            models = self._fit_walk_forward_models(comp_category, n_prior, prior_mids)
            self.last_rf_models[comp_category] = models
            self.last_rf_n_prior[comp_category] = n_prior
            self.last_rf_season[comp_category] = season
        else:
            base_model = self.last_rf_models[comp_category]
            models = WindowExpectationModels(
                category=comp_category,
                regime=REGIME_WALK_FORWARD_RF,
                n_prior_matches=n_prior,
                par_total=base_model.par_total,
                par_curve=base_model.par_curve,
                w_curve=base_model.w_curve,
                efs_model=base_model.efs_model,
                runs_model=base_model.runs_model,
                sr_model=base_model.sr_model,
                target_center=base_model.target_center,
                rrr_center=base_model.rrr_center,
                p2_runs_mean=base_model.p2_runs_mean,
                p2_runs_std=base_model.p2_runs_std,
                p2_sr_mean=base_model.p2_sr_mean,
                p2_sr_std=base_model.p2_sr_std,
                p2_norm_mean=base_model.p2_norm_mean,
                p2_norm_std=base_model.p2_norm_std,
                p3_norm_mean=base_model.p3_norm_mean,
                p3_norm_std=base_model.p3_norm_std,
            )
        self.window_cache[cache_key] = models
        return models

    def _build_cold_start_models(
        self, comp_category: str, n_prior: int
    ) -> WindowExpectationModels:
        par_tot = (
            IPL_HISTORICAL_PAR_TOTAL if comp_category == "IPL" else 165.0
        )
        # Linear par curve 0..120
        b_grid = np.arange(121)
        par_curve = (b_grid / 120.0) * par_tot

        return WindowExpectationModels(
            category=comp_category,
            regime=REGIME_COLD_START,
            n_prior_matches=n_prior,
            par_total=par_tot,
            par_curve=par_curve,
            w_curve=dict(PHASE1_HISTORICAL_WICKET_LOSS_CURVE),
            efs_model=None,
            runs_model=None,
            sr_model=None,
            target_center=par_tot,
            rrr_center=par_tot / 20.0,
        )

    def _build_other_t20_models(
        self, n_prior: int, prior_mids: set[int], season: str
    ) -> WindowExpectationModels:
        """Deterministic non-ML empirical shrinkage for OTHER_T20 (comp 2670 and 3289)."""
        if n_prior == 0:
            # First tournament (2670, 2024): cold start neutral par 155.0
            par_tot = 155.0
            b_grid = np.arange(121)
            par_curve = (b_grid / 120.0) * par_tot
            w_curve = dict(PHASE1_HISTORICAL_WICKET_LOSS_CURVE)
        else:
            # Second tournament (3289, 2025): prior 15 matches from 2670 exist
            prior_inn1 = self.match_states_df[
                (self.match_states_df["match_id"].isin(prior_mids))
                & (self.match_states_df["innings"] == 1)
            ]
            obs_scores = (
                prior_inn1.groupby("match_id")["score_after"].max().values
            )
            raw_mean = float(np.mean(obs_scores)) if len(obs_scores) > 0 else 155.0
            # Empirical shrinkage toward neutral 160.0 (m0 = 5)
            par_tot = float((len(obs_scores) * raw_mean + 5.0 * 160.0) / (len(obs_scores) + 5.0))

            # Compute empirical par curve from prior completed 1st innings
            b_grid = np.arange(121)
            par_curve = np.zeros(121, dtype=np.float64)
            for b in range(1, 121):
                b_slice = prior_inn1[
                    prior_inn1["legal_balls_completed_after"] == b
                ]
                if len(b_slice) >= 3:
                    par_curve[b] = float(b_slice["score_after"].mean())
                else:
                    par_curve[b] = (b / 120.0) * par_tot
            # Guarantee monotonicity
            for b in range(1, 121):
                if par_curve[b] < par_curve[b - 1]:
                    par_curve[b] = par_curve[b - 1]
            par_curve[120] = max(par_curve[120], par_tot)

            # Compute empirical wicket curve
            w_curve = dict(PHASE1_HISTORICAL_WICKET_LOSS_CURVE)
            for b in sorted(w_curve.keys()):
                if b > 0:
                    b_slice = prior_inn1[
                        prior_inn1["legal_balls_completed_after"] == b
                    ]
                    if len(b_slice) >= 3:
                        w_curve[b] = float(b_slice["wickets_lost_after"].mean())

        return WindowExpectationModels(
            category="OTHER_T20",
            regime=REGIME_LOW_SAMPLE_NO_ML,
            n_prior_matches=n_prior,
            par_total=par_tot,
            par_curve=par_curve,
            w_curve=w_curve,
            efs_model=None,
            runs_model=None,
            sr_model=None,
            target_center=par_tot,
            rrr_center=par_tot / 20.0,
        )

    def _fit_walk_forward_models(
        self, comp_category: str, n_prior: int, prior_mids: set[int]
    ) -> WindowExpectationModels:
        """Fits walk-forward models and empirical curves strictly on prior matches."""
        prior_states = self.match_states_df[
            self.match_states_df["match_id"].isin(prior_mids)
        ]
        prior_stints = self.stints_df[
            (self.stints_df["match_id"].isin(prior_mids))
            & (~self.stints_df["is_dnb"])
        ]

        prior_inn1 = prior_states[prior_states["innings"] == 1]
        final_scores_dict = (
            prior_inn1.groupby("match_id")["score_after"].max().to_dict()
        )
        obs_totals = list(final_scores_dict.values())
        par_tot = float(np.mean(obs_totals)) if len(obs_totals) > 0 else 165.0

        # 1. Par curve 0..120
        par_curve = np.zeros(121, dtype=np.float64)
        for b in range(1, 121):
            b_rows = prior_inn1[prior_inn1["legal_balls_completed_after"] == b]
            if len(b_rows) >= 5:
                par_curve[b] = float(b_rows["score_after"].mean())
            else:
                par_curve[b] = (b / 120.0) * par_tot
        for b in range(1, 121):
            if par_curve[b] < par_curve[b - 1]:
                par_curve[b] = par_curve[b - 1]
        par_curve[120] = max(par_curve[120], par_tot)

        # 2. Wicket curve 0..120
        w_curve = dict(PHASE1_HISTORICAL_WICKET_LOSS_CURVE)
        for b in sorted(w_curve.keys()):
            if b > 0:
                b_rows = prior_inn1[prior_inn1["legal_balls_completed_after"] == b]
                if len(b_rows) >= 5:
                    w_curve[b] = float(b_rows["wickets_lost_after"].mean())

        # 3. Fit ExpectedScoreRFModel (EFS)
        # End of over 1..19 in Innings 1
        eoo = (
            prior_inn1.sort_values(["match_id", "innings_ball_num"])
            .groupby(["match_id", "overid"])
            .last()
            .reset_index()
        )
        eoo = eoo[eoo["overid"].between(1, 19)].copy()
        eoo["final_team_score"] = eoo["match_id"].map(final_scores_dict)

        def phase_code(ov: int) -> int:
            return 0 if ov <= 6 else (1 if ov <= 15 else 2)

        eoo["phase_code"] = eoo["overid"].map(phase_code)

        X_efs = eoo[
            [
                "score_after",
                "wickets_lost_after",
                "wickets_remaining",
                "overs_completed_decimal",
                "legal_balls_remaining",
                "current_run_rate",
                "phase_code",
            ]
        ].values
        y_efs = eoo["final_team_score"].values

        efs_rf = RandomForestRegressor(
            n_estimators=100,
            max_depth=12,
            min_samples_split=10,
            min_samples_leaf=5,
            random_state=42,
            n_jobs=-1,
        )
        efs_rf.fit(X_efs, y_efs)

        # 4. Fit ExpectedRunsRFModel and ExpectedSRRFModel
        # Stints features
        st_feats = prior_stints.copy()
        st_feats["phase_code"] = [
            0
            if float(o) <= 6.0
            else (1 if float(o) <= 15.0 else 2)
            for o in st_feats["entry_over_decimal"]
        ]
        st_feats["is_chase"] = (st_feats["innings"] == 2).astype(int)
        st_feats["req_rr_clean"] = st_feats["required_rr_entry"].fillna(0.0)
        st_feats["req_runs_clean"] = st_feats["runs_required_entry"].fillna(0)
        st_feats["efs_entry_clean"] = [
            float(t) if c == 1 and pd.notna(t) else par_tot
            for c, t in zip(st_feats["is_chase"], st_feats["target_runs"])
        ]

        X_batter = st_feats[
            [
                "batting_order",
                "entry_over_decimal",
                "entry_balls_remaining",
                "entry_wickets_remaining",
                "entry_team_score",
                "entry_team_rr",
                "phase_code",
                "is_chase",
                "req_rr_clean",
                "req_runs_clean",
                "efs_entry_clean",
            ]
        ].values
        y_runs = st_feats["actual_runs"].values
        y_sr = st_feats["actual_sr"].values

        runs_rf = RandomForestRegressor(
            n_estimators=100,
            max_depth=8,
            min_samples_split=20,
            min_samples_leaf=10,
            random_state=42,
            n_jobs=-1,
        )
        runs_rf.fit(X_batter, y_runs)

        # SR model fit restricted to balls_faced > 0
        bf_mask = (st_feats["balls_faced"] > 0).values
        if np.sum(bf_mask) >= 30:
            sr_rf = RandomForestRegressor(
                n_estimators=100,
                max_depth=8,
                min_samples_split=20,
                min_samples_leaf=10,
                random_state=42,
                n_jobs=-1,
            )
            sr_rf.fit(X_batter[bf_mask], y_sr[bf_mask])
        else:
            sr_rf = None

        # Empirical P2 anchors from prior stints
        p_runs = st_feats["actual_runs"].values
        p_sr = st_feats[st_feats["balls_faced"] > 0]["actual_sr"].values

        runs_mean = float(np.mean(p_runs)) if len(p_runs) > 0 else 19.8
        runs_std = float(np.std(p_runs)) if len(p_runs) > 0 else 21.6
        if runs_std < 1.0:
            runs_std = 21.6

        sr_mean = float(np.mean(p_sr)) if len(p_sr) > 0 else 125.0
        sr_std = float(np.std(p_sr)) if len(p_sr) > 0 else 50.0
        if sr_std < 5.0:
            sr_std = 50.0

        return WindowExpectationModels(
            category=comp_category,
            regime=REGIME_WALK_FORWARD_RF,
            n_prior_matches=n_prior,
            par_total=par_tot,
            par_curve=par_curve,
            w_curve=w_curve,
            efs_model=efs_rf,
            runs_model=runs_rf,
            sr_model=sr_rf,
            target_center=par_tot,
            rrr_center=par_tot / 20.0,
            p2_runs_mean=runs_mean,
            p2_runs_std=runs_std,
            p2_sr_mean=sr_mean,
            p2_sr_std=sr_std,
            p2_norm_mean=-0.068,
            p2_norm_std=1.029,
            p3_norm_mean=0.159,
            p3_norm_std=1.513,
        )

