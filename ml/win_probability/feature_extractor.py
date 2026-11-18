"""Stage 6B authoritative feature extraction pipeline for pre-match and live delivery states."""

from __future__ import annotations

from typing import Final

import numpy as np
import pandas as pd

from ml.win_probability.schema import (
    ALL_CATALOG_FEATURES,
    FORBIDDEN_LEAKAGE_COLUMNS,
    INNINGS_1_FEATURES,
    INNINGS_2_FEATURES,
    STAGE_A_FEATURES,
    STAGE_B_FEATURES,
    TARGET_BATTING_WIN,
    TARGET_HOME_WIN,
    TRAIN_END_DATE,
    VAL_END_DATE,
    VAL_START_DATE,
    validate_feature_matrix_no_leakage,
)
from ml.win_probability.team_strength import TeamStrengthAggregator
from ml.win_probability.venue_priors import VenuePriorsCalculator

TEAM_WIN_RATE_SHRINKAGE_WEIGHT: Final[float] = 5.0


def calculate_resource_percentage(wickets_remaining: int | float, balls_remaining: int | float) -> float:
    """Calculate non-linear remaining batting resources percentage in [0.0, 100.0]."""
    w = float(wickets_remaining)
    b = float(balls_remaining)
    if w <= 0.0 or b <= 0.0:
        return 0.0
    exponent = -(b / 120.0) * (0.20 + 0.08 * w)
    val = 100.0 * (1.0 - np.exp(exponent)) / (1.0 - np.exp(-1.0))
    return float(np.clip(val, 0.0, 100.0))


