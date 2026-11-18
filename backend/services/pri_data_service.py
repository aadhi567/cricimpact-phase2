"""High-performance read-only in-memory data service for Stage PRI-2/PRI-3 Pressure Reliability Index (PRI).

Strict governance invariants:
- Consumes all 10 PRI-2 production artifacts strictly read-only, loaded once at startup.
- Zero recalculation of PRI metrics, zero shrinkage, zero composite score.
- Preserves exact stored Wilson confidence intervals and actual opportunity counts.
- Applies authoritative B8 Pakistan visibility exclusion to default overall leaderboards only,
  without mutating datasets or restricting individual player profile access.
"""

from __future__ import annotations

import json
import math
from typing import Any, Dict, List, Optional, Set
import numpy as np
import pandas as pd

from backend.core.config import settings
from ml.contribution.pressure_reliability.filters import (
    load_pakistan_player_ids,
    validate_min_opportunities,
)


def _clean_val(val: Any) -> Any:
    if val is None:
        return None
    if isinstance(val, (np.bool_, bool)):
        return bool(val)
    if isinstance(val, (np.integer, int)):
        return int(val)
    if isinstance(val, (np.floating, float)):
        if math.isnan(float(val)) or math.isinf(float(val)):
            return None
        return float(val)
    if isinstance(val, pd.Timestamp):
        return val.strftime("%Y-%m-%d")
    try:
        if pd.isna(val):
            return None
    except (TypeError, ValueError):
        pass
    return str(val)


def _row_to_clean_dict(row: Dict[str, Any]) -> Dict[str, Any]:
    return {k: _clean_val(v) for k, v in row.items()}


BATTING_SORT_COLUMNS = {
    "positive_hpc_pct": "positive_hpc_pct",
    "avg_hpc_under_pressure": "avg_hpc_under_pressure",
    "total_hpc_under_pressure": "total_hpc_under_pressure",
    "pressure_innings": "pressure_innings",
}

BOWLING_SORT_COLUMNS = {
    "positive_pcs_pct": "positive_pcs_pct",
    "avg_pcs_under_pressure": "avg_pcs_under_pressure",
    "total_pressure_contribution_rpe": "total_pressure_contribution_rpe",
    "pressure_spells": "pressure_spells",
}


