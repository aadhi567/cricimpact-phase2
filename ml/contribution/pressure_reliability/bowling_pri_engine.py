"""Stage PRI-2: Independent Bowling Pressure Reliability Engine.

Evaluates bowler reliability under genuine batting-team danger using approved decision EXO_2:
    EXO_2 = (max_over_entry_pti >= 35.0) AND (legal_balls >= 12)

Exogenous pre-over evaluation guarantees that a bowler who immediately takes a wicket to break
a dangerous partnership is NEVER removed from the pressure sample.

Strict invariants:
- Read-only consumer of frozen PCS delivery and spell production outputs.
- NO SHRINKAGE applied at any level (career, season, or tournament).
- NO COMPOSITE SCORE combining Reliability Rate and Contribution Quality.
- Preserves existing PCS spell definitions (`pcs_spell`, `total_rpe`) without recomputing PCS.
- Neutral PCS (== 50.00) is classified as neutral, never positive.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import pandas as pd

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
    BOWLING_EXO2_MAX_ENTRY_PTI_THRESHOLD,
    BOWLING_EXO2_MIN_LEGAL_BALLS,
    BOWLING_EXO5_MEAN_ENTRY_PTI_THRESHOLD,
    BOWLING_EXO5_MIN_LEGAL_BALLS,
    BOWLING_STAND_BREAK_PTI_THRESHOLD,
    COMPETITIONS_CSV_PATH,
    MATCHES_CSV_PATH,
    PCS_DELIVERIES_PATH,
    PCS_NEUTRAL_ANCHOR,
    PCS_SPELLS_PATH,
    PLAYER_MAPPING_CSV_PATH,
)


def _normalize_season_year(val: Any) -> str:
    s = str(val).strip()
    if len(s) >= 4 and s[:4].isdigit():
        return s[:4]
    return s


class BowlingPRIEngine:
    """Independent, unshrunk, dual-axis Bowling Pressure Reliability Engine."""

    def __init__(
        self,
        max_entry_pti_threshold: float = BOWLING_EXO2_MAX_ENTRY_PTI_THRESHOLD,
        min_legal_balls: int = BOWLING_EXO2_MIN_LEGAL_BALLS,
        exo5_mean_entry_pti_threshold: float = BOWLING_EXO5_MEAN_ENTRY_PTI_THRESHOLD,
        exo5_min_legal_balls: int = BOWLING_EXO5_MIN_LEGAL_BALLS,
    ) -> None:
        self.max_entry_pti_threshold = float(max_entry_pti_threshold)
        self.min_legal_balls = int(min_legal_balls)
        self.exo5_mean_entry_pti_threshold = float(exo5_mean_entry_pti_threshold)
        self.exo5_min_legal_balls = int(exo5_min_legal_balls)

    def load_all_bowling_spells(self) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        """Load all validated PCS match spells enriched with strictly exogenous over-entry danger."""
        deliv = pd.read_pickle(PCS_DELIVERIES_PATH)
        spells = pd.read_pickle(PCS_SPELLS_PATH)
        matches_df = pd.read_csv(MATCHES_CSV_PATH)
        comps_df = pd.read_csv(COMPETITIONS_CSV_PATH)
        mapping_df = pd.read_csv(PLAYER_MAPPING_CSV_PATH)

        player_names = (
            mapping_df.drop_duplicates("player_id")
            .set_index("player_id")["player_name"]
            .to_dict()
        )
        team_names = (
            mapping_df.drop_duplicates("team_id")
            .set_index("team_id")["team_name"]
            .to_dict()
            if "team_id" in mapping_df.columns
            else {}
        )
        pak_ids = load_pakistan_player_ids()

        # Sort chronologically strictly within match & innings
        deliv = deliv.sort_values(["match_id", "innings", "innings_ball_num"]).reset_index(drop=True)

        # 1. Strictly EXOGENOUS pre-over entry threat (Ball 1 of every over bowled by bowler)
        over_entries = deliv.groupby(["match_id", "innings", "overid", "bowler_id"], as_index=False).first()
        over_entries["_is_danger_over_35"] = (over_entries["pti"] >= self.max_entry_pti_threshold).astype(int)
        over_entries["_is_danger_over_25"] = (over_entries["pti"] >= BOWLING_STAND_BREAK_PTI_THRESHOLD).astype(int)

        exo_spell = over_entries.groupby(["match_id", "innings", "bowler_id"], as_index=False).agg(
            overs_entries_count=("overid", "count"),
            max_over_entry_pti=("pti", "max"),
            mean_over_entry_pti=("pti", "mean"),
            first_over_entry_pti=("pti", "first"),
            danger_overs_pti35=("_is_danger_over_35", "sum"),
            danger_overs_pti25=("_is_danger_over_25", "sum"),
            max_over_entry_ptnr_runs=("partnership_runs_current", "max"),
            mean_over_entry_phi_acc=("phi_acc", "mean"),
        )

        # 2. Additional genuine spell diagnostics directly from PCS deliveries
        deliv["_is_stand_break"] = (
            deliv["is_bowler_wkt"].fillna(False).astype(bool)
            & (deliv["pti"] >= BOWLING_STAND_BREAK_PTI_THRESHOLD)
        ).astype(int)
        deliv["_is_bwkt_int"] = deliv["is_bowler_wkt"].fillna(False).astype(int)
        deliv["_is_non_bwkt_int"] = deliv["is_non_bowler_wkt"].fillna(False).astype(int)

        over_wkts = deliv.groupby(["match_id", "innings", "overid", "bowler_id"], as_index=False)["_is_bwkt_int"].sum()
        over_wkts["_is_multi_wkt_over"] = (over_wkts["_is_bwkt_int"] >= 2).astype(int)
        mwo_spell = over_wkts.groupby(["match_id", "innings", "bowler_id"], as_index=False).agg(
            multi_wicket_overs_in_spell=("_is_multi_wkt_over", "sum")
        )

        diag_spell = deliv.groupby(["match_id", "innings", "bowler_id"], as_index=False).agg(
            stand_breaks_count=("_is_stand_break", "sum"),
            non_bowler_wkts_in_spell=("_is_non_bwkt_int", "sum"),
            within_spell_mean_pti=("pti", "mean"),
        )

        # 3. Merge authoritative competition metadata via matches.csv -> competitions.csv
        match_comp = matches_df[["match_id", "comp_id"]].merge(
            comps_df[["comp_id", "comp_name", "match_format"]],
            on="comp_id",
            how="left",
        )

        sp = spells.copy()
        sp = sp.merge(exo_spell, on=["match_id", "innings", "bowler_id"], how="left")
        sp = sp.merge(diag_spell, on=["match_id", "innings", "bowler_id"], how="left")
        sp = sp.merge(mwo_spell, on=["match_id", "innings", "bowler_id"], how="left")
        sp = sp.merge(match_comp, on="match_id", how="left")

        # Validate 100% exogenous mapping & competition mapping (Stop Condition §13)
        if sp["max_over_entry_pti"].isna().any():
            raise RuntimeError("Failed to map exogenous over-entry PTI to all PCS spells.")
        if sp["comp_id"].isna().any():
            raise RuntimeError("Failed to map authoritative comp_id to all PCS spells.")

        sp["comp_id"] = sp["comp_id"].astype(int)
        sp["comp_name"] = sp["comp_name"].fillna("Unknown Competition").astype(str)
        sp["match_format"] = sp["match_format"].fillna("T20").astype(str)
        sp["season_year"] = sp["match_date"].astype(str).str[:4]
        sp.loc[~sp["season_year"].str.isdigit(), "season_year"] = sp["season"].map(_normalize_season_year)
        sp["bowler_id"] = sp["bowler_id"].astype(int)
        sp["bowler_name"] = sp["bowler_id"].map(player_names).fillna("Bowler " + sp["bowler_id"].astype(str))
        sp["team_name"] = sp["bowling_team_id"].map(team_names).fillna("")
        sp["opponent_name"] = sp["batting_team_id"].map(team_names).fillna("")
        sp["is_pakistan_player"] = sp["bowler_id"].isin(pak_ids)
        sp["spell_id"] = (
            sp["match_id"].astype(str)
            + "_"
            + sp["innings"].astype(str)
            + "_"
            + sp["bowler_id"].astype(str)
        )

        # Exact EXO_2 primary qualification & EXO_5 sensitivity flag
        sp["qualifies_exo2"] = (
            (sp["max_over_entry_pti"] >= self.max_entry_pti_threshold)
            & (sp["legal_balls"] >= self.min_legal_balls)
        )
        sp["qualifies_exo5"] = (
            (sp["mean_over_entry_pti"] >= self.exo5_mean_entry_pti_threshold)
            & (sp["legal_balls"] >= self.exo5_min_legal_balls)
        )

        # Exact polarity classification (PCS == 50.0 is strictly neutral, NEVER positive)
        sp["pcs_outcome"] = np.where(
            sp["pcs_spell"] > PCS_NEUTRAL_ANCHOR,
            "positive",
            np.where(sp["pcs_spell"] < PCS_NEUTRAL_ANCHOR, "negative", "neutral"),
        )
        sp["is_positive_pcs"] = sp["pcs_outcome"] == "positive"
        sp["is_negative_pcs"] = sp["pcs_outcome"] == "negative"
        sp["is_neutral_pcs"] = sp["pcs_outcome"] == "neutral"

        # Diagnostic flags
        sp["is_dangerous_partnership_spell"] = sp["max_over_entry_pti"] >= self.max_entry_pti_threshold
        sp["is_partnership_breaking_spell"] = sp["stand_breaks_count"] >= 1
        sp["is_multi_wicket_spell"] = sp["wickets"] >= 2
        sp["is_wicketless_positive_spell"] = (sp["wickets"] == 0) & sp["is_positive_pcs"]

        sp = sp.sort_values(["match_date", "match_id", "innings", "bowler_id"]).reset_index(drop=True)

        dups = int(sp.duplicated(subset=["match_id", "innings", "bowler_id"]).sum())
        if dups > 0:
            raise RuntimeError(f"Duplicate bowling spells detected: {dups}")

        audit_meta = {
            "source_deliveries": int(len(deliv)),
            "source_matches": int(sp["match_id"].nunique()),
            "source_total_spells": int(len(sp)),
            "exo2_qualifying_spells": int(sp["qualifies_exo2"].sum()),
            "exo5_qualifying_spells": int(sp["qualifies_exo5"].sum()),
            "exo2_positive_spells": int((sp["qualifies_exo2"] & sp["is_positive_pcs"]).sum()),
            "exo2_negative_spells": int((sp["qualifies_exo2"] & sp["is_negative_pcs"]).sum()),
            "exo2_neutral_spells": int((sp["qualifies_exo2"] & sp["is_neutral_pcs"]).sum()),
            "duplicate_spells": dups,
        }
        return sp, audit_meta

    def _aggregate_group(
        self,
        all_scope_df: pd.DataFrame,
        group_cols: List[str],
        extra_first_cols: Optional[List[str]] = None,
    ) -> pd.DataFrame:
        """Aggregate unshrunk dual-axis Bowling PRI metrics over arbitrary grouping keys.

        Strict rules:
        - NO SHRINKAGE applied (no 48-ball shrinkage, no EB prior pulling).
        - Uses existing PCS spell-level `pcs_spell` and additive `total_rpe` unchanged.
        - Neutral PCS (== 50.00) NEVER counted as positive.
        - Bowlers with 0 qualifying pressure spells get NaN reliability (never 0%).
        """
        extra_first_cols = extra_first_cols or []
        records: List[Dict[str, Any]] = []

        for grp_key, grp in all_scope_df.groupby(group_cols, sort=False):
            if not isinstance(grp_key, tuple):
                grp_key = (grp_key,)
            key_dict = dict(zip(group_cols, grp_key))

            total_spells = int(len(grp))
            qual = grp[grp["qualifies_exo2"]]
            n_opp = int(len(qual))

            bowler_name = str(grp["bowler_name"].iloc[0])
            teams_list = sorted(t for t in grp["team_name"].dropna().unique() if str(t).strip())
            primary_team = teams_list[-1] if teams_list else None
            is_pak = bool(grp["is_pakistan_player"].any())

            row: Dict[str, Any] = {
                **key_dict,
                "bowler_name": bowler_name,
                "is_pakistan_player": is_pak,
                "primary_team": primary_team,
                "teams_count": len(teams_list),
                "total_matches": int(grp["match_id"].nunique()),
                "total_spells": total_spells,
                "pressure_spells": n_opp,
                "pressure_opportunity_share_pct": (
                    round((n_opp / total_spells) * 100.0, 2) if total_spells > 0 else None
                ),
            }
            for col in extra_first_cols:
                row[col] = grp[col].iloc[0]

            if n_opp == 0:
                row.update({
                    "positive_pcs_spells": 0,
                    "negative_pcs_spells": 0,
                    "neutral_pcs_spells": 0,
                    "positive_pcs_pct": np.nan,
                    "negative_pcs_pct": np.nan,
                    "neutral_pcs_pct": np.nan,
                    "avg_pcs_under_pressure": np.nan,
                    "total_pressure_contribution_rpe": np.nan,
                    "avg_rpe_under_pressure": np.nan,
                    "highest_pcs_spell": np.nan,
                    "lowest_pcs_spell": np.nan,
                    "total_legal_balls_pressure": 0,
                    "total_wickets_pressure": 0,
                    "total_runs_conceded_pressure": 0,
                    "economy_under_pressure": np.nan,
                    "avg_max_over_entry_pti": np.nan,
                    "dangerous_partnership_spells": 0,
                    "partnership_breaking_spells": 0,
                    "total_stand_breaks": 0,
                    "total_sup_pressure": np.nan,
                    "avg_sup_pressure": np.nan,
                    "total_dci_pressure": np.nan,
                    "avg_dci_pressure": np.nan,
                    "total_swi_pressure": np.nan,
                    "total_leakage_pressure": np.nan,
                    "multi_wicket_spells": 0,
                    "multi_wicket_overs_total": 0,
                    "wicketless_positive_spells": 0,
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
                pos_n = int(qual["is_positive_pcs"].sum())
                neg_n = int(qual["is_negative_pcs"].sum())
                neu_n = int(qual["is_neutral_pcs"].sum())
                assert pos_n + neg_n + neu_n == n_opp, "PCS polarity partition mismatch"

                pos_pct = (pos_n / n_opp) * 100.0
                neg_pct = (neg_n / n_opp) * 100.0
                neu_pct = (neu_n / n_opp) * 100.0

                avg_pcs = float(qual["pcs_spell"].mean())
                tot_rpe = float(qual["total_rpe"].sum())
                avg_rpe = tot_rpe / n_opp
                tot_balls = int(qual["legal_balls"].sum())
                tot_wkts = int(qual["wickets"].sum())
                tot_runs = int(qual["bowler_runs"].sum())
                econ = (tot_runs * 6.0 / tot_balls) if tot_balls > 0 else np.nan

                ci = wilson_interval_pair(pos_n, n_opp)

                row.update({
                    "positive_pcs_spells": pos_n,
                    "negative_pcs_spells": neg_n,
                    "neutral_pcs_spells": neu_n,
                    "positive_pcs_pct": round(pos_pct, 2),
                    "negative_pcs_pct": round(neg_pct, 2),
                    "neutral_pcs_pct": round(neu_pct, 2),
                    "avg_pcs_under_pressure": round(avg_pcs, 2),
                    "total_pressure_contribution_rpe": round(tot_rpe, 4),
                    "avg_rpe_under_pressure": round(avg_rpe, 4),
                    "highest_pcs_spell": round(float(qual["pcs_spell"].max()), 2),
                    "lowest_pcs_spell": round(float(qual["pcs_spell"].min()), 2),
                    "total_legal_balls_pressure": tot_balls,
                    "total_wickets_pressure": tot_wkts,
                    "total_runs_conceded_pressure": tot_runs,
                    "economy_under_pressure": round(float(econ), 2) if not np.isnan(econ) else np.nan,
                    "avg_max_over_entry_pti": round(float(qual["max_over_entry_pti"].mean()), 2),
                    "dangerous_partnership_spells": int(qual["is_dangerous_partnership_spell"].sum()),
                    "partnership_breaking_spells": int(qual["is_partnership_breaking_spell"].sum()),
                    "total_stand_breaks": int(qual["stand_breaks_count"].sum()),
                    "total_sup_pressure": round(float(qual["total_sup"].sum()), 4),
                    "avg_sup_pressure": round(float(qual["total_sup"].mean()), 4),
                    "total_dci_pressure": round(float(qual["total_dci"].sum()), 4),
                    "avg_dci_pressure": round(float(qual["total_dci"].mean()), 4),
                    "total_swi_pressure": round(float(qual["total_swi"].sum()), 4),
                    "total_leakage_pressure": round(float(qual["total_leakage"].sum()), 4),
                    "multi_wicket_spells": int(qual["is_multi_wicket_spell"].sum()),
                    "multi_wicket_overs_total": int(qual["multi_wicket_overs_in_spell"].sum()),
                    "wicketless_positive_spells": int(qual["is_wicketless_positive_spell"].sum()),
                    **ci,
                    "sample_confidence_tier": classify_sample_confidence(n_opp),
                    "has_pressure_opportunities": True,
                    "status": "Evaluated",
                })

            records.append(row)

        df_out = pd.DataFrame(records)
        if len(df_out) > 0:
            df_out = df_out.sort_values(
                by=["has_pressure_opportunities", "positive_pcs_pct", "avg_pcs_under_pressure", "pressure_spells"],
                ascending=[False, False, False, False],
                na_position="last",
            ).reset_index(drop=True)
        return df_out

    def run(self) -> Dict[str, Any]:
        """Execute full independent Bowling PRI pipeline (Career, Season, Tournament)."""
        all_spells_df, audit_meta = self.load_all_bowling_spells()
        pressure_spells_df = all_spells_df[all_spells_df["qualifies_exo2"]].copy().reset_index(drop=True)

        # Career, Season (calendar year), Tournament independent unshrunk aggregations
        career_df = self._aggregate_group(all_spells_df, group_cols=["bowler_id"])
        season_df = self._aggregate_group(
            all_spells_df,
            group_cols=["season_year", "bowler_id"],
        ).rename(columns={"season_year": "season"})
        tournament_df = self._aggregate_group(
            all_spells_df,
            group_cols=["comp_id", "bowler_id"],
            extra_first_cols=["comp_name", "competition_category", "match_format", "season_year"],
        ).rename(columns={"season_year": "season"})

        # Strict Reconciliation Checks
        assert int(career_df["pressure_spells"].sum()) == len(pressure_spells_df), "Career pressure_spells mismatch"
        assert int(season_df["pressure_spells"].sum()) == len(pressure_spells_df), "Season pressure_spells mismatch"
        assert int(tournament_df["pressure_spells"].sum()) == len(pressure_spells_df), "Tournament pressure_spells mismatch"
        assert abs(float(career_df["total_pressure_contribution_rpe"].sum()) - float(pressure_spells_df["total_rpe"].sum())) < 1e-2
        assert abs(float(season_df["total_pressure_contribution_rpe"].sum()) - float(pressure_spells_df["total_rpe"].sum())) < 1e-2
        assert abs(float(tournament_df["total_pressure_contribution_rpe"].sum()) - float(pressure_spells_df["total_rpe"].sum())) < 1e-2

        return {
            "all_spells": all_spells_df,
            "pressure_spells": pressure_spells_df,
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
        sort_by: str = "positive_pcs_pct",
        ascending: bool = False,
    ) -> pd.DataFrame:
        """Reusable Overall Bowling PRI Leaderboard filter (custom min + B8 Pakistan visibility)."""
        visible = apply_overall_leaderboard_visibility(
            career_df,
            player_id_col="bowler_id",
            exclude_pakistan=exclude_pakistan,
        )
        return apply_min_opportunity_filter(
            visible,
            count_col="pressure_spells",
            min_opportunities=min_opportunities,
            sort_by=sort_by,
            ascending=ascending,
        )