class WinProbabilityFeatureExtractor:
    """End-to-end feature engineering and extraction engine for Win Probability models."""

    def __init__(
        self,
        match_states_df: pd.DataFrame,
        playing_eleven_df: pd.DataFrame,
        causal_abc_df: pd.DataFrame,
        ball_by_ball_df: pd.DataFrame | None = None,
    ) -> None:
        """Initialize feature extractor with validated inputs."""
        self.df_ms = match_states_df.copy()
        self.df_ms["match_date"] = pd.to_datetime(self.df_ms["match_date"]).dt.strftime("%Y-%m-%d")

        # Initialize aggregators
        self.venue_calc = VenuePriorsCalculator(self.df_ms, ball_by_ball_df)
        self.team_agg = TeamStrengthAggregator(playing_eleven_df, causal_abc_df, self.df_ms)

        # Pre-compute historical match results for team win rates
        self._build_team_win_history()

    def _build_team_win_history(self) -> None:
        """Pre-index match outcomes to compute causal prior team win rates."""
        matches = self.df_ms[["match_id", "match_date", "home_team_id", "away_team_id", "win_team_id_raw"]].drop_duplicates()
        self.match_results = matches

    def get_causal_team_win_rate(self, team_id: int, target_match_date: str) -> float:
        """Compute strictly causal historical win rate for a team before target_match_date."""
        target_dt = str(pd.to_datetime(target_match_date).strftime("%Y-%m-%d"))
        prior_m = self.match_results[
            ((self.match_results["home_team_id"] == team_id) | (self.match_results["away_team_id"] == team_id))
            & (self.match_results["match_date"] < target_dt)
        ]
        n_matches = len(prior_m)
        if n_matches == 0:
            return 0.50

        wins = int((prior_m["win_team_id_raw"] == team_id).sum())
        obs_rate = wins / n_matches

        # Bayesian shrinkage to 0.50
        w = n_matches / (n_matches + TEAM_WIN_RATE_SHRINKAGE_WEIGHT)
        shrunk_rate = w * obs_rate + (1.0 - w) * 0.50
        return float(np.clip(shrunk_rate, 0.10, 0.90))

    def extract_pre_match_features_for_match(self, match_id: int) -> dict[str, dict[str, Any]]:
        """Extract both Stage A and Stage B feature payloads for a single match."""
        m_rows = self.df_ms[self.df_ms["match_id"] == match_id]
        if m_rows.empty:
            raise ValueError(f"Match ID {match_id} not found in match states.")

        row = m_rows.iloc[0]
        m_date = str(row["match_date"])
        venue_id = int(row["venue_id"])
        comp_cat = str(row["competition_category"])
        home_team = int(row["home_team_id"])
        away_team = int(row["away_team_id"])

        # 1. Venue priors (strictly prior dates)
        venue_priors = self.venue_calc.get_venue_priors(venue_id, m_date, comp_cat)

        # 2. Team prior win rates (strictly prior dates)
        home_win_rate = self.get_causal_team_win_rate(home_team, m_date)
        away_win_rate = self.get_causal_team_win_rate(away_team, m_date)

        # Stage A Features (7 features)
        stage_a_dict: dict[str, Any] = {
            "competition_category": comp_cat,
            "venue_avg_first_inn_score": venue_priors["venue_avg_first_inn_score"],
            "venue_chase_win_pct": venue_priors["venue_chase_win_pct"],
            "venue_avg_death_rr": venue_priors["venue_avg_death_rr"],
            "venue_pace_spin_wicket_ratio": venue_priors["venue_pace_spin_wicket_ratio"],
            "team_a_prior_win_rate": home_win_rate,
            "team_b_prior_win_rate": away_win_rate,
        }

        # Stage B Check: Are BOTH toss and confirmed XI announced?
        toss_win_team = row.get("toss_win_team_id")
        toss_opted = row.get("toss_opted")
        is_toss_known = pd.notna(toss_win_team) and pd.notna(toss_opted)

        home_lineup = self.team_agg.get_active_lineup(match_id, home_team)
        away_lineup = self.team_agg.get_active_lineup(match_id, away_team)
        is_xi_confirmed = (len(home_lineup) >= 10) and (len(away_lineup) >= 10)

        # Lineup aggregations
        home_strength = self.team_agg.compute_batting_strength(match_id, home_team, m_date, comp_cat)
        away_strength = self.team_agg.compute_batting_strength(match_id, away_team, m_date, comp_cat)
        home_bowling = self.team_agg.compute_bowling_strength(home_team, m_date, comp_cat)
        away_bowling = self.team_agg.compute_bowling_strength(away_team, m_date, comp_cat)

        is_home_toss_winner = bool(toss_win_team == home_team) if is_toss_known else False
        toss_dec_bat = bool(str(toss_opted).lower() == "bat") if is_toss_known else True

        # Pre-match probability heuristics for Stage A & Stage B baseline
        # (Will be replaced by trained Stage A/B model in Sub-Stage 6B.2)
        base_log_odds = (home_win_rate - away_win_rate) * 2.0
        p_stage_a = float(1.0 / (1.0 + np.exp(-base_log_odds)))

        lineup_edge = (home_strength["batting_lineup_mean_abc"] - away_strength["batting_lineup_mean_abc"]) * 0.03
        toss_edge = 0.05 if (is_home_toss_winner and venue_priors["venue_chase_win_pct"] > 0.50 and not toss_dec_bat) else 0.0
        p_stage_b = float(np.clip(1.0 / (1.0 + np.exp(-(base_log_odds + lineup_edge + toss_edge))), 0.10, 0.90)) if (is_toss_known and is_xi_confirmed) else p_stage_a

        stage_b_dict: dict[str, Any] = {
            "competition_category": comp_cat,
            "venue_avg_first_inn_score": venue_priors["venue_avg_first_inn_score"],
            "venue_chase_win_pct": venue_priors["venue_chase_win_pct"],
            "venue_avg_death_rr": venue_priors["venue_avg_death_rr"],
            "venue_pace_spin_wicket_ratio": venue_priors["venue_pace_spin_wicket_ratio"],
            "pre_match_prob_stage_a": p_stage_a,
            "batting_lineup_top3_abc": home_strength["batting_lineup_top3_abc"],
            "batting_lineup_mid4_abc": home_strength["batting_lineup_mid4_abc"],
            "batting_lineup_tail_abc": home_strength["batting_lineup_tail_abc"],
            "batting_lineup_mean_abc": home_strength["batting_lineup_mean_abc"],
            "batting_lineup_std_abc": home_strength["batting_lineup_std_abc"],
            "batting_cold_start_count": home_strength["batting_cold_start_count"],
            "bowling_unit_powerplay_econ": away_bowling["bowling_unit_powerplay_econ"],
            "bowling_unit_middle_econ": away_bowling["bowling_unit_middle_econ"],
            "bowling_unit_death_econ": away_bowling["bowling_unit_death_econ"],
            "bowling_unit_strike_rate": away_bowling["bowling_unit_strike_rate"],
            "relative_batting_edge": home_strength["batting_lineup_mean_abc"] - away_strength["batting_lineup_mean_abc"],
            "is_batting_team_toss_winner": is_home_toss_winner,
            "toss_decision_bat": toss_dec_bat,
            "team_prior_win_rate_diff": home_win_rate - away_win_rate,
            "stage_b_pending": not (is_toss_known and is_xi_confirmed),
            "pre_match_prob_stage_b": p_stage_b,
            "stage_b_prob_delta": p_stage_b - p_stage_a,
        }

        return {"stage_a": stage_a_dict, "stage_b": stage_b_dict}

    def extract_delivery_features(self) -> tuple[pd.DataFrame, pd.DataFrame]:
        """Extract delivery-grain features across all 190,575 standard deliveries.

        Returns (inns1_df, inns2_df).
        """
        df = self.df_ms.copy()

        # 1. Clean data types for rolling features
        df["team_runs_f"] = df["team_runs"].astype(float).fillna(0.0)
        df["is_wicket_f"] = df["is_wicket_event"].astype(float).fillna(0.0)

        # Shift by 1 to get state strictly BEFORE delivery
        df["runs_prev"] = df.groupby(["match_id", "innings"])["team_runs_f"].shift(1).fillna(0.0)
        df["wkts_prev"] = df.groupby(["match_id", "innings"])["is_wicket_f"].shift(1).fillna(0.0)

        # Rolling 12-ball and 24-ball delivery window aggregates
        df["runs_last_12_balls"] = (
            df.groupby(["match_id", "innings"])["runs_prev"]
            .transform(lambda s: s.rolling(12, min_periods=1).sum())
            .astype(int)
        )
        df["wickets_last_12_balls"] = (
            df.groupby(["match_id", "innings"])["wkts_prev"]
            .transform(lambda s: s.rolling(12, min_periods=1).sum())
            .astype(int)
        )
        df["runs_last_24_balls"] = (
            df.groupby(["match_id", "innings"])["runs_prev"]
            .transform(lambda s: s.rolling(24, min_periods=1).sum())
            .astype(int)
        )

        # Partnership calculations
        p_start_score = df.groupby(["match_id", "innings", "wickets_lost_before"])["score_before"].transform("min")
        df["partnership_runs_current"] = (df["score_before"] - p_start_score).astype(int)

        p_start_balls = df.groupby(["match_id", "innings", "wickets_lost_before"])["legal_balls_completed_before"].transform("min")
        df["partnership_balls_current"] = (df["legal_balls_completed_before"] - p_start_balls).astype(int)

        # Resource percentage remaining
        df["resource_percentage_remaining"] = [
            calculate_resource_percentage(w, b)
            for w, b in zip(df["wickets_remaining"], df["legal_balls_remaining_before"])
        ]

        # Targets
        df[TARGET_BATTING_WIN] = (df["batting_team_id"] == df["win_team_id_raw"]).astype(int)
        df[TARGET_HOME_WIN] = (df["home_team_id"] == df["win_team_id_raw"]).astype(int)

        # Map pre-match and venue features per match
        match_meta_records: list[dict[str, Any]] = []
        for m_id in df["match_id"].unique():
            pm = self.extract_pre_match_features_for_match(int(m_id))
            sb = pm["stage_b"]
            record = {"match_id": m_id}
            record.update(sb)
            match_meta_records.append(record)

        meta_df = pd.DataFrame(match_meta_records)
        df = df.merge(meta_df, on="match_id", how="left")

        # Innings 1 specific: Expected Final Score Gap
        # EFS = score_before + balls_rem * (expected_rr / 6.0)
        # Expected RR: weighted blend of CRR and venue par RR adjusted by wickets
        venue_rr = df["venue_avg_first_inn_score"] / 20.0
        wkt_adj = np.sqrt(np.clip(df["wickets_remaining"] / 10.0, 0.1, 1.0))
        crr_safe = np.clip(df["current_run_rate"], 4.0, 15.0)
        expected_rr = 0.5 * crr_safe + 0.5 * (venue_rr * wkt_adj)
        projected_total = df["score_before"] + df["legal_balls_remaining_before"] * (expected_rr / 6.0)
        df["expected_final_score_gap"] = projected_total - df["venue_avg_first_inn_score"]

        # Innings 2 specific: Target Pressure Index
        rrr_safe = df["required_run_rate"].fillna(0.0).clip(0.0, 36.0)
        venue_crr_safe = np.clip(venue_rr, 6.0, 12.0)
        df["target_pressure_index"] = (rrr_safe / venue_crr_safe) * (1.0 + df["wickets_lost_before"] / 5.0)

        # Split into Innings 1 and Innings 2
        inns1 = df[df["innings"] == 1].copy()
        inns2 = df[df["innings"] == 2].copy()

        # Rename current_run_rate to current_run_rate_before and required_run_rate to required_run_rate_before
        inns1["current_run_rate_before"] = inns1["current_run_rate"]
        inns1["wickets_remaining_before"] = inns1["wickets_remaining"]

        inns2["current_run_rate_before"] = inns2["current_run_rate"]
        inns2["wickets_remaining_before"] = inns2["wickets_remaining"]
        inns2["required_run_rate_before"] = inns2["required_run_rate"].fillna(99.0).clip(0.0, 99.0)
        inns2["rrr_minus_crr_before"] = inns2["rrr_minus_crr"].fillna(0.0).clip(-30.0, 99.0)

        # Clean target_runs and runs_required
        inns2["target_runs"] = inns2["target_runs"].fillna(0).astype(int)
        inns2["runs_required_before"] = inns2["runs_required_before"].fillna(0).astype(int)

        # Validate no leakage in feature definitions
        validate_feature_matrix_no_leakage(INNINGS_1_FEATURES)
        validate_feature_matrix_no_leakage(INNINGS_2_FEATURES)

        return inns1, inns2

    def get_chronological_splits(
        self,
        inns1_df: pd.DataFrame,
        inns2_df: pd.DataFrame,
    ) -> dict[str, dict[str, pd.DataFrame]]:
        """Partition datasets chronologically into Train (2022-2024), Val (2025), and Test (2026)."""
        splits: dict[str, dict[str, pd.DataFrame]] = {}

        for partition_name, (start_dt, end_dt) in [
            ("train", ("2022-01-01", TRAIN_END_DATE)),
            ("val", (VAL_START_DATE, VAL_END_DATE)),
            ("test", (TEST_START_DATE, "2026-12-31")),
        ]:
            i1 = inns1_df[(inns1_df["match_date"] >= start_dt) & (inns1_df["match_date"] <= end_dt)].copy()
            i2 = inns2_df[(inns2_df["match_date"] >= start_dt) & (inns2_df["match_date"] <= end_dt)].copy()

            splits[partition_name] = {
                "inns1": i1,
                "inns2": i2,
            }

        return splits

