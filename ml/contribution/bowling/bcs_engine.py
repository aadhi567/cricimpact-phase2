"""Stage B4 Bowling Contribution Score (BCS) Synthesis Engine."""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from ml.contribution.bowling.config import load_bowling_config
from ml.contribution.bowling.dot_ball_pressure_engine import DotBallPressureEngine
from ml.contribution.bowling.erp_engine import ExpectedRunsPreventedEngine
from ml.contribution.bowling.first_innings_scoring_pressure_engine import FirstInningsScoringPressureEngine
from ml.contribution.bowling.leverage_engine import MatchLeverageEngine
from ml.contribution.bowling.required_run_rate_pressure_engine import RequiredRunRatePressureEngine
from ml.contribution.bowling.schema import (
    BOWLER_CREDITED_DISMISSALS,
    NON_BOWLER_DISMISSALS,
    NON_BOWLER_EXTRAS,
    DeliveryContributionResult,
    validate_delivery_invariants,
)
from ml.contribution.bowling.wicket_value_engine import ContextWicketValueEngine
from ml.contribution.bowling.wqm_engine import WicketQualityMultiplierEngine


class BowlingContributionEngine:
    """Core synthesis engine for delivery-level Bowling Contribution Score (BCS).

    Synthesizes:
        BCS = [ERP + I(is_bowler_wkt) * WQM * V_wkt] * Leverage

    Enforces:
        - Non-bowler dismissal exclusion (Run-outs receive 0 wicket credit)
        - Non-bowler extras safeguard (Pure byes/leg-byes receive 0 ERP and 0 BCS)
        - Single leverage application (no pre-baked leverage in V_wkt)
        - Complete explanatory pressure diagnostics (unbundled from BCS)
    """

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        self.config = config or load_bowling_config()
        self.erp_engine = ExpectedRunsPreventedEngine(self.config)
        self.wqm_engine = WicketQualityMultiplierEngine(self.config)
        self.wicket_val_engine = ContextWicketValueEngine(self.config)
        self.leverage_engine = MatchLeverageEngine(self.config)
        self.dot_pressure_engine = DotBallPressureEngine(self.config)
        self.rrr_pressure_engine = RequiredRunRatePressureEngine(self.config)
        self.first_inns_pressure_engine = FirstInningsScoringPressureEngine(self.config)

    def evaluate_delivery(
        self,
        match_id: int,
        innings: int,
        innings_ball_num: int,
        bowler_id: int,
        striker_id: int,
        is_legal: bool,
        innings_phase: str,
        score_before: int,
        wickets_lost_before: int,
        overid: int,
        batter_runs: int,
        extras_type: str | None,
        extras1_runs: int,
        is_wicket_event: bool,
        dismissal_type_canonical: str | None,
        dismissed_player_id: int | None,
        # Batter quality & form
        abc_prior_shrunk: float = 50.0,
        abc_prior_last5_mean: float | None = None,
        total_career_innings: int = 10,
        striker_cum_runs_before: int = 0,
        striker_cum_balls_before: int = 0,
        # Situational context
        required_run_rate: float | None = None,
        legal_balls_remaining_before: int | None = None,
        consecutive_dots_before: int = 0,
        bowler_cum_runs_before: int = 0,
        bowler_cum_legal_balls_before: int = 0,
    ) -> DeliveryContributionResult:
        """Synthesize full contribution assessment for a single delivery."""
        # 1. Classify extras & bowler runs
        is_non_bowler_extra = extras_type in NON_BOWLER_EXTRAS
        bowler_runs = self.erp_engine.calculate_bowler_runs(batter_runs, extras_type, extras1_runs)

        # 2. Expected Runs Prevented (ERP)
        exp_runs, bowler_runs, erp = self.erp_engine.evaluate_delivery(
            innings=innings,
            phase=innings_phase,
            score_before=score_before,
            wickets_lost_before=wickets_lost_before,
            overid=overid,
            is_legal=is_legal,
            batter_runs=batter_runs,
            extras_type=extras_type,
            extras1_runs=extras1_runs,
        )

        # 3. Wicket Classification & Value
        bowler_credited_set = {d.lower() for d in BOWLER_CREDITED_DISMISSALS}
        is_bowler_wkt = bool(
            is_wicket_event
            and dismissal_type_canonical
            and dismissal_type_canonical.strip().lower() in bowler_credited_set
        )

        if is_bowler_wkt:
            v_wkt = self.wicket_val_engine.evaluate_delivery(overid, wickets_lost_before, innings_phase)
            wqm = self.wqm_engine.evaluate_delivery(
                abc_prior_shrunk=abc_prior_shrunk,
                abc_prior_last5_mean=abc_prior_last5_mean,
                total_career_innings=total_career_innings,
                striker_cum_runs=striker_cum_runs_before,
                striker_cum_balls=striker_cum_balls_before,
            )
        else:
            v_wkt = 0.0
            wqm = 1.0  # Neutral baseline when no wicket

        # 4. Match Leverage
        leverage = self.leverage_engine.evaluate_delivery(
            innings=innings,
            phase=innings_phase,
            wickets_lost_before=wickets_lost_before,
            required_run_rate=required_run_rate,
            legal_balls_remaining_before=legal_balls_remaining_before,
        )

        # 5. Core Synthesis
        wicket_impact = (wqm * v_wkt) if is_bowler_wkt else 0.0
        unweighted_run_impact = erp + wicket_impact
        bcs = unweighted_run_impact * leverage

        # 6. Explanatory Diagnostics
        (
            dot_ball,
            exp_dot_prob,
            dot_residual,
            consecutive_dots_after,
            dot_pressure_idx,
        ) = self.dot_pressure_engine.evaluate_delivery(
            is_legal=is_legal,
            bowler_runs=bowler_runs,
            is_non_bowler_extra=is_non_bowler_extra,
            consecutive_dots_before=consecutive_dots_before,
            innings=innings,
            phase=innings_phase,
        )

        rrr_before, bowler_econ, rrr_pressure_idx = self.rrr_pressure_engine.evaluate_delivery(
            innings=innings,
            required_run_rate=required_run_rate,
            bowler_cum_runs=bowler_cum_runs_before,
            bowler_cum_legal_balls=bowler_cum_legal_balls_before,
        )

        first_inns_restriction = self.first_inns_pressure_engine.evaluate_delivery(
            innings=innings,
            exp_bowler_runs=exp_runs,
            bowler_runs=bowler_runs,
            is_non_bowler_extra=is_non_bowler_extra,
        )

        # 7. Validate invariants
        validate_delivery_invariants(
            bcs=bcs,
            erp=erp,
            v_wkt=v_wkt,
            wqm=wqm,
            leverage=leverage,
            is_bowler_wkt=is_bowler_wkt,
            is_non_bowler_extra=is_non_bowler_extra,
            batter_runs=batter_runs,
            bowler_runs=bowler_runs,
        )

        # Attribution factor
        alpha_attr = 0.0 if (is_non_bowler_extra or (is_wicket_event and not is_bowler_wkt)) else 1.0

        return DeliveryContributionResult(
            match_id=match_id,
            innings=innings,
            innings_ball_num=innings_ball_num,
            bowler_id=bowler_id,
            striker_id=striker_id,
            is_legal=is_legal,
            bowler_runs=bowler_runs,
            is_bowler_wkt=is_bowler_wkt,
            is_non_bowler_extra=is_non_bowler_extra,
            exp_bowler_runs=exp_runs,
            erp=erp,
            v_wkt=v_wkt,
            wqm=wqm,
            leverage=leverage,
            unweighted_run_impact=unweighted_run_impact,
            bcs=bcs,
            bwpa=0.0,  # Computed by bWPA engine
            alpha_attr=alpha_attr,
            dot_ball=dot_ball,
            exp_dot_prob=exp_dot_prob,
            dot_residual=dot_residual,
            consecutive_dots_before=consecutive_dots_before,
            consecutive_dots_after=consecutive_dots_after,
            dot_pressure_index=dot_pressure_idx,
            rrr_before=rrr_before,
            bowler_econ_current=bowler_econ,
            rrr_pressure_index=rrr_pressure_idx,
            first_inns_scoring_restriction=first_inns_restriction,
        )

    def evaluate_dataframe(
        self,
        df: pd.DataFrame,
        causal_abc_df: pd.DataFrame | None = None,
    ) -> pd.DataFrame:
        """Vectorized execution across entire delivery dataset."""
        res = df.copy()

        # 1. Extras and bowler runs
        res["is_non_bowler_extra"] = res["extras_type"].isin(NON_BOWLER_EXTRAS)
        res["bowler_runs"] = res["batter_runs"] + np.where(
            res["extras_type"].isin(["wide", "Overstep", "other"]),
            res["extras1_runs"],
            0,
        )

        # 2. ERP
        res = self.erp_engine.evaluate_dataframe(res)

        # 3. Wicket classification & value
        canonical_dismissal = res["dismissal_type_canonical"].fillna("").astype(str).str.strip().str.lower()
        bowler_credited_lower = [d.lower() for d in BOWLER_CREDITED_DISMISSALS]
        res["is_bowler_wkt"] = res["is_wicket_event"].astype(bool) & canonical_dismissal.isin(
            bowler_credited_lower
        )

        res = self.wicket_val_engine.evaluate_dataframe(res)
        res["v_wkt"] = np.where(res["is_bowler_wkt"], res["V_wkt"], 0.0)

        res = self.wqm_engine.evaluate_dataframe(res, causal_abc_df)
        res["wqm"] = np.where(res["is_bowler_wkt"], res["WQM"], 1.0)

        # 4. Leverage
        res["leverage"] = self.leverage_engine.evaluate_dataframe(res)

        # 5. Core Synthesis
        wkt_impact = np.where(res["is_bowler_wkt"], res["wqm"] * res["v_wkt"], 0.0)
        res["unweighted_run_impact"] = res["erp"] + wkt_impact
        res["bcs"] = res["unweighted_run_impact"] * res["leverage"]

        # 6. Explanatory Diagnostics
        (
            dot_ball,
            exp_dot_prob,
            dot_residual,
            dots_before,
            dots_after,
            dot_pressure_idx,
        ) = self.dot_pressure_engine.evaluate_dataframe(res)
        res["dot_ball"] = dot_ball
        res["exp_dot_prob"] = exp_dot_prob
        res["dot_residual"] = dot_residual
        res["consecutive_dots_before"] = dots_before
        res["consecutive_dots_after"] = dots_after
        res["dot_pressure_index"] = dot_pressure_idx

        rrr_before, bowler_econ, rrr_pressure_idx = self.rrr_pressure_engine.evaluate_dataframe(res)
        res["rrr_before"] = rrr_before
        res["bowler_econ_current"] = bowler_econ
        res["rrr_pressure_index"] = rrr_pressure_idx

        res["first_inns_scoring_restriction"] = self.first_inns_pressure_engine.evaluate_dataframe(
            res, res["exp_bowler_runs"], res["bowler_runs"], res["is_non_bowler_extra"]
        )

        # 7. Attribution factor for Win Probability
        # alpha_attr = 0 on pure non-bowler extras or non-bowler wickets
        is_non_bowler_wkt = res["is_wicket_event"].astype(bool) & (~res["is_bowler_wkt"])
        res["alpha_attr"] = np.where(res["is_non_bowler_extra"] | is_non_bowler_wkt, 0.0, 1.0)

        return res
