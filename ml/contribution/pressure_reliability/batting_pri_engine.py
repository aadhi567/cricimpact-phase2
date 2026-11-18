"""Stage PRI-2: Independent Batting Pressure Reliability Engine.

Evaluates batter reliability under genuine match pressure using approved decision T10:
    T10 = (mean_p >= 40.0) OR (peak_p >= 60.0)

Strict invariants:
- Read-only consumer of frozen HPP/HPC production outputs.
- NO SHRINKAGE applied at any level (career, season, or tournament).
- NO COMPOSITE SCORE combining Reliability Rate and Contribution Quality.
- DNB stints are strictly excluded from opportunities and never treated as zero.
- Neutral HPC (== 0.0) is classified as neutral, never positive.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import pandas as pd

from ml.contribution.hpp_engine import (
    FALLBACK_EXPECTED_TOTAL,
    calculate_delivery_pressure,
)
from ml.contribution.pressure_reliability.confidence import (
    classify_sample_confidence,
    wilson_interval_pair,
)
from ml.contribution.pressure_reliability.filters import (
    apply_min_opportunity_filter,
    apply_overall_leaderboard_visibility,
    load_pakistan_player_ids,
)
from ml.contribution.pressure_reliability.schema import (
    BATTING_SENSITIVITY_ENTRY_P_THRESHOLD,
    BATTING_T10_MEAN_P_THRESHOLD,
    BATTING_T10_PEAK_P_THRESHOLD,
    COMPETITIONS_CSV_PATH,
    HPC_NEUTRAL_ANCHOR,
    HPP_MATCH_DATA_PATH,
    MATCH_INDEX_PATH,
    MATCH_STATES_PATH,
    MATCHES_CSV_PATH,
    PLAYER_MAPPING_CSV_PATH,
    TRAJECTORIES_DIR,
)


def _normalize_season_year(val: Any) -> str:
    s = str(val).strip()
    if len(s) >= 4 and s[:4].isdigit():
        return s[:4]
    return s


class BattingPRIEngine:
    """Independent, unshrunk, dual-axis Batting Pressure Reliability Engine."""

    def __init__(
        self,
        mean_p_threshold: float = BATTING_T10_MEAN_P_THRESHOLD,
        peak_p_threshold: float = BATTING_T10_PEAK_P_THRESHOLD,
        entry_p_sensitivity_threshold: float = BATTING_SENSITIVITY_ENTRY_P_THRESHOLD,
    ) -> None:
        self.mean_p_threshold = float(mean_p_threshold)
        self.peak_p_threshold = float(peak_p_threshold)
        self.entry_p_sensitivity_threshold = float(entry_p_sensitivity_threshold)

    def _build_entry_pressure_and_id_lookups(
        self,
        match_states_path: Path = MATCH_STATES_PATH,
        mapping_path: Path = PLAYER_MAPPING_CSV_PATH,
    ) -> Tuple[
        Dict[Tuple[int, int, str], int],
        Dict[Tuple[int, int], List[Tuple[int, int, int]]],
        Dict[Tuple[int, int, int], float],
        Dict[int, str],
    ]:
        """Extract exact (match, inn, name)->player_id and strictly causal stint entry_p."""
        mapping_df = pd.read_csv(mapping_path)
        pid_to_name = (
            mapping_df.drop_duplicates("player_id")
            .set_index("player_id")["player_name"]
            .to_dict()
        )

        ms = pd.read_pickle(match_states_path)
        ms = ms.sort_values(["match_id", "innings", "innings_ball_num"]).reset_index(drop=True)

        # Compute venue benchmark total (inns1 average, causal fallback if unavailable)
        if "venue_avg_first_inn_score" in ms.columns:
            bench_series = pd.to_numeric(ms["venue_avg_first_inn_score"], errors="coerce").fillna(FALLBACK_EXPECTED_TOTAL)
        else:
            bench_series = pd.Series(FALLBACK_EXPECTED_TOTAL, index=ms.index)
        ms["_bench_total"] = bench_series

        # First ball faced by each (match_id, innings, striker_id) -> strictly causal entry_p
        first_balls = ms.groupby(["match_id", "innings", "striker_id"], as_index=False).first()
        entry_p_lookup: Dict[Tuple[int, int, int], float] = {}
        name_lookup: Dict[Tuple[int, int, str], int] = {}

        for _, r in first_balls.iterrows():
            mid = int(r["match_id"])
            inn = int(r["innings"])
            sid = int(r["striker_id"])
            ep = calculate_delivery_pressure(
                innings=inn,
                legal_balls_before=int(r.get("legal_balls_completed_before", 0) or 0),
                wickets_before=int(r.get("wickets_lost_before", 0) or 0),
                score_before=int(r.get("score_before", 0) or 0),
                bench_total=float(r["_bench_total"]),
                required_run_rate=r.get("required_run_rate_before", r.get("required_run_rate")),
                legal_balls_remaining_before=r.get("legal_balls_remaining_before"),
            )
            entry_p_lookup[(mid, inn, sid)] = round(float(ep), 2)
            mapped_name = pid_to_name.get(sid)
            if pd.notna(mapped_name):
                name_lookup[(mid, inn, str(mapped_name).strip())] = sid

        # Build runs/balls signature per (match_id, innings) for 100% fallback resolution of spelling variants
        # (e.g., Aneurin Donald vs AHT Donald)
        ms["_is_faced_ball"] = (~ms["is_wide"].fillna(False).astype(bool)).astype(int)
        stint_sigs = ms.groupby(["match_id", "innings", "striker_id"], as_index=False).agg(
            runs=("batter_runs", "sum"),
            balls=("_is_faced_ball", "sum"),
        )
        sig_by_mi: Dict[Tuple[int, int], List[Tuple[int, int, int]]] = {}
        for _, r in stint_sigs.iterrows():
            key = (int(r["match_id"]), int(r["innings"]))
            sig_by_mi.setdefault(key, []).append((int(r["striker_id"]), int(r["runs"]), int(r["balls"])))

        return name_lookup, sig_by_mi, entry_p_lookup, pid_to_name

    def load_all_batting_stints(self) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        """Load all validated HPP batting stints enriched with authoritative metadata."""
        with open(HPP_MATCH_DATA_PATH, "r", encoding="utf-8") as f:
            raw_match_data = json.load(f)
        with open(MATCH_INDEX_PATH, "r", encoding="utf-8") as f:
            match_index_list = json.load(f)
        match_index_map = {int(m["id"]): m for m in match_index_list}

        matches_df = pd.read_csv(MATCHES_CSV_PATH)
        comps_df = pd.read_csv(COMPETITIONS_CSV_PATH)
        match_comp_df = matches_df[["match_id", "comp_id", "match_date"]].merge(
            comps_df[["comp_id", "comp_name", "match_format", "season"]],
            on="comp_id",
            how="left",
        )
        match_comp_map = match_comp_df.set_index("match_id").to_dict(orient="index")

        # Authoritative innings batting teams from trajectory headers
        team_map: Dict[int, Tuple[str, str]] = {}
        if TRAJECTORIES_DIR.exists():
            for mid_str in raw_match_data.keys():
                tp = TRAJECTORIES_DIR / f"{mid_str}.json"
                if tp.exists():
                    with open(tp, "r", encoding="utf-8") as tf:
                        td = json.load(tf)
                    team_map[int(mid_str)] = (td.get("team_a_name", ""), td.get("team_b_name", ""))

        name_lookup, sig_by_mi, entry_p_lookup, _ = self._build_entry_pressure_and_id_lookups()
        pak_ids = load_pakistan_player_ids()

        # Also map unique player_name -> player_id for DNB rows
        mapping_df = pd.read_csv(PLAYER_MAPPING_CSV_PATH)
        unique_name_pid = (
            mapping_df.groupby("player_name")["player_id"]
            .agg(lambda s: int(s.iloc[0]) if s.nunique() == 1 else np.nan)
            .dropna()
            .astype(int)
            .to_dict()
        )

        records: List[Dict[str, Any]] = []
        unresolved_batted = 0

        for mid_str, stints in raw_match_data.items():
            mid = int(mid_str)
            m_idx = match_index_map.get(mid, {})
            m_comp = match_comp_map.get(mid, {})

            comp_id = int(m_comp["comp_id"]) if pd.notna(m_comp.get("comp_id")) else -1
            comp_name = str(m_comp.get("comp_name") or m_idx.get("comp_name") or "Unknown Competition")
            comp_category = str(m_idx.get("comp") or m_comp.get("match_format") or "T20")
            match_format = str(m_comp.get("match_format") or "T20")
            match_date = str(m_idx.get("date") or m_comp.get("match_date") or "")
            season_year = _normalize_season_year(m_idx.get("year") or match_date[:4] or m_comp.get("season", ""))
            ta, tb = team_map.get(mid, (m_idx.get("home", ""), m_idx.get("away", "")))

            # Track already claimed striker_ids in this (match_id, innings) for exact fallback
            claimed_by_inn: Dict[int, set[int]] = {1: set(), 2: set()}
            for s in stints:
                inn = int(s.get("inn", 1))
                pname = str(s["name"]).strip()
                pid_exact = name_lookup.get((mid, inn, pname))
                if pid_exact is not None:
                    claimed_by_inn.setdefault(inn, set()).add(pid_exact)

            for s in stints:
                inn = int(s.get("inn", 1))
                pname = str(s["name"]).strip()
                is_dnb = bool(s.get("is_dnb", False))
                runs = None if is_dnb else int(s.get("runs", 0))
                balls = None if is_dnb else int(s.get("balls", 0))

                pid: Optional[int] = name_lookup.get((mid, inn, pname))
                if pid is None and not is_dnb:
                    # Fallback: match unclaimed striker_id in this (match, innings) by exact (runs, balls)
                    candidates = [
                        cand_pid
                        for (cand_pid, c_runs, c_balls) in sig_by_mi.get((mid, inn), [])
                        if cand_pid not in claimed_by_inn.get(inn, set())
                        and c_runs == runs
                        and c_balls == balls
                    ]
                    if len(candidates) == 1:
                        pid = candidates[0]
                        claimed_by_inn.setdefault(inn, set()).add(pid)
                    else:
                        # Last resort: unique name in mapping
                        pid = unique_name_pid.get(pname)
                        if pid is None:
                            unresolved_batted += 1
                elif pid is None and is_dnb:
                    pid = unique_name_pid.get(pname)

                mean_p = None if is_dnb else float(s["mean_p"])
                peak_p = None if is_dnb else float(s["peak_p"])
                hpc = None if is_dnb else float(s["hpc"])
                rae = None if is_dnb else float(s["rae"])
                exp_runs = None if is_dnb else float(s["exp_runs"])
                entry_p = None if (is_dnb or pid is None) else entry_p_lookup.get((mid, inn, pid))

                # T10 Qualification (Strictly Non-DNB)
                if is_dnb or mean_p is None or peak_p is None or hpc is None:
                    qualifies_t10 = False
                    t10_reason = "dnb"
                    qualifies_entry_p = False
                    hpc_outcome = "dnb"
                else:
                    cond_mean = mean_p >= self.mean_p_threshold
                    cond_peak = peak_p >= self.peak_p_threshold
                    qualifies_t10 = bool(cond_mean or cond_peak)
                    if cond_mean and cond_peak:
                        t10_reason = "both"
                    elif cond_mean:
                        t10_reason = "mean_p_only"
                    elif cond_peak:
                        t10_reason = "peak_p_only"
                    else:
                        t10_reason = "below_threshold"

                    qualifies_entry_p = bool(
                        entry_p is not None and entry_p >= self.entry_p_sensitivity_threshold
                    )

                    if hpc > HPC_NEUTRAL_ANCHOR:
                        hpc_outcome = "positive"
                    elif hpc < HPC_NEUTRAL_ANCHOR:
                        hpc_outcome = "negative"
                    else:
                        hpc_outcome = "neutral"

                team_name = ta if inn == 1 else tb
                opp_name = tb if inn == 1 else ta
                is_pak = bool(pid is not None and int(pid) in pak_ids)

                records.append({
                    "match_id": mid,
                    "innings": inn,
                    "match_date": match_date,
                    "season": season_year,
                    "comp_id": comp_id,
                    "comp_name": comp_name,
                    "comp_category": comp_category,
                    "match_format": match_format,
                    "player_id": int(pid) if pid is not None else -1,
                    "batter_name": pname,
                    "team_name": team_name,
                    "opponent_name": opp_name,
                    "is_pakistan_player": is_pak,
                    "is_dnb": is_dnb,
                    "runs": runs,
                    "balls": balls,
                    "fours": None if is_dnb else int(s.get("fours", 0)),
                    "sixes": None if is_dnb else int(s.get("sixes", 0)),
                    "exp_runs": exp_runs,
                    "rae": rae,
                    "mean_p": mean_p,
                    "peak_p": peak_p,
                    "entry_p": entry_p,
                    "hpc": hpc,
                    "pressure_tier": "DNB" if is_dnb else str(s.get("tier") or "Low"),
                    "is_out": False if is_dnb else bool(s.get("is_out", False)),
                    "qualifies_t10": qualifies_t10,
                    "t10_reason": t10_reason,
                    "qualifies_entry_p_sensitivity": qualifies_entry_p,
                    "hpc_outcome": hpc_outcome,
                    "is_positive_hpc": hpc_outcome == "positive",
                    "is_negative_hpc": hpc_outcome == "negative",
                    "is_neutral_hpc": hpc_outcome == "neutral",
                })

        all_df = pd.DataFrame(records)
        all_df = all_df.sort_values(["match_date", "match_id", "innings", "batter_name"]).reset_index(drop=True)

        # Invariant check: no duplicate (match_id, innings, player_id) for batted stints
        batted_df = all_df[~all_df["is_dnb"]]
        dups = int(batted_df.duplicated(subset=["match_id", "innings", "player_id"]).sum())
        if dups > 0:
            raise RuntimeError(f"Duplicate batted stints detected: {dups}")

        audit_meta = {
            "source_matches": int(all_df["match_id"].nunique()),
            "source_total_stints": int(len(all_df)),
            "source_batted_stints": int(len(batted_df)),
            "source_dnb_stints": int(all_df["is_dnb"].sum()),
            "unresolved_batted_player_ids": unresolved_batted,
            "t10_qualifying_innings": int(all_df["qualifies_t10"].sum()),
            "t10_both_count": int((all_df["t10_reason"] == "both").sum()),
            "t10_mean_p_only_count": int((all_df["t10_reason"] == "mean_p_only").sum()),
            "t10_peak_p_only_count": int((all_df["t10_reason"] == "peak_p_only").sum()),
            "entry_p_sensitivity_innings": int(all_df["qualifies_entry_p_sensitivity"].sum()),
            "duplicate_batted_stints": dups,
        }
        return all_df, audit_meta

    def _aggregate_group(
        self,
        all_scope_df: pd.DataFrame,
        group_cols: List[str],
        extra_first_cols: Optional[List[str]] = None,
    ) -> pd.DataFrame:
        """Aggregate unshrunk dual-axis Batting PRI metrics over arbitrary grouping keys.

        Strict rules:
        - NO SHRINKAGE applied.
        - DNB excluded from pressure_innings and all averages.
        - Neutral HPC (== 0) NEVER counted as positive.
        - Players with 0 qualifying pressure innings get NaN reliability (never 0%).
        """
        extra_first_cols = extra_first_cols or []
        records: List[Dict[str, Any]] = []

        for grp_key, grp in all_scope_df.groupby(group_cols, sort=False):
            if not isinstance(grp_key, tuple):
                grp_key = (grp_key,)
            key_dict = dict(zip(group_cols, grp_key))

            batted = grp[~grp["is_dnb"]]
            dnb_cnt = int(grp["is_dnb"].sum())
            total_batted = int(len(batted))
            qual = batted[batted["qualifies_t10"]]
            n_opp = int(len(qual))

            # Pick canonical batter_name (most frequent in group) and primary_team
            batter_name = str(grp["batter_name"].mode().iloc[0])
            teams_list = sorted(t for t in grp["team_name"].dropna().unique() if str(t).strip())
            primary_team = teams_list[-1] if teams_list else None
            is_pak = bool(grp["is_pakistan_player"].any())

            row: Dict[str, Any] = {
                **key_dict,
                "batter_name": batter_name,
                "is_pakistan_player": is_pak,
                "primary_team": primary_team,
                "teams_count": len(teams_list),
                "total_matches": int(grp["match_id"].nunique()),
                "total_batted_innings": total_batted,
                "dnb_innings": dnb_cnt,
                "pressure_innings": n_opp,
                "pressure_opportunity_share_pct": (
                    round((n_opp / total_batted) * 100.0, 2) if total_batted > 0 else None
                ),
            }
            for col in extra_first_cols:
                row[col] = grp[col].iloc[0]

            if n_opp == 0:
                row.update({
                    "positive_hpc_innings": 0,
                    "negative_hpc_innings": 0,
                    "neutral_hpc_innings": 0,
                    "positive_hpc_pct": np.nan,
                    "negative_hpc_pct": np.nan,
                    "neutral_hpc_pct": np.nan,
                    "avg_hpc_under_pressure": np.nan,
                    "total_hpc_under_pressure": np.nan,
                    "highest_hpc": np.nan,
                    "lowest_hpc": np.nan,
                    "avg_rae_under_pressure": np.nan,
                    "total_rae_under_pressure": np.nan,
                    "total_runs_under_pressure": 0,
                    "total_balls_under_pressure": 0,
                    "mean_pressure": np.nan,
                    "avg_peak_pressure": np.nan,
                    "max_peak_pressure": np.nan,
                    "wilson_ci95_low": np.nan,
                    "wilson_ci95_high": np.nan,
                    "wilson_ci95_width": np.nan,
                    "wilson_ci90_low": np.nan,
                    "wilson_ci90_high": np.nan,
                    "wilson_ci90_width": np.nan,
                    "sample_confidence_tier": classify_sample_confidence(0),
                    "has_pressure_opportunities": False,
                    "status": "No Pressure Opportunities",
                })
            else:
                pos_n = int(qual["is_positive_hpc"].sum())
                neg_n = int(qual["is_negative_hpc"].sum())
                neu_n = int(qual["is_neutral_hpc"].sum())
                assert pos_n + neg_n + neu_n == n_opp, "Polarity partition mismatch"

                pos_pct = (pos_n / n_opp) * 100.0
                neg_pct = (neg_n / n_opp) * 100.0
                neu_pct = (neu_n / n_opp) * 100.0

                tot_hpc = float(qual["hpc"].sum())
                avg_hpc = tot_hpc / n_opp
                tot_rae = float(qual["rae"].sum())
                avg_rae = tot_rae / n_opp

                ci = wilson_interval_pair(pos_n, n_opp)

                row.update({
                    "positive_hpc_innings": pos_n,
                    "negative_hpc_innings": neg_n,
                    "neutral_hpc_innings": neu_n,
                    "positive_hpc_pct": round(pos_pct, 2),
                    "negative_hpc_pct": round(neg_pct, 2),
                    "neutral_hpc_pct": round(neu_pct, 2),
                    "avg_hpc_under_pressure": round(avg_hpc, 4),
                    "total_hpc_under_pressure": round(tot_hpc, 4),
                    "highest_hpc": round(float(qual["hpc"].max()), 2),
                    "lowest_hpc": round(float(qual["hpc"].min()), 2),
                    "avg_rae_under_pressure": round(avg_rae, 4),
                    "total_rae_under_pressure": round(tot_rae, 4),
                    "total_runs_under_pressure": int(qual["runs"].sum()),
                    "total_balls_under_pressure": int(qual["balls"].sum()),
                    "mean_pressure": round(float(qual["mean_p"].mean()), 2),
                    "avg_peak_pressure": round(float(qual["peak_p"].mean()), 2),
                    "max_peak_pressure": round(float(qual["peak_p"].max()), 2),
                    **ci,
                    "sample_confidence_tier": classify_sample_confidence(n_opp),
                    "has_pressure_opportunities": True,
                    "status": "Evaluated",
                })

            records.append(row)

        df_out = pd.DataFrame(records)
        if len(df_out) > 0:
            df_out = df_out.sort_values(
                by=["has_pressure_opportunities", "positive_hpc_pct", "avg_hpc_under_pressure", "pressure_innings"],
                ascending=[False, False, False, False],
                na_position="last",
            ).reset_index(drop=True)
        return df_out

    def run(self) -> Dict[str, Any]:
        """Execute full independent Batting PRI pipeline (Career, Season, Tournament)."""
        all_stints_df, audit_meta = self.load_all_batting_stints()
        pressure_innings_df = all_stints_df[all_stints_df["qualifies_t10"]].copy().reset_index(drop=True)

        # Career, Season, Tournament independent unshrunk aggregations
        career_df = self._aggregate_group(all_stints_df, group_cols=["player_id"])
        season_df = self._aggregate_group(all_stints_df, group_cols=["season", "player_id"])
        tournament_df = self._aggregate_group(
            all_stints_df,
            group_cols=["comp_id", "player_id"],
            extra_first_cols=["comp_name", "comp_category", "match_format", "season"],
        )

        # Strict Reconciliation Checks
        assert int(career_df["pressure_innings"].sum()) == len(pressure_innings_df), "Career pressure_innings mismatch"
        assert int(season_df["pressure_innings"].sum()) == len(pressure_innings_df), "Season pressure_innings mismatch"
        assert int(tournament_df["pressure_innings"].sum()) == len(pressure_innings_df), "Tournament pressure_innings mismatch"
        assert abs(float(career_df["total_hpc_under_pressure"].sum()) - float(pressure_innings_df["hpc"].sum())) < 1e-2
        assert abs(float(season_df["total_hpc_under_pressure"].sum()) - float(pressure_innings_df["hpc"].sum())) < 1e-2
        assert abs(float(tournament_df["total_hpc_under_pressure"].sum()) - float(pressure_innings_df["hpc"].sum())) < 1e-2

        return {
            "all_stints": all_stints_df,
            "pressure_innings": pressure_innings_df,
            "career": career_df,
            "season": season_df,
            "tournament": tournament_df,
            "audit_meta": audit_meta,
        }

    @staticmethod
    def get_overall_leaderboard(
        career_df: pd.DataFrame,
        min_opportunities: Any = 0,
        exclude_pakistan: bool = True,
        sort_by: str = "positive_hpc_pct",
        ascending: bool = False,
    ) -> pd.DataFrame:
        """Reusable Overall Batting PRI Leaderboard filter (custom min + B8 Pakistan visibility)."""
        visible = apply_overall_leaderboard_visibility(
            career_df,
            player_id_col="player_id",
            exclude_pakistan=exclude_pakistan,
        )
        return apply_min_opportunity_filter(
            visible,
            count_col="pressure_innings",
            min_opportunities=min_opportunities,
            sort_by=sort_by,
            ascending=ascending,
        )
