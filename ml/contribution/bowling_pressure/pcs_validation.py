"""Stage B7.5 Comprehensive PCS Testing & Validation Suite (20 Scenarios)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
import numpy as np
import pandas as pd

from ml.contribution.bowling_pressure.config import load_pcs_config
from ml.contribution.bowling_pressure.pcs_delivery_engine import PCSDeliveryEngine
from ml.contribution.bowling_pressure.pcs_normalizer import PCSNormalizer


class PCSValidationSuite:
    """Executes formula-level verification across all 20 required validation scenarios."""

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        self.config = config or load_pcs_config()
        self.engine = PCSDeliveryEngine(self.config)
        self.normalizer = PCSNormalizer(
            k_slope=float(self.config["parameters"]["k_sigmoid_slope"]),
            sigma_ref_1st=float(self.config["parameters"]["sigma_ref_1st"]),
            sigma_ref_2nd=float(self.config["parameters"]["sigma_ref_2nd"]),
        )
        self.results: dict[str, Any] = {}

    def _create_mock_delivery_df(self, rows: list[dict[str, Any]]) -> pd.DataFrame:
        """Utility to convert scenario dictionaries to compliant DataFrame."""
        defaults = {
            "match_id": 99901,
            "season": "2024",
            "competition_category": "IPL",
            "venue_id": 101,
            "venue_avg_first_inn_score": 165.0,
            "innings": 1,
            "innings_ball_num": 1,
            "overid": 1,
            "over_ball_num": 1,
            "bowler_id": 5001,
            "striker_id": 1001,
            "non_striker_id": 1002,
            "bowling_team_id": 201,
            "batting_team_id": 202,
            "score_before": 0,
            "wickets_lost_before": 0,
            "legal_balls_completed_before": 0,
            "legal_balls_remaining_before": 120,
            "current_run_rate": 8.0,
            "target_runs": None,
            "runs_required_before": None,
            "required_run_rate": None,
            "team_runs": 0,
            "bowler_runs": 0,
            "exp_bowler_runs": 1.25,
            "is_legal_delivery": True,
            "is_wide": False,
            "is_no_ball": False,
            "is_boundary_four": False,
            "is_boundary_six": False,
            "is_wicket_event": False,
            "dismissal_type_canonical": "",
            "extras_type": "",
            "leverage": 1.00,
            "V_wkt": 10.0,
            "abc_prior_shrunk": 1.00,
            "striker_cum_balls": 15,
            "striker_cum_runs": 20,
        }
        full_rows = []
        for r in rows:
            row_dict = defaults.copy()
            row_dict.update(r)
            full_rows.append(row_dict)
        return pd.DataFrame(full_rows)

    def run_all_tests(self) -> dict[str, Any]:
        """Execute all 20 required validation scenarios."""
        tests = [
            self.test_01_dangerous_stand_broken,
            self.test_02_rapid_stand_broken,
            self.test_03_struggling_star_dismissed,
            self.test_04_tailender_in_dangerous_stand,
            self.test_05_two_wickets_in_one_over,
            self.test_06_three_wickets_in_one_over,
            self.test_07_run_out_between_bowler_wickets,
            self.test_08_economical_wicketless_spell,
            self.test_09_expensive_wicket_taking_spell,
            self.test_10_successful_chase_ends_early,
            self.test_11_wicket_near_chase_end,
            self.test_12_cross_innings_comparability,
            self.test_13_negative_pressure_performance,
            self.test_14_neutral_pressure_performance,
            self.test_15_positive_pressure_performance,
            self.test_16_insufficient_acc_window,
            self.test_17_wide_and_no_ball,
            self.test_18_byes_and_leg_byes,
            self.test_19_wicket_plus_runs,
            self.test_20_non_bowler_dismissal,
        ]
        
        all_passed = True
        summary = []
        for t in tests:
            res = t()
            summary.append(res)
            if not res["passed"]:
                all_passed = False

        self.results = {
            "all_passed": bool(all_passed),
            "total_scenarios": len(tests),
            "passed_count": int(sum(1 for s in summary if s["passed"])),
            "scenarios": summary,
        }
        return self.results

    def save_validation_results(self, output_path: str | Path) -> None:
        """Save validation results to JSON."""
        p = Path(output_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        # Convert any numpy types to native Python types
        def _convert(obj: Any) -> Any:
            if isinstance(obj, (np.bool_, bool)):
                return bool(obj)
            if isinstance(obj, (np.integer, int)):
                return int(obj)
            if isinstance(obj, (np.floating, float)):
                return float(obj)
            if isinstance(obj, dict):
                return {k: _convert(v) for k, v in obj.items()}
            if isinstance(obj, list):
                return [_convert(x) for x in obj]
            return obj

        cleaned = _convert(self.results)
        with open(p, "w", encoding="utf-8") as f:
            json.dump(cleaned, f, indent=2)

    def test_01_dangerous_stand_broken(self) -> dict[str, Any]:
        """Scenario 1: Dangerous partnership broken."""
        df = self._create_mock_delivery_df([{
            "innings": 2, "overid": 11, "target_runs": 175, "score_before": 95, "wickets_lost_before": 1,
            "legal_balls_completed_before": 60, "legal_balls_remaining_before": 60,
            "runs_required_before": 80, "required_run_rate": 8.0, "current_run_rate": 9.5,
            "partnership_runs_current": 65, "partnership_balls_current": 38,
            "is_wicket_event": True, "dismissal_type_canonical": "caught",
            "leverage": 1.45, "V_wkt": 12.0, "abc_prior_shrunk": 1.35,
            "striker_cum_balls": 25, "striker_cum_runs": 45,
        }])
        evaluated = self.engine.evaluate_deliveries(df)
        rpe = float(evaluated["rpe"].iloc[0])
        pcs = float(self.normalizer.normalize(rpe, innings=2)[0])
        pti = float(evaluated["pti"].iloc[0])
        passed = (rpe >= 15.0) and (pcs >= 68.0) and (pti > 20.0)
        return {
            "id": 1, "name": "Dangerous stand broken",
            "passed": passed, "rpe": round(rpe, 2), "pcs": round(pcs, 2),
            "details": f"SWI: {evaluated['swi'].iloc[0]:.2f}, PTI: {pti:.2f}",
        }

    def test_02_rapid_stand_broken(self) -> dict[str, Any]:
        """Scenario 2: Rapidly accelerating smaller stand broken."""
        df = self._create_mock_delivery_df([{
            "innings": 1, "overid": 8, "score_before": 75, "wickets_lost_before": 2,
            "legal_balls_completed_before": 45, "legal_balls_remaining_before": 75,
            "current_run_rate": 10.0, "is_wicket_event": True, "dismissal_type_canonical": "bowled",
            "leverage": 1.30, "V_wkt": 14.0, "abc_prior_shrunk": 1.40,
        }])
        evaluated = self.engine.evaluate_deliveries(df)
        rpe = float(evaluated["rpe"].iloc[0])
        pcs = float(self.normalizer.normalize(rpe, innings=1)[0])
        passed = (rpe >= 14.0) and (pcs >= 68.0)
        return {"id": 2, "name": "Rapid stand broken", "passed": passed, "rpe": round(rpe, 2), "pcs": round(pcs, 2)}

    def test_03_struggling_star_dismissed(self) -> dict[str, Any]:
        """Scenario 3: High-quality batter dismissed during a struggling innings."""
        df = self._create_mock_delivery_df([{
            "innings": 1, "overid": 14, "score_before": 98, "wickets_lost_before": 2,
            "legal_balls_completed_before": 84, "legal_balls_remaining_before": 36,
            "current_run_rate": 7.0, "is_wicket_event": True, "dismissal_type_canonical": "lbw",
            "leverage": 1.25, "V_wkt": 8.0, "abc_prior_shrunk": 1.60, "striker_cum_balls": 28, "striker_cum_runs": 22,
        }])
        evaluated = self.engine.evaluate_deliveries(df)
        rpe = float(evaluated["rpe"].iloc[0])
        pcs = float(self.normalizer.normalize(rpe, innings=1)[0])
        passed = (rpe > 0.0) and (55.0 <= pcs <= 68.0)
        return {"id": 3, "name": "Struggling star dismissed", "passed": passed, "rpe": round(rpe, 2), "pcs": round(pcs, 2)}

    def test_04_tailender_in_dangerous_stand(self) -> dict[str, Any]:
        """Scenario 4: Low-quality batter dismissed during a dangerous partnership."""
        df = self._create_mock_delivery_df([{
            "innings": 1, "overid": 12, "score_before": 115, "wickets_lost_before": 2,
            "legal_balls_completed_before": 72, "legal_balls_remaining_before": 48,
            "current_run_rate": 9.58, "is_wicket_event": True, "dismissal_type_canonical": "caught",
            "leverage": 1.15, "V_wkt": 11.0, "abc_prior_shrunk": 0.65, "striker_cum_balls": 12, "striker_cum_runs": 15,
        }])
        evaluated = self.engine.evaluate_deliveries(df)
        rpe = float(evaluated["rpe"].iloc[0])
        pcs = float(self.normalizer.normalize(rpe, innings=1)[0])
        passed = (evaluated["swi"].iloc[0] >= 10.0) and (pcs >= 62.0)
        return {"id": 4, "name": "Tailender in dangerous stand", "passed": passed, "swi": round(float(evaluated["swi"].iloc[0]), 2), "pcs": round(pcs, 2)}

    def test_05_two_wickets_in_one_over(self) -> dict[str, Any]:
        """Scenario 5: Two wickets in one over."""
        rows = [
            {"innings": 2, "overid": 15, "target_runs": 165, "score_before": 112, "wickets_lost_before": 2, "legal_balls_completed_before": 85, "legal_balls_remaining_before": 35, "runs_required_before": 53, "required_run_rate": 9.08, "is_wicket_event": True, "dismissal_type_canonical": "bowled", "leverage": 1.55, "V_wkt": 10.0},
            {"innings": 2, "overid": 15, "target_runs": 165, "score_before": 112, "wickets_lost_before": 3, "legal_balls_completed_before": 86, "legal_balls_remaining_before": 34, "runs_required_before": 53, "required_run_rate": 9.35, "is_wicket_event": False, "team_runs": 0, "leverage": 1.60},
            {"innings": 2, "overid": 15, "target_runs": 165, "score_before": 112, "wickets_lost_before": 3, "legal_balls_completed_before": 87, "legal_balls_remaining_before": 33, "runs_required_before": 53, "required_run_rate": 9.63, "is_wicket_event": True, "dismissal_type_canonical": "lbw", "leverage": 1.70, "V_wkt": 12.0},
        ]
        df = self._create_mock_delivery_df(rows)
        evaluated = self.engine.evaluate_deliveries(df)
        total_rpe = float(evaluated["rpe"].sum())
        pcs = float(self.normalizer.normalize(total_rpe, innings=2)[0])
        passed = (total_rpe >= 35.0) and (pcs >= 82.0)
        return {"id": 5, "name": "Two wickets in one over", "passed": passed, "total_rpe": round(total_rpe, 2), "pcs": round(pcs, 2)}

    def test_06_three_wickets_in_one_over(self) -> dict[str, Any]:
        """Scenario 6: Three wickets in one over (Hat-trick)."""
        rows = [
            {"innings": 1, "overid": 19, "score_before": 155, "wickets_lost_before": 4, "legal_balls_completed_before": 108, "legal_balls_remaining_before": 12, "is_wicket_event": True, "dismissal_type_canonical": "bowled", "leverage": 1.60, "V_wkt": 9.0},
            {"innings": 1, "overid": 19, "score_before": 155, "wickets_lost_before": 5, "legal_balls_completed_before": 109, "legal_balls_remaining_before": 11, "is_wicket_event": True, "dismissal_type_canonical": "caught", "leverage": 1.65, "V_wkt": 10.0},
            {"innings": 1, "overid": 19, "score_before": 155, "wickets_lost_before": 6, "legal_balls_completed_before": 110, "legal_balls_remaining_before": 10, "is_wicket_event": True, "dismissal_type_canonical": "lbw", "leverage": 1.70, "V_wkt": 11.0},
        ]
        df = self._create_mock_delivery_df(rows)
        evaluated = self.engine.evaluate_deliveries(df)
        total_rpe = float(evaluated["rpe"].sum())
        pcs = float(self.normalizer.normalize(total_rpe, innings=1)[0])
        passed = (total_rpe >= 40.0) and (pcs >= 88.0)
        return {"id": 6, "name": "Three wickets in one over", "passed": passed, "total_rpe": round(total_rpe, 2), "pcs": round(pcs, 2)}

    def test_07_run_out_between_bowler_wickets(self) -> dict[str, Any]:
        """Scenario 7: Run-out between two bowler-credited wickets."""
        rows = [
            {"innings": 1, "overid": 16, "score_before": 120, "wickets_lost_before": 4, "is_wicket_event": True, "dismissal_type_canonical": "bowled", "leverage": 1.35, "V_wkt": 8.0},
            {"innings": 1, "overid": 16, "score_before": 120, "wickets_lost_before": 5, "is_wicket_event": True, "dismissal_type_canonical": "run out", "team_runs": 1, "bowler_runs": 1, "leverage": 1.40, "V_wkt": 9.0},
            {"innings": 1, "overid": 16, "score_before": 121, "wickets_lost_before": 6, "is_wicket_event": True, "dismissal_type_canonical": "caught", "leverage": 1.45, "V_wkt": 10.0},
        ]
        df = self._create_mock_delivery_df(rows)
        evaluated = self.engine.evaluate_deliveries(df)
        ro_rpe = float(evaluated["rpe"].iloc[1])
        w2_swi = float(evaluated["swi"].iloc[2])
        passed = (ro_rpe == 0.0) and (w2_swi > 0.0)
        return {"id": 7, "name": "Run-out between bowler wickets", "passed": passed, "ro_rpe": ro_rpe, "w2_swi": round(w2_swi, 2)}

    def test_08_economical_wicketless_spell(self) -> dict[str, Any]:
        """Scenario 8: Economical wicketless spell controlling a dangerous stand."""
        rows = []
        for i in range(24):
            r = 0 if i % 3 != 0 else 1
            b_rem = 72 - i
            runs_req = 105 - (i // 3)
            rrr = (runs_req / b_rem) * 6.0
            rows.append({
                "innings": 2, "overid": 7 + (i // 6), "target_runs": 185, "score_before": 80 + i, "wickets_lost_before": 2,
                "legal_balls_completed_before": 48 + i, "legal_balls_remaining_before": b_rem,
                "runs_required_before": runs_req, "required_run_rate": rrr,
                "is_wicket_event": False, "team_runs": r, "bowler_runs": r, "leverage": 1.25,
            })
        df = self._create_mock_delivery_df(rows)
        evaluated = self.engine.evaluate_deliveries(df)
        total_rpe = float(evaluated["rpe"].sum())
        pcs = float(self.normalizer.normalize(total_rpe, innings=2)[0])
        passed = (total_rpe >= 12.0) and (pcs >= 65.0)
        return {"id": 8, "name": "Economical wicketless spell", "passed": passed, "total_rpe": round(total_rpe, 2), "pcs": round(pcs, 2)}

    def test_09_expensive_wicket_taking_spell(self) -> dict[str, Any]:
        """Scenario 9: Expensive wicket-taking spell."""
        rows = []
        cur_runs_req = 80
        for i in range(24):
            is_wkt = (i == 20)
            r = 0 if is_wkt else (4 if i % 2 == 0 else 2)
            b_rem = 48 - i
            rrr = (cur_runs_req / b_rem) * 6.0
            rows.append({
                "innings": 2, "overid": 13 + (i // 6), "target_runs": 170, "score_before": 90 + (80 - cur_runs_req),
                "wickets_lost_before": 6 if i < 20 else 7,
                "legal_balls_completed_before": 72 + i, "legal_balls_remaining_before": b_rem,
                "runs_required_before": cur_runs_req, "required_run_rate": rrr,
                "is_wicket_event": is_wkt, "dismissal_type_canonical": "bowled" if is_wkt else "",
                "team_runs": r, "bowler_runs": r, "leverage": 1.10, "V_wkt": 3.0,
            })
            cur_runs_req = max(1, cur_runs_req - r)
        df = self._create_mock_delivery_df(rows)
        evaluated = self.engine.evaluate_deliveries(df)
        total_rpe = float(evaluated["rpe"].sum())
        pcs = float(self.normalizer.normalize(total_rpe, innings=2)[0])
        passed = (total_rpe < 0.0) and (pcs < 40.0)
        return {"id": 9, "name": "Expensive wicket-taking spell", "passed": passed, "total_rpe": round(total_rpe, 2), "pcs": round(pcs, 2)}

    def test_10_successful_chase_ends_early(self) -> dict[str, Any]:
        """Scenario 10: Successful chase ending before scheduled overs."""
        df = self._create_mock_delivery_df([{
            "innings": 2, "overid": 18, "target_runs": 150, "score_before": 150, "wickets_lost_before": 3,
            "legal_balls_completed_before": 102, "legal_balls_remaining_before": 18,
            "runs_required_before": 0, "required_run_rate": 0.0, "current_run_rate": 8.82,
            "is_wicket_event": False, "team_runs": 1,
        }])
        evaluated = self.engine.evaluate_deliveries(df)
        swi = float(evaluated["swi"].iloc[0])
        passed = (swi == 0.0)
        return {"id": 10, "name": "Successful chase ends early", "passed": passed, "swi": swi}

    def test_11_wicket_near_chase_end(self) -> dict[str, Any]:
        """Scenario 11: Wicket near the end of a difficult chase."""
        df = self._create_mock_delivery_df([{
            "innings": 2, "overid": 18, "target_runs": 180, "score_before": 155, "wickets_lost_before": 5,
            "legal_balls_completed_before": 108, "legal_balls_remaining_before": 12,
            "runs_required_before": 25, "required_run_rate": 12.5, "is_wicket_event": True,
            "dismissal_type_canonical": "bowled", "leverage": 1.75, "V_wkt": 6.5,
        }])
        evaluated = self.engine.evaluate_deliveries(df)
        swi = float(evaluated["swi"].iloc[0])
        passed = (swi >= 8.0)
        return {"id": 11, "name": "Wicket near chase end", "passed": passed, "swi": round(swi, 2)}

    def test_12_cross_innings_comparability(self) -> dict[str, Any]:
        """Scenario 12: First-innings vs Second-innings impact."""
        pcs_1 = float(self.normalizer.normalize(17.50, innings=1)[0])
        pcs_2 = float(self.normalizer.normalize(18.80, innings=2)[0])
        diff = abs(pcs_1 - pcs_2)
        passed = (diff < 1.0) and (68.0 <= pcs_1 <= 72.0)
        return {"id": 12, "name": "Cross-innings comparability", "passed": passed, "pcs_inn1": round(pcs_1, 2), "pcs_inn2": round(pcs_2, 2)}

    def test_13_negative_pressure_performance(self) -> dict[str, Any]:
        """Scenario 13: Negative pressure performance (heavy boundary leakage)."""
        df = self._create_mock_delivery_df([
            {"team_runs": 6, "bowler_runs": 6, "is_boundary_six": True, "leverage": 1.50},
            {"team_runs": 4, "bowler_runs": 4, "is_boundary_four": True, "leverage": 1.50},
            {"team_runs": 4, "bowler_runs": 4, "is_boundary_four": True, "leverage": 1.50},
        ])
        evaluated = self.engine.evaluate_deliveries(df)
        total_rpe = float(evaluated["rpe"].sum())
        pcs = float(self.normalizer.normalize(total_rpe, innings=1)[0])
        passed = (total_rpe < -10.0) and (pcs < 35.0)
        return {"id": 13, "name": "Negative pressure performance", "passed": passed, "total_rpe": round(total_rpe, 2), "pcs": round(pcs, 2)}

    def test_14_neutral_pressure_performance(self) -> dict[str, Any]:
        """Scenario 14: Neutral pressure performance (exact tour par)."""
        pcs = float(self.normalizer.normalize(0.00, innings=1)[0])
        passed = (pcs == 50.00)
        return {"id": 14, "name": "Neutral pressure performance", "passed": passed, "pcs": round(pcs, 2)}

    def test_15_positive_pressure_performance(self) -> dict[str, Any]:
        """Scenario 15: Positive pressure performance."""
        pcs = float(self.normalizer.normalize(25.0, innings=1)[0])
        passed = (pcs >= 75.0)
        return {"id": 15, "name": "Positive pressure performance", "passed": passed, "pcs": round(pcs, 2)}

    def test_16_insufficient_acc_window(self) -> dict[str, Any]:
        """Scenario 16: Insufficient acceleration-window history (stand < 6 balls)."""
        df = self._create_mock_delivery_df([{
            "score_before": 10, "wickets_lost_before": 1, "legal_balls_completed_before": 3,
            "legal_balls_remaining_before": 117,
        }])
        evaluated = self.engine.evaluate_deliveries(df)
        phi_acc = float(evaluated["phi_acc"].iloc[0])
        passed = (0.95 <= phi_acc <= 1.05)
        return {"id": 16, "name": "Insufficient acc window", "passed": passed, "phi_acc": round(phi_acc, 2)}

    def test_17_wide_and_no_ball(self) -> dict[str, Any]:
        """Scenario 17: Wide and no-ball situations."""
        df = self._create_mock_delivery_df([
            {"is_legal_delivery": False, "is_wide": True, "team_runs": 1, "bowler_runs": 1},
            {"is_legal_delivery": False, "is_no_ball": True, "team_runs": 2, "bowler_runs": 2},
        ])
        evaluated = self.engine.evaluate_deliveries(df)
        dci = float(evaluated["dci"].sum())
        passed = (dci == 0.0)  # Extras cannot be dot balls!
        return {"id": 17, "name": "Wide and no-ball", "passed": passed, "dci": dci}

    def test_18_byes_and_leg_byes(self) -> dict[str, Any]:
        """Scenario 18: Byes and leg-byes (non-bowler extras)."""
        df = self._create_mock_delivery_df([{
            "is_legal_delivery": True, "extras_type": "byes", "team_runs": 4, "bowler_runs": 0,
        }])
        evaluated = self.engine.evaluate_deliveries(df)
        alpha = float(evaluated["alpha_attr"].iloc[0])
        leakage = float(evaluated["leakage"].iloc[0])
        passed = (alpha == 0.0) and (leakage == 0.0)
        return {"id": 18, "name": "Byes and leg-byes", "passed": passed, "alpha_attr": alpha, "leakage": leakage}

    def test_19_wicket_plus_runs(self) -> dict[str, Any]:
        """Scenario 19: Wicket plus runs on the same delivery (wide-stumping)."""
        df = self._create_mock_delivery_df([{
            "is_legal_delivery": False, "is_wide": True, "team_runs": 1, "bowler_runs": 1,
            "is_wicket_event": True, "dismissal_type_canonical": "stumped", "leverage": 1.40, "V_wkt": 8.0,
        }])
        evaluated = self.engine.evaluate_deliveries(df)
        rpe = float(evaluated["rpe"].iloc[0])
        passed = bool((rpe > 0.0) and (evaluated["is_bowler_wkt"].iloc[0] == True))
        return {"id": 19, "name": "Wicket plus runs", "passed": passed, "rpe": round(rpe, 2)}

    def test_20_non_bowler_dismissal(self) -> dict[str, Any]:
        """Scenario 20: Non-bowler dismissal attribution (obstructing the field / retired out)."""
        df = self._create_mock_delivery_df([{
            "is_wicket_event": True, "dismissal_type_canonical": "retired out", "leverage": 1.20,
        }])
        evaluated = self.engine.evaluate_deliveries(df)
        rpe = float(evaluated["rpe"].iloc[0])
        alpha = float(evaluated["alpha_attr"].iloc[0])
        passed = (rpe == 0.0) and (alpha == 0.0)
        return {"id": 20, "name": "Non-bowler dismissal", "passed": passed, "rpe": rpe, "alpha_attr": alpha}
