"""Read-only in-memory data service for validated Batting HPP/HPC production outputs.

Stage B9: Batting HPP Dashboard UI Modernization.
Strictly reads frozen, validated batting JSON artifacts from docs/worm_graph/
without modifying any underlying HPP, HPC, RAE, expected runs, pressure, or DNB values.
"""

import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from backend.core.config import settings


def _r(val: Optional[float], decimals: int = 2) -> Optional[float]:
    if val is None:
        return None
    if isinstance(val, float) and (math.isnan(val) or math.isinf(val)):
        return None
    return round(float(val), decimals)


class BattingDataService:
    """Singleton read-only service serving validated Batting HPP/HPC analytics."""

    _instance: Optional["BattingDataService"] = None

    def __init__(self) -> None:
        self.is_initialized: bool = False
        self.leaderboards_raw: Dict[str, Any] = {}
        self.match_index_list: List[Dict[str, Any]] = []
        self.match_index_map: Dict[str, Dict[str, Any]] = {}
        self.match_stints_raw: Dict[str, List[Dict[str, Any]]] = {}
        self.match_teams_map: Dict[str, Tuple[str, str, str, str]] = {}
        self.trajectory_cache: Dict[str, Dict[str, Any]] = {}

        # Indexed stints repository
        self.all_stints: List[Dict[str, Any]] = []
        self.player_stints_map: Dict[str, List[Dict[str, Any]]] = {}
        self.player_id_map: Dict[str, int] = {}
        self.id_to_player_name: Dict[int, str] = {}

        # Filter metadata caches (derived authoritatively from data, never hardcoded)
        self.seasons: List[str] = []
        self.tournaments: List[Dict[str, Any]] = []
        self.comp_categories: List[str] = []
        self.teams: List[str] = []
        self.pressure_tiers: List[str] = ["Low", "Medium", "High", "Extreme"]

    @classmethod
    def get_instance(cls) -> "BattingDataService":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def initialize(self) -> None:
        """Load validated batting HPP JSON artifacts into memory once."""
        if self.is_initialized:
            return

        # 1. Load hpp_leaderboards.json
        with open(settings.BATTING_LEADERBOARDS_FILE, "r", encoding="utf-8") as f:
            self.leaderboards_raw = json.load(f)

        for row in self.leaderboards_raw.get("career_top", []):
            name = row.get("batter_name")
            pid = row.get("player_id")
            if name and pid is not None:
                self.player_id_map[name] = int(pid)
                self.id_to_player_name[int(pid)] = name

        for row in self.leaderboards_raw.get("season_top", []):
            name = row.get("batter_name")
            pid = row.get("player_id")
            if name and pid is not None and name not in self.player_id_map:
                self.player_id_map[name] = int(pid)
                self.id_to_player_name[int(pid)] = name

        # 2. Load match_index.json
        with open(settings.BATTING_MATCH_INDEX_FILE, "r", encoding="utf-8") as f:
            self.match_index_list = json.load(f)
        self.match_index_map = {str(m["id"]): m for m in self.match_index_list}

        # 3. Load hpp_match_data.json
        with open(settings.BATTING_MATCH_DATA_FILE, "r", encoding="utf-8") as f:
            self.match_stints_raw = json.load(f)

        # 4. Extract authoritative team_a (inn 1) / team_b (inn 2) from trajectory files
        traj_dir = settings.BATTING_TRAJECTORIES_DIR
        teams_set: Set[str] = set()
        if traj_dir.exists():
            for mid in self.match_stints_raw.keys():
                t_path = traj_dir / f"{mid}.json"
                if t_path.exists():
                    try:
                        with open(t_path, "r", encoding="utf-8") as tf:
                            tdata = json.load(tf)
                        ta = tdata.get("team_a_name") or ""
                        tb = tdata.get("team_b_name") or ""
                        ca = tdata.get("team_a_color") or "#EC4899"
                        cb = tdata.get("team_b_color") or "#3B82F6"
                        self.match_teams_map[str(mid)] = (ta, tb, ca, cb)
                        if ta:
                            teams_set.add(ta)
                        if tb:
                            teams_set.add(tb)
                    except Exception:
                        pass

        # 5. Build enriched read-only stints repository (preserving exact HPP/HPC/RAE/DNB fields)
        seasons_set: Set[str] = set()
        comp_cat_set: Set[str] = set()
        comp_counts: Dict[str, Dict[str, Any]] = {}
        player_stints: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        all_stints: List[Dict[str, Any]] = []

        for mid, stints in self.match_stints_raw.items():
            mid_str = str(mid)
            meta = self.match_index_map.get(mid_str, {})
            match_date = meta.get("date") or ""
            match_year = str(meta.get("year")) if meta.get("year") is not None else ""
            comp_cat = meta.get("comp") or "T20"
            comp_name = meta.get("comp_name") or comp_cat
            home = meta.get("home") or ""
            away = meta.get("away") or ""
            winner = meta.get("winner") or ""
            result = meta.get("result") or ""
            venue = meta.get("venue") or ""

            ta, tb, _, _ = self.match_teams_map.get(mid_str, (home, away, "#EC4899", "#3B82F6"))
            teams_label = f"{ta} vs {tb}" if ta and tb else f"{home} vs {away}"

            if match_year:
                seasons_set.add(match_year)
            if comp_cat:
                comp_cat_set.add(comp_cat)
            if comp_name:
                if comp_name not in comp_counts:
                    comp_counts[comp_name] = {
                        "comp_name": comp_name,
                        "comp_category": comp_cat,
                        "seasons": set(),
                        "matches": set(),
                    }
                if match_year:
                    comp_counts[comp_name]["seasons"].add(match_year)
                comp_counts[comp_name]["matches"].add(mid_str)

            for s in stints:
                inn = int(s.get("inn", 1))
                is_dnb = bool(s.get("is_dnb", False))
                team = ta if inn == 1 else tb
                opponent = tb if inn == 1 else ta
                if team:
                    teams_set.add(team)

                # Preserve DNB semantics strictly: never convert None to 0
                enriched = {
                    "match_id": mid_str,
                    "date": match_date,
                    "season": match_year,
                    "comp_category": comp_cat,
                    "comp_name": comp_name,
                    "venue": venue,
                    "teams": teams_label,
                    "team": team,
                    "opponent": opponent,
                    "winner": winner,
                    "result": result,
                    "name": s["name"],
                    "inn": inn,
                    "runs": None if is_dnb else int(s.get("runs", 0)),
                    "balls": None if is_dnb else int(s.get("balls", 0)),
                    "fours": None if is_dnb else int(s.get("fours", 0)),
                    "sixes": None if is_dnb else int(s.get("sixes", 0)),
                    "exp_runs": None if is_dnb else _r(s.get("exp_runs"), 2),
                    "rae": None if is_dnb else _r(s.get("rae"), 2),
                    "mean_p": None if is_dnb else _r(s.get("mean_p"), 2),
                    "peak_p": None if is_dnb else _r(s.get("peak_p"), 2),
                    "hpc": None if is_dnb else _r(s.get("hpc"), 2),
                    "tier": "DNB" if is_dnb else (s.get("tier") or "Low"),
                    "dismissal": "Not Batted" if is_dnb else (s.get("dismissal") or "not out"),
                    "dismissal_type": None if is_dnb else s.get("dismissal_type"),
                    "is_out": False if is_dnb else bool(s.get("is_out", False)),
                    "is_dnb": is_dnb,
                }
                all_stints.append(enriched)
                player_stints[s["name"]].append(enriched)

        # Chronological sort for each player
        for pname, plist in player_stints.items():
            plist.sort(key=lambda x: (x["date"], int(x["match_id"]), x["inn"]))

        self.all_stints = all_stints
        self.player_stints_map = dict(player_stints)
        self.seasons = sorted(seasons_set)
        self.comp_categories = sorted(comp_cat_set)
        self.teams = sorted(t for t in teams_set if t)
        self.tournaments = sorted(
            [
                {
                    "comp_name": info["comp_name"],
                    "comp_category": info["comp_category"],
                    "seasons": sorted(info["seasons"]),
                    "match_count": len(info["matches"]),
                }
                for info in comp_counts.values()
            ],
            key=lambda x: (-x["match_count"], x["comp_name"]),
        )
        self.is_initialized = True

    # ------------------------------------------------------------------
    # Filtering & Aggregation Helpers (Strictly Read-Only, DNB-Safe)
    # ------------------------------------------------------------------
    def _filter_stints(
        self,
        stints: List[Dict[str, Any]],
        season: Optional[str] = None,
        tournament: Optional[str] = None,
        comp_category: Optional[str] = None,
        team: Optional[str] = None,
        tier: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        out = stints
        if season and season.lower() != "all":
            out = [s for s in out if s["season"] == str(season)]
        if comp_category and comp_category.lower() != "all":
            out = [s for s in out if s["comp_category"].lower() == comp_category.lower()]
        if tournament and tournament.lower() != "all":
            t_low = tournament.lower()
            out = [s for s in out if s["comp_name"].lower() == t_low or s["comp_category"].lower() == t_low]
        if team and team.lower() != "all":
            tm_low = team.lower()
            out = [s for s in out if (s["team"] or "").lower() == tm_low]
        if tier and tier.lower() != "all":
            tr_low = tier.lower()
            out = [s for s in out if (s["tier"] or "").lower() == tr_low]
        return out

    def _aggregate_player_stints(self, name: str, stints: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Aggregate a player's validated stints, strictly excluding DNB from all averages."""
        batted = [s for s in stints if not s["is_dnb"]]
        dnb_stints = [s for s in stints if s["is_dnb"]]
        match_ids = {s["match_id"] for s in stints}
        teams_played = sorted({s["team"] for s in stints if s["team"]})

        inns = len(batted)
        dnb_count = len(dnb_stints)
        runs = sum(s["runs"] or 0 for s in batted)
        balls = sum(s["balls"] or 0 for s in batted)
        fours = sum(s["fours"] or 0 for s in batted)
        sixes = sum(s["sixes"] or 0 for s in batted)
        outs = sum(1 for s in batted if s["is_out"])
        not_outs = inns - outs

        exp_runs = sum(s["exp_runs"] for s in batted if s["exp_runs"] is not None)
        total_rae = sum(s["rae"] for s in batted if s["rae"] is not None)
        total_hpc = sum(s["hpc"] for s in batted if s["hpc"] is not None)
        pos_inns = sum(1 for s in batted if s["hpc"] is not None and s["hpc"] > 0)
        neg_inns = sum(1 for s in batted if s["hpc"] is not None and s["hpc"] < 0)
        neutral_inns = inns - pos_inns - neg_inns
        pos_hpc_sum = sum(s["hpc"] for s in batted if s["hpc"] is not None and s["hpc"] > 0)
        neg_hpc_sum = sum(s["hpc"] for s in batted if s["hpc"] is not None and s["hpc"] < 0)

        p_vals = [s["mean_p"] for s in batted if s["mean_p"] is not None]
        avg_pressure = (sum(p_vals) / len(p_vals)) if p_vals else None

        crisis = [s for s in batted if s["tier"] in ("High", "Extreme")]
        crisis_hpc = sum(s["hpc"] for s in crisis if s["hpc"] is not None)

        batting_avg = (runs / outs) if outs > 0 else None
        strike_rate = (runs / balls * 100.0) if balls > 0 else None
        mean_hpc = (total_hpc / inns) if inns > 0 else None
        mean_rae = (total_rae / inns) if inns > 0 else None
        positive_pct = (pos_inns / inns * 100.0) if inns > 0 else None

        return {
            "batter_name": name,
            "player_id": self.player_id_map.get(name),
            "teams": teams_played,
            "primary_team": teams_played[0] if teams_played else None,
            "total_matches": len(match_ids),
            "innings_batted": inns,
            "dnb_count": dnb_count,
            "actual_runs": runs,
            "balls_faced": balls,
            "fours": fours,
            "sixes": sixes,
            "outs": outs,
            "not_outs": not_outs,
            "batting_average": _r(batting_avg, 2),
            "strike_rate": _r(strike_rate, 2),
            "expected_runs": _r(exp_runs, 2) if inns > 0 else None,
            "total_rae": _r(total_rae, 2) if inns > 0 else None,
            "mean_rae": _r(mean_rae, 2),
            "total_hpc": _r(total_hpc, 2) if inns > 0 else None,
            "mean_hpc": _r(mean_hpc, 2),
            "pos_hpc_sum": _r(pos_hpc_sum, 2) if inns > 0 else None,
            "neg_hpc_sum": _r(neg_hpc_sum, 2) if inns > 0 else None,
            "positive_innings": pos_inns,
            "negative_innings": neg_inns,
            "neutral_innings": neutral_inns,
            "positive_contribution_pct": _r(positive_pct, 1),
            "avg_pressure_faced": _r(avg_pressure, 2),
            "crisis_innings": len(crisis),
            "crisis_total_hpc": _r(crisis_hpc, 2) if inns > 0 else None,
        }

    # ------------------------------------------------------------------
    # Public API Methods
    # ------------------------------------------------------------------
    def get_health(self) -> Dict[str, Any]:
        batted = sum(1 for s in self.all_stints if not s["is_dnb"])
        dnb = sum(1 for s in self.all_stints if s["is_dnb"])
        return {
            "status": "healthy" if self.is_initialized else "uninitialized",
            "matches_evaluated": len(self.match_stints_raw),
            "total_stints": len(self.all_stints),
            "batted_stints": batted,
            "dnb_stints": dnb,
            "unique_batters": len(self.player_stints_map),
            "seasons": self.seasons,
            "tournaments_count": len(self.tournaments),
            "teams_count": len(self.teams),
        }

    def get_filters(self) -> Dict[str, Any]:
        return {
            "seasons": self.seasons,
            "comp_categories": self.comp_categories,
            "tournaments": self.tournaments,
            "teams": self.teams,
            "pressure_tiers": self.pressure_tiers,
        }

    def get_dashboard(
        self,
        season: Optional[str] = None,
        tournament: Optional[str] = None,
        comp_category: Optional[str] = None,
        team: Optional[str] = None,
        tier: Optional[str] = None,
    ) -> Dict[str, Any]:
        filtered = self._filter_stints(
            self.all_stints,
            season=season,
            tournament=tournament,
            comp_category=comp_category,
            team=team,
            tier=tier,
        )
        batted = [s for s in filtered if not s["is_dnb"]]
        dnb = [s for s in filtered if s["is_dnb"]]
        match_ids = {s["match_id"] for s in filtered}

        total_runs = sum(s["runs"] or 0 for s in batted)
        total_balls = sum(s["balls"] or 0 for s in batted)
        total_exp = sum(s["exp_runs"] for s in batted if s["exp_runs"] is not None)
        total_hpc = sum(s["hpc"] for s in batted if s["hpc"] is not None)
        total_rae = sum(s["rae"] for s in batted if s["rae"] is not None)
        pos_stints = [s for s in batted if s["hpc"] is not None and s["hpc"] > 0]
        neg_stints = [s for s in batted if s["hpc"] is not None and s["hpc"] < 0]
        pos_hpc_sum = sum(s["hpc"] for s in pos_stints)
        neg_hpc_sum = sum(s["hpc"] for s in neg_stints)
        p_vals = [s["mean_p"] for s in batted if s["mean_p"] is not None]

        inns_cnt = len(batted)
        kpis = {
            "total_runs": total_runs,
            "total_balls": total_balls,
            "total_expected_runs": _r(total_exp, 1),
            "total_hpc": _r(total_hpc, 2),
            "avg_hpc": _r(total_hpc / inns_cnt, 2) if inns_cnt > 0 else 0.0,
            "total_rae": _r(total_rae, 2),
            "avg_rae": _r(total_rae / inns_cnt, 2) if inns_cnt > 0 else 0.0,
            "avg_pressure_faced": _r(sum(p_vals) / len(p_vals), 2) if p_vals else 0.0,
            "positive_contribution_pct": _r(len(pos_stints) / inns_cnt * 100.0, 2) if inns_cnt > 0 else 0.0,
            "positive_stints": len(pos_stints),
            "negative_stints": len(neg_stints),
            "pos_hpc_sum": _r(pos_hpc_sum, 1),
            "neg_hpc_sum": _r(neg_hpc_sum, 1),
            "matches_played": len(match_ids),
            "batted_stints": inns_cnt,
            "dnb_stints": len(dnb),
            "unique_batters": len({s["name"] for s in batted}),
            "corpus_strike_rate": _r(total_runs / total_balls * 100.0, 1) if total_balls > 0 else 0.0,
        }

        # Aggregate per player in active scope
        by_player: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for s in filtered:
            by_player[s["name"]].append(s)

        player_rows = [
            self._aggregate_player_stints(name, plist)
            for name, plist in by_player.items()
            if any(not x["is_dnb"] for x in plist)
        ]

        # Dynamic min-innings threshold for rate lists so small samples adapt when filtered
        min_inns_qual = 10 if inns_cnt > 2000 else (3 if inns_cnt > 200 else 1)
        qual_players = [p for p in player_rows if p["innings_batted"] >= min_inns_qual]
        if not qual_players:
            qual_players = player_rows

        top_contributors = sorted(
            player_rows,
            key=lambda p: p["total_hpc"] if p["total_hpc"] is not None else -1e9,
            reverse=True,
        )[:10]

        best_positive = sorted(
            qual_players,
            key=lambda p: (
                p["positive_contribution_pct"] if p["positive_contribution_pct"] is not None else -1e9,
                p["total_hpc"] if p["total_hpc"] is not None else -1e9,
            ),
            reverse=True,
        )[:10]

        negative_contributors = sorted(
            [p for p in player_rows if p["total_hpc"] is not None and p["total_hpc"] < 0],
            key=lambda p: p["total_hpc"],
        )[:10]

        # Recent performance trends (latest season in scope vs overall scope mean HPC)
        latest_season = max((s["season"] for s in batted if s["season"]), default=None)
        recent_trends = []
        if latest_season:
            recent_by_p: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
            for s in batted:
                if s["season"] == latest_season:
                    recent_by_p[s["name"]].append(s)
            career_lookup = {p["batter_name"]: p for p in player_rows}
            recent_min = 5 if len(recent_by_p) > 40 else 1
            for name, r_stints in recent_by_p.items():
                if len(r_stints) < recent_min:
                    continue
                r_agg = self._aggregate_player_stints(name, r_stints)
                c_agg = career_lookup.get(name)
                delta = None
                if c_agg and r_agg["mean_hpc"] is not None and c_agg["mean_hpc"] is not None:
                    delta = _r(r_agg["mean_hpc"] - c_agg["mean_hpc"], 2)
                recent_trends.append({
                    **r_agg,
                    "recent_season": latest_season,
                    "career_mean_hpc": c_agg["mean_hpc"] if c_agg else None,
                    "trend_delta": delta,
                })
            recent_trends.sort(
                key=lambda x: x["total_hpc"] if x["total_hpc"] is not None else -1e9,
                reverse=True,
            )
            recent_trends = recent_trends[:10]

        # 1. HPC Distribution Histogram (batted stints)
        bins = [
            ("<= -15", -1e9, -15.0),
            ("-15 to -10", -15.0, -10.0),
            ("-10 to -5", -10.0, -5.0),
            ("-5 to 0", -5.0, 0.0),
            ("0 to +5", 0.0, 5.0),
            ("+5 to +10", 5.0, 10.0),
            ("+10 to +20", 10.0, 20.0),
            ("> +20", 20.0, 1e9),
        ]
        hpc_dist = []
        for label, lo, hi in bins:
            if label == "<= -15":
                cnt = sum(1 for s in batted if s["hpc"] is not None and s["hpc"] <= hi)
            elif label == "> +20":
                cnt = sum(1 for s in batted if s["hpc"] is not None and s["hpc"] > lo)
            elif label == "0 to +5":
                cnt = sum(1 for s in batted if s["hpc"] is not None and 0.0 <= s["hpc"] <= hi)
            elif label == "-5 to 0":
                cnt = sum(1 for s in batted if s["hpc"] is not None and lo < s["hpc"] < 0.0)
            else:
                cnt = sum(1 for s in batted if s["hpc"] is not None and lo < s["hpc"] <= hi)
            hpc_dist.append({"label": label, "count": cnt, "is_positive": lo >= 0.0})

        # 2. Runs vs HPC Scatter (Top 120 batters by runs in scope)
        runs_vs_hpc = [
            {
                "batter_name": p["batter_name"],
                "runs": p["actual_runs"],
                "total_hpc": p["total_hpc"],
                "mean_hpc": p["mean_hpc"],
                "innings": p["innings_batted"],
                "strike_rate": p["strike_rate"],
                "positive_pct": p["positive_contribution_pct"],
            }
            for p in sorted(qual_players, key=lambda x: x["actual_runs"], reverse=True)[:120]
        ]

        # 3. Season Contribution Trend
        season_groups: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for s in batted:
            if s["season"]:
                season_groups[s["season"]].append(s)
        season_trend = []
        for yr in sorted(season_groups.keys()):
            st = season_groups[yr]
            n = len(st)
            s_runs = sum(x["runs"] or 0 for x in st)
            s_hpc = sum(x["hpc"] for x in st if x["hpc"] is not None)
            s_rae = sum(x["rae"] for x in st if x["rae"] is not None)
            s_p = [x["mean_p"] for x in st if x["mean_p"] is not None]
            s_pos = sum(1 for x in st if x["hpc"] is not None and x["hpc"] > 0)
            season_trend.append({
                "season": yr,
                "matches": len({x["match_id"] for x in st}),
                "stints": n,
                "total_runs": s_runs,
                "total_hpc": _r(s_hpc, 1),
                "avg_hpc": _r(s_hpc / n, 2) if n else 0.0,
                "avg_rae": _r(s_rae / n, 2) if n else 0.0,
                "avg_pressure": _r(sum(s_p) / len(s_p), 2) if s_p else 0.0,
                "positive_pct": _r(s_pos / n * 100.0, 1) if n else 0.0,
            })

        # 4. Pressure vs Contribution (Tier breakdown + Pressure deciles)
        pressure_tiers = []
        for tname in ["Low", "Medium", "High", "Extreme"]:
            tst = [s for s in batted if s["tier"] == tname]
            n = len(tst)
            t_runs = sum(x["runs"] or 0 for x in tst)
            t_exp = sum(x["exp_runs"] for x in tst if x["exp_runs"] is not None)
            t_hpc = sum(x["hpc"] for x in tst if x["hpc"] is not None)
            t_rae = sum(x["rae"] for x in tst if x["rae"] is not None)
            t_p = [x["mean_p"] for x in tst if x["mean_p"] is not None]
            t_pos = sum(1 for x in tst if x["hpc"] is not None and x["hpc"] > 0)
            pressure_tiers.append({
                "tier": tname,
                "stints": n,
                "share_pct": _r(n / inns_cnt * 100.0, 1) if inns_cnt else 0.0,
                "avg_pressure": _r(sum(t_p) / len(t_p), 2) if t_p else 0.0,
                "total_runs": t_runs,
                "total_expected_runs": _r(t_exp, 1),
                "total_hpc": _r(t_hpc, 1),
                "avg_hpc": _r(t_hpc / n, 2) if n else 0.0,
                "avg_rae": _r(t_rae / n, 2) if n else 0.0,
                "positive_pct": _r(t_pos / n * 100.0, 1) if n else 0.0,
            })

        # 5. Innings Comparison (1st Innings vs 2nd Innings Chase)
        innings_comparison = []
        for inn_num, label in [(1, "1st Innings (Setting)"), (2, "2nd Innings (Chasing)")]:
            ist = [s for s in batted if s["inn"] == inn_num]
            n = len(ist)
            i_runs = sum(x["runs"] or 0 for x in ist)
            i_hpc = sum(x["hpc"] for x in ist if x["hpc"] is not None)
            i_rae = sum(x["rae"] for x in ist if x["rae"] is not None)
            i_p = [x["mean_p"] for x in ist if x["mean_p"] is not None]
            i_pos = sum(1 for x in ist if x["hpc"] is not None and x["hpc"] > 0)
            innings_comparison.append({
                "innings": inn_num,
                "label": label,
                "stints": n,
                "total_runs": i_runs,
                "total_hpc": _r(i_hpc, 1),
                "avg_hpc": _r(i_hpc / n, 2) if n else 0.0,
                "avg_rae": _r(i_rae / n, 2) if n else 0.0,
                "avg_pressure": _r(sum(i_p) / len(i_p), 2) if i_p else 0.0,
                "positive_pct": _r(i_pos / n * 100.0, 1) if n else 0.0,
            })

        # 6. Player Contribution Ranking (Top 10 positive + Bottom 5 negative for chart)
        ranking_chart = {
            "top": [
                {"batter_name": p["batter_name"], "total_hpc": p["total_hpc"], "runs": p["actual_runs"]}
                for p in top_contributors[:10]
            ],
            "bottom": [
                {"batter_name": p["batter_name"], "total_hpc": p["total_hpc"], "runs": p["actual_runs"]}
                for p in negative_contributors[:5]
            ],
        }

        return {
            "scope": {
                "season": season or "all",
                "tournament": tournament or "all",
                "comp_category": comp_category or "all",
                "team": team or "all",
                "tier": tier or "all",
                "min_innings_qual": min_inns_qual,
            },
            "kpis": kpis,
            "top_contributors": top_contributors,
            "best_positive_contributors": best_positive,
            "negative_contributors": negative_contributors,
            "recent_trends": recent_trends,
            "charts": {
                "hpc_distribution": hpc_dist,
                "runs_vs_hpc": runs_vs_hpc,
                "season_trend": season_trend,
                "pressure_vs_contribution": pressure_tiers,
                "innings_comparison": innings_comparison,
                "player_ranking": ranking_chart,
            },
        }

    def get_explorer(
        self,
        search: Optional[str] = None,
        season: Optional[str] = None,
        team: Optional[str] = None,
        tournament: Optional[str] = None,
        comp_category: Optional[str] = None,
        tier: Optional[str] = None,
        min_inns: int = 1,
        min_hpc: Optional[float] = None,
        max_hpc: Optional[float] = None,
        sort_by: str = "total_hpc",
        sort_order: str = "desc",
        page: int = 1,
        page_size: int = 25,
    ) -> Dict[str, Any]:
        filtered = self._filter_stints(
            self.all_stints,
            season=season,
            tournament=tournament,
            comp_category=comp_category,
            team=team,
            tier=tier,
        )

        by_player: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for s in filtered:
            by_player[s["name"]].append(s)

        rows = [
            self._aggregate_player_stints(name, plist)
            for name, plist in by_player.items()
            if any(not x["is_dnb"] for x in plist)
        ]

        if search and search.strip():
            q = search.strip().lower()
            rows = [
                r for r in rows
                if q in r["batter_name"].lower()
                or any(q in tm.lower() for tm in r["teams"])
            ]

        if min_inns > 0:
            rows = [r for r in rows if r["innings_batted"] >= min_inns]

        if min_hpc is not None:
            rows = [r for r in rows if r["total_hpc"] is not None and r["total_hpc"] >= min_hpc]

        if max_hpc is not None:
            rows = [r for r in rows if r["total_hpc"] is not None and r["total_hpc"] <= max_hpc]

        valid_sorts = {
            "total_hpc", "mean_hpc", "actual_runs", "strike_rate", "batting_average",
            "total_rae", "mean_rae", "positive_contribution_pct", "avg_pressure_faced",
            "crisis_total_hpc", "innings_batted", "balls_faced", "batter_name",
        }
        s_key = sort_by if sort_by in valid_sorts else "total_hpc"
        reverse = sort_order.lower() != "asc"

        if s_key == "batter_name":
            rows.sort(key=lambda r: r["batter_name"].lower(), reverse=reverse)
        else:
            rows.sort(
                key=lambda r: (
                    r[s_key] is not None,
                    r[s_key] if r[s_key] is not None else (-1e9 if reverse else 1e9),
                ),
                reverse=reverse,
            )

        # Assign contiguous ranks 1..N
        for idx, r in enumerate(rows, start=1):
            r["rank"] = idx

        total_items = len(rows)
        page_size = max(1, min(page_size, 100))
        total_pages = max(1, math.ceil(total_items / page_size))
        page = max(1, min(page, total_pages))
        start = (page - 1) * page_size
        page_items = rows[start : start + page_size]

        return {
            "items": page_items,
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total_items": total_items,
                "total_pages": total_pages,
            },
            "filters_applied": {
                "search": search or "",
                "season": season or "all",
                "team": team or "all",
                "tournament": tournament or "all",
                "comp_category": comp_category or "all",
                "tier": tier or "all",
                "min_inns": min_inns,
                "min_hpc": min_hpc,
                "max_hpc": max_hpc,
                "sort_by": s_key,
                "sort_order": "desc" if reverse else "asc",
            },
        }

    def list_players(self, search: Optional[str] = None, limit: int = 1000) -> List[Dict[str, Any]]:
        res = []
        q = search.strip().lower() if search and search.strip() else None
        for name, stints in self.player_stints_map.items():
            if q and q not in name.lower():
                continue
            batted = [s for s in stints if not s["is_dnb"]]
            dnb = len(stints) - len(batted)
            runs = sum(s["runs"] or 0 for s in batted)
            hpc = sum(s["hpc"] for s in batted if s["hpc"] is not None)
            teams = sorted({s["team"] for s in stints if s["team"]})
            res.append({
                "batter_name": name,
                "player_id": self.player_id_map.get(name),
                "primary_team": teams[0] if teams else None,
                "teams": teams,
                "innings_batted": len(batted),
                "dnb_count": dnb,
                "actual_runs": runs,
                "total_hpc": _r(hpc, 2) if batted else None,
            })
        res.sort(key=lambda x: (x["total_hpc"] if x["total_hpc"] is not None else -1e9), reverse=True)
        return res[:limit]

    def resolve_player_name(self, identifier: str) -> Optional[str]:
        """Resolve exact batter name, case-insensitive name, or numeric player_id."""
        if identifier in self.player_stints_map:
            return identifier
        if identifier.isdigit():
            pid = int(identifier)
            if pid in self.id_to_player_name:
                return self.id_to_player_name[pid]
        low = identifier.strip().lower()
        for name in self.player_stints_map.keys():
            if name.lower() == low:
                return name
        return None

    def get_player_profile(
        self,
        identifier: str,
        season: Optional[str] = None,
        tournament: Optional[str] = None,
        comp_category: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        name = self.resolve_player_name(identifier)
        if not name:
            return None

        all_p_stints = self.player_stints_map[name]
        available_seasons = sorted({s["season"] for s in all_p_stints if s["season"]})
        available_tournaments = sorted({s["comp_name"] for s in all_p_stints if s["comp_name"]})

        scoped = self._filter_stints(
            all_p_stints,
            season=season,
            tournament=tournament,
            comp_category=comp_category,
        )

        summary = self._aggregate_player_stints(name, scoped)
        batted = [s for s in scoped if not s["is_dnb"]]

        # Contribution by innings (1st vs 2nd)
        by_innings = []
        for inn_num, label in [(1, "1st Innings (Setting)"), (2, "2nd Innings (Chasing)")]:
            ist = [s for s in batted if s["inn"] == inn_num]
            n = len(ist)
            i_runs = sum(x["runs"] or 0 for x in ist)
            i_balls = sum(x["balls"] or 0 for x in ist)
            i_hpc = sum(x["hpc"] for x in ist if x["hpc"] is not None)
            i_rae = sum(x["rae"] for x in ist if x["rae"] is not None)
            i_p = [x["mean_p"] for x in ist if x["mean_p"] is not None]
            i_pos = sum(1 for x in ist if x["hpc"] is not None and x["hpc"] > 0)
            by_innings.append({
                "innings": inn_num,
                "label": label,
                "innings_batted": n,
                "runs": i_runs,
                "balls": i_balls,
                "strike_rate": _r(i_runs / i_balls * 100.0, 1) if i_balls > 0 else None,
                "total_hpc": _r(i_hpc, 2) if n else None,
                "mean_hpc": _r(i_hpc / n, 2) if n else None,
                "total_rae": _r(i_rae, 2) if n else None,
                "avg_pressure": _r(sum(i_p) / len(i_p), 2) if i_p else None,
                "positive_pct": _r(i_pos / n * 100.0, 1) if n else None,
            })

        # Contribution by pressure tier
        by_tier = []
        for tname in ["Low", "Medium", "High", "Extreme"]:
            tst = [s for s in batted if s["tier"] == tname]
            n = len(tst)
            t_runs = sum(x["runs"] or 0 for x in tst)
            t_hpc = sum(x["hpc"] for x in tst if x["hpc"] is not None)
            t_rae = sum(x["rae"] for x in tst if x["rae"] is not None)
            t_pos = sum(1 for x in tst if x["hpc"] is not None and x["hpc"] > 0)
            by_tier.append({
                "tier": tname,
                "innings_batted": n,
                "runs": t_runs,
                "total_hpc": _r(t_hpc, 2) if n else 0.0,
                "mean_hpc": _r(t_hpc / n, 2) if n else None,
                "total_rae": _r(t_rae, 2) if n else 0.0,
                "positive_pct": _r(t_pos / n * 100.0, 1) if n else None,
            })

        # Season-wise breakdown
        s_groups: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for s in scoped:
            if s["season"]:
                s_groups[s["season"]].append(s)
        season_breakdown = []
        for yr in sorted(s_groups.keys()):
            agg = self._aggregate_player_stints(name, s_groups[yr])
            season_breakdown.append({"season": yr, **agg})

        # Chronological match log WITH cumulative HPC (only incrementing on batted stints, NEVER on DNB)
        cum_hpc = 0.0
        match_log = []
        batted_seq = 0
        for s in scoped:
            if not s["is_dnb"] and s["hpc"] is not None:
                cum_hpc += s["hpc"]
                batted_seq += 1
                row_cum = _r(cum_hpc, 2)
                seq_num = batted_seq
            else:
                row_cum = None
                seq_num = None
            match_log.append({
                **s,
                "batted_index": seq_num,
                "cumulative_hpc": row_cum,
            })

        return {
            "summary": summary,
            "available_seasons": available_seasons,
            "available_tournaments": available_tournaments,
            "scope": {
                "season": season or "all",
                "tournament": tournament or "all",
                "comp_category": comp_category or "all",
            },
            "by_innings": by_innings,
            "by_pressure_tier": by_tier,
            "season_breakdown": season_breakdown,
            "match_log": match_log,
        }

    def compare_players(
        self,
        player_names: List[str],
        season: Optional[str] = None,
        tournament: Optional[str] = None,
        comp_category: Optional[str] = None,
    ) -> Dict[str, Any]:
        resolved: List[str] = []
        for raw_name in player_names:
            r = self.resolve_player_name(raw_name)
            if r and r not in resolved:
                resolved.append(r)

        profiles = []
        all_seasons: Set[str] = set()
        match_participation: Dict[str, Dict[str, Dict[str, Any]]] = defaultdict(dict)

        for pname in resolved:
            prof = self.get_player_profile(
                pname,
                season=season,
                tournament=tournament,
                comp_category=comp_category,
            )
            if not prof:
                continue
            for sb in prof["season_breakdown"]:
                all_seasons.add(sb["season"])
            for ml in prof["match_log"]:
                match_participation[ml["match_id"]][pname] = ml

            # Career cumulative trend points (batted stints only)
            cum_trend = [
                {
                    "batted_index": ml["batted_index"],
                    "date": ml["date"],
                    "cumulative_hpc": ml["cumulative_hpc"],
                    "hpc": ml["hpc"],
                    "runs": ml["runs"],
                }
                for ml in prof["match_log"]
                if not ml["is_dnb"]
            ]

            profiles.append({
                "batter_name": pname,
                "summary": prof["summary"],
                "by_innings": prof["by_innings"],
                "by_pressure_tier": prof["by_pressure_tier"],
                "season_breakdown": prof["season_breakdown"],
                "cumulative_trend": cum_trend,
            })

        # Shared matches where at least 2 compared players appeared
        common_matches = []
        for mid, pmap in match_participation.items():
            if len(pmap) >= 2:
                sample = next(iter(pmap.values()))
                common_matches.append({
                    "match_id": mid,
                    "date": sample["date"],
                    "season": sample["season"],
                    "comp_name": sample["comp_name"],
                    "teams": sample["teams"],
                    "result": sample["result"],
                    "players": {
                        pn: {
                            "team": st["team"],
                            "inn": st["inn"],
                            "is_dnb": st["is_dnb"],
                            "runs": st["runs"],
                            "balls": st["balls"],
                            "exp_runs": st["exp_runs"],
                            "rae": st["rae"],
                            "mean_p": st["mean_p"],
                            "hpc": st["hpc"],
                            "tier": st["tier"],
                            "dismissal": st["dismissal"],
                        }
                        for pn, st in pmap.items()
                    },
                })
        common_matches.sort(key=lambda m: (m["date"], int(m["match_id"])), reverse=True)

        return {
            "players": profiles,
            "seasons": sorted(all_seasons),
            "common_matches": common_matches[:50],
            "total_common_matches": len(common_matches),
            "scope": {
                "season": season or "all",
                "tournament": tournament or "all",
                "comp_category": comp_category or "all",
            },
        }

    def list_matches(
        self,
        search: Optional[str] = None,
        season: Optional[str] = None,
        tournament: Optional[str] = None,
        comp_category: Optional[str] = None,
        team: Optional[str] = None,
        page: int = 1,
        page_size: int = 30,
    ) -> Dict[str, Any]:
        items = []
        for mid_str in self.match_stints_raw.keys():
            meta = self.match_index_map.get(mid_str, {})
            ta, tb, ca, cb = self.match_teams_map.get(
                mid_str, (meta.get("home", ""), meta.get("away", ""), "#EC4899", "#3B82F6")
            )
            yr = str(meta.get("year", ""))
            comp_cat = meta.get("comp", "T20")
            comp_name = meta.get("comp_name", comp_cat)

            if season and season.lower() != "all" and yr != str(season):
                continue
            if comp_category and comp_category.lower() != "all" and comp_cat.lower() != comp_category.lower():
                continue
            if tournament and tournament.lower() != "all" and comp_name.lower() != tournament.lower() and comp_cat.lower() != tournament.lower():
                continue
            if team and team.lower() != "all":
                tm = team.lower()
                if ta.lower() != tm and tb.lower() != tm:
                    continue
            if search and search.strip():
                q = search.strip().lower()
                hay = f"{mid_str} {ta} {tb} {comp_name} {meta.get('venue', '')} {meta.get('result', '')}".lower()
                if q not in hay:
                    continue

            stints = self.match_stints_raw.get(mid_str, [])
            batted = [s for s in stints if not s.get("is_dnb")]
            top_batter = max(batted, key=lambda x: x.get("hpc") if x.get("hpc") is not None else -1e9) if batted else None

            items.append({
                "match_id": mid_str,
                "date": meta.get("date", ""),
                "season": yr,
                "comp_category": comp_cat,
                "comp_name": comp_name,
                "team_a": ta,
                "team_b": tb,
                "team_a_color": ca,
                "team_b_color": cb,
                "winner": meta.get("winner", ""),
                "result": meta.get("result", ""),
                "venue": meta.get("venue", ""),
                "balls": meta.get("balls", 0),
                "top_batter_name": top_batter["name"] if top_batter else None,
                "top_batter_hpc": _r(top_batter["hpc"], 2) if top_batter and top_batter.get("hpc") is not None else None,
                "top_batter_runs": top_batter["runs"] if top_batter else None,
            })

        items.sort(key=lambda m: (m["date"], int(m["match_id"])), reverse=True)
        total_items = len(items)
        page_size = max(1, min(page_size, 100))
        total_pages = max(1, math.ceil(total_items / page_size))
        page = max(1, min(page, total_pages))
        start = (page - 1) * page_size

        return {
            "items": items[start : start + page_size],
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total_items": total_items,
                "total_pages": total_pages,
            },
        }

    def get_match_detail(self, match_id: str) -> Optional[Dict[str, Any]]:
        mid_str = str(match_id)
        if mid_str not in self.match_stints_raw:
            return None

        # Load and cache trajectory JSON (read-only)
        if mid_str not in self.trajectory_cache:
            t_path = settings.BATTING_TRAJECTORIES_DIR / f"{mid_str}.json"
            if not t_path.exists():
                return None
            with open(t_path, "r", encoding="utf-8") as f:
                self.trajectory_cache[mid_str] = json.load(f)

        raw_traj = self.trajectory_cache[mid_str]
        meta = self.match_index_map.get(mid_str, {})

        # Parse points using exact worm_graph.html over.ball normalization (Stage 6B.7)
        points = []
        for arr in raw_traj.get("points", []):
            rem = arr[6] if (arr[6] != -1 and arr[6] is not None) else 120
            legal_comp = max(0, 120 - rem)
            l_num = legal_comp + 1
            over_num = (l_num - 1) // 6
            ball_num = ((l_num - 1) % 6) + 1
            corrected_ob = f"{over_num}.{ball_num}"
            points.append({
                "ball_index": arr[0],
                "innings": arr[1],
                "raw_over_ball": arr[2],
                "over_ball": corrected_ob,
                "score": arr[3],
                "wickets": arr[4],
                "runs_required": None if arr[5] == -1 else arr[5],
                "legal_balls_remaining": None if arr[6] == -1 else arr[6],
                "team_a_prob": arr[7],
                "team_b_prob": arr[8],
                "delta_team_a_prob": arr[9],
                "runs_on_ball": arr[10],
                "is_wicket": bool(arr[11]),
                "is_four": bool(arr[12]),
                "is_six": bool(arr[13]),
                "is_no_ball": bool(arr[14]),
                "event_label": arr[15],
                "striker_name": arr[16],
                "bowler_name": arr[17],
            })

        # Synchronize key moments with corrected over_ball
        moments = []
        for m in raw_traj.get("moments", []):
            matched_pt = next(
                (p for p in points if p["innings"] == m["innings"] and (p["raw_over_ball"] == m["over_ball"] or p["over_ball"] == m["over_ball"])),
                None,
            )
            moments.append({
                **m,
                "over_ball": matched_pt["over_ball"] if matched_pt else m["over_ball"],
                "ball_index": matched_pt["ball_index"] if matched_pt else None,
            })

        # Enriched batting stints split by innings (strictly preserving DNB!)
        stints = [s for s in self.all_stints if s["match_id"] == mid_str]
        inn1 = [s for s in stints if s["inn"] == 1]
        inn2 = [s for s in stints if s["inn"] == 2]

        return {
            "match_id": mid_str,
            "match_date": raw_traj.get("match_date") or meta.get("date", ""),
            "season": str(meta.get("year", "")),
            "comp_category": meta.get("comp") or raw_traj.get("competition_category", "T20"),
            "comp_name": meta.get("comp_name") or raw_traj.get("competition_category", "T20"),
            "venue_name": raw_traj.get("venue_name") or meta.get("venue", ""),
            "team_a_name": raw_traj.get("team_a_name"),
            "team_b_name": raw_traj.get("team_b_name"),
            "team_a_color": raw_traj.get("team_a_color", "#EC4899"),
            "team_b_color": raw_traj.get("team_b_color", "#3B82F6"),
            "winner_name": raw_traj.get("winner_name") or meta.get("winner", ""),
            "result_text": raw_traj.get("result_text") or meta.get("result", ""),
            "innings_1_balls": raw_traj.get("innings_1_balls", 0),
            "innings_2_balls": raw_traj.get("innings_2_balls", 0),
            "total_balls": raw_traj.get("total_balls", len(points)),
            "target_score": raw_traj.get("target_score"),
            "pre_match": meta.get("pre_match"),
            "prediction_provenance": raw_traj.get("prediction_provenance"),
            "calibration_method": raw_traj.get("calibration_method"),
            "points": points,
            "moments": moments,
            "innings_1_stints": inn1,
            "innings_2_stints": inn2,
        }
