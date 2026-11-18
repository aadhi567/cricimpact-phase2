"""Stage 6B causal team strength aggregator using Stage 5C Track B ABC and confirmed lineups."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

import numpy as np
import pandas as pd

# Default category baselines for cold start and shrinkage
DEFAULT_COLD_START_ABC: Final[float] = 50.0
DEFAULT_TAIL_ABC: Final[float] = 35.0
DEFAULT_LINEUP_STD: Final[float] = 12.0

DEFAULT_BOWLING_PARS: Final[dict[str, dict[str, float]]] = {
    "IPL": {
        "powerplay_econ": 8.00,
        "middle_econ": 8.10,
        "death_econ": 10.75,
        "strike_rate": 19.20,
    },
    "T20I": {
        "powerplay_econ": 7.20,
        "middle_econ": 7.50,
        "death_econ": 9.80,
        "strike_rate": 18.50,
    },
    "OTHER_T20": {
        "powerplay_econ": 7.40,
        "middle_econ": 7.60,
        "death_econ": 9.30,
        "strike_rate": 19.00,
    },
    "ALL": {
        "powerplay_econ": 7.55,
        "middle_econ": 7.75,
        "death_econ": 10.20,
        "strike_rate": 18.85,
    },
}

BOWLING_SHRINKAGE_WEIGHT: Final[float] = 3.0


class TeamStrengthAggregator:
    """Aggregates causal player-level prior ABC features into lineup-level team strength metrics."""

    def __init__(
        self,
        playing_eleven_df: pd.DataFrame,
        causal_abc_df: pd.DataFrame,
        match_states_df: pd.DataFrame | None = None,
    ) -> None:
        """Initialize with playing eleven and Track B causal ABC data.

        Parameters
        ----------
        playing_eleven_df : pd.DataFrame
            Raw playing_eleven.csv containing player selection and batting order.
        causal_abc_df : pd.DataFrame
            Stage 5C Track B pre_match_causal_abc_features_v1.pkl.gz.
        match_states_df : pd.DataFrame, optional
            Stage 5B match states dataset used to pre-index team bowling statistics.
        """
        self._pe = playing_eleven_df.copy()
        self._abc = causal_abc_df.copy()
        self._pre_index_data(match_states_df)

    def _pre_index_data(self, df_ms: pd.DataFrame | None) -> None:
        """Pre-index player ABC and historical team bowling statistics."""
        # Standardize dates
        self._abc["match_date"] = pd.to_datetime(self._abc["match_date"]).dt.strftime("%Y-%m-%d")

        # Fast lookup mapping: (match_id, player_id) -> (abc_prior_shrunk, is_abc_cold_start)
        self.player_abc_lookup: dict[tuple[int, int], tuple[float, bool]] = {}
        for row in self._abc.itertuples(index=False):
            m_id = int(row.match_id)
            p_id = int(row.player_id)
            val = float(row.abc_prior_shrunk) if pd.notna(row.abc_prior_shrunk) else DEFAULT_COLD_START_ABC
            cold = bool(row.is_abc_cold_start) if pd.notna(row.is_abc_cold_start) else True
            self.player_abc_lookup[(m_id, p_id)] = (val, cold)

        # Pre-index team rolling historical mean ABC for Stage A fallback
        team_match_means = (
            self._abc.groupby(["match_id", "team_id", "match_date"])["abc_prior_shrunk"]
            .mean()
            .reset_index()
        )
        self.team_historical_means = team_match_means

        # Pre-index team bowling stats across phases
        if df_ms is not None:
            self._build_bowling_history(df_ms)
        else:
            self.team_bowling_history = pd.DataFrame()

    def _build_bowling_history(self, df_ms: pd.DataFrame) -> None:
        """Compile match-level bowling phase stats per team."""
        ms = df_ms[["match_id", "match_date", "bowling_team_id", "innings_phase", "team_runs", "is_legal_delivery", "is_wicket_event"]].copy()
        ms["match_date"] = pd.to_datetime(ms["match_date"]).dt.strftime("%Y-%m-%d")

        # Group by match and phase
        agg = (
            ms.groupby(["match_id", "match_date", "bowling_team_id", "innings_phase"])
            .agg(runs=("team_runs", "sum"), balls=("is_legal_delivery", "sum"), wkts=("is_wicket_event", "sum"))
            .reset_index()
        )
        self.team_bowling_history = agg

    def get_active_lineup(self, match_id: int, team_id: int) -> list[tuple[int, int, float, bool]]:
        """Extract the confirmed active 11 players for a team in a match.

        Returns list of (player_id, batting_order, abc_prior_shrunk, is_cold_start).
        """
        team_pe = self._pe[(self._pe["match_id"] == match_id) & (self._pe["team_id"] == team_id)]
        if team_pe.empty:
            return []

        # Filter played players
        played = team_pe[team_pe["is_played"].isin([True, 1, "1"])].copy()

        # Handle IPL Impact Player: If 12 players and an impact player subbed in, drop subbed-off
        if len(played) > 11:
            has_impact_on = (played["is_impact"] == 1).any()
            has_impact_off = (played["is_impact_off"] == 1).any()
            if has_impact_on and has_impact_off:
                # Remove the player who was substituted off
                played = played[played["is_impact_off"] != 1]

        # Sort by batting order
        played["order_clean"] = played["batting_order"].fillna(99.0).astype(float)
        played = played.sort_values("order_clean")

        lineup: list[tuple[int, int, float, bool]] = []
        for _, row in played.iterrows():
            p_id = int(row["player_id"])
            b_order = int(row["order_clean"]) if row["order_clean"] < 99 else len(lineup) + 1
            if (match_id, p_id) in self.player_abc_lookup:
                abc_val, is_cold = self.player_abc_lookup[(match_id, p_id)]
            else:
                abc_val, is_cold = DEFAULT_COLD_START_ABC, True
            lineup.append((p_id, b_order, abc_val, is_cold))

        return lineup

    def compute_batting_strength(
        self,
        match_id: int,
        team_id: int,
        match_date: str,
        competition_category: str = "ALL",
    ) -> dict[str, float]:
        """Compute lineup-level batting strength metrics."""
        lineup = self.get_active_lineup(match_id, team_id)

        if not lineup:
            # Stage A Fallback: Use franchise/team historical rolling average prior to match_date
            return self._compute_team_fallback_batting(team_id, match_date, competition_category)

        # Extract values
        abc_scores = [p[2] for p in lineup]
        cold_flags = [p[3] for p in lineup]

        # Top 3 (positions 1-3)
        top3_vals = abc_scores[:3]
        top3_mean = float(np.mean(top3_vals)) if top3_vals else DEFAULT_COLD_START_ABC

        # Mid 4 (positions 4-7)
        mid4_vals = abc_scores[3:7]
        mid4_mean = float(np.mean(mid4_vals)) if mid4_vals else DEFAULT_COLD_START_ABC

        # Tail (positions 8-11)
        tail_vals = abc_scores[7:11]
        tail_mean = float(np.mean(tail_vals)) if tail_vals else DEFAULT_TAIL_ABC

        # Overall Lineup Mean & Std
        lineup_mean = float(np.mean(abc_scores))
        lineup_std = float(np.std(abc_scores)) if len(abc_scores) > 1 else DEFAULT_LINEUP_STD
        cold_count = int(sum(cold_flags))

        return {
            "batting_lineup_top3_abc": float(np.clip(top3_mean, 10.0, 90.0)),
            "batting_lineup_mid4_abc": float(np.clip(mid4_mean, 10.0, 90.0)),
            "batting_lineup_tail_abc": float(np.clip(tail_mean, 10.0, 75.0)),
            "batting_lineup_mean_abc": float(np.clip(lineup_mean, 15.0, 85.0)),
            "batting_lineup_std_abc": float(np.clip(lineup_std, 0.0, 30.0)),
            "batting_cold_start_count": float(cold_count),
        }

    def _compute_team_fallback_batting(
        self,
        team_id: int,
        match_date: str,
        competition_category: str,
    ) -> dict[str, float]:
        """Compute rolling historical franchise batting rating when XI is unavailable (Stage A)."""
        target_dt = str(pd.to_datetime(match_date).strftime("%Y-%m-%d"))
        prior_team_matches = self.team_historical_means[
            (self.team_historical_means["team_id"] == team_id)
            & (self.team_historical_means["match_date"] < target_dt)
        ]

        if not prior_team_matches.empty:
            mean_val = float(prior_team_matches["abc_prior_shrunk"].mean())
        else:
            mean_val = DEFAULT_COLD_START_ABC

        return {
            "batting_lineup_top3_abc": float(np.clip(mean_val + 2.0, 10.0, 90.0)),
            "batting_lineup_mid4_abc": float(np.clip(mean_val, 10.0, 90.0)),
            "batting_lineup_tail_abc": float(np.clip(DEFAULT_TAIL_ABC, 10.0, 75.0)),
            "batting_lineup_mean_abc": float(np.clip(mean_val, 15.0, 85.0)),
            "batting_lineup_std_abc": DEFAULT_LINEUP_STD,
            "batting_cold_start_count": 11.0,
        }

    def compute_bowling_strength(
        self,
        bowling_team_id: int,
        match_date: str,
        competition_category: str = "ALL",
    ) -> dict[str, float]:
        """Compute causal bowling unit phase economy and strike rates for a team prior to match_date."""
        target_dt = str(pd.to_datetime(match_date).strftime("%Y-%m-%d"))
        cat_key = competition_category if competition_category in DEFAULT_BOWLING_PARS else "ALL"
        pars = DEFAULT_BOWLING_PARS[cat_key]

        if self.team_bowling_history.empty:
            return {
                "bowling_unit_powerplay_econ": pars["powerplay_econ"],
                "bowling_unit_middle_econ": pars["middle_econ"],
                "bowling_unit_death_econ": pars["death_econ"],
                "bowling_unit_strike_rate": pars["strike_rate"],
            }

        # Filter strictly prior matches
        prior_b = self.team_bowling_history[
            (self.team_bowling_history["bowling_team_id"] == bowling_team_id)
            & (self.team_bowling_history["match_date"] < target_dt)
        ]

        if prior_b.empty:
            return {
                "bowling_unit_powerplay_econ": pars["powerplay_econ"],
                "bowling_unit_middle_econ": pars["middle_econ"],
                "bowling_unit_death_econ": pars["death_econ"],
                "bowling_unit_strike_rate": pars["strike_rate"],
            }

        n_matches = len(prior_b["match_id"].unique())
        w = n_matches / (n_matches + BOWLING_SHRINKAGE_WEIGHT)

        # Powerplay
        pp = prior_b[prior_b["innings_phase"] == "powerplay"]
        pp_balls = float(pp["balls"].sum())
        if pp_balls >= 18:
            obs_pp_econ = float(pp["runs"].sum()) / (pp_balls / 6.0)
            shrunk_pp = w * obs_pp_econ + (1.0 - w) * pars["powerplay_econ"]
        else:
            shrunk_pp = pars["powerplay_econ"]

        # Middle
        mid = prior_b[prior_b["innings_phase"] == "middle"]
        mid_balls = float(mid["balls"].sum())
        if mid_balls >= 30:
            obs_mid_econ = float(mid["runs"].sum()) / (mid_balls / 6.0)
            shrunk_mid = w * obs_mid_econ + (1.0 - w) * pars["middle_econ"]
        else:
            shrunk_mid = pars["middle_econ"]

        # Death
        dth = prior_b[prior_b["innings_phase"] == "death"]
        dth_balls = float(dth["balls"].sum())
        if dth_balls >= 18:
            obs_dth_econ = float(dth["runs"].sum()) / (dth_balls / 6.0)
            shrunk_dth = w * obs_dth_econ + (1.0 - w) * pars["death_econ"]
        else:
            shrunk_dth = pars["death_econ"]

        # Overall Strike Rate
        tot_balls = float(prior_b["balls"].sum())
        tot_wkts = float(prior_b["wkts"].sum())
        if tot_wkts >= 5:
            obs_sr = tot_balls / tot_wkts
            shrunk_sr = w * obs_sr + (1.0 - w) * pars["strike_rate"]
        else:
            shrunk_sr = pars["strike_rate"]

        return {
            "bowling_unit_powerplay_econ": float(np.clip(shrunk_pp, 4.0, 14.0)),
            "bowling_unit_middle_econ": float(np.clip(shrunk_mid, 4.0, 14.0)),
            "bowling_unit_death_econ": float(np.clip(shrunk_dth, 6.0, 18.0)),
            "bowling_unit_strike_rate": float(np.clip(shrunk_sr, 10.0, 40.0)),
        }

    def get_match_team_strength(
        self,
        match_id: int,
        batting_team_id: int,
        bowling_team_id: int,
        match_date: str,
        competition_category: str = "ALL",
    ) -> dict[str, float]:
        """Compute all 11 Group 2 team strength features for a specific match delivery context."""
        batting_features = self.compute_batting_strength(match_id, batting_team_id, match_date, competition_category)
        bowling_features = self.compute_bowling_strength(bowling_team_id, match_date, competition_category)

        # For relative edge, compute opponent batting mean
        opp_batting = self.compute_batting_strength(match_id, bowling_team_id, match_date, competition_category)
        rel_edge = batting_features["batting_lineup_mean_abc"] - opp_batting["batting_lineup_mean_abc"]

        result = dict(batting_features)
        result.update(bowling_features)
        result["relative_batting_edge"] = float(np.clip(rel_edge, -40.0, 40.0))
        return result

