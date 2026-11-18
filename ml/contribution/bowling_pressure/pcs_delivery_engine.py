"""Stage B7.5 Delivery-Level Pressure Contribution Score (PCS) Engine."""

from __future__ import annotations

from typing import Any
import numpy as np
import pandas as pd

from ml.contribution.bowling_pressure.acceleration_engine import AccelerationEngine
from ml.contribution.bowling_pressure.batter_threat_engine import BatterThreatEngine
from ml.contribution.bowling_pressure.causal_features import CausalFeatureExtractor
from ml.contribution.bowling_pressure.config import load_pcs_config
from ml.contribution.bowling_pressure.dot_choke_engine import DotChokeEngine
from ml.contribution.bowling_pressure.leakage_engine import LeakageEngine
from ml.contribution.bowling_pressure.partnership_share_engine import PartnershipShareEngine
from ml.contribution.bowling_pressure.partnership_threat_engine import PartnershipThreatEngine
from ml.contribution.bowling_pressure.partnership_tracker import PartnershipTracker
from ml.contribution.bowling_pressure.pcs_normalizer import PCSNormalizer
from ml.contribution.bowling_pressure.scoring_suppression_engine import ScoringSuppressionEngine
from ml.contribution.bowling_pressure.sequential_wicket_engine import SequentialWicketEngine
from ml.contribution.bowling_pressure.situational_wicket_engine import SituationalWicketEngine


