"""High-performance in-memory read-only data service for Stage B7.5 Bowling Pressure Contribution Score (PCS)."""

import json
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple, Any
import numpy as np
import pandas as pd

from backend.core.config import settings
from backend.schemas.pcs import (
    PCSBowlerProfileResponse,
    PCSComparisonItem,
    PCSComparisonResponse,
    PCSDashboardResponse,
    PCSDeliveryDetailItem,
    PCSDistributionBin,
    PCSDistributionSummary,
    PCSHealthResponse,
    PCSLeaderboardItem,
    PCSLeaderboardResponse,
    PCSMatchDetailResponse,
    PCSMatchListResponse,
    PCSMatchSummaryItem,
    PCSPressureBreakdown,
    PCSSeasonHistoryItem,
    PCSSpellDeliveriesResponse,
    PCSSpellHistoryItem,
    PCSTopBowlerItem,
    PCSTopSpellItem,
    PCSTournamentItem,
    PCSTournamentsResponse,
    PaginationMetadata,
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
    """Format legal balls into decimal overs (e.g. 4.0) and cricket string notation."""
    overs_completed = legal_balls // 6
    remaining_balls = legal_balls % 6
    notation_float = round(overs_completed + (remaining_balls / 10.0), 1)
    notation_str = f"{overs_completed}.{remaining_balls}"
    return notation_float, notation_str


class PCSDataService:
    """Singleton service providing read-only access to PCS production outputs."""

    _instance: Optional["PCSDataService"] = None

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

        # Precomputed Dashboard & Match summaries cache
        self.dashboard_cache: Optional[PCSDashboardResponse] = None
        self.matches_list_cache: List[PCSMatchSummaryItem] = []
        self.matches_dict_cache: Dict[int, PCSMatchSummaryItem] = {}
        self.available_seasons: List[str] = []

        # Tournament & Nationality Filtering
        self.pakistan_player_ids: Set[int] = set()
        self.competitions_df: pd.DataFrame = pd.DataFrame()
        self.matches_df: pd.DataFrame = pd.DataFrame()
        self.match_to_comp: Dict[int, int] = {}
        self.tournaments_list: List[PCSTournamentItem] = []
        self.comp_by_id: Dict[int, Dict[str, Any]] = {}

    @classmethod
    def get_instance(cls) -> "PCSDataService":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def initialize(self) -> None:
        """Load datasets, verify integrity, and construct fast in-memory indexes."""
        if self.is_initialized:
            return

        # 1. Load manifest and verify existence
        if not settings.PCS_MANIFEST_FILE.exists():
            raise FileNotFoundError(f"PCS Manifest file not found at {settings.PCS_MANIFEST_FILE}")
        with open(settings.PCS_MANIFEST_FILE, "r", encoding="utf-8") as f:
            self.manifest = json.load(f)

        # 2. Load primary datasets
        self.career_df = pd.read_pickle(settings.PCS_CAREER_FILE)
        self.season_df = pd.read_pickle(settings.PCS_SEASON_FILE)
        self.spells_df = pd.read_pickle(settings.PCS_SPELLS_FILE)
        self.deliv_df = pd.read_pickle(settings.PCS_DELIVERIES_FILE)

        # Verify dataset row counts against expected production constants
        if len(self.career_df) != settings.EXPECTED_CAREER_BOWLERS:
            raise ValueError(f"PCS Career count {len(self.career_df)} != {settings.EXPECTED_CAREER_BOWLERS}")
        if len(self.season_df) != settings.EXPECTED_SEASON_RECORDS:
            raise ValueError(f"PCS Season count {len(self.season_df)} != {settings.EXPECTED_SEASON_RECORDS}")
        if len(self.spells_df) != settings.EXPECTED_SPELLS:
            raise ValueError(f"PCS Spells count {len(self.spells_df)} != {settings.EXPECTED_SPELLS}")
        if len(self.deliv_df) != settings.EXPECTED_DELIVERIES:
            raise ValueError(f"PCS Deliveries count {len(self.deliv_df)} != {settings.EXPECTED_DELIVERIES}")

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

        # Populate names from delivery data if mapping file has gaps
        if "bowler_name" in self.spells_df.columns:
            spell_names = self.spells_df.dropna(subset=["bowler_name"]).set_index("bowler_id")["bowler_name"].to_dict()
            for b_id, name in spell_names.items():
                if b_id not in self.player_names:
                    self.player_names[int(b_id)] = str(name)

        # 4. Construct canonical spell_id in spells and deliveries
        # Format: "{match_id}_{innings}_{bowler_id}"
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

        # 6. Extract available seasons sorted chronologically
        raw_seasons = sorted(self.season_df["season"].dropna().unique().tolist())
        self.available_seasons = raw_seasons

        # 7. Build in-memory lookup indexes
        self._build_lookup_indexes()

        # 8. Precompute Dashboard and Matches Cache
        self._build_dashboard_cache()
        self._build_matches_cache()

        # 9. Build tournaments metadata cache
        self._build_tournaments_cache()

        self.is_initialized = True

    def _build_lookup_indexes(self) -> None:
        """Construct dictionary indexes for fast O(1) query lookups."""
        # Index Career records by bowler_id
        for _, row in self.career_df.iterrows():
            b_id = int(row["bowler_id"])
            b_name = self.player_names.get(b_id, f"Bowler {b_id}")
            self.career_by_id[b_id] = {
                "bowler_id": b_id,
                "bowler_name": b_name,
                "team_name": None,
                "matches": _clean_int(row["matches"]),
                "spells": _clean_int(row["spells"]),
                "legal_balls": _clean_int(row["legal_balls"]),
                "overs": _clean_float(row["overs"], 1),
                "bowler_runs": _clean_int(row["bowler_runs"]),
                "wickets": _clean_int(row["wickets"]),
                "economy": _clean_float(row["economy"], 2),
                "strike_rate": _clean_float(row["strike_rate"], 1),
                "pcs_career_raw": _clean_float(row["pcs_career_raw"], 2),
                "pcs_career_shrunk": _clean_float(row["pcs_career_shrunk"], 2),
                "shrinkage_weight": _clean_float(row["shrinkage_weight"], 3),
                "total_rpe": _clean_float(row["total_rpe"], 2),
                "dot_balls": _clean_int(row["dot_balls"]),
                "boundaries": _clean_int(row["boundaries"]),
            }

        # Index Seasons by bowler_id
        for _, row in self.season_df.iterrows():
            b_id = int(row["bowler_id"])
            if b_id not in self.season_by_player:
                self.season_by_player[b_id] = []
            self.season_by_player[b_id].append({
                "season": str(row["season"]),
                "matches": _clean_int(row["matches"]),
                "spells": _clean_int(row["spells"]),
                "legal_balls": _clean_int(row["legal_balls"]),
                "overs": _clean_float(row["overs"], 1),
                "bowler_runs": _clean_int(row["bowler_runs"]),
                "wickets": _clean_int(row["wickets"]),
                "economy": _clean_float(row["economy"], 2),
                "strike_rate": _clean_float(row["strike_rate"], 1),
                "pcs_raw": _clean_float(row["pcs_season_raw"], 2),
                "pcs_shrunk": _clean_float(row["pcs_season_shrunk"], 2),
                "shrinkage_weight": _clean_float(row["shrinkage_weight"], 3),
                "total_rpe": _clean_float(row["total_rpe"], 2),
            })

        # Index Spells by bowler_id, match_id, and spell_id
        for _, row in self.spells_df.iterrows():
            b_id = int(row["bowler_id"])
            m_id = int(row["match_id"])
            s_id = str(row["spell_id"])
            b_name = self.player_names.get(b_id, f"Bowler {b_id}")
            bowl_team = self.team_names.get(_clean_int(row.get("bowling_team_id")), "Bowling Team")
            bat_team = self.team_names.get(_clean_int(row.get("batting_team_id")), "Batting Team")

            pcs_val = _clean_float(row["pcs_spell"], 2)
            category = "neutral"
            if pcs_val is not None:
                if pcs_val > 50.00:
                    category = "positive"
                elif pcs_val < 50.00:
                    category = "negative"

            spell_item = {
                "spell_id": s_id,
                "match_id": m_id,
                "innings": _clean_int(row["innings"]),
                "match_date": _clean_str(row.get("match_date")),
                "season": str(row["season"]),
                "bowler_id": b_id,
                "bowler_name": b_name,
                "bowling_team": bowl_team,
                "batting_team": bat_team,
                "overs": _clean_float(row["overs"], 1),
                "legal_balls": _clean_int(row["legal_balls"]),
                "bowler_runs": _clean_int(row["bowler_runs"]),
                "wickets": _clean_int(row["wickets"]),
                "economy": _clean_float(row["economy"], 2),
                "dot_balls": _clean_int(row["dot_balls"]),
                "boundaries": _clean_int(row["boundaries"]),
                "total_swi": _clean_float(row["total_swi"], 2),
                "total_dci": _clean_float(row["total_dci"], 2),
                "total_sup": _clean_float(row["total_sup"], 2),
                "total_leakage": _clean_float(row["total_leakage"], 2),
                "total_rpe": _clean_float(row["total_rpe"], 2),
                "pcs_spell": pcs_val,
                "pressure_category": category,
            }

            self.spells_by_id[s_id] = spell_item

            if b_id not in self.spells_by_player:
                self.spells_by_player[b_id] = []
            self.spells_by_player[b_id].append(spell_item)

            if m_id not in self.spells_by_match:
                self.spells_by_match[m_id] = []
            self.spells_by_match[m_id].append(spell_item)

            # Populate authoritative team_name on career record from spell bowling_team
            if b_id in self.career_by_id and bowl_team and bowl_team != "Bowling Team":
                self.career_by_id[b_id]["team_name"] = bowl_team

    def _build_dashboard_cache(self) -> None:
        """Precompute dashboard metrics and bipolar distribution buckets."""
        total_spells = len(self.spells_df)
        total_deliv = len(self.deliv_df)
        legal_balls = int(self.spells_df["legal_balls"].sum())
        total_wkts = int(self.spells_df["wickets"].sum())
        total_runs = int(self.spells_df["bowler_runs"].sum())
        overall_econ = round((total_runs * 6.0) / legal_balls, 2) if legal_balls > 0 else 0.0

        pcs_series = self.spells_df["pcs_spell"].dropna()
        avg_spell_pcs = round(float(pcs_series.mean()), 2)

        # Highest and lowest spells
        best_spell_row = self.spells_df.sort_values("pcs_spell", ascending=False).iloc[0]
        worst_spell_row = self.spells_df.sort_values("pcs_spell", ascending=True).iloc[0]
        best_spell = PCSTopSpellItem(**self.spells_by_id[str(best_spell_row["spell_id"])])
        worst_spell = PCSTopSpellItem(**self.spells_by_id[str(worst_spell_row["spell_id"])])

        # Bipolar Distribution Breakdown
        pos_count = int((pcs_series > 50.00).sum())
        neu_count = int((pcs_series == 50.00).sum())
        neg_count = int((pcs_series < 50.00).sum())

        pos_pct = round((pos_count / total_spells) * 100.0, 1)
        neu_pct = round((neu_count / total_spells) * 100.0, 1)
        neg_pct = round((neg_count / total_spells) * 100.0, 1)

        # 7-bin bipolar histogram
        bins_def = [
            ("0–25 (Severe Leakage)", 0.0, 25.0, "negative"),
            ("25–40 (High Pressure Conceded)", 25.0, 40.0, "negative"),
            ("40–49.99 (Modest Negative)", 40.0, 50.0, "negative"),
            ("50.00 (Neutral Baseline)", 50.0, 50.001, "neutral"),
            ("50.01–60 (Solid Containment)", 50.001, 60.0, "positive"),
            ("60–75 (High Pressure Impact)", 60.0, 75.0, "positive"),
            ("75–100 (Match-Winning Choke/Haul)", 75.0, 100.0, "positive"),
        ]

        dist_bins: List[PCSDistributionBin] = []
        for label, low, high, cat in bins_def:
            if cat == "neutral":
                c = int((pcs_series == 50.00).sum())
            elif cat == "negative" and high == 50.0:
                c = int(((pcs_series >= low) & (pcs_series < 50.00)).sum())
            elif cat == "positive" and low == 50.001:
                c = int(((pcs_series > 50.00) & (pcs_series <= high)).sum())
            else:
                c = int(((pcs_series >= low) & (pcs_series < high)).sum())
            p = round((c / total_spells) * 100.0, 1)
            dist_bins.append(PCSDistributionBin(
                bin_label=label,
                min_pcs=low,
                max_pcs=high,
                count=c,
                percentage=p,
                category=cat,
            ))

        q25, q50, q75 = np.percentile(pcs_series, [25, 50, 75])
        dist_summary = PCSDistributionSummary(
            mean=round(float(pcs_series.mean()), 2),
            std=round(float(pcs_series.std()), 2),
            median=round(float(q50), 2),
            min=round(float(pcs_series.min()), 2),
            max=round(float(pcs_series.max()), 2),
            q25=round(float(q25), 2),
            q75=round(float(q75), 2),
            iqr=round(float(q75 - q25), 2),
            positive_spells_count=pos_count,
            neutral_spells_count=neu_count,
            negative_spells_count=neg_count,
            positive_spells_pct=pos_pct,
            neutral_spells_pct=neu_pct,
            negative_spells_pct=neg_pct,
            bins=dist_bins,
        )

        # Top Career Leaders by Shrunk PCS (min 240 balls)
        eligible_career = self.career_df[self.career_df["legal_balls"] >= 240].sort_values("pcs_career_shrunk", ascending=False).head(10)
        top_career: List[PCSTopBowlerItem] = []
        for _, r in eligible_career.iterrows():
            top_career.append(PCSTopBowlerItem(**self.career_by_id[int(r["bowler_id"])]))

        # Top Season Leaders (min 120 balls)
        eligible_season = self.season_df[self.season_df["legal_balls"] >= 120].sort_values("pcs_season_shrunk", ascending=False).head(10)
        top_seasons: List[Dict[str, Any]] = []
        for _, r in eligible_season.iterrows():
            b_id = int(r["bowler_id"])
            top_seasons.append({
                "bowler_id": b_id,
                "bowler_name": self.player_names.get(b_id, f"Bowler {b_id}"),
                "season": str(r["season"]),
                "spells": int(r["spells"]),
                "legal_balls": int(r["legal_balls"]),
                "wickets": int(r["wickets"]),
                "economy": float(r["economy"]),
                "pcs_season_raw": float(r["pcs_season_raw"]),
                "pcs_season_shrunk": float(r["pcs_season_shrunk"]),
            })

        # Season-by-season PCS progression & positive pressure share trends
        season_trends: List[Dict[str, Any]] = []
        for s_yr in self.available_seasons:
            s_grp = self.spells_df[self.spells_df["season"].astype(str) == str(s_yr)]
            if len(s_grp) == 0:
                continue
            s_pcs = s_grp["pcs_spell"].dropna()
            n_s = len(s_pcs)
            pos_s = int((s_pcs > 50.00).sum())
            neg_s = int((s_pcs < 50.00).sum())
            season_trends.append({
                "season": str(s_yr),
                "spells": n_s,
                "avg_spell_pcs": round(float(s_pcs.mean()), 2) if n_s > 0 else 50.0,
                "median_spell_pcs": round(float(s_pcs.median()), 2) if n_s > 0 else 50.0,
                "positive_spells_pct": round((pos_s / n_s) * 100.0, 1) if n_s > 0 else 0.0,
                "negative_spells_pct": round((neg_s / n_s) * 100.0, 1) if n_s > 0 else 0.0,
            })

        self.dashboard_cache = PCSDashboardResponse(
            total_matches=len(self.spells_df["match_id"].unique()),
            total_spells=total_spells,
            total_deliveries=total_deliv,
            legal_balls=legal_balls,
            total_wickets=total_wkts,
            total_bowler_runs=total_runs,
            overall_economy=overall_econ,
            average_spell_pcs=avg_spell_pcs,
            highest_spell_pcs=best_spell,
            lowest_spell_pcs=worst_spell,
            pcs_distribution=dist_summary,
            top_career_leaders=top_career,
            top_season_leaders=top_seasons,
            season_trends=season_trends,
            available_seasons=self.available_seasons,
        )

    def _build_matches_cache(self) -> None:
        """Precompute match listing metadata."""
        match_groups = self.spells_df.groupby("match_id")
        matches: List[PCSMatchSummaryItem] = []

        for m_id, grp in match_groups:
            first_row = grp.iloc[0]
            best_spell_row = grp.sort_values("pcs_spell", ascending=False).iloc[0]
            b_id = int(best_spell_row["bowler_id"])
            b_name = self.player_names.get(b_id, f"Bowler {b_id}")

            home_team = self.team_names.get(_clean_int(first_row.get("bowling_team_id")), "Team 1")
            away_team = self.team_names.get(_clean_int(first_row.get("batting_team_id")), "Team 2")

            item = PCSMatchSummaryItem(
                match_id=int(m_id),
                match_date=_clean_str(first_row.get("match_date")),
                season=str(first_row.get("season")),
                home_team=home_team,
                away_team=away_team,
                venue=str(first_row.get("venue_id", "T20 Venue")),
                total_spells=len(grp),
                best_spell_pcs=_clean_float(best_spell_row["pcs_spell"], 2) or 50.0,
                best_spell_bowler=b_name,
            )
            matches.append(item)
            self.matches_dict_cache[int(m_id)] = item

        # Sort matches descending by date or match_id
        matches.sort(key=lambda x: (x.match_date or "", x.match_id), reverse=True)
        self.matches_list_cache = matches

    # --- API Query Methods ---

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
            item = PCSTournamentItem(
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

    def get_tournaments(self) -> PCSTournamentsResponse:
        """Return authoritative list of all tournaments for PCS."""
        if not self.is_initialized:
            self.initialize()
        return PCSTournamentsResponse(
            status="success",
            total=len(self.tournaments_list),
            items=self.tournaments_list,
        )

    def _compute_tournament_leaderboard(self, comp_id: int) -> pd.DataFrame:
        """Aggregate bowler pressure metrics strictly within a selected tournament."""
        spells = self.spells_df[self.spells_df["comp_id"] == comp_id].copy()
        if spells.empty:
            return pd.DataFrame()

        spells["pcs_x_balls"] = spells["pcs_spell"] * spells["legal_balls"]

        agg = spells.groupby("bowler_id", as_index=False).agg(
            matches=("match_id", "nunique"),
            spells=("match_id", "count"),
            legal_balls=("legal_balls", "sum"),
            bowler_runs=("bowler_runs", "sum"),
            wickets=("wickets", "sum"),
            dot_balls=("dot_balls", "sum"),
            boundaries=("boundaries", "sum"),
            mean_leverage=("mean_leverage", "mean"),
            total_rpe=("total_rpe", "sum"),
            raw_pcs_mean=("pcs_spell", "mean"),
            pcs_x_balls_sum=("pcs_x_balls", "sum"),
        )

        if agg.empty:
            return pd.DataFrame()

        balls_sum = agg["legal_balls"].to_numpy(dtype=float)
        pcs_prod_sum = agg["pcs_x_balls_sum"].to_numpy(dtype=float)
        weighted_mean = np.where(balls_sum > 0, pcs_prod_sum / balls_sum, agg["raw_pcs_mean"].to_numpy(dtype=float))
        agg["weighted_pcs_mean"] = weighted_mean

        agg["overs"] = (agg["legal_balls"] // 6) + ((agg["legal_balls"] % 6) / 10.0)
        agg["economy"] = np.where(
            agg["legal_balls"] > 0,
            (agg["bowler_runs"] * 6.0) / agg["legal_balls"],
            0.0,
        ).round(2)
        wkts = agg["wickets"].to_numpy(dtype=float)
        agg["strike_rate"] = np.where(
            wkts > 0,
            np.divide(balls_sum, wkts, out=np.full_like(balls_sum, np.nan), where=wkts > 0),
            np.nan,
        ).round(1)

        # Empirical Bayes shrinkage (M0 = 48.0 balls, prior = 50.0)
        m0_balls = 48.0
        w = balls_sum / (balls_sum + m0_balls)
        shrunk_pcs = w * weighted_mean + (1.0 - w) * 50.0

        agg["shrinkage_weight"] = w.round(3)
        agg["pcs_season_raw"] = weighted_mean.round(2)
        agg["pcs_season_shrunk"] = shrunk_pcs.round(2)
        agg["pcs_raw"] = agg["pcs_season_raw"]
        agg["pcs_shrunk"] = agg["pcs_season_shrunk"]

        return agg

    def get_health(self) -> PCSHealthResponse:
        """Return system health and dataset status."""
        return PCSHealthResponse(
            service_initialized=self.is_initialized,
            pipeline_version=self.manifest.get("version", "1.0.0"),
            total_deliveries=len(self.deliv_df),
            total_spells=len(self.spells_df),
            total_career_records=len(self.career_df),
            total_season_records=len(self.season_df),
            datasets={
                "manifest": settings.PCS_MANIFEST_FILE.exists(),
                "career": settings.PCS_CAREER_FILE.exists(),
                "season": settings.PCS_SEASON_FILE.exists(),
                "spells": settings.PCS_SPELLS_FILE.exists(),
                "deliveries": settings.PCS_DELIVERIES_FILE.exists(),
                "validation": settings.PCS_VALIDATION_FILE.exists(),
            },
        )

    def get_dashboard(self) -> PCSDashboardResponse:
        """Return cached dashboard payload."""
        if self.dashboard_cache is None:
            self._build_dashboard_cache()
        return self.dashboard_cache

    def get_leaderboard(
        self,
        scope: str = "career",
        season: Optional[str] = None,
        tournament: Optional[str] = None,
        min_balls: int = 60,
        sort_by: str = "pcs_shrunk",
        order: str = "desc",
        search: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> PCSLeaderboardResponse:
        """Query paginated and filtered PCS leaderboard."""
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

        if active_tournament_id is not None:
            df = self._compute_tournament_leaderboard(active_tournament_id)
            raw_col = "pcs_raw"
            shrunk_col = "pcs_shrunk"
        elif scope == "season":
            df = self.season_df.copy()
            if season:
                df = df[df["season"].astype(str) == str(season)]
            raw_col = "pcs_season_raw"
            shrunk_col = "pcs_season_shrunk"
        else:
            df = self.career_df.copy()
            raw_col = "pcs_career_raw"
            shrunk_col = "pcs_career_shrunk"

        if df.empty:
            return PCSLeaderboardResponse(
                items=[],
                pagination=PaginationMetadata(
                    total_items=0,
                    total_pages=0,
                    current_page=1,
                    page_size=page_size,
                ),
                available_seasons=self.available_seasons,
                current_scope=scope,
                active_season=season,
                tournament_filter=tournament if tournament and str(tournament).lower() != "all" else None,
            )

        # Exclude Pakistan players (Requirement 1 & Combined behavior)
        if self.pakistan_player_ids:
            df = df[~df["bowler_id"].isin(self.pakistan_player_ids)].copy()

        # Apply minimum legal balls threshold
        df = df[df["legal_balls"] >= min_balls]

        # Attach bowler names for searching and display
        df["bowler_name"] = df["bowler_id"].map(self.player_names).fillna(df["bowler_id"].astype(str))

        if search:
            query = search.strip().lower()
            df = df[df["bowler_name"].str.lower().str.contains(query, na=False)]

        # Determine sorting column
        sort_mapping = {
            "pcs_shrunk": shrunk_col,
            "pcs_raw": raw_col,
            "wickets": "wickets",
            "economy": "economy",
            "legal_balls": "legal_balls",
            "total_rpe": "total_rpe",
        }
        target_col = sort_mapping.get(sort_by, shrunk_col)
        ascending = (order.lower() == "asc")
        # Invert default for economy (lower economy is better)
        if sort_by == "economy" and order.lower() == "desc":
            ascending = True

        df = df.sort_values(by=target_col, ascending=ascending)

        total_items = len(df)
        page_size = min(max(1, page_size), settings.MAX_PAGE_SIZE)
        total_pages = max(1, (total_items + page_size - 1) // page_size) if total_items > 0 else 0
        page = min(max(1, page), max(1, total_pages))

        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        page_df = df.iloc[start_idx:end_idx]

        items: List[PCSLeaderboardItem] = []
        for rank_offset, (_, row) in enumerate(page_df.iterrows(), start=1):
            rank = start_idx + rank_offset
            b_id = int(row["bowler_id"])
            b_spells = self.spells_by_player.get(b_id, [])
            pos_spells = sum(1 for s in b_spells if s.get("pcs_spell", 50.0) > 50.0)
            neg_spells = sum(1 for s in b_spells if s.get("pcs_spell", 50.0) < 50.0)
            tot_spells = len(b_spells) if b_spells else 1
            pos_pct = round((pos_spells / tot_spells) * 100.0, 1)
            neg_pct = round((neg_spells / tot_spells) * 100.0, 1)

            items.append(PCSLeaderboardItem(
                rank=rank,
                bowler_id=b_id,
                bowler_name=str(row["bowler_name"]),
                team_name=None,
                season=str(row.get("season")) if scope == "season" else None,
                matches=_clean_int(row["matches"]),
                spells=_clean_int(row["spells"]),
                legal_balls=_clean_int(row["legal_balls"]),
                overs=_clean_float(row["overs"], 1) or 0.0,
                bowler_runs=_clean_int(row["bowler_runs"]),
                wickets=_clean_int(row["wickets"]),
                economy=_clean_float(row["economy"], 2) or 0.0,
                strike_rate=_clean_float(row.get("strike_rate"), 1),
                pcs_raw=_clean_float(row[raw_col], 2) or 50.0,
                pcs_shrunk=_clean_float(row[shrunk_col], 2) or 50.0,
                shrinkage_weight=_clean_float(row["shrinkage_weight"], 3) or 0.0,
                total_rpe=_clean_float(row["total_rpe"], 2) or 0.0,
                dot_balls=_clean_int(row["dot_balls"]),
                boundaries=_clean_int(row["boundaries"]),
                positive_spells_pct=pos_pct,
                negative_spells_pct=neg_pct,
            ))

        return PCSLeaderboardResponse(
            items=items,
            pagination=PaginationMetadata(
                total_items=total_items,
                total_pages=total_pages,
                current_page=page,
                page_size=page_size,
            ),
            available_seasons=self.available_seasons,
            current_scope=scope,
            active_season=season,
            tournament_filter=tournament if tournament and str(tournament).lower() != "all" else None,
        )

    def get_player_profile(self, player_id: int) -> Optional[PCSBowlerProfileResponse]:
        """Return comprehensive bowler pressure profile."""
        if player_id not in self.career_by_id:
            return None

        career_dict = self.career_by_id[player_id]
        career_item = PCSTopBowlerItem(**career_dict)

        # Seasons history sorted descending
        seasons_raw = self.season_by_player.get(player_id, [])
        seasons_history = [PCSSeasonHistoryItem(**s) for s in sorted(seasons_raw, key=lambda x: str(x["season"]), reverse=True)]

        # Spells history sorted descending by match_date or match_id
        spells_raw = self.spells_by_player.get(player_id, [])
        spells_history = []
        for s in sorted(spells_raw, key=lambda x: (x.get("match_date") or "", x["match_id"]), reverse=True):
            opp = s["batting_team"] if s.get("batting_team") else "Opposition"
            venue = "T20 Match"
            spells_history.append(PCSSpellHistoryItem(
                spell_id=s["spell_id"],
                match_id=s["match_id"],
                match_date=s.get("match_date"),
                season=s["season"],
                opposition=opp,
                venue=venue,
                innings=s["innings"],
                overs=s["overs"],
                legal_balls=s["legal_balls"],
                bowler_runs=s["bowler_runs"],
                wickets=s["wickets"],
                economy=s["economy"],
                dot_balls=s["dot_balls"],
                boundaries=s["boundaries"],
                total_swi=s["total_swi"],
                total_dci=s["total_dci"],
                total_sup=s["total_sup"],
                total_leakage=s["total_leakage"],
                total_rpe=s["total_rpe"],
                pcs_spell=s["pcs_spell"],
                pressure_category=s["pressure_category"],
            ))

        # Detailed pressure breakdown from spell aggregates
        num_spells = max(1, len(spells_raw))
        avg_swi = round(sum(s["total_swi"] for s in spells_raw) / num_spells, 2)
        avg_dci = round(sum(s["total_dci"] for s in spells_raw) / num_spells, 2)
        avg_sup = round(sum(s["total_sup"] for s in spells_raw) / num_spells, 2)
        avg_leakage = round(sum(s["total_leakage"] for s in spells_raw) / num_spells, 2)
        total_dots = sum(s["dot_balls"] for s in spells_raw)
        total_balls = max(1, sum(s["legal_balls"] for s in spells_raw))
        dot_pct = round((total_dots / total_balls) * 100.0, 1)

        # Count multi-wicket spells / stand breaks
        multi_wkt_spells = sum(1 for s in spells_raw if s["wickets"] >= 2)
        stand_breaks = sum(1 for s in spells_raw if s["total_swi"] >= 15.0)

        breakdown = PCSPressureBreakdown(
            avg_swi_per_spell=avg_swi,
            avg_dci_per_spell=avg_dci,
            avg_sup_per_spell=avg_sup,
            avg_leakage_per_spell=avg_leakage,
            avg_pti_when_wicket=round(avg_swi * 1.25, 2),
            strike_starvation_index=round(avg_dci * 0.45, 2),
            stand_break_count=stand_breaks,
            multi_wicket_overs_count=multi_wkt_spells,
            dot_ball_pct=dot_pct,
        )

        return PCSBowlerProfileResponse(
            bowler_id=player_id,
            bowler_name=career_item.bowler_name,
            team_name=career_item.team_name,
            career=career_item,
            season_history=seasons_history,
            spells_history=spells_history,
            pressure_breakdown=breakdown,
        )

    def compare_bowlers(self, player_ids: List[int]) -> PCSComparisonResponse:
        """Compare up to 5 bowlers side-by-side on PCS dimensions."""
        clean_ids = [int(p) for p in player_ids[:settings.MAX_COMPARISON_PLAYERS] if int(p) in self.career_by_id]
        bowlers: List[PCSComparisonItem] = []

        for p_id in clean_ids:
            c = self.career_by_id[p_id]
            spells = self.spells_by_player.get(p_id, [])
            pcs_list = [s["pcs_spell"] for s in spells if s.get("pcs_spell") is not None]

            avg_pcs = round(float(np.mean(pcs_list)), 2) if pcs_list else 50.0
            best_pcs = round(float(np.max(pcs_list)), 2) if pcs_list else 50.0
            worst_pcs = round(float(np.min(pcs_list)), 2) if pcs_list else 50.0

            pos_spells = sum(1 for p in pcs_list if p > 50.0)
            neg_spells = sum(1 for p in pcs_list if p < 50.0)
            tot_spells = len(pcs_list) if pcs_list else 1
            pos_pct = round((pos_spells / tot_spells) * 100.0, 1)
            neg_pct = round((neg_spells / tot_spells) * 100.0, 1)

            avg_swi = round(float(np.mean([s["total_swi"] for s in spells])), 2) if spells else 0.0
            avg_dci = round(float(np.mean([s["total_dci"] for s in spells])), 2) if spells else 0.0
            avg_sup = round(float(np.mean([s["total_sup"] for s in spells])), 2) if spells else 0.0
            avg_leakage = round(float(np.mean([s["total_leakage"] for s in spells])), 2) if spells else 0.0

            seasons = self.season_by_player.get(p_id, [])

            bowlers.append(PCSComparisonItem(
                bowler_id=p_id,
                bowler_name=c["bowler_name"],
                team_name=c["team_name"],
                matches=c["matches"],
                spells=c["spells"],
                legal_balls=c["legal_balls"],
                overs=c["overs"],
                wickets=c["wickets"],
                economy=c["economy"],
                pcs_career_raw=c["pcs_career_raw"],
                pcs_career_shrunk=c["pcs_career_shrunk"],
                avg_spell_pcs=avg_pcs,
                best_spell_pcs=best_pcs,
                worst_spell_pcs=worst_pcs,
                positive_spells_count=pos_spells,
                negative_spells_count=neg_spells,
                positive_spells_pct=pos_pct,
                negative_spells_pct=neg_pct,
                total_rpe=c["total_rpe"],
                avg_swi=avg_swi,
                avg_dci=avg_dci,
                avg_sup=avg_sup,
                avg_leakage=avg_leakage,
                seasons_data=seasons,
            ))

        return PCSComparisonResponse(bowlers=bowlers)

    def get_matches(
        self,
        season: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> PCSMatchListResponse:
        """Return paginated list of matches for explorer."""
        filtered = self.matches_list_cache
        if season:
            filtered = [m for m in filtered if m.season == season]

        total_items = len(filtered)
        page_size = min(max(1, page_size), settings.MAX_PAGE_SIZE)
        total_pages = max(1, (total_items + page_size - 1) // page_size)
        page = min(max(1, page), total_pages)

        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        page_matches = filtered[start_idx:end_idx]

        return PCSMatchListResponse(
            matches=page_matches,
            pagination=PaginationMetadata(
                total_items=total_items,
                total_pages=total_pages,
                current_page=page,
                page_size=page_size,
            ),
            available_seasons=self.available_seasons,
        )

    def get_match_detail(self, match_id: int) -> Optional[PCSMatchDetailResponse]:
        """Return match detail with bowler spells and delivery-by-delivery timeline."""
        spells_raw = self.spells_by_match.get(match_id)
        if not spells_raw:
            return None

        # Bowler spells in match
        bowler_spells = [PCSTopSpellItem(**s) for s in spells_raw]

        # Extract deliveries for this match from deliv_df
        match_delivs_mask = (self.deliv_df["match_id"] == match_id)
        df_m = self.deliv_df[match_delivs_mask].sort_values(["innings", "innings_ball_num"])

        timeline: List[PCSDeliveryDetailItem] = []
        for _, row in df_m.iterrows():
            b_id = int(row["bowler_id"])
            s_id = int(row["striker_id"])
            ns_id = int(row.get("non_striker_id", 0))

            b_name = self.player_names.get(b_id, f"Bowler {b_id}")
            s_name = self.player_names.get(s_id, f"Batter {s_id}")

            is_wkt = bool(row["is_wicket_event"])
            is_bwkt = bool(row.get("is_bowler_wkt", False))
            diss_type = _clean_str(row.get("dismissal_type_canonical"))

            seq_note = None
            if is_wkt:
                if is_bwkt:
                    seq_note = f"Wicket: {diss_type or 'out'} credited to {b_name}"
                else:
                    seq_note = f"Team Wicket: {diss_type or 'run out'} (non-bowler dismissal)"

            timeline.append(PCSDeliveryDetailItem(
                innings_ball_num=_clean_int(row["innings_ball_num"]),
                innings=_clean_int(row["innings"]),
                overid=_clean_int(row["overid"]),
                over_ball_num=_clean_int(row["over_ball_num"]),
                bowler_id=b_id,
                bowler_name=b_name,
                striker_id=s_id,
                striker_name=s_name,
                non_striker_id=ns_id,
                score_before=_clean_int(row["score_before"]),
                wickets_lost_before=_clean_int(row["wickets_lost_before"]),
                legal_balls_rem=_clean_int(row["legal_balls_remaining_before"]),
                current_run_rate=_clean_float(row["current_run_rate"], 2) or 0.0,
                req_run_rate=_clean_float(row.get("required_run_rate"), 2),
                team_runs=_clean_int(row["team_runs"]),
                bowler_runs=_clean_int(row["bowler_runs"]),
                is_legal=bool(row["is_legal_delivery"]),
                is_wide=bool(row["is_wide"]),
                is_no_ball=bool(row["is_no_ball"]),
                is_dot=bool(row.get("is_dot_ball", False)),
                is_boundary=bool(row["is_boundary_four"] or row["is_boundary_six"]),
                is_wicket=is_wkt,
                dismissal_type=diss_type,
                is_bowler_wkt=is_bwkt,
                leverage=_clean_float(row.get("leverage", 1.0), 2) or 1.0,
                pti=_clean_float(row.get("pti", 0.0), 2) or 0.0,
                swi=_clean_float(row.get("swi", 0.0), 2) or 0.0,
                dci=_clean_float(row.get("dci", 0.0), 2) or 0.0,
                sup=_clean_float(row.get("sup", 0.0), 2) or 0.0,
                leakage=_clean_float(row.get("leakage", 0.0), 2) or 0.0,
                rpe=_clean_float(row.get("rpe", 0.0), 2) or 0.0,
                pcs_delivery=_clean_float(row.get("pcs_delivery", 50.0), 2) or 50.0,
                sequential_event_note=seq_note,
            ))

        first_row = df_m.iloc[0]
        return PCSMatchDetailResponse(
            match_id=match_id,
            season=str(first_row.get("season")),
            match_date=_clean_str(first_row.get("match_date")),
            competition=str(first_row.get("competition_category", "T20")),
            venue=str(first_row.get("venue_id", "T20 Venue")),
            bowler_spells=bowler_spells,
            delivery_timeline=timeline,
        )

    def get_spell_deliveries(self, spell_id: str) -> Optional[PCSSpellDeliveriesResponse]:
        """Return delivery-level breakdown for a specific bowler spell."""
        spell_dict = self.spells_by_id.get(spell_id)
        if not spell_dict:
            return None

        indices = self.deliv_indices_by_spell.get(spell_id)
        if indices is None or len(indices) == 0:
            return None

        df_spell_deliv = self.deliv_df.iloc[indices].sort_values("innings_ball_num")

        deliveries: List[PCSDeliveryDetailItem] = []
        for _, row in df_spell_deliv.iterrows():
            b_id = int(row["bowler_id"])
            s_id = int(row["striker_id"])
            ns_id = int(row.get("non_striker_id", 0))

            b_name = self.player_names.get(b_id, f"Bowler {b_id}")
            s_name = self.player_names.get(s_id, f"Batter {s_id}")

            is_wkt = bool(row["is_wicket_event"])
            is_bwkt = bool(row.get("is_bowler_wkt", False))
            diss_type = _clean_str(row.get("dismissal_type_canonical"))

            seq_note = None
            if is_wkt:
                if is_bwkt:
                    seq_note = f"Wicket: {diss_type or 'out'} credited to {b_name}"
                else:
                    seq_note = f"Team Wicket: {diss_type or 'run out'}"

            deliveries.append(PCSDeliveryDetailItem(
                innings_ball_num=_clean_int(row["innings_ball_num"]),
                innings=_clean_int(row["innings"]),
                overid=_clean_int(row["overid"]),
                over_ball_num=_clean_int(row["over_ball_num"]),
                bowler_id=b_id,
                bowler_name=b_name,
                striker_id=s_id,
                striker_name=s_name,
                non_striker_id=ns_id,
                score_before=_clean_int(row["score_before"]),
                wickets_lost_before=_clean_int(row["wickets_lost_before"]),
                legal_balls_rem=_clean_int(row["legal_balls_remaining_before"]),
                current_run_rate=_clean_float(row["current_run_rate"], 2) or 0.0,
                req_run_rate=_clean_float(row.get("required_run_rate"), 2),
                team_runs=_clean_int(row["team_runs"]),
                bowler_runs=_clean_int(row["bowler_runs"]),
                is_legal=bool(row["is_legal_delivery"]),
                is_wide=bool(row["is_wide"]),
                is_no_ball=bool(row["is_no_ball"]),
                is_dot=bool(row.get("is_dot_ball", False)),
                is_boundary=bool(row["is_boundary_four"] or row["is_boundary_six"]),
                is_wicket=is_wkt,
                dismissal_type=diss_type,
                is_bowler_wkt=is_bwkt,
                leverage=_clean_float(row.get("leverage", 1.0), 2) or 1.0,
                pti=_clean_float(row.get("pti", 0.0), 2) or 0.0,
                swi=_clean_float(row.get("swi", 0.0), 2) or 0.0,
                dci=_clean_float(row.get("dci", 0.0), 2) or 0.0,
                sup=_clean_float(row.get("sup", 0.0), 2) or 0.0,
                leakage=_clean_float(row.get("leakage", 0.0), 2) or 0.0,
                rpe=_clean_float(row.get("rpe", 0.0), 2) or 0.0,
                pcs_delivery=_clean_float(row.get("pcs_delivery", 50.0), 2) or 50.0,
                sequential_event_note=seq_note,
            ))

        return PCSSpellDeliveriesResponse(
            spell_id=spell_id,
            bowler_id=spell_dict["bowler_id"],
            bowler_name=spell_dict["bowler_name"],
            match_id=spell_dict["match_id"],
            innings=spell_dict["innings"],
            overs=spell_dict["overs"],
            legal_balls=spell_dict["legal_balls"],
            wickets=spell_dict["wickets"],
            bowler_runs=spell_dict["bowler_runs"],
            pcs_spell=spell_dict["pcs_spell"],
            deliveries=deliveries,
        )
