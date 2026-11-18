"""High-performance in-memory data service for Stage B4 Bowling Contribution Model outputs."""

import json
import math
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple, Any
import numpy as np
import pandas as pd

from backend.core.config import settings
from backend.schemas.bowling import (
    BCSDistribution,
    BowlerComparisonItem,
    BowlerComparisonResponse,
    BowlerLeaderboardItem,
    BowlingDashboardResponse,
    BowlingLeaderboardResponse,
    BowlerProfileResponse,
    BowlerSpellSummary,
    BowlingTournamentsResponse,
    DeliveryDetailItem,
    MatchListItem,
    MatchListResponse,
    MatchSpellsResponse,
    PaginationMetadata,
    PhaseBreakdownItem,
    SeasonRecord,
    SpellDeliveriesResponse,
    SpellDetailItem,
    TopPerformerSummary,
    TopSpellSummary,
    TournamentItem,
)


def _clean_float(val: Any, decimals: int = 2) -> Optional[float]:
    """Safely convert numpy/pandas float to python float, replacing NaN/Inf with None."""
    if val is None or pd.isna(val) or np.isinf(val):
        return None
    return round(float(val), decimals)


def _clean_int(val: Any) -> int:
    """Safely convert numpy/pandas integer to python int."""
    if val is None or pd.isna(val):
        return 0
    return int(val)


def _clean_str(val: Any) -> Optional[str]:
    """Safely convert value to string or None if NaN/None."""
    if val is None or pd.isna(val):
        return None
    return str(val)


def _format_overs(legal_balls: int) -> Tuple[float, str]:
    """Format legal balls into decimal overs (e.g. 4.0) and cricket string notation (e.g. '4.0', '3.5')."""
    overs_completed = legal_balls // 6
    remaining_balls = legal_balls % 6
    notation_float = round(overs_completed + (remaining_balls / 10.0), 1)
    notation_str = f"{overs_completed}.{remaining_balls}"
    return notation_float, notation_str


