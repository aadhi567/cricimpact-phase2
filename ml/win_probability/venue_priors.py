"""Stage 6B causal venue priors calculator with empirical Bayesian shrinkage."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

import numpy as np
import pandas as pd

# Empirical category baseline priors grounded in 2022-2026 standard data
CATEGORY_VENUE_DEFAULTS: Final[dict[str, dict[str, float]]] = {
    "IPL": {
        "venue_avg_first_inn_score": 186.5,
        "venue_chase_win_pct": 0.524,
        "venue_avg_death_rr": 10.75,
        "venue_pace_spin_wicket_ratio": 1.80,
    },
    "T20I": {
        "venue_avg_first_inn_score": 171.4,
        "venue_chase_win_pct": 0.484,
        "venue_avg_death_rr": 9.83,
        "venue_pace_spin_wicket_ratio": 1.75,
    },
    "OTHER_T20": {
        "venue_avg_first_inn_score": 155.5,
        "venue_chase_win_pct": 0.571,
        "venue_avg_death_rr": 9.29,
        "venue_pace_spin_wicket_ratio": 1.75,
    },
    "ALL": {
        "venue_avg_first_inn_score": 177.5,
        "venue_chase_win_pct": 0.505,
        "venue_avg_death_rr": 10.23,
        "venue_pace_spin_wicket_ratio": 1.78,
    },
}

SHRINKAGE_PRIOR_WEIGHT: Final[float] = 5.0


@dataclass(frozen=True)
class VenuePriorRecord:
    """Historical venue priors computed causally for a specific match date."""

    venue_id: int
    match_date: str
    sample_size: int
    venue_avg_first_inn_score: float
    venue_chase_win_pct: float
    venue_avg_death_rr: float
    venue_pace_spin_wicket_ratio: float


class VenuePriorsCalculator:
    """Calculates strictly causal historical venue metrics with empirical Bayesian shrinkage.

    Enforces source.match_date < target.match_date and excludes same-day matches.
    """

    def __init__(self, match_states_df: pd.DataFrame, ball_by_ball_df: pd.DataFrame | None = None) -> None:
        """Initialize and pre-index match-level venue outcomes."""
        self._build_match_aggregates(match_states_df, ball_by_ball_df)

    def _build_match_aggregates(self, df_ms: pd.DataFrame, bbb_df: pd.DataFrame | None) -> None:
        """Pre-index match-level statistics needed for causal venue lookups."""
        # 1. First innings totals per match
        inns1 = df_ms[df_ms["innings"] == 1]
        self.m1_scores = (
            inns1.groupby(["match_id", "match_date", "venue_id", "competition_category"])["score_after"]
            .max()
            .reset_index()
            .rename(columns={"score_after": "first_inn_total"})
        )
        self.m1_scores["match_date"] = pd.to_datetime(self.m1_scores["match_date"]).dt.strftime("%Y-%m-%d")

        # 2. Match chase outcomes (chase won = 1 if chasing team won)
        matches = df_ms[["match_id", "match_date", "venue_id", "competition_category", "win_team_id_raw"]].drop_duplicates()
        chase_teams = df_ms[df_ms["innings"] == 2][["match_id", "batting_team_id"]].drop_duplicates()
        chase_df = matches.merge(chase_teams, on="match_id")
        chase_df["chase_won"] = (chase_df["win_team_id_raw"] == chase_df["batting_team_id"]).astype(int)
        chase_df["match_date"] = pd.to_datetime(chase_df["match_date"]).dt.strftime("%Y-%m-%d")
        self.chase_outcomes = chase_df[["match_id", "match_date", "venue_id", "competition_category", "chase_won"]]

        # 3. Death overs run rate per match
        death = df_ms[df_ms["innings_phase"] == "death"]
        if not death.empty:
            death_stats = (
                death.groupby(["match_id", "match_date", "venue_id", "competition_category"])
                .agg(death_runs=("team_runs", "sum"), death_balls=("is_legal_delivery", "sum"))
                .reset_index()
            )
            death_stats["match_date"] = pd.to_datetime(death_stats["match_date"]).dt.strftime("%Y-%m-%d")
            self.death_stats = death_stats
        else:
            self.death_stats = pd.DataFrame(columns=["match_id", "match_date", "venue_id", "competition_category", "death_runs", "death_balls"])

        # 4. Pace vs spin wicket breakdown
        if bbb_df is not None and "pace_or_spin" in bbb_df.columns:
            std_match_ids = set(self.m1_scores["match_id"].unique())
            wkts = bbb_df[bbb_df["match_id"].isin(std_match_ids) & (bbb_df["is_wicket"] == 1)].copy()
            wkts["is_pace"] = (wkts["pace_or_spin"].astype(str).str.lower() == "pace").astype(int)
            wkts["is_spin"] = (wkts["pace_or_spin"].astype(str).str.lower() == "spin").astype(int)
            # Link match_date and venue_id
            m_meta = self.m1_scores[["match_id", "match_date", "venue_id"]].drop_duplicates()
            wkts = wkts.merge(m_meta, on="match_id", how="inner")
            self.wkt_breakdown = wkts.groupby(["match_id", "match_date", "venue_id"]).agg(
                pace_wkts=("is_pace", "sum"),
                spin_wkts=("is_spin", "sum"),
            ).reset_index()
        else:
            self.wkt_breakdown = pd.DataFrame(columns=["match_id", "match_date", "venue_id", "pace_wkts", "spin_wkts"])

    def get_venue_priors(
        self,
        venue_id: int,
        target_match_date: str,
        competition_category: str = "ALL",
    ) -> dict[str, float]:
        """Compute strictly causal venue priors for a target match date.

        Parameters
        ----------
        venue_id : int
            The venue identifier.
        target_match_date : str
            ISO string date ('YYYY-MM-DD'). Only matches with match_date < target_match_date are used.
        competition_category : str
            Tournament category ('IPL', 'T20I', 'OTHER_T20', or 'ALL').
        """
        # Formatted target date
        target_dt = str(pd.to_datetime(target_match_date).strftime("%Y-%m-%d"))

        # Category baseline lookup
        cat_key = competition_category if competition_category in CATEGORY_VENUE_DEFAULTS else "ALL"
        defaults = CATEGORY_VENUE_DEFAULTS[cat_key]

        # 1. Filter prior matches for this venue strictly before target date
        v_scores = self.m1_scores[
            (self.m1_scores["venue_id"] == venue_id) & (self.m1_scores["match_date"] < target_dt)
        ]
        n_matches = len(v_scores)

        # First innings score
        if n_matches > 0:
            obs_score = float(v_scores["first_inn_total"].mean())
            # Bayesian shrinkage
            w = n_matches / (n_matches + SHRINKAGE_PRIOR_WEIGHT)
            shrunk_score = w * obs_score + (1.0 - w) * defaults["venue_avg_first_inn_score"]
        else:
            shrunk_score = defaults["venue_avg_first_inn_score"]

        # 2. Chase win rate
        v_chase = self.chase_outcomes[
            (self.chase_outcomes["venue_id"] == venue_id) & (self.chase_outcomes["match_date"] < target_dt)
        ]
        n_chase = len(v_chase)
        if n_chase > 0:
            obs_chase = float(v_chase["chase_won"].mean())
            w = n_chase / (n_chase + SHRINKAGE_PRIOR_WEIGHT)
            shrunk_chase = w * obs_chase + (1.0 - w) * defaults["venue_chase_win_pct"]
        else:
            shrunk_chase = defaults["venue_chase_win_pct"]

        # 3. Death overs run rate
        v_death = self.death_stats[
            (self.death_stats["venue_id"] == venue_id) & (self.death_stats["match_date"] < target_dt)
        ]
        tot_death_balls = int(v_death["death_balls"].sum()) if not v_death.empty else 0
        if tot_death_balls >= 30:  # At least 5 death overs recorded
            tot_death_runs = float(v_death["death_runs"].sum())
            obs_death_rr = tot_death_runs / (tot_death_balls / 6.0)
            n_death_matches = len(v_death)
            w = n_death_matches / (n_death_matches + SHRINKAGE_PRIOR_WEIGHT)
            shrunk_death_rr = w * obs_death_rr + (1.0 - w) * defaults["venue_avg_death_rr"]
        else:
            shrunk_death_rr = defaults["venue_avg_death_rr"]

        # 4. Pace vs spin ratio
        v_wkts = self.wkt_breakdown[
            (self.wkt_breakdown["venue_id"] == venue_id) & (self.wkt_breakdown["match_date"] < target_dt)
        ]
        tot_pace = float(v_wkts["pace_wkts"].sum()) if not v_wkts.empty else 0.0
        tot_spin = float(v_wkts["spin_wkts"].sum()) if not v_wkts.empty else 0.0
        if tot_spin >= 5:
            obs_ratio = tot_pace / max(1.0, tot_spin)
            n_wkt_matches = len(v_wkts)
            w = n_wkt_matches / (n_wkt_matches + SHRINKAGE_PRIOR_WEIGHT)
            shrunk_ratio = w * obs_ratio + (1.0 - w) * defaults["venue_pace_spin_wicket_ratio"]
        else:
            shrunk_ratio = defaults["venue_pace_spin_wicket_ratio"]

        # Clamping to valid physical boundaries
        return {
            "venue_avg_first_inn_score": float(np.clip(shrunk_score, 110.0, 240.0)),
            "venue_chase_win_pct": float(np.clip(shrunk_chase, 0.20, 0.80)),
            "venue_avg_death_rr": float(np.clip(shrunk_death_rr, 6.0, 16.0)),
            "venue_pace_spin_wicket_ratio": float(np.clip(shrunk_ratio, 0.2, 5.0)),
            "venue_prior_sample_size": float(n_matches),
        }