class PRIDataService:
    """Singleton read-only service exposing validated PRI-2 artifacts."""

    _instance: Optional["PRIDataService"] = None

    def __init__(self) -> None:
        self.is_initialized: bool = False
        self.manifest: Dict[str, Any] = {}
        self.validation_metrics: Dict[str, Any] = {}

        # Read-only DataFrames loaded once
        self.batting_innings_df: pd.DataFrame = pd.DataFrame()
        self.batting_career_df: pd.DataFrame = pd.DataFrame()
        self.batting_season_df: pd.DataFrame = pd.DataFrame()
        self.batting_tournament_df: pd.DataFrame = pd.DataFrame()

        self.bowling_spells_df: pd.DataFrame = pd.DataFrame()
        self.bowling_career_df: pd.DataFrame = pd.DataFrame()
        self.bowling_season_df: pd.DataFrame = pd.DataFrame()
        self.bowling_tournament_df: pd.DataFrame = pd.DataFrame()

        # Authoritative B8 Pakistan visibility IDs
        self.pakistan_player_ids: Set[int] = set()

        # O(1) Player lookup indexes
        self.batting_career_by_id: Dict[int, Dict[str, Any]] = {}
        self.batting_seasons_by_id: Dict[int, List[Dict[str, Any]]] = {}
        self.batting_tournaments_by_id: Dict[int, List[Dict[str, Any]]] = {}
        self.batting_innings_by_id: Dict[int, List[Dict[str, Any]]] = {}

        self.bowling_career_by_id: Dict[int, Dict[str, Any]] = {}
        self.bowling_seasons_by_id: Dict[int, List[Dict[str, Any]]] = {}
        self.bowling_tournaments_by_id: Dict[int, List[Dict[str, Any]]] = {}
        self.bowling_spells_by_id: Dict[int, List[Dict[str, Any]]] = {}

        # Cached metadata / overview payloads
        self.overview_cache: Optional[Dict[str, Any]] = None
        self.filters_cache: Optional[Dict[str, Any]] = None
        self.artifacts_loaded_count: int = 0

    @classmethod
    def get_instance(cls) -> "PRIDataService":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def initialize(self) -> None:
        """Load all 10 PRI-2 production artifacts once and construct O(1) indexes."""
        if self.is_initialized:
            return

        required_files = [
            settings.PRI_MANIFEST_FILE,
            settings.PRI_VALIDATION_FILE,
            settings.PRI_BATTING_INNINGS_FILE,
            settings.PRI_BATTING_CAREER_FILE,
            settings.PRI_BATTING_SEASON_FILE,
            settings.PRI_BATTING_TOURNAMENT_FILE,
            settings.PRI_BOWLING_SPELLS_FILE,
            settings.PRI_BOWLING_CAREER_FILE,
            settings.PRI_BOWLING_SEASON_FILE,
            settings.PRI_BOWLING_TOURNAMENT_FILE,
        ]
        for path in required_files:
            if not path.exists():
                raise FileNotFoundError(f"Missing required PRI-2 artifact: {path}")

        with open(settings.PRI_MANIFEST_FILE, "r", encoding="utf-8") as f:
            self.manifest = json.load(f)
        with open(settings.PRI_VALIDATION_FILE, "r", encoding="utf-8") as f:
            self.validation_metrics = json.load(f)

        # Verify strict governance flags in manifest
        gov = self.manifest.get("governance", {})
        if gov.get("shrinkage_applied") is not False:
            raise RuntimeError("PRI-2 governance violation: shrinkage_applied must be False.")
        if gov.get("composite_score_applied") is not False:
            raise RuntimeError("PRI-2 governance violation: composite_score_applied must be False.")

        # Load all 8 pickled DataFrames strictly read-only
        self.batting_innings_df = pd.read_pickle(settings.PRI_BATTING_INNINGS_FILE)
        self.batting_career_df = pd.read_pickle(settings.PRI_BATTING_CAREER_FILE)
        self.batting_season_df = pd.read_pickle(settings.PRI_BATTING_SEASON_FILE)
        self.batting_tournament_df = pd.read_pickle(settings.PRI_BATTING_TOURNAMENT_FILE)

        self.bowling_spells_df = pd.read_pickle(settings.PRI_BOWLING_SPELLS_FILE)
        self.bowling_career_df = pd.read_pickle(settings.PRI_BOWLING_CAREER_FILE)
        self.bowling_season_df = pd.read_pickle(settings.PRI_BOWLING_SEASON_FILE)
        self.bowling_tournament_df = pd.read_pickle(settings.PRI_BOWLING_TOURNAMENT_FILE)

        # Verify loaded row counts match manifest
        gen = self.manifest.get("generated_outputs", {})
        count_checks = {
            "batting_pri_pressure_innings_v1.pkl.gz": len(self.batting_innings_df),
            "batting_pri_career_v1.pkl.gz": len(self.batting_career_df),
            "batting_pri_season_v1.pkl.gz": len(self.batting_season_df),
            "batting_pri_tournament_v1.pkl.gz": len(self.batting_tournament_df),
            "bowling_pri_pressure_spells_v1.pkl.gz": len(self.bowling_spells_df),
            "bowling_pri_career_v1.pkl.gz": len(self.bowling_career_df),
            "bowling_pri_season_v1.pkl.gz": len(self.bowling_season_df),
            "bowling_pri_tournament_v1.pkl.gz": len(self.bowling_tournament_df),
        }
        for fname, actual_rows in count_checks.items():
            expected_rows = gen.get(fname, {}).get("rows")
            if expected_rows is not None and actual_rows != expected_rows:
                raise ValueError(f"PRI-2 row count mismatch for {fname}: {actual_rows} != {expected_rows}")

        # Authoritative B8 Pakistan player_id set
        self.pakistan_player_ids = load_pakistan_player_ids(settings.PLAYER_MAPPING_FILE)

        # Normalize string columns used for filtering without altering numeric values
        self.batting_season_df["season"] = self.batting_season_df["season"].astype(str)
        self.batting_tournament_df["season"] = self.batting_tournament_df["season"].astype(str)
        self.bowling_season_df["season"] = self.bowling_season_df["season"].astype(str)
        self.bowling_tournament_df["season"] = self.bowling_tournament_df["season"].astype(str)

        self._build_indexes()
        self._build_caches()

        self.artifacts_loaded_count = 10
        self.is_initialized = True

    def _build_indexes(self) -> None:
        # Batting indexes (single-pass vectorized sort -> O(N) dict append)
        for rec in self.batting_career_df.to_dict(orient="records"):
            pid = int(rec["player_id"])
            self.batting_career_by_id[pid] = _row_to_clean_dict(rec)

        for rec in self.batting_season_df.sort_values("season", ascending=True).to_dict(orient="records"):
            pid = int(rec["player_id"])
            self.batting_seasons_by_id.setdefault(pid, []).append(_row_to_clean_dict(rec))

        for rec in self.batting_tournament_df.sort_values(
            ["pressure_innings", "season"], ascending=[False, False]
        ).to_dict(orient="records"):
            pid = int(rec["player_id"])
            self.batting_tournaments_by_id.setdefault(pid, []).append(_row_to_clean_dict(rec))

        bat_match_cols = [
            "player_id", "match_id", "innings", "match_date", "season", "comp_id", "comp_name",
            "team_name", "opponent_name", "runs", "balls", "fours", "sixes",
            "exp_runs", "rae", "mean_p", "peak_p", "entry_p", "hpc",
            "pressure_tier", "is_out", "t10_reason", "hpc_outcome",
        ]
        bat_match_cols = [c for c in bat_match_cols if c in self.batting_innings_df.columns]
        for rec in self.batting_innings_df.sort_values("match_date", ascending=False)[bat_match_cols].to_dict(
            orient="records"
        ):
            pid = int(rec["player_id"])
            self.batting_innings_by_id.setdefault(pid, []).append(_row_to_clean_dict(rec))

        # Bowling indexes
        for rec in self.bowling_career_df.to_dict(orient="records"):
            bid = int(rec["bowler_id"])
            self.bowling_career_by_id[bid] = _row_to_clean_dict(rec)

        for rec in self.bowling_season_df.sort_values("season", ascending=True).to_dict(orient="records"):
            bid = int(rec["bowler_id"])
            self.bowling_seasons_by_id.setdefault(bid, []).append(_row_to_clean_dict(rec))

        for rec in self.bowling_tournament_df.sort_values(
            ["pressure_spells", "season"], ascending=[False, False]
        ).to_dict(orient="records"):
            bid = int(rec["bowler_id"])
            self.bowling_tournaments_by_id.setdefault(bid, []).append(_row_to_clean_dict(rec))

        bowl_match_cols = [
            "bowler_id", "spell_id", "match_id", "innings", "match_date", "season_year", "comp_id", "comp_name",
            "team_name", "opponent_name", "overs", "legal_balls", "bowler_runs", "wickets",
            "economy", "max_over_entry_pti", "mean_over_entry_pti", "stand_breaks_count",
            "multi_wicket_overs_in_spell", "pcs_spell", "total_rpe", "total_sup",
            "total_dci", "total_swi", "total_leakage", "pcs_outcome",
            "is_wicketless_positive_spell",
        ]
        bowl_match_cols = [c for c in bowl_match_cols if c in self.bowling_spells_df.columns]
        for rec in self.bowling_spells_df.sort_values("match_date", ascending=False)[bowl_match_cols].to_dict(
            orient="records"
        ):
            bid = int(rec["bowler_id"])
            self.bowling_spells_by_id.setdefault(bid, []).append(_row_to_clean_dict(rec))

    def _build_caches(self) -> None:
        # 1. Corpus-level Overview Cache (directly from PRI-2 outputs & validation metrics)
        bat_inns = self.batting_innings_df
        bat_pos = int(bat_inns["is_positive_hpc"].sum())
        bat_neg = int(bat_inns["is_negative_hpc"].sum())
        bat_neu = int(bat_inns["is_neutral_hpc"].sum())
        bat_n = len(bat_inns)
        bat_eval = int(self.batting_career_df["has_pressure_opportunities"].sum())

        bowl_sp = self.bowling_spells_df
        bowl_pos = int(bowl_sp["is_positive_pcs"].sum())
        bowl_neg = int(bowl_sp["is_negative_pcs"].sum())
        bowl_neu = int(bowl_sp["is_neutral_pcs"].sum())
        bowl_n = len(bowl_sp)
        bowl_eval = int(self.bowling_career_df["has_pressure_opportunities"].sum())

        # Season-wise chart series (explicitly includes total_hpc & total_rpe)
        bat_season_series = []
        for yr, grp in bat_inns.groupby("season", sort=True):
            n = len(grp)
            pos = int(grp["is_positive_hpc"].sum())
            neg = int(grp["is_negative_hpc"].sum())
            neu = int(grp["is_neutral_hpc"].sum())
            bat_season_series.append({
                "season": str(yr),
                "pressure_innings": int(n),
                "positive_hpc_innings": pos,
                "negative_hpc_innings": neg,
                "neutral_hpc_innings": neu,
                "positive_hpc_pct": round((pos / n) * 100.0, 2) if n else None,
                "avg_hpc_under_pressure": round(float(grp["hpc"].mean()), 4) if n else None,
                "total_hpc_under_pressure": round(float(grp["hpc"].sum()), 2) if n else 0.0,
            })

        bowl_season_series = []
        for yr, grp in bowl_sp.groupby("season_year", sort=True):
            n = len(grp)
            pos = int(grp["is_positive_pcs"].sum())
            neg = int(grp["is_negative_pcs"].sum())
            neu = int(grp["is_neutral_pcs"].sum())
            bowl_season_series.append({
                "season": str(yr),
                "pressure_spells": int(n),
                "positive_pcs_spells": pos,
                "negative_pcs_spells": neg,
                "neutral_pcs_spells": neu,
                "positive_pcs_pct": round((pos / n) * 100.0, 2) if n else None,
                "avg_pcs_under_pressure": round(float(grp["pcs_spell"].mean()), 2) if n else None,
                "total_pressure_contribution_rpe": round(float(grp["total_rpe"].sum()), 2) if n else 0.0,
            })

        # Scatter summaries (Reliability vs Opportunity Count — default overall visibility, >= 3 opps for readability)
        bat_vis = self._apply_pakistan_visibility(self.batting_career_df, "player_id", exclude_pakistan=True)
        bat_sc_df = bat_vis[bat_vis["pressure_innings"] >= 3]
        bat_scatter = [
            {
                "player_id": int(r["player_id"]),
                "batter_name": str(r["batter_name"]),
                "primary_team": _clean_val(r["primary_team"]),
                "pressure_innings": int(r["pressure_innings"]),
                "positive_hpc_pct": _clean_val(r["positive_hpc_pct"]),
                "avg_hpc_under_pressure": _clean_val(r["avg_hpc_under_pressure"]),
                "wilson_ci95_low": _clean_val(r["wilson_ci95_low"]),
                "wilson_ci95_high": _clean_val(r["wilson_ci95_high"]),
                "sample_confidence_tier": str(r["sample_confidence_tier"]),
            }
            for r in bat_sc_df.to_dict(orient="records")
        ]

        bowl_vis = self._apply_pakistan_visibility(self.bowling_career_df, "bowler_id", exclude_pakistan=True)
        bowl_sc_df = bowl_vis[bowl_vis["pressure_spells"] >= 3]
        bowl_scatter = [
            {
                "bowler_id": int(r["bowler_id"]),
                "bowler_name": str(r["bowler_name"]),
                "primary_team": _clean_val(r["primary_team"]),
                "pressure_spells": int(r["pressure_spells"]),
                "positive_pcs_pct": _clean_val(r["positive_pcs_pct"]),
                "avg_pcs_under_pressure": _clean_val(r["avg_pcs_under_pressure"]),
                "wilson_ci95_low": _clean_val(r["wilson_ci95_low"]),
                "wilson_ci95_high": _clean_val(r["wilson_ci95_high"]),
                "sample_confidence_tier": str(r["sample_confidence_tier"]),
            }
            for r in bowl_sc_df.to_dict(orient="records")
        ]

        self.overview_cache = {
            "status": "success",
            "scope": "corpus_level",
            "note": "Corpus-level aggregate statistics across 798 T20 matches (2022–2026). These are dataset-wide summaries, not individual player ratings.",
            "methodology": {
                "stage": self.manifest.get("stage"),
                "methodology_id": self.manifest.get("methodology_id"),
                "shrinkage_applied": False,
                "composite_score_applied": False,
                "batting_definition": "T10: mean_p >= 40 OR peak_p >= 60 (DNB strictly excluded)",
                "bowling_definition": "EXO_2: max_over_entry_pti >= 35 AND legal_balls >= 12 (exogenous pre-over threat)",
            },
            "batting": {
                "scope_label": "Corpus-Level Batting Statistics",
                "total_matches": int(self.manifest["batting_audit_summary"]["source_matches"]),
                "total_batted_stints": int(self.manifest["batting_audit_summary"]["source_batted_stints"]),
                "dnb_stints_excluded": int(self.manifest["batting_audit_summary"]["source_dnb_stints"]),
                "total_qualifying_pressure_innings": bat_n,
                "evaluated_batters": bat_eval,
                "total_career_batters": int(len(self.batting_career_df)),
                "zero_opportunity_batters": int(len(self.batting_career_df) - bat_eval),
                "overall_positive_hpc_pct": round((bat_pos / bat_n) * 100.0, 2) if bat_n else 0.0,
                "avg_hpc_under_pressure": round(float(bat_inns["hpc"].mean()), 4) if bat_n else 0.0,
                "total_hpc_under_pressure": round(float(bat_inns["hpc"].sum()), 2) if bat_n else 0.0,
                "positive_pressure_innings": bat_pos,
                "negative_pressure_innings": bat_neg,
                "neutral_pressure_innings": bat_neu,
                "season_series": bat_season_series,
                "scatter_points": bat_scatter,
            },
            "bowling": {
                "scope_label": "Corpus-Level Bowling Statistics",
                "total_matches": int(self.manifest["bowling_audit_summary"]["source_matches"]),
                "total_spells": int(self.manifest["bowling_audit_summary"]["source_total_spells"]),
                "total_deliveries": int(self.manifest["bowling_audit_summary"]["source_deliveries"]),
                "total_qualifying_pressure_spells": bowl_n,
                "evaluated_bowlers": bowl_eval,
                "total_career_bowlers": int(len(self.bowling_career_df)),
                "zero_opportunity_bowlers": int(len(self.bowling_career_df) - bowl_eval),
                "overall_positive_pcs_pct": round((bowl_pos / bowl_n) * 100.0, 2) if bowl_n else 0.0,
                "avg_pcs_under_pressure": round(float(bowl_sp["pcs_spell"].mean()), 2) if bowl_n else 50.0,
                "total_pressure_contribution_rpe": round(float(bowl_sp["total_rpe"].sum()), 2) if bowl_n else 0.0,
                "positive_pressure_spells": bowl_pos,
                "negative_pressure_spells": bowl_neg,
                "neutral_pressure_spells": bowl_neu,
                "season_series": bowl_season_series,
                "scatter_points": bowl_scatter,
            },
        }

        # 2. Filters Metadata Cache
        seasons = sorted(
            set(self.batting_season_df["season"].unique()).union(set(self.bowling_season_df["season"].unique())),
            reverse=True,
        )

        bat_t_grp = (
            self.batting_tournament_df.groupby(["comp_id", "comp_name"], as_index=False)
            .agg(
                season=("season", "min"),
                pressure_innings=("pressure_innings", "sum"),
                evaluated_players=("has_pressure_opportunities", "sum"),
            )
            .sort_values(["pressure_innings", "comp_name"], ascending=[False, True])
        )
        bat_tournaments = [
            {
                "comp_id": int(r["comp_id"]),
                "comp_name": str(r["comp_name"]),
                "season": str(r["season"]),
                "pressure_innings": int(r["pressure_innings"]),
                "evaluated_players": int(r["evaluated_players"]),
            }
            for r in bat_t_grp.to_dict(orient="records")
        ]

        bowl_t_grp = (
            self.bowling_tournament_df.groupby(["comp_id", "comp_name"], as_index=False)
            .agg(
                season=("season", "min"),
                pressure_spells=("pressure_spells", "sum"),
                evaluated_players=("has_pressure_opportunities", "sum"),
            )
            .sort_values(["pressure_spells", "comp_name"], ascending=[False, True])
        )
        bowl_tournaments = [
            {
                "comp_id": int(r["comp_id"]),
                "comp_name": str(r["comp_name"]),
                "season": str(r["season"]),
                "pressure_spells": int(r["pressure_spells"]),
                "evaluated_players": int(r["evaluated_players"]),
            }
            for r in bowl_t_grp.to_dict(orient="records")
        ]

        bat_teams = sorted(
            t for t in self.batting_career_df["primary_team"].dropna().astype(str).unique() if t.strip()
        )
        bowl_teams = sorted(
            t for t in self.bowling_career_df["primary_team"].dropna().astype(str).unique() if t.strip()
        )

        # Compact player lists for comparison dropdowns (all evaluated players, ordered by opportunities desc)
        bat_players_sel = [
            {
                "player_id": int(r["player_id"]),
                "batter_name": str(r["batter_name"]),
                "primary_team": _clean_val(r["primary_team"]),
                "pressure_innings": int(r["pressure_innings"]),
                "positive_hpc_pct": _clean_val(r["positive_hpc_pct"]),
            }
            for r in self.batting_career_df[self.batting_career_df["has_pressure_opportunities"]]
            .sort_values(["pressure_innings", "batter_name"], ascending=[False, True])
            .to_dict(orient="records")
        ]
        bowl_players_sel = [
            {
                "bowler_id": int(r["bowler_id"]),
                "bowler_name": str(r["bowler_name"]),
                "primary_team": _clean_val(r["primary_team"]),
                "pressure_spells": int(r["pressure_spells"]),
                "positive_pcs_pct": _clean_val(r["positive_pcs_pct"]),
            }
            for r in self.bowling_career_df[self.bowling_career_df["has_pressure_opportunities"]]
            .sort_values(["pressure_spells", "bowler_name"], ascending=[False, True])
            .to_dict(orient="records")
        ]

        self.filters_cache = {
            "status": "success",
            "seasons": seasons,
            "batting_tournaments": bat_tournaments,
            "bowling_tournaments": bowl_tournaments,
            "batting_teams": bat_teams,
            "bowling_teams": bowl_teams,
            "batting_players": bat_players_sel,
            "bowling_players": bowl_players_sel,
        }

    def _apply_pakistan_visibility(
        self,
        df: pd.DataFrame,
        id_col: str,
        exclude_pakistan: bool = True,
    ) -> pd.DataFrame:
        """Apply authoritative B8 Pakistan exclusion by verified player_id only."""
        if not exclude_pakistan or len(df) == 0:
            return df.copy()

        def _is_verified_pak(val: Any) -> bool:
            if pd.isna(val):
                return False
            try:
                return int(val) in self.pakistan_player_ids
            except (ValueError, TypeError):
                return False

        return df[~df[id_col].map(_is_verified_pak)].copy()

    def get_health(self) -> Dict[str, Any]:
        return {
            "status": "healthy" if self.is_initialized else "uninitialized",
            "service_initialized": self.is_initialized,
            "artifacts_loaded": self.artifacts_loaded_count,
            "stage": self.manifest.get("stage"),
            "methodology_id": self.manifest.get("methodology_id"),
            "governance": self.manifest.get("governance"),
            "counts": {
                "batting_pressure_innings": int(len(self.batting_innings_df)),
                "batting_career_players": int(len(self.batting_career_df)),
                "batting_season_rows": int(len(self.batting_season_df)),
                "batting_tournament_rows": int(len(self.batting_tournament_df)),
                "bowling_pressure_spells": int(len(self.bowling_spells_df)),
                "bowling_career_players": int(len(self.bowling_career_df)),
                "bowling_season_rows": int(len(self.bowling_season_df)),
                "bowling_tournament_rows": int(len(self.bowling_tournament_df)),
                "authoritative_pakistan_ids": int(len(self.pakistan_player_ids)),
            },
        }

    def get_overview(self) -> Dict[str, Any]:
        return self.overview_cache or {}

    def get_filters(self) -> Dict[str, Any]:
        return self.filters_cache or {}

    def _query_leaderboard(
        self,
        df: pd.DataFrame,
        *,
        domain: str,
        scope: str,
        id_col: str,
        name_col: str,
        count_col: str,
        allowed_sort: Dict[str, str],
        default_sort: str,
        min_opportunities: Any = 0,
        season: Optional[str] = None,
        tournament: Optional[str] = None,
        team: Optional[str] = None,
        search: Optional[str] = None,
        sort_by: Optional[str] = None,
        order: str = "desc",
        page: int = 1,
        page_size: int = 20,
        exclude_pakistan: bool = True,
    ) -> Dict[str, Any]:
        # 1. Strict custom integer >= 0 validation
        min_n = validate_min_opportunities(min_opportunities)
        effective_min = max(1, min_n)  # Players with 0 qualifying opps never receive artificial 0%

        sort_key = sort_by or default_sort
        if sort_key not in allowed_sort:
            raise ValueError(f"Unsupported sort_by '{sort_key}'. Allowed: {sorted(allowed_sort.keys())}")
        sort_col = allowed_sort[sort_key]

        if order not in ("asc", "desc"):
            raise ValueError(f"Invalid order '{order}'. Must be 'asc' or 'desc'.")

        # 2. Apply authoritative B8 Pakistan visibility policy on default overall leaderboards
        work = self._apply_pakistan_visibility(df, id_col=id_col, exclude_pakistan=exclude_pakistan)

        # 3. Scope-specific filters (strictly from authoritative PRI-2 table, never recomputed)
        if scope == "season" and season and str(season).strip().lower() != "all":
            work = work[work["season"].astype(str) == str(season).strip()]

        if scope == "tournament" and tournament and str(tournament).strip().lower() != "all":
            t_str = str(tournament).strip()
            if t_str.isdigit():
                work = work[work["comp_id"].astype(int) == int(t_str)]
            else:
                work = work[work["comp_name"].astype(str).str.lower() == t_str.lower()]

        if team and str(team).strip().lower() != "all":
            team_q = str(team).strip().lower()
            work = work[work["primary_team"].fillna("").astype(str).str.lower() == team_q]

        if search and str(search).strip():
            q = str(search).strip().lower()
            name_match = work[name_col].fillna("").astype(str).str.lower().str.contains(q, regex=False)
            team_match = work["primary_team"].fillna("").astype(str).str.lower().str.contains(q, regex=False)
            if "comp_name" in work.columns:
                comp_match = work["comp_name"].fillna("").astype(str).str.lower().str.contains(q, regex=False)
                work = work[name_match | team_match | comp_match]
            else:
                work = work[name_match | team_match]

        # 4. Apply custom minimum opportunity filter (always excluding 0-opportunity rows)
        total_before_min = int((work[count_col] >= 1).sum())
        work = work[work[count_col] >= effective_min].copy()

        # 5. Deterministic sorting (never mutates underlying values; no hidden composite score)
        asc = order == "asc"
        secondary_col = (
            "avg_hpc_under_pressure" if domain == "batting" else "avg_pcs_under_pressure"
        )
        sort_cols = [sort_col]
        sort_dirs = [asc]
        if secondary_col != sort_col:
            sort_cols.append(secondary_col)
            sort_dirs.append(False)
        if count_col != sort_col:
            sort_cols.append(count_col)
            sort_dirs.append(False)
        sort_cols.append(name_col)
        sort_dirs.append(True)

        if len(work) > 0:
            work = work.sort_values(by=sort_cols, ascending=sort_dirs, na_position="last").reset_index(drop=True)
            work["rank"] = range(1, len(work) + 1)

        total_items = int(len(work))
        total_pages = max(1, math.ceil(total_items / page_size)) if total_items > 0 else 1
        start = (page - 1) * page_size
        end = start + page_size
        page_df = work.iloc[start:end]

        items = [_row_to_clean_dict(r) for r in page_df.to_dict(orient="records")]

        return {
            "status": "success",
            "domain": domain,
            "scope": scope,
            "governance": {
                "shrinkage_applied": False,
                "composite_score_applied": False,
                "pakistan_excluded_default": exclude_pakistan,
                "min_opportunities_requested": min_n,
                "effective_min_opportunities": effective_min,
            },
            "filters_applied": {
                "min_opportunities": min_n,
                "season": season if scope == "season" else None,
                "tournament": tournament if scope == "tournament" else None,
                "team": team,
                "search": search,
                "sort_by": sort_key,
                "order": order,
            },
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total_items": total_items,
                "total_pages": total_pages,
                "has_next": page < total_pages,
                "has_prev": page > 1,
                "total_evaluated_before_min_filter": total_before_min,
            },
            "items": items,
        }

    # --- Batting Leaderboard Endpoints ---
    def get_batting_career(self, **kwargs: Any) -> Dict[str, Any]:
        return self._query_leaderboard(
            self.batting_career_df,
            domain="batting",
            scope="career",
            id_col="player_id",
            name_col="batter_name",
            count_col="pressure_innings",
            allowed_sort=BATTING_SORT_COLUMNS,
            default_sort="positive_hpc_pct",
            **kwargs,
        )

    def get_batting_season(self, **kwargs: Any) -> Dict[str, Any]:
        return self._query_leaderboard(
            self.batting_season_df,
            domain="batting",
            scope="season",
            id_col="player_id",
            name_col="batter_name",
            count_col="pressure_innings",
            allowed_sort=BATTING_SORT_COLUMNS,
            default_sort="positive_hpc_pct",
            **kwargs,
        )

    def get_batting_tournament(self, **kwargs: Any) -> Dict[str, Any]:
        return self._query_leaderboard(
            self.batting_tournament_df,
            domain="batting",
            scope="tournament",
            id_col="player_id",
            name_col="batter_name",
            count_col="pressure_innings",
            allowed_sort=BATTING_SORT_COLUMNS,
            default_sort="positive_hpc_pct",
            **kwargs,
        )

    # --- Bowling Leaderboard Endpoints ---
    def get_bowling_career(self, **kwargs: Any) -> Dict[str, Any]:
        return self._query_leaderboard(
            self.bowling_career_df,
            domain="bowling",
            scope="career",
            id_col="bowler_id",
            name_col="bowler_name",
            count_col="pressure_spells",
            allowed_sort=BOWLING_SORT_COLUMNS,
            default_sort="positive_pcs_pct",
            **kwargs,
        )

    def get_bowling_season(self, **kwargs: Any) -> Dict[str, Any]:
        return self._query_leaderboard(
            self.bowling_season_df,
            domain="bowling",
            scope="season",
            id_col="bowler_id",
            name_col="bowler_name",
            count_col="pressure_spells",
            allowed_sort=BOWLING_SORT_COLUMNS,
            default_sort="positive_pcs_pct",
            **kwargs,
        )

    def get_bowling_tournament(self, **kwargs: Any) -> Dict[str, Any]:
        return self._query_leaderboard(
            self.bowling_tournament_df,
            domain="bowling",
            scope="tournament",
            id_col="bowler_id",
            name_col="bowler_name",
            count_col="pressure_spells",
            allowed_sort=BOWLING_SORT_COLUMNS,
            default_sort="positive_pcs_pct",
            **kwargs,
        )

    # --- Individual Player Profiles (ALL players accessible, including Pakistan) ---
    def get_batting_player_profile(self, player_id: int) -> Optional[Dict[str, Any]]:
        career = self.batting_career_by_id.get(int(player_id))
        if career is None:
            return None
        seasons = self.batting_seasons_by_id.get(int(player_id), [])
        tournaments = self.batting_tournaments_by_id.get(int(player_id), [])
        matches = self.batting_innings_by_id.get(int(player_id), [])
        return {
            "status": "success",
            "domain": "batting",
            "governance": {
                "shrinkage_applied": False,
                "composite_score_applied": False,
                "definition": "T10: mean_p >= 40 OR peak_p >= 60 (DNB strictly excluded)",
            },
            "career": career,
            "seasons": seasons,
            "tournaments": tournaments,
            "pressure_innings": matches,
        }

    def get_bowling_player_profile(self, bowler_id: int) -> Optional[Dict[str, Any]]:
        career = self.bowling_career_by_id.get(int(bowler_id))
        if career is None:
            return None
        seasons = self.bowling_seasons_by_id.get(int(bowler_id), [])
        tournaments = self.bowling_tournaments_by_id.get(int(bowler_id), [])
        spells = self.bowling_spells_by_id.get(int(bowler_id), [])
        return {
            "status": "success",
            "domain": "bowling",
            "governance": {
                "shrinkage_applied": False,
                "composite_score_applied": False,
                "definition": "EXO_2: max_over_entry_pti >= 35 AND legal_balls >= 12",
            },
            "career": career,
            "seasons": seasons,
            "tournaments": tournaments,
            "pressure_spells": spells,
        }

    # --- Up-to-5 Player Comparison (strictly domain-separated) ---
    def compare_batters(self, player_ids: List[int]) -> Dict[str, Any]:
        resolved: List[Dict[str, Any]] = []
        missing: List[int] = []
        seen: Set[int] = set()
        for pid in player_ids:
            if pid in seen:
                continue
            seen.add(pid)
            career = self.batting_career_by_id.get(pid)
            if career is None:
                missing.append(pid)
            else:
                resolved.append({
                    **career,
                    "seasons": self.batting_seasons_by_id.get(pid, []),
                })
        return {
            "status": "success",
            "domain": "batting",
            "governance": {"shrinkage_applied": False, "composite_score_applied": False},
            "count": len(resolved),
            "missing_ids": missing,
            "players": resolved,
        }

    def compare_bowlers(self, bowler_ids: List[int]) -> Dict[str, Any]:
        resolved: List[Dict[str, Any]] = []
        missing: List[int] = []
        seen: Set[int] = set()
        for bid in bowler_ids:
            if bid in seen:
                continue
            seen.add(bid)
            career = self.bowling_career_by_id.get(bid)
            if career is None:
                missing.append(bid)
            else:
                resolved.append({
                    **career,
                    "seasons": self.bowling_seasons_by_id.get(bid, []),
                })
        return {
            "status": "success",
            "domain": "bowling",
            "governance": {"shrinkage_applied": False, "composite_score_applied": False},
            "count": len(resolved),
            "missing_ids": missing,
            "players": resolved,
        }