class BowlingDataService:
    """Singleton service providing read-only access to BCM production outputs."""

    _instance: Optional["BowlingDataService"] = None

    def __init__(self):
        self.is_initialized: bool = False
        self.manifest: Dict[str, Any] = {}
        
        # Raw dataframes
        self.career_df: pd.DataFrame = pd.DataFrame()
        self.season_df: pd.DataFrame = pd.DataFrame()
        self.spells_df: pd.DataFrame = pd.DataFrame()
        self.deliv_df: pd.DataFrame = pd.DataFrame()
        
        # Name lookup maps
        self.player_names: Dict[int, str] = {}
        self.team_names: Dict[int, str] = {}
        
        # In-memory indexes
        self.career_by_id: Dict[int, Dict[str, Any]] = {}
        self.season_by_player: Dict[int, List[Dict[str, Any]]] = {}
        self.spells_by_player: Dict[int, List[Dict[str, Any]]] = {}
        self.spells_by_match: Dict[int, List[Dict[str, Any]]] = {}
        self.spells_by_id: Dict[str, Dict[str, Any]] = {}
        self.deliv_indices_by_spell: Dict[str, np.ndarray] = {}
        
        # Pre-aggregated tables
        self.bowler_phase_df: pd.DataFrame = pd.DataFrame()
        self.spell_phase_df: pd.DataFrame = pd.DataFrame()
        self.corpus_phase_summary: List[PhaseBreakdownItem] = []
        
        # Precomputed Dashboard & Matches Cache
        self.dashboard_cache: Optional[BowlingDashboardResponse] = None
        self.matches_list_cache: List[MatchListItem] = []
        self.matches_dict_cache: Dict[int, MatchListItem] = {}

        # Tournament & Nationality Filtering
        self.pakistan_player_ids: Set[int] = set()
        self.competitions_df: pd.DataFrame = pd.DataFrame()
        self.matches_df: pd.DataFrame = pd.DataFrame()
        self.match_to_comp: Dict[int, int] = {}
        self.tournaments_list: List[TournamentItem] = []
        self.comp_by_id: Dict[int, Dict[str, Any]] = {}

    @classmethod
    def get_instance(cls) -> "BowlingDataService":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def initialize(self) -> None:
        """Load datasets, verify integrity against manifest, and build fast in-memory indexes."""
        if self.is_initialized:
            return

        # 1. Load manifest and verify file existence
        if not settings.MANIFEST_FILE.exists():
            raise FileNotFoundError(f"Manifest file not found at {settings.MANIFEST_FILE}")
        with open(settings.MANIFEST_FILE, "r", encoding="utf-8") as f:
            self.manifest = json.load(f)

        # 2. Load primary datasets
        self.career_df = pd.read_pickle(settings.CAREER_FILE)
        self.season_df = pd.read_pickle(settings.SEASON_FILE)
        self.spells_df = pd.read_pickle(settings.SPELLS_FILE)
        self.deliv_df = pd.read_pickle(settings.DELIVERIES_FILE)

        # Verify dataset row counts against expected production constants
        if len(self.career_df) != settings.EXPECTED_CAREER_BOWLERS:
            raise ValueError(f"Career count {len(self.career_df)} != {settings.EXPECTED_CAREER_BOWLERS}")
        if len(self.season_df) != settings.EXPECTED_SEASON_RECORDS:
            raise ValueError(f"Season count {len(self.season_df)} != {settings.EXPECTED_SEASON_RECORDS}")
        if len(self.spells_df) != settings.EXPECTED_SPELLS:
            raise ValueError(f"Spells count {len(self.spells_df)} != {settings.EXPECTED_SPELLS}")
        if len(self.deliv_df) != settings.EXPECTED_DELIVERIES:
            raise ValueError(f"Deliveries count {len(self.deliv_df)} != {settings.EXPECTED_DELIVERIES}")

        # 3. Load name mappings & Authoritative Nationality
        if settings.PLAYER_MAPPING_FILE.exists():
            mapping_df = pd.read_csv(settings.PLAYER_MAPPING_FILE)
            self.player_names = dict(zip(mapping_df["player_id"].astype(int), mapping_df["player_name"]))
            self.team_names = dict(zip(mapping_df["team_id"].astype(int), mapping_df["team_name"]))

            # Authoritatively identify players with Pakistan nationality
            # Normalized comparison against verified country representations (Pakistan, Pakistan A, PAK)
            pak_mask = mapping_df["team_name"].astype(str).str.strip().str.upper().isin(["PAKISTAN", "PAKISTAN A", "PAK"])
            self.pakistan_player_ids = set(mapping_df.loc[pak_mask, "player_id"].dropna().astype(int).unique())

        # Load authoritative competitions and matches metadata
        comp_path = settings.RAW_DIR / "competitions.csv"
        matches_path = settings.RAW_DIR / "matches.csv"
        if comp_path.exists():
            self.competitions_df = pd.read_csv(comp_path)
        if matches_path.exists():
            self.matches_df = pd.read_csv(matches_path)
            self.match_to_comp = dict(zip(self.matches_df["match_id"].astype(int), self.matches_df["comp_id"].astype(int)))
            if "comp_id" not in self.spells_df.columns:
                self.spells_df["comp_id"] = self.spells_df["match_id"].map(self.match_to_comp)

        # 4. Construct canonical spell_id in spells and deliveries
        # Spell ID convention: "{match_id}_{innings}_{bowler_id}"
        self.spells_df["spell_id"] = (
            self.spells_df["match_id"].astype(str)
            + "_"
            + self.spells_df["innings"].astype(str)
            + "_"
            + self.spells_df["bowler_id"].astype(str)
        )
        self.deliv_df["spell_id"] = (
            self.deliv_df["match_id"].astype(str)
            + "_"
            + self.deliv_df["innings"].astype(str)
            + "_"
            + self.deliv_df["bowler_id"].astype(str)
        )

        # 5. Build delivery group index for O(1) spell deliveries lookup
        self.deliv_indices_by_spell = self.deliv_df.groupby("spell_id").indices

        # 6. Precompute phase aggregations
        self._build_phase_aggregations()

        # 7. Build in-memory dictionaries
        self._build_lookup_indexes()

        # 8. Precompute Dashboard cache & Match summaries
        self._build_dashboard_cache()
        self._build_matches_cache()

        # 9. Build tournaments metadata cache
        self._build_tournaments_cache()

        self.is_initialized = True

    def _build_phase_aggregations(self) -> None:
        """Pre-aggregate deliveries by phase for corpus, per-bowler, and per-spell."""
        # 1. Corpus-level phase summary
        corpus_agg = self.deliv_df.groupby("innings_phase").agg(
            legal_balls=("is_legal_delivery", "sum"),
            runs=("bowler_runs", "sum"),
            wickets=("is_bowler_wkt", "sum"),
            dots=("dot_ball", "sum"),
            boundaries=("is_boundary_four", lambda s: int(s.sum() + self.deliv_df.loc[s.index, "is_boundary_six"].sum())),
            total_erp=("erp", "sum"),
            total_bcs=("bcs", "sum"),
            total_bwpa=("bwpa", "sum"),
            mean_leverage=("leverage", "mean"),
        ).reset_index()

        self.corpus_phase_summary = []
        for _, row in corpus_agg.iterrows():
            balls = _clean_int(row["legal_balls"])
            overs_dec, _ = _format_overs(balls)
            runs = _clean_int(row["runs"])
            wkts = _clean_int(row["wickets"])
            dots = _clean_int(row["dots"])
            bounds = _clean_int(row["boundaries"])
            econ = round((runs * 6.0 / balls), 2) if balls > 0 else 0.0
            dot_pct = round((dots * 100.0 / balls), 1) if balls > 0 else 0.0
            bound_pct = round((bounds * 100.0 / balls), 1) if balls > 0 else 0.0
            total_bcs = _clean_float(row["total_bcs"], 2) or 0.0
            bcs_per_ov = round((total_bcs / (balls / 6.0)), 2) if balls > 0 else 0.0

            self.corpus_phase_summary.append(
                PhaseBreakdownItem(
                    phase=row["innings_phase"],
                    legal_balls=balls,
                    overs=overs_dec,
                    runs=runs,
                    wickets=wkts,
                    economy=econ,
                    dot_pct=dot_pct,
                    boundary_pct=bound_pct,
                    avg_leverage=_clean_float(row["mean_leverage"], 3) or 1.0,
                    total_erp=_clean_float(row["total_erp"], 2) or 0.0,
                    total_bcs=total_bcs,
                    bcs_per_over=bcs_per_ov,
                    total_bwpa=_clean_float(row["total_bwpa"], 4) or 0.0,
                )
            )

        # 2. Per-bowler phase breakdown
        self.bowler_phase_df = self.deliv_df.groupby(["bowler_id", "innings_phase"]).agg(
            legal_balls=("is_legal_delivery", "sum"),
            runs=("bowler_runs", "sum"),
            wickets=("is_bowler_wkt", "sum"),
            dots=("dot_ball", "sum"),
            fours=("is_boundary_four", "sum"),
            sixes=("is_boundary_six", "sum"),
            total_erp=("erp", "sum"),
            total_bcs=("bcs", "sum"),
            total_bwpa=("bwpa", "sum"),
            mean_leverage=("leverage", "mean"),
        ).reset_index()
        self.bowler_phase_df["boundaries"] = self.bowler_phase_df["fours"] + self.bowler_phase_df["sixes"]

        # 3. Per-spell phase breakdown
        self.spell_phase_df = self.deliv_df.groupby(["spell_id", "innings_phase"]).agg(
            legal_balls=("is_legal_delivery", "sum"),
            runs=("bowler_runs", "sum"),
            wickets=("is_bowler_wkt", "sum"),
            dots=("dot_ball", "sum"),
            fours=("is_boundary_four", "sum"),
            sixes=("is_boundary_six", "sum"),
            total_erp=("erp", "sum"),
            total_bcs=("bcs", "sum"),
            total_bwpa=("bwpa", "sum"),
            mean_leverage=("leverage", "mean"),
        ).reset_index()
        self.spell_phase_df["boundaries"] = self.spell_phase_df["fours"] + self.spell_phase_df["sixes"]

    def _build_lookup_indexes(self) -> None:
        """Populate dictionaries for instant O(1) lookups."""
        # Career index
        for row in self.career_df.to_dict("records"):
            b_id = int(row["bowler_id"])
            self.career_by_id[b_id] = row

        # Season index
        for row in self.season_df.to_dict("records"):
            b_id = int(row["bowler_id"])
            self.season_by_player.setdefault(b_id, []).append(row)

        # Spells index
        for row in self.spells_df.to_dict("records"):
            b_id = int(row["bowler_id"])
            m_id = int(row["match_id"])
            s_id = str(row["spell_id"])
            
            self.spells_by_player.setdefault(b_id, []).append(row)
            self.spells_by_match.setdefault(m_id, []).append(row)
            self.spells_by_id[s_id] = row

    def _build_dashboard_cache(self) -> None:
        """Precompute dashboard metrics."""
        total_matches = int(self.spells_df["match_id"].nunique())
        total_spells = len(self.spells_df)
        total_deliveries = len(self.deliv_df)
        legal_balls = int(self.career_df["legal_balls"].sum())
        total_wickets = int(self.career_df["wickets"].sum())
        total_bowler_runs = int(self.career_df["bowler_runs"].sum())
        dot_balls = int(self.career_df["dot_balls"].sum())

        overall_economy = round((total_bowler_runs * 6.0 / legal_balls), 2) if legal_balls > 0 else 0.0
        dot_ball_pct = round((dot_balls * 100.0 / legal_balls), 1) if legal_balls > 0 else 0.0

        # BCS Distribution across all 9,482 spells
        bcs_series = self.spells_df["total_bcs"]
        pos_share = round(float((bcs_series > 0).mean() * 100.0), 2)
        neg_share = round(float((bcs_series < 0).mean() * 100.0), 2)

        distribution = BCSDistribution(
            mean=round(float(bcs_series.mean()), 2),
            median=round(float(bcs_series.median()), 2),
            std=round(float(bcs_series.std()), 2),
            min=round(float(bcs_series.min()), 2),
            max=round(float(bcs_series.max()), 2),
            p25=round(float(bcs_series.quantile(0.25)), 2),
            p75=round(float(bcs_series.quantile(0.75)), 2),
            positive_share_pct=pos_share,
            negative_share_pct=neg_share,
        )

        # Top Career BCS (Top 5)
        top_career_bcs_df = self.career_df.sort_values("total_bcs", ascending=False).head(5)
        top_career_bcs: List[TopPerformerSummary] = []
        for _, r in top_career_bcs_df.iterrows():
            top_career_bcs.append(
                TopPerformerSummary(
                    bowler_id=int(r["bowler_id"]),
                    bowler_name=str(r["bowler_name"]),
                    matches=int(r["matches"]),
                    spells=int(r["spells"]),
                    overs=float(r["overs"]),
                    wickets=int(r["wickets"]),
                    economy=float(r["economy"]),
                    total_bcs=float(r["total_bcs"]),
                    total_bwpa=float(r["total_bwpa"]),
                )
            )

        # Top Career bWPA (Top 5)
        top_career_bwpa_df = self.career_df.sort_values("total_bwpa", ascending=False).head(5)
        top_career_bwpa: List[TopPerformerSummary] = []
        for _, r in top_career_bwpa_df.iterrows():
            top_career_bwpa.append(
                TopPerformerSummary(
                    bowler_id=int(r["bowler_id"]),
                    bowler_name=str(r["bowler_name"]),
                    matches=int(r["matches"]),
                    spells=int(r["spells"]),
                    overs=float(r["overs"]),
                    wickets=int(r["wickets"]),
                    economy=float(r["economy"]),
                    total_bcs=float(r["total_bcs"]),
                    total_bwpa=float(r["total_bwpa"]),
                )
            )

        # Top Match Spells (Top 5)
        top_spells_df = self.spells_df.sort_values("total_bcs", ascending=False).head(5)
        top_spells: List[TopSpellSummary] = []
        for _, r in top_spells_df.iterrows():
            top_spells.append(
                TopSpellSummary(
                    spell_id=str(r["spell_id"]),
                    match_id=int(r["match_id"]),
                    innings=int(r["innings"]),
                    bowler_id=int(r["bowler_id"]),
                    bowler_name=str(r["bowler_name"]),
                    team=str(r["team"]),
                    opponent=str(r["opponent"]),
                    overs=float(r["overs"]),
                    wickets=int(r["wickets"]),
                    runs_conceded=int(r["bowler_runs"]),
                    total_bcs=float(r["total_bcs"]),
                    total_bwpa=float(r["total_bwpa"]),
                )
            )

        self.dashboard_cache = BowlingDashboardResponse(
            status="success",
            total_matches=total_matches,
            total_spells=total_spells,
            total_deliveries=total_deliveries,
            legal_balls=legal_balls,
            total_wickets=total_wickets,
            total_bowler_runs=total_bowler_runs,
            overall_economy=overall_economy,
            dot_ball_pct=dot_ball_pct,
            bcs_distribution=distribution,
            phase_breakdown=self.corpus_phase_summary,
            top_career_bcs=top_career_bcs,
            top_career_bwpa=top_career_bwpa,
            top_match_spells=top_spells,
        )

    def _build_matches_cache(self) -> None:
        """Precompute match summaries with teams and top bowler."""
        matches_grouped = self.spells_df.groupby("match_id")
        
        matches_list = []
        for match_id, group in matches_grouped:
            first_row = group.iloc[0]
            m_date = str(first_row["match_date"])
            season = str(first_row["season"])
            venue = str(first_row["venue"])
            comp_cat = str(first_row["competition_category"])
            
            # Extract unique teams
            teams = sorted(list(set(group["team"].dropna().unique()).union(set(group["opponent"].dropna().unique()))))
            total_spells = len(group)
            total_wickets = int(group["wickets"].sum())

            # Top bowler in match
            top_row = group.sort_values("total_bcs", ascending=False).iloc[0]
            top_bowler = TopSpellSummary(
                spell_id=str(top_row["spell_id"]),
                match_id=int(match_id),
                innings=int(top_row["innings"]),
                bowler_id=int(top_row["bowler_id"]),
                bowler_name=str(top_row["bowler_name"]),
                team=str(top_row["team"]),
                opponent=str(top_row["opponent"]),
                overs=float(top_row["overs"]),
                wickets=int(top_row["wickets"]),
                runs_conceded=int(top_row["bowler_runs"]),
                total_bcs=float(top_row["total_bcs"]),
                total_bwpa=float(top_row["total_bwpa"]),
            )

            item = MatchListItem(
                match_id=int(match_id),
                match_date=m_date,
                season=season,
                venue=venue,
                competition_category=comp_cat,
                teams=teams,
                total_spells=total_spells,
                total_wickets=total_wickets,
                top_bowler=top_bowler,
            )
            matches_list.append(item)
            self.matches_dict_cache[int(match_id)] = item

        # Default sort by match_date descending
        matches_list.sort(key=lambda m: (m.match_date, m.match_id), reverse=True)
        self.matches_list_cache = matches_list

    # =========================================================================
    # PUBLIC QUERY METHODS
    # =========================================================================

    def _build_tournaments_cache(self) -> None:
        """Build tournament list from authoritative competitions.csv and match spells."""
        if self.competitions_df.empty:
            return

        match_counts = {}
        spell_counts = {}
        if "comp_id" in self.spells_df.columns:
            match_counts = self.spells_df.groupby("comp_id")["match_id"].nunique().to_dict()
            spell_counts = self.spells_df.groupby("comp_id").size().to_dict()

        items = []
        for _, row in self.competitions_df.iterrows():
            c_id = int(row["comp_id"])
            c_name = str(row["comp_name"])
            c_season = str(row.get("season", ""))
            c_format = str(row.get("match_format", "T20"))
            m_count = int(match_counts.get(c_id, 0))
            s_count = int(spell_counts.get(c_id, 0))

            display_name = f"{c_name} ({c_season})" if c_season and c_season not in c_name else c_name
            item = TournamentItem(
                comp_id=c_id,
                comp_name=c_name,
                display_name=display_name,
                season=c_season,
                match_format=c_format,
                match_count=m_count,
                spells_count=s_count,
            )
            items.append(item)
            self.comp_by_id[c_id] = item.model_dump()

        # Sort: chronological by season descending, then name ascending
        items.sort(key=lambda x: (str(x.season) if x.season else "", x.comp_name), reverse=True)
        self.tournaments_list = items

    def get_tournaments(self) -> BowlingTournamentsResponse:
        """Return authoritative list of all tournaments from competitions.csv."""
        if not self.is_initialized:
            self.initialize()
        return BowlingTournamentsResponse(
            status="success",
            total=len(self.tournaments_list),
            items=self.tournaments_list,
        )

    def _compute_tournament_leaderboard(self, comp_id: int, phase: Optional[str] = None) -> pd.DataFrame:
        """Aggregate bowling statistics strictly within a selected tournament."""
        spells = self.spells_df[self.spells_df["comp_id"] == comp_id].copy()
        if spells.empty:
            return pd.DataFrame()

        if phase:
            target_spell_ids = set(spells["spell_id"].unique())
            phase_delivs = self.deliv_df[
                (self.deliv_df["spell_id"].isin(target_spell_ids)) &
                (self.deliv_df["innings_phase"].str.lower() == phase.lower().strip())
            ]
            if phase_delivs.empty:
                return pd.DataFrame()

            agg = phase_delivs.groupby("bowler_id", as_index=False).agg(
                matches=("match_id", "nunique"),
                spells=("spell_id", "nunique"),
                legal_balls=("is_legal_delivery", "sum"),
                bowler_runs=("bowler_runs", "sum"),
                wickets=("is_bowler_wkt", "sum"),
                maidens=("is_legal_delivery", lambda _: 0),
                dot_balls=("dot_ball", "sum"),
                boundaries=("is_boundary_four", lambda s: int(s.sum() + phase_delivs.loc[s.index, "is_boundary_six"].sum())),
                total_erp=("erp", "sum"),
                total_bcs=("bcs", "sum"),
                total_bwpa=("bwpa", "sum"),
                mean_leverage=("leverage", "mean"),
                mean_wqm=("leverage", lambda _: 1.0),
            )
        else:
            agg = spells.groupby("bowler_id", as_index=False).agg(
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
                mean_wqm=("mean_wqm", "mean"),
            )

        if agg.empty:
            return pd.DataFrame()

        agg["bowler_name"] = agg["bowler_id"].map(self.player_names).fillna(agg["bowler_id"].astype(str))

        balls = agg["legal_balls"].to_numpy(dtype=float)
        runs = agg["bowler_runs"].to_numpy(dtype=float)
        wkts = agg["wickets"].to_numpy(dtype=float)
        dots = agg["dot_balls"].to_numpy(dtype=float)
        bounds = agg["boundaries"].to_numpy(dtype=float)
        bcs = agg["total_bcs"].to_numpy(dtype=float)

        agg["economy"] = np.where(balls > 0, (runs * 6.0) / balls, 0.0).round(2)
        agg["overs"] = ((agg["legal_balls"] // 6) + (agg["legal_balls"] % 6) / 10.0).round(1)
        agg["dot_pct"] = np.where(balls > 0, (dots * 100.0) / balls, 0.0).round(1)
        agg["boundary_pct"] = np.where(balls > 0, (bounds * 100.0) / balls, 0.0).round(1)
        agg["strike_rate"] = np.where(wkts > 0, np.divide(balls, wkts, out=np.full_like(balls, np.nan), where=wkts > 0), np.nan).round(1)
        agg["bowling_average"] = np.where(wkts > 0, np.divide(runs, wkts, out=np.full_like(runs, np.nan), where=wkts > 0), np.nan).round(2)
        agg["bcs_per_over"] = np.where(balls > 0, (bcs / (balls / 6.0)), 0.0).round(2)

        # Empirical Bayes shrinkage (M0 = 46.5 balls, prior = 2.39)
        w = balls / (balls + 46.5)
        prior = 2.39
        shrunk_po = w * agg["bcs_per_over"] + (1.0 - w) * prior
        agg["shrunk_bcs_per_over"] = shrunk_po.round(2)
        agg["total_bcs_shrunk"] = (agg["shrunk_bcs_per_over"] * (balls / 6.0)).round(2)

        return agg

    def get_dashboard(self) -> BowlingDashboardResponse:
        """Return precomputed high-level bowling dashboard KPIs and summaries."""
        if not self.is_initialized:
            self.initialize()
        return self.dashboard_cache

    def get_leaderboard(
        self,
        season: Optional[str] = None,
        phase: Optional[str] = None,
        tournament: Optional[str] = None,
        min_balls: int = settings.DEFAULT_MIN_BALLS,
        sort_by: str = "total_bcs",
        order: str = "desc",
        page: int = 1,
        page_size: int = settings.DEFAULT_PAGE_SIZE,
    ) -> BowlingLeaderboardResponse:
        """Return filterable, sortable, paginated bowling leaderboard."""
        if not self.is_initialized:
            self.initialize()

        # Validate page and page_size
        page = max(1, page)
        page_size = max(1, min(page_size, settings.MAX_PAGE_SIZE))

        # Resolve tournament if provided
        active_tournament_id: Optional[int] = None
        if tournament and str(tournament).lower() != "all":
            s_tourn = str(tournament).strip()
            if s_tourn.isdigit():
                c_id = int(s_tourn)
                if c_id in self.comp_by_id:
                    active_tournament_id = c_id
            if active_tournament_id is None:
                t_lower = s_tourn.lower()
                for c_id, t_info in self.comp_by_id.items():
                    if t_info["comp_name"].lower() == t_lower or t_info["display_name"].lower() == t_lower:
                        active_tournament_id = c_id
                        break

        # 1. Determine base dataframe
        if active_tournament_id is not None:
            df = self._compute_tournament_leaderboard(active_tournament_id, phase=phase)
        elif phase:
            phase_lower = phase.lower().strip()
            df = self._compute_phase_leaderboard(phase_lower)
        elif season and season.lower() != "all":
            df = self.season_df[self.season_df["season"].astype(str) == str(season)].copy()
        else:
            df = self.career_df.copy()

        if df.empty:
            return BowlingLeaderboardResponse(
                status="success",
                season_filter=season if season and season.lower() != "all" else None,
                phase_filter=phase,
                tournament_filter=tournament if tournament and str(tournament).lower() != "all" else None,
                min_balls_filter=min_balls,
                sort_by=sort_by,
                order=order,
                pagination=PaginationMetadata(
                    total_items=0,
                    total_pages=0,
                    current_page=1,
                    page_size=page_size,
                ),
                items=[],
            )

        # 2. Exclude Pakistan players (Requirement 1 & Combined behavior)
        if self.pakistan_player_ids:
            df = df[~df["bowler_id"].isin(self.pakistan_player_ids)].copy()

        # 3. Filter by min_balls
        df = df[df["legal_balls"] >= min_balls].copy()

        # 3. Sort
        ascending = order.lower() == "asc"
        valid_sort_cols = {
            "total_bcs": "total_bcs",
            "total_bcs_shrunk": "total_bcs_shrunk",
            "shrunk_bcs": "total_bcs_shrunk",
            "total_bwpa": "total_bwpa",
            "bcs_per_over": "bcs_per_over",
            "shrunk_bcs_per_over": "shrunk_bcs_per_over",
            "wickets": "wickets",
            "economy": "economy",
            "dot_pct": "dot_pct",
            "strike_rate": "strike_rate",
            "bowling_average": "bowling_average",
            "legal_balls": "legal_balls",
            "total_erp": "total_erp",
        }
        sort_col = valid_sort_cols.get(sort_by, "total_bcs")
        
        # When sorting, handle nulls gracefully
        df = df.sort_values(by=sort_col, ascending=ascending, na_position="last")

        total_items = len(df)
        total_pages = math.ceil(total_items / page_size) if total_items > 0 else 0

        # 4. Paginate
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        page_df = df.iloc[start_idx:end_idx]

        items: List[BowlerLeaderboardItem] = []
        for i, (_, row) in enumerate(page_df.iterrows()):
            balls = _clean_int(row["legal_balls"])
            overs_dec, overs_str = _format_overs(balls)
            rank = start_idx + i + 1

            items.append(
                BowlerLeaderboardItem(
                    rank=rank,
                    bowler_id=int(row["bowler_id"]),
                    bowler_name=str(row["bowler_name"]),
                    matches=_clean_int(row.get("matches", 0)),
                    spells=_clean_int(row.get("spells", 0)),
                    legal_balls=balls,
                    overs=overs_dec,
                    overs_formatted=overs_str,
                    bowler_runs=_clean_int(row["bowler_runs"]),
                    wickets=_clean_int(row["wickets"]),
                    maidens=_clean_int(row.get("maidens", 0)),
                    dot_balls=_clean_int(row.get("dot_balls", 0)),
                    boundaries=_clean_int(row.get("boundaries", 0)),
                    economy=_clean_float(row["economy"], 2) or 0.0,
                    dot_pct=_clean_float(row.get("dot_pct", 0.0), 1) or 0.0,
                    boundary_pct=_clean_float(row.get("boundary_pct", 0.0), 1) or 0.0,
                    strike_rate=_clean_float(row.get("strike_rate"), 1),
                    bowling_average=_clean_float(row.get("bowling_average"), 2),
                    total_erp=_clean_float(row.get("total_erp", 0.0), 2) or 0.0,
                    mean_leverage=_clean_float(row.get("mean_leverage", 1.0), 3) or 1.0,
                    mean_wqm=_clean_float(row.get("mean_wqm", 1.0), 3) or 1.0,
                    total_bcs=_clean_float(row["total_bcs"], 2) or 0.0,
                    bcs_per_over=_clean_float(row.get("bcs_per_over", 0.0), 2) or 0.0,
                    shrunk_bcs_per_over=_clean_float(row.get("shrunk_bcs_per_over"), 2),
                    total_bcs_shrunk=_clean_float(row.get("total_bcs_shrunk"), 2),
                    shrunk_bcs=_clean_float(row.get("total_bcs_shrunk"), 2),
                    total_bwpa=_clean_float(row["total_bwpa"], 4) or 0.0,
                )
            )

        return BowlingLeaderboardResponse(
            status="success",
            season_filter=season if season and season.lower() != "all" else None,
            phase_filter=phase,
            tournament_filter=tournament if tournament and str(tournament).lower() != "all" else None,
            min_balls_filter=min_balls,
            sort_by=sort_col,
            order=order,
            pagination=PaginationMetadata(
                total_items=total_items,
                total_pages=total_pages,
                current_page=page,
                page_size=page_size,
            ),
            items=items,
        )

    def _compute_phase_leaderboard(self, phase: str) -> pd.DataFrame:
        """Compute on-demand phase-level leaderboard from pre-aggregated bowler phase data."""
        pdf = self.bowler_phase_df[self.bowler_phase_df["innings_phase"] == phase].copy()
        if pdf.empty:
            return pd.DataFrame()

        # Join bowler name and metadata from career_df
        pdf = pdf.merge(self.career_df[["bowler_id", "bowler_name", "matches", "spells"]], on="bowler_id", how="left")

        pdf["economy"] = (pdf["runs"] * 6.0 / pdf["legal_balls"]).round(2)
        pdf["overs"] = ((pdf["legal_balls"] // 6) + (pdf["legal_balls"] % 6) / 10.0).round(1)
        pdf["dot_pct"] = (pdf["dots"] * 100.0 / pdf["legal_balls"]).round(1)
        pdf["boundary_pct"] = (pdf["boundaries"] * 100.0 / pdf["legal_balls"]).round(1)
        pdf["strike_rate"] = np.where(pdf["wickets"] > 0, (pdf["legal_balls"] / pdf["wickets"]).round(1), np.nan)
        pdf["bowling_average"] = np.where(pdf["wickets"] > 0, (pdf["runs"] / pdf["wickets"]).round(2), np.nan)
        pdf["bcs_per_over"] = (pdf["total_bcs"] / (pdf["legal_balls"] / 6.0)).round(2)
        pdf["mean_wqm"] = 1.0  # Phase summary baseline default

        # Rename to match career columns
        pdf = pdf.rename(columns={
            "runs": "bowler_runs",
            "dots": "dot_balls",
        })
        return pdf

    def get_player_profile(self, player_id: int) -> Optional[BowlerProfileResponse]:
        """Return comprehensive profile for a bowler, including career, phase splits, seasons, and spells."""
        if not self.is_initialized:
            self.initialize()

        career_row = self.career_by_id.get(player_id)
        if not career_row:
            return None

        # 1. Career Summary
        balls = _clean_int(career_row["legal_balls"])
        overs_dec, overs_str = _format_overs(balls)
        career_summary = BowlerLeaderboardItem(
            rank=_clean_int(career_row.get("rank", 0)),
            bowler_id=player_id,
            bowler_name=str(career_row["bowler_name"]),
            matches=_clean_int(career_row.get("matches", 0)),
            spells=_clean_int(career_row.get("spells", 0)),
            legal_balls=balls,
            overs=overs_dec,
            overs_formatted=overs_str,
            bowler_runs=_clean_int(career_row["bowler_runs"]),
            wickets=_clean_int(career_row["wickets"]),
            maidens=_clean_int(career_row.get("maidens", 0)),
            dot_balls=_clean_int(career_row.get("dot_balls", 0)),
            boundaries=_clean_int(career_row.get("boundaries", 0)),
            economy=_clean_float(career_row["economy"], 2) or 0.0,
            dot_pct=_clean_float(career_row.get("dot_pct", 0.0), 1) or 0.0,
            boundary_pct=_clean_float(career_row.get("boundary_pct", 0.0), 1) or 0.0,
            strike_rate=_clean_float(career_row.get("strike_rate"), 1),
            bowling_average=_clean_float(career_row.get("bowling_average"), 2),
            total_erp=_clean_float(career_row.get("total_erp", 0.0), 2) or 0.0,
            mean_leverage=_clean_float(career_row.get("mean_leverage", 1.0), 3) or 1.0,
            mean_wqm=_clean_float(career_row.get("mean_wqm", 1.0), 3) or 1.0,
            total_bcs=_clean_float(career_row["total_bcs"], 2) or 0.0,
            bcs_per_over=_clean_float(career_row.get("bcs_per_over", 0.0), 2) or 0.0,
            shrunk_bcs_per_over=_clean_float(career_row.get("shrunk_bcs_per_over"), 2),
            total_bcs_shrunk=_clean_float(career_row.get("total_bcs_shrunk"), 2),
            shrunk_bcs=_clean_float(career_row.get("total_bcs_shrunk"), 2),
            total_bwpa=_clean_float(career_row["total_bwpa"], 4) or 0.0,
        )

        # 2. Phase Splits
        phase_splits = self._get_bowler_phase_splits(player_id)

        # 3. Season Breakdown
        season_records: List[SeasonRecord] = []
        raw_seasons = self.season_by_player.get(player_id, [])
        sorted_seasons = sorted(raw_seasons, key=lambda s: str(s["season"]))
        for s in sorted_seasons:
            s_balls = _clean_int(s["legal_balls"])
            s_overs, _ = _format_overs(s_balls)
            season_records.append(
                SeasonRecord(
                    season=str(s["season"]),
                    matches=_clean_int(s.get("matches", 0)),
                    spells=_clean_int(s.get("spells", 0)),
                    legal_balls=s_balls,
                    overs=s_overs,
                    bowler_runs=_clean_int(s["bowler_runs"]),
                    wickets=_clean_int(s["wickets"]),
                    economy=_clean_float(s["economy"], 2) or 0.0,
                    dot_pct=_clean_float(s.get("dot_pct", 0.0), 1) or 0.0,
                    total_erp=_clean_float(s.get("total_erp", 0.0), 2) or 0.0,
                    total_bcs=_clean_float(s["total_bcs"], 2) or 0.0,
                    bcs_per_over=_clean_float(s.get("bcs_per_over", 0.0), 2) or 0.0,
                    total_bwpa=_clean_float(s["total_bwpa"], 4) or 0.0,
                )
            )

        # 4. Spells (Top 5 by BCS & Recent 5 by date)
        player_spells = self.spells_by_player.get(player_id, [])
        
        # Sort for top spells
        top_spells_raw = sorted(player_spells, key=lambda sp: sp["total_bcs"], reverse=True)[:5]
        top_spells = [self._format_bowler_spell_summary(sp) for sp in top_spells_raw]

        # Sort for recent spells
        recent_spells_raw = sorted(player_spells, key=lambda sp: (str(sp["match_date"]), sp["match_id"]), reverse=True)[:5]
        recent_spells = [self._format_bowler_spell_summary(sp) for sp in recent_spells_raw]

        return BowlerProfileResponse(
            status="success",
            bowler_id=player_id,
            bowler_name=str(career_row["bowler_name"]),
            career_summary=career_summary,
            phase_splits=phase_splits,
            season_breakdown=season_records,
            top_spells=top_spells,
            recent_spells=recent_spells,
        )

    def _get_bowler_phase_splits(self, player_id: int) -> List[PhaseBreakdownItem]:
        """Compute phase splits for a single bowler across powerplay, middle, death."""
        p_df = self.bowler_phase_df[self.bowler_phase_df["bowler_id"] == player_id]
        
        splits: List[PhaseBreakdownItem] = []
        phase_order = ["powerplay", "middle", "death"]
        
        for phase in phase_order:
            row = p_df[p_df["innings_phase"] == phase]
            if not row.empty:
                r = row.iloc[0]
                balls = _clean_int(r["legal_balls"])
                overs_dec, _ = _format_overs(balls)
                runs = _clean_int(r["runs"])
                wkts = _clean_int(r["wickets"])
                dots = _clean_int(r["dots"])
                bounds = _clean_int(r["boundaries"])
                econ = round((runs * 6.0 / balls), 2) if balls > 0 else 0.0
                dot_pct = round((dots * 100.0 / balls), 1) if balls > 0 else 0.0
                bound_pct = round((bounds * 100.0 / balls), 1) if balls > 0 else 0.0
                total_bcs = _clean_float(r["total_bcs"], 2) or 0.0
                bcs_per_ov = round((total_bcs / (balls / 6.0)), 2) if balls > 0 else 0.0

                splits.append(
                    PhaseBreakdownItem(
                        phase=phase,
                        legal_balls=balls,
                        overs=overs_dec,
                        runs=runs,
                        wickets=wkts,
                        economy=econ,
                        dot_pct=dot_pct,
                        boundary_pct=bound_pct,
                        avg_leverage=_clean_float(r["mean_leverage"], 3) or 1.0,
                        total_erp=_clean_float(r["total_erp"], 2) or 0.0,
                        total_bcs=total_bcs,
                        bcs_per_over=bcs_per_ov,
                        total_bwpa=_clean_float(r["total_bwpa"], 4) or 0.0,
                    )
                )
            else:
                splits.append(
                    PhaseBreakdownItem(
                        phase=phase,
                        legal_balls=0,
                        overs=0.0,
                        runs=0,
                        wickets=0,
                        economy=0.0,
                        dot_pct=0.0,
                        boundary_pct=0.0,
                        avg_leverage=1.0,
                        total_erp=0.0,
                        total_bcs=0.0,
                        bcs_per_over=0.0,
                        total_bwpa=0.0,
                    )
                )
        return splits

    def _format_bowler_spell_summary(self, sp: Dict[str, Any]) -> BowlerSpellSummary:
        """Format raw spell dictionary into BowlerSpellSummary model."""
        balls = _clean_int(sp["legal_balls"])
        overs_dec, overs_str = _format_overs(balls)
        return BowlerSpellSummary(
            spell_id=str(sp["spell_id"]),
            match_id=int(sp["match_id"]),
            match_date=str(sp["match_date"]),
            season=str(sp["season"]),
            venue=str(sp["venue"]),
            team=str(sp["team"]),
            opponent=str(sp["opponent"]),
            innings=int(sp["innings"]),
            legal_balls=balls,
            overs=overs_dec,
            overs_formatted=overs_str,
            bowler_runs=int(sp["bowler_runs"]),
            wickets=int(sp["wickets"]),
            economy=float(sp["economy"]),
            dot_balls=int(sp["dot_balls"]),
            total_erp=float(sp["total_erp"]),
            total_bcs=float(sp["total_bcs"]),
            total_bwpa=float(sp["total_bwpa"]),
        )

    def compare_bowlers(self, player_ids: List[int]) -> BowlerComparisonResponse:
        """Compare between 2 and 5 distinct bowlers side-by-side."""
        if not self.is_initialized:
            self.initialize()

        if len(player_ids) < settings.MIN_COMPARISON_PLAYERS or len(player_ids) > settings.MAX_COMPARISON_PLAYERS:
            raise ValueError(
                f"Player comparison requires between {settings.MIN_COMPARISON_PLAYERS} and "
                f"{settings.MAX_COMPARISON_PLAYERS} players. Received: {len(player_ids)}"
            )

        if len(set(player_ids)) != len(player_ids):
            raise ValueError("Duplicate player IDs are not allowed in bowler comparison.")

        bowlers_list: List[BowlerComparisonItem] = []
        for pid in player_ids:
            profile = self.get_player_profile(pid)
            if not profile:
                raise KeyError(f"Bowler with ID {pid} not found in career database.")
            
            bowlers_list.append(
                BowlerComparisonItem(
                    bowler_id=profile.bowler_id,
                    bowler_name=profile.bowler_name,
                    career_summary=profile.career_summary,
                    phase_splits=profile.phase_splits,
                )
            )

        return BowlerComparisonResponse(
            status="success",
            bowlers_count=len(bowlers_list),
            bowlers=bowlers_list,
        )

    def get_matches(
        self,
        season: Optional[str] = None,
        team: Optional[str] = None,
        sort_by: str = "match_date",
        order: str = "desc",
        page: int = 1,
        page_size: int = settings.DEFAULT_PAGE_SIZE,
    ) -> MatchListResponse:
        """Return paginated list of matches with metadata and match top bowler."""
        if not self.is_initialized:
            self.initialize()

        matches = list(self.matches_list_cache)

        # Filters
        if season and season.lower() != "all":
            matches = [m for m in matches if m.season == season]
        if team:
            t_lower = team.lower().strip()
            matches = [m for m in matches if any(t_lower in t.lower() for t in m.teams)]

        # Sorting
        reverse = order.lower() == "desc"
        if sort_by == "total_bcs":
            matches.sort(
                key=lambda m: (m.top_bowler.total_bcs if m.top_bowler else 0.0, m.match_date),
                reverse=reverse,
            )
        elif sort_by == "match_id":
            matches.sort(key=lambda m: m.match_id, reverse=reverse)
        else:  # match_date
            matches.sort(key=lambda m: (m.match_date, m.match_id), reverse=reverse)

        total_items = len(matches)
        total_pages = math.ceil(total_items / page_size) if total_items > 0 else 0

        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        items = matches[start_idx:end_idx]

        return MatchListResponse(
            status="success",
            season_filter=season,
            team_filter=team,
            pagination=PaginationMetadata(
                total_items=total_items,
                total_pages=total_pages,
                current_page=page,
                page_size=page_size,
            ),
            items=items,
        )

    def get_match_spells(self, match_id: int) -> Optional[MatchSpellsResponse]:
        """Return all bowling spells in a given match."""
        if not self.is_initialized:
            self.initialize()

        match_meta = self.matches_dict_cache.get(match_id)
        if not match_meta:
            return None

        raw_spells = self.spells_by_match.get(match_id, [])
        # Sort by innings ascending, then total_bcs descending
        sorted_spells = sorted(raw_spells, key=lambda s: (s["innings"], -s["total_bcs"]))

        spell_items: List[SpellDetailItem] = []
        for s in sorted_spells:
            spell_id = str(s["spell_id"])
            balls = _clean_int(s["legal_balls"])
            overs_dec, overs_str = _format_overs(balls)

            # Spell phase breakdown
            phase_items = self._get_spell_phase_splits(spell_id)

            spell_items.append(
                SpellDetailItem(
                    spell_id=spell_id,
                    innings=int(s["innings"]),
                    bowler_id=int(s["bowler_id"]),
                    bowler_name=str(s["bowler_name"]),
                    team=str(s["team"]),
                    opponent=str(s["opponent"]),
                    legal_balls=balls,
                    overs=overs_dec,
                    overs_formatted=overs_str,
                    bowler_runs=int(s["bowler_runs"]),
                    wickets=int(s["wickets"]),
                    maidens=int(s.get("maidens", 0)),
                    dot_balls=int(s.get("dot_balls", 0)),
                    boundaries=int(s.get("boundaries", 0)),
                    economy=float(s["economy"]),
                    dot_pct=float(s["dot_pct"]),
                    boundary_pct=float(s["boundary_pct"]),
                    strike_rate=_clean_float(s.get("strike_rate"), 1),
                    bowling_average=_clean_float(s.get("bowling_average"), 2),
                    total_erp=float(s["total_erp"]),
                    mean_wqm=float(s["mean_wqm"]),
                    mean_leverage=float(s["mean_leverage"]),
                    mean_dot_pressure=float(s["mean_dot_pressure"]),
                    mean_rrr_pressure=float(s["mean_rrr_pressure"]),
                    total_bcs=float(s["total_bcs"]),
                    total_bwpa=float(s["total_bwpa"]),
                    phase_breakdown=phase_items,
                )
            )

        return MatchSpellsResponse(
            status="success",
            match_id=match_id,
            match_date=match_meta.match_date,
            venue=match_meta.venue,
            spells_count=len(spell_items),
            spells=spell_items,
        )

    def _get_spell_phase_splits(self, spell_id: str) -> List[PhaseBreakdownItem]:
        """Compute phase splits for a single spell."""
        p_df = self.spell_phase_df[self.spell_phase_df["spell_id"] == spell_id]
        splits: List[PhaseBreakdownItem] = []
        phase_order = ["powerplay", "middle", "death"]

        for phase in phase_order:
            row = p_df[p_df["innings_phase"] == phase]
            if not row.empty:
                r = row.iloc[0]
                balls = _clean_int(r["legal_balls"])
                overs_dec, _ = _format_overs(balls)
                runs = _clean_int(r["runs"])
                wkts = _clean_int(r["wickets"])
                dots = _clean_int(r["dots"])
                bounds = _clean_int(r["boundaries"])
                econ = round((runs * 6.0 / balls), 2) if balls > 0 else 0.0
                dot_pct = round((dots * 100.0 / balls), 1) if balls > 0 else 0.0
                bound_pct = round((bounds * 100.0 / balls), 1) if balls > 0 else 0.0
                total_bcs = _clean_float(r["total_bcs"], 2) or 0.0
                bcs_per_ov = round((total_bcs / (balls / 6.0)), 2) if balls > 0 else 0.0

                splits.append(
                    PhaseBreakdownItem(
                        phase=phase,
                        legal_balls=balls,
                        overs=overs_dec,
                        runs=runs,
                        wickets=wkts,
                        economy=econ,
                        dot_pct=dot_pct,
                        boundary_pct=bound_pct,
                        avg_leverage=_clean_float(r["mean_leverage"], 3) or 1.0,
                        total_erp=_clean_float(r["total_erp"], 2) or 0.0,
                        total_bcs=total_bcs,
                        bcs_per_over=bcs_per_ov,
                        total_bwpa=_clean_float(r["total_bwpa"], 4) or 0.0,
                    )
                )
        return splits

    def get_spell_deliveries(self, spell_id: str) -> Optional[SpellDeliveriesResponse]:
        """Return delivery-level transition data for a specific bowling spell."""
        if not self.is_initialized:
            self.initialize()

        spell_row = self.spells_by_id.get(spell_id)
        if not spell_row:
            return None

        indices = self.deliv_indices_by_spell.get(spell_id)
        if indices is None or len(indices) == 0:
            return None

        spell_delivs = self.deliv_df.iloc[indices].copy()
        # Sort deliveries in chronological order within innings
        spell_delivs = spell_delivs.sort_values(by=["innings_ball_num", "over_ball_num"])

        delivery_items: List[DeliveryDetailItem] = []
        for idx, (_, row) in enumerate(spell_delivs.iterrows()):
            striker_id = int(row["striker_id"])
            non_striker_id = int(row["non_striker_id"])
            striker_name = self.player_names.get(striker_id, f"Player {striker_id}")
            non_striker_name = self.player_names.get(non_striker_id, f"Player {non_striker_id}")

            dismissed_id = row.get("resolved_dismissed_player_id")
            dismissed_name = None
            if pd.notna(dismissed_id) and dismissed_id is not None:
                dismissed_name = self.player_names.get(int(dismissed_id), f"Player {int(dismissed_id)}")

            delivery_items.append(
                DeliveryDetailItem(
                    ball_index=idx + 1,
                    innings_ball_num=int(row["innings_ball_num"]),
                    overid=int(row["overid"]),
                    over_ball_num=int(row["over_ball_num"]),
                    innings_phase=str(row["innings_phase"]),
                    striker_id=striker_id,
                    striker_name=striker_name,
                    non_striker_id=non_striker_id,
                    non_striker_name=non_striker_name,
                    batter_runs=int(row["batter_runs"]),
                    bowler_runs=int(row["bowler_runs"]),
                    team_runs=int(row["team_runs"]),
                    extras_type=_clean_str(row.get("extras_type")),
                    is_legal_delivery=bool(row["is_legal_delivery"]),
                    is_dot_ball=bool(row.get("dot_ball", False)),
                    is_boundary=bool(row.get("is_boundary_four", False) or row.get("is_boundary_six", False)),
                    is_wicket_event=bool(row.get("is_wicket_event", False)),
                    is_bowler_wkt=bool(row.get("is_bowler_wkt", False)),
                    dismissal_type=_clean_str(row.get("dismissal_type_canonical")),
                    dismissed_player_name=dismissed_name,
                    score_before=int(row["score_before"]),
                    wickets_lost_before=int(row["wickets_lost_before"]),
                    legal_balls_remaining_before=int(row.get("legal_balls_remaining_before", 0)),
                    score_after=int(row["score_after"]),
                    wickets_lost_after=int(row["wickets_lost_after"]),
                    required_run_rate=_clean_float(row.get("required_run_rate"), 2),
                    current_run_rate=_clean_float(row.get("current_run_rate"), 2),
                    exp_bowler_runs=_clean_float(row["exp_bowler_runs"], 3) or 0.0,
                    erp=_clean_float(row["erp"], 3) or 0.0,
                    WQM=_clean_float(row["WQM"], 3) or 1.0,
                    V_wkt=_clean_float(row["V_wkt"], 3) or 0.0,
                    leverage=_clean_float(row["leverage"], 3) or 1.0,
                    dot_pressure_index=_clean_float(row.get("dot_pressure_index", 0.0), 3) or 0.0,
                    rrr_pressure_index=_clean_float(row.get("rrr_pressure_index", 0.0), 3) or 0.0,
                    bcs=_clean_float(row["bcs"], 3) or 0.0,
                    bwpa=_clean_float(row["bwpa"], 4) or 0.0,
                    delta_wp_bowl=_clean_float(row.get("delta_wp_bowl", row["bwpa"]), 4) or 0.0,
                )
            )

        return SpellDeliveriesResponse(
            status="success",
            spell_id=spell_id,
            match_id=int(spell_row["match_id"]),
            innings=int(spell_row["innings"]),
            bowler_id=int(spell_row["bowler_id"]),
            bowler_name=str(spell_row["bowler_name"]),
            team=str(spell_row["team"]),
            opponent=str(spell_row["opponent"]),
            deliveries_count=len(delivery_items),
            deliveries=delivery_items,
        )