class PCSDeliveryEngine:
    """Master delivery-level engine synthesizing situational wickets, containment, and leakage."""

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        self.config = config or load_pcs_config()
        params = self.config.get("parameters", {})

        self.causal_extractor = CausalFeatureExtractor()
        self.threat_engine = BatterThreatEngine(
            w_striker=float(params.get("w_striker_threat", 0.60)),
            w_non_striker=float(params.get("w_non_striker_threat", 0.40)),
            starve_weight=float(params.get("dci_starve_weight", 0.25)),
        )
        self.ptnr_tracker = PartnershipTracker()
        self.share_engine = PartnershipShareEngine()
        self.acc_engine = AccelerationEngine(
            primary_window=int(params.get("primary_acc_window", 12)),
            sensitivity_window=int(params.get("sensitivity_acc_window", 18)),
        )
        self.pti_engine = PartnershipThreatEngine()
        self.swi_engine = SituationalWicketEngine(
            alpha_res=float(params.get("alpha_resource_elasticity", 0.55))
        )
        self.dci_engine = DotChokeEngine(
            cluster_weight=float(params.get("dci_cluster_weight", 0.35))
        )
        self.sup_engine = ScoringSuppressionEngine()
        self.leak_engine = LeakageEngine()
        self.seq_engine = SequentialWicketEngine()
        self.normalizer = PCSNormalizer(
            k_slope=float(params.get("k_sigmoid_slope", 0.85)),
            sigma_ref_1st=float(params.get("sigma_ref_1st", 17.50)),
            sigma_ref_2nd=float(params.get("sigma_ref_2nd", 18.80)),
        )

    def evaluate_deliveries(self, df_deliveries: pd.DataFrame) -> pd.DataFrame:
        """Execute complete delivery-level PCS evaluation across delivery corpus."""
        df = df_deliveries.copy()

        # 1. Causal feature extraction (rolling windows, pre-delivery lag-1)
        df = self.causal_extractor.extract_delivery_features(df)

        # 2. Dynamic active partnership tracking
        df = self.ptnr_tracker.track_partnerships(df)

        # 3. Dismissal and attribution classification
        is_bwkt, is_non_bwkt, is_non_bextra, alpha_attr = self.seq_engine.classify_deliveries(df)
        df["is_bowler_wkt"] = is_bwkt
        df["is_non_bowler_wkt"] = is_non_bwkt
        df["is_non_bowler_extra"] = is_non_bextra
        df["alpha_attr"] = alpha_attr

        # 4. Batter and Non-Striker threat evaluation
        # Use existing abc_prior_shrunk or fallback
        abc_str = df.get("abc_prior_shrunk", pd.Series(1.0, index=df.index)).fillna(1.0).to_numpy()
        cum_balls_str = df.get("striker_cum_balls", pd.Series(10, index=df.index)).fillna(10).to_numpy()
        cum_runs_str = df.get("striker_cum_runs", pd.Series(12, index=df.index)).fillna(12).to_numpy()

        striker_threat = self.threat_engine.evaluate_batter_threat(abc_str, cum_runs_str, cum_balls_str)
        # Evaluate non-striker threat
        if "non_striker_id" in df.columns and "striker_id" in df.columns and "abc_prior_shrunk" in df.columns:
            try:
                player_abc = df.groupby("striker_id")["abc_prior_shrunk"].last()
                ns_abc = df["non_striker_id"].map(player_abc).fillna(50.0).to_numpy()
                non_striker_threat = self.threat_engine.evaluate_batter_threat(ns_abc, 12, 10)
            except Exception:
                non_striker_threat = np.roll(striker_threat, 1)
                non_striker_threat[0] = 1.00
        else:
            non_striker_threat = np.roll(striker_threat, 1)
            non_striker_threat[0] = 1.00

        phi_bat, starve_mult = self.threat_engine.evaluate_composite_threat(striker_threat, non_striker_threat)
        df["striker_threat"] = striker_threat
        df["non_striker_threat"] = non_striker_threat
        df["phi_bat"] = phi_bat
        df["starve_mult"] = starve_mult

        # 5. Partnership contribution share
        # Approximate striker runs in stand as proportional to cumulative runs
        ptnr_runs = df["partnership_runs_current"].to_numpy()
        s_share = self.share_engine.evaluate_contribution_share(
            striker_runs_in_ptnr=ptnr_runs * 0.50, partnership_runs=ptnr_runs
        )
        df["striker_share"] = s_share

        # 6. Acceleration evaluation
        phi_acc, acc_12, acc_18 = self.acc_engine.evaluate_acceleration(
            runs_last_12=df["runs_last_12_balls"],
            runs_last_18=df["runs_last_18_balls"],
            partnership_run_rate=df["partnership_run_rate"],
            legal_balls_in_stand=df["partnership_balls_current"],
        )
        df["phi_acc"] = phi_acc
        df["acc_12_rpo"] = acc_12
        df["acc_18_rpo"] = acc_18

        # 7. Partnership Threat Index (PTI)
        ref_rr = np.where(
            df["innings"] == 2,
            df["required_run_rate_before"].clip(lower=6.0),
            (df.get("venue_avg_first_inn_score", pd.Series(165.0, index=df.index)) / 20.0),
        )
        pti = self.pti_engine.evaluate_pti(
            partnership_runs=df["partnership_runs_current"],
            partnership_run_rate=df["partnership_run_rate"],
            reference_run_rate=ref_rr,
            phi_acc=phi_acc,
            phi_bat=phi_bat,
        )
        df["pti"] = pti

        # 8. Leverage extraction (from BCM leverage column)
        lev = df.get("leverage", pd.Series(1.0, index=df.index)).fillna(1.0).clip(0.50, 2.00).to_numpy()
        df["leverage"] = lev

        # 9. Situational Wicket Importance (SWI)
        venue_avg = pd.to_numeric(df.get("venue_avg_first_inn_score", pd.Series(165.0, index=df.index)), errors="coerce").fillna(165.0).to_numpy(dtype=float)
        runs_req = pd.to_numeric(df.get("runs_required_before", pd.Series(0, index=df.index)), errors="coerce").fillna(0).to_numpy(dtype=float)
        w_rem = (10 - df["wickets_lost_before"]).to_numpy(dtype=float)
        b_rem = df["legal_balls_remaining_before"].to_numpy(dtype=float)
        v_wkt_arr = pd.to_numeric(df.get("V_wkt", pd.Series(np.nan, index=df.index)), errors="coerce").to_numpy(dtype=float)
        v_wkt_safe = None if np.all(np.isnan(v_wkt_arr)) else v_wkt_arr

        swi = self.swi_engine.evaluate_swi(
            innings=df["innings"],
            is_bowler_wicket=df["is_bowler_wkt"],
            leverage=lev,
            score_before=df["score_before"],
            balls_remaining=b_rem,
            wickets_remaining=w_rem,
            current_run_rate=df["current_run_rate_before"],
            required_run_rate=df["required_run_rate_before"],
            runs_required=runs_req,
            venue_avg_first_inn_score=venue_avg,
            v_wkt=v_wkt_safe,
            overid=df.get("overid", None),
            wickets_lost_before=df["wickets_lost_before"],
            partnership_run_rate=df["partnership_run_rate"],
        )
        df["swi"] = swi

        # 10. Dot Choke Index (DCI)
        is_legal = df["is_legal_delivery"].fillna(True).astype(bool).to_numpy()
        team_runs = df["team_runs"].fillna(0).astype(int).to_numpy()
        is_dot = is_legal & (team_runs == 0) & (~df["is_bowler_wkt"])
        df["is_dot_ball"] = is_dot

        dci = self.dci_engine.evaluate_dci(
            is_dot_ball=is_dot,
            dots_last_12=df["dots_last_12_balls"],
            leverage=lev,
            starvation_mult=starve_mult,
        )
        df["dci"] = dci

        # 11. Scoring rate suppression (Sup)
        # Conceded runs charged to bowler
        bowler_runs = df.get("bowler_runs", df["team_runs"]).fillna(0).astype(int).to_numpy()
        sup = self.sup_engine.evaluate_suppression(
            innings=df["innings"],
            is_legal_delivery=is_legal,
            runs_conceded=bowler_runs,
            leverage=lev,
            required_run_rate_before=df["required_run_rate_before"],
            legal_balls_remaining_before=b_rem,
            runs_required_before=runs_req,
        )
        # Suppress rate credit if a wicket was already taken on this ball
        sup = np.where(df["is_bowler_wkt"], 0.0, sup)
        df["sup"] = sup

        # 12. Run Leakage Penalty (Leakage)
        exp_runs = df.get("exp_bowler_runs", pd.Series(1.25, index=df.index)).fillna(1.25).to_numpy()
        leakage = self.leak_engine.evaluate_leakage(
            runs_conceded=bowler_runs,
            leverage=lev,
            exp_runs=exp_runs,
        )
        df["leakage"] = leakage

        # 13. Synthesis of Raw Pressure Effect (RPE)
        # Wicket intervention branch vs Containment branch
        pti_bonus = np.clip(pti / 15.0, 0.0, 5.0)  # Up to +5.0 extra credit for breaking massive stands
        wkt_rpe = swi + pti_bonus - leakage
        dot_rpe = dci + sup - leakage

        raw_rpe = np.where(
            df["is_bowler_wkt"],
            wkt_rpe,
            np.where(df["is_non_bowler_wkt"], 0.0, dot_rpe),
        )

        # Apply attribution factor
        df["rpe"] = alpha_attr * raw_rpe

        # Delivery-level normalized PCS
        pcs_del = self.normalizer.normalize(
            rpe=df["rpe"].to_numpy(),
            innings=df["innings"].to_numpy(),
        )
        df["pcs_delivery"] = pcs_del.round(2)

        return df
