"""Stage 5C Phase 7U Baseline Scorer (Engine B0).

Implements the exact Phase 7U production contribution engine across
IPL, T20I, and OTHER_T20, serving as the benchmark comparator.
"""

from __future__ import annotations

import math
from typing import Any

from ml.contribution.schema import (
    ENGINE_PHASE7U,
    LEVERAGE_MAX,
    LEVERAGE_MIN,
    REGIME_PHASE7U_HEURISTIC,
    SCORE_MAX,
    SCORE_MIN,
    TRACK_A_TAG,
)


def score_stint_phase7u(
    stint: dict[str, Any],
    use_causal_rr_gap: bool = False,
    use_personal_dismissal: bool = False,
) -> dict[str, Any]:
    """Scores a single batter stint using the Phase 7U baseline methodology.

    Parameters
    ----------
    stint : dict[str, Any]
        Batter stint dictionary from StintBuilder.
    use_causal_rr_gap : bool
        If True, wire causal rr_gap_entry into C_chase; else retain 0.0 (baseline parity).
    use_personal_dismissal : bool
        If True, S_res applies only if batter is dismissed; else uses partner wicket fall.

    Returns
    -------
    dict[str, Any]
        Scored record with all pillar components and contribution_score.
    """
    res = dict(stint)
    res["engine_name"] = ENGINE_PHASE7U
    res["track_tag"] = TRACK_A_TAG
    res["expectation_regime"] = REGIME_PHASE7U_HEURISTIC
    res["is_cold_start_expectation"] = False

    # 1. DNB Gate: If player did not bat, return NULL (None) for all score columns
    if stint.get("is_dnb", False):
        res.update(
            {
                "c_wkt": None,
                "c_chase": None,
                "c_eff": None,
                "leverage_l": None,
                "expected_runs": None,
                "expected_sr": None,
                "run_deviation": None,
                "sr_deviation": None,
                "z_runs": None,
                "z_sr": None,
                "z_pace": None,
                "z_bnd": None,
                "z_base": None,
                "bonus_not_out": None,
                "p2_raw": None,
                "z2": None,
                "p2_score": None,
                "adjusted_p2": None,
                "expected_final_entry": None,
                "expected_final_exit": None,
                "expected_final_change": None,
                "par_win": None,
                "par_obs_delta": None,
                "delta_t_obs": None,
                "kappa_entry": None,
                "w_excess": None,
                "f_res": None,
                "kappa_res": None,
                "delta_t_res": None,
                "delta_t_sat": None,
                "accel": None,
                "r_eff": None,
                "g_eff": None,
                "v_max": None,
                "f_chase": None,
                "pen_cap": None,
                "s_res": None,
                "p3_raw_unfloored": None,
                "is_preservation_eligible": False,
                "p3_raw": None,
                "z3": None,
                "p3_score": None,
                "adjusted_p3": None,
                "contribution_score": None,
                "raw_contribution": None,
            }
        )
        return res

    inn = int(stint["innings"])
    r = float(stint["actual_runs"])
    b = int(stint["balls_faced"])
    sr = float(stint["actual_sr"])
    bnd_pct = float(stint["boundary_pct"])
    is_out = bool(stint["is_out"])
    wkts_lost_during_stay = int(stint["wickets_lost_during_stay"])

    # Phase 7U heuristic expected runs and SR
    exp_runs = round(1.25 * b, 1)
    exp_sr = 125.0
    run_dev = r - exp_runs
    sr_dev = sr - exp_sr

    # -------------------------------------------------------------
    # Pillar 1: Match Context & Dual-Slope Leverage
    # -------------------------------------------------------------
    entry_over = float(stint["entry_over_notation"])  # cricket notation used in Phase 1
    w_rem_entry = max(1, min(10, int(stint["entry_wickets_remaining"])))
    w_lost_entry = 10 - w_rem_entry
    t_clamped = max(0.0, min(20.0, entry_over))
    b_rem_entry = max(0, min(120, int(stint["entry_balls_remaining"])))

    # Wicket Crisis Signal (C_wkt)
    if t_clamped <= 0.2 and w_lost_entry == 0:
        c_wkt = 35.0
    else:
        loss_rate = w_lost_entry / max(0.8, t_clamped)
        scarcity = (b_rem_entry / 6.0) / w_rem_entry
        collapse_bonus = (
            min(15.0, (w_lost_entry - 2.0) * 5.0)
            if (t_clamped <= 6.0 and w_lost_entry >= 3)
            else 0.0
        )
        c_wkt = (
            50.0
            + 20.0
            * math.tanh(
                0.55 * (loss_rate - 0.30) / 0.25
                + 0.45 * (scarcity - 1.8) / 0.8
            )
            + collapse_bonus
        )
    c_wkt = max(10.0, min(95.0, c_wkt))

    # Chase / Tempo Pressure Signal (C_chase)
    if inn == 1:
        if t_clamped <= 4.0:
            c_chase = 50.0
        else:
            team_rr_en = float(stint["entry_team_rr"])
            c_chase = 50.0 + 10.0 * math.tanh((7.5 - team_rr_en) / 2.0)
            c_chase = max(20.0, min(80.0, c_chase))
    else:
        tgt = float(stint["target_runs"]) if stint["target_runs"] is not None else 165.0
        rrr_en = float(stint["required_rr_entry"]) if stint["required_rr_entry"] is not None else 8.25
        rrr_clamped = max(0.0, min(24.0, rrr_en))
        if use_causal_rr_gap and stint.get("rr_gap_entry") is not None:
            gap = max(-4.0, min(8.0, float(stint["rr_gap_entry"])))
        else:
            gap = 0.0  # Phase 1 compute_context_and_leverage parity (ABC-R03)

        c_chase = (
            50.0
            + 22.0
            * math.tanh(
                0.55 * (rrr_clamped - 8.25) / 2.5
                + 0.35 * (tgt - 165.0) / 30.0
                + 0.10 * (gap / 2.5 if t_clamped > 4.0 else 0.0)
            )
        )
        c_chase = max(10.0, min(95.0, c_chase))

    # Composite Effective Context & Dual-Slope Leverage
    if inn == 1:
        c_eff = 0.65 * c_wkt + 0.35 * c_chase
    else:
        c_eff = 0.55 * c_wkt + 0.45 * c_chase

    alpha = 0.48 if c_eff >= 50.0 else 0.38
    leverage_l = max(
        LEVERAGE_MIN,
        min(LEVERAGE_MAX, 1.0 + alpha * (c_eff - 50.0) / 50.0),
    )

    # -------------------------------------------------------------
    # Pillar 2: Individual Batter Execution
    # -------------------------------------------------------------
    if b == 0:
        z_sr = 0.0
        z_pace = 0.0
        z_bnd = 0.0
    else:
        z_sr = max(-3.0, min(3.5, (sr - 125.0) / 50.0))
        r_ref = (
            float(stint["entry_team_rr"])
            if inn == 1
            else min(24.0, float(stint["required_rr_entry"]) if stint["required_rr_entry"] is not None else 8.25)
        )
        z_pace = max(-3.0, min(3.5, (0.06 * sr - r_ref) / 3.5))
        z_bnd = max(-2.5, min(2.5, (bnd_pct - 45.0) / 30.0))

    z_runs = (r - 19.8) / 21.6
    z_base = 0.7 * (run_dev / 14.5) + 0.3 * max(-3.0, min(3.0, sr_dev / 48.0))
    bonus_not_out = 0.25 if (not is_out and b >= 1) else 0.0

    p2_raw = (
        0.35 * z_runs
        + 0.25 * z_sr
        + 0.20 * z_pace
        + 0.10 * z_bnd
        + 0.10 * z_base
        + bonus_not_out
    )
    z2 = (p2_raw - (-0.068)) / 1.029
    p2_score = max(
        SCORE_MIN,
        min(SCORE_MAX, 100.0 / (1.0 + math.exp(-1.40 * z2))),
    )
    adj_p2 = max(
        SCORE_MIN,
        min(SCORE_MAX, 50.0 + (p2_score - 50.0) * leverage_l),
    )

    # -------------------------------------------------------------
    # Pillar 3: Team-State Impact
    # -------------------------------------------------------------
    # Dynamic Wicket Resource Cost S_res
    b_rem_exit = max(0, min(120, int(stint["exit_balls_remaining"])))
    w_rem_exit = max(0, min(10, int(stint["exit_wickets_remaining"])))
    c_base = (b_rem_exit / 120.0) * (10.0 / max(1.0, w_rem_exit + 2.0)) * 0.5

    # Trigger: partner wicket during stay vs personal dismissal sensitivity
    if use_personal_dismissal:
        wicket_fell = is_out
    else:
        wicket_fell = wkts_lost_during_stay > 0  # Phase 1 parity (ABC-R04)

    if wicket_fell:
        s_res = -(c_base - min(0.7 * c_base, 0.02 * max(0.0, r - 15.0)))
    else:
        s_res = 0.15 * (w_rem_exit / 10.0)

    accel = max(
        -3.0,
        min(
            3.0,
            (float(stint["window_team_rr"]) - float(stint["entry_team_rr"]))
            / 3.0,
        ),
    )

    r_eff = None
    g_eff = None
    v_max = None
    f_chase = None
    pen_cap = None

    if inn == 1:
        # Phase 7U Innings 1 heuristic fallback (EFS and trajectory are NaN)
        p3_raw_unfloored = accel + s_res
    else:
        # Phase 7U Innings 2 Model E Feasibility Saturation
        w_rem_chase = float(w_rem_entry)
        b_rem_chase = float(b_rem_entry)
        rrr_chase = float(stint["required_rr_entry"]) if stint["required_rr_entry"] is not None else 8.25

        v_max = (
            12.0
            + 3.0 * math.tanh((w_rem_chase - 3.5) / 2.0)
            + 4.0 * (12.0 / (b_rem_chase + 6.0))
        )
        f_chase = 1.0 / (
            1.0 + math.exp(4.0 * (rrr_chase / max(6.0, v_max) - 1.25))
        )
        pen_cap = 4.0 + 6.0 * f_chase

        delta_rrr = float(stint["required_rr_change"]) if stint["required_rr_change"] is not None else 0.0
        delta_rr_gap = float(stint["rr_gap_change"]) if stint["rr_gap_change"] is not None else 0.0
        t_prog_chg = float(stint["target_progress_change"]) if stint["target_progress_change"] is not None else 0.0

        if delta_rrr < 0:
            r_eff = -pen_cap * math.tanh(abs(delta_rrr) / pen_cap)
        else:
            r_eff = min(12.0, delta_rrr)

        if delta_rr_gap < 0:
            g_eff = -pen_cap * math.tanh(abs(delta_rr_gap) / pen_cap)
        else:
            g_eff = min(12.0, delta_rr_gap)

        p3_raw_unfloored = (
            0.50 * (r_eff / 3.0)
            + 0.25 * (g_eff / 3.0)
            + 0.25 * ((t_prog_chg - 0.15) / 0.15)
            + s_res
        )

    # State Preservation Floor (64.0 default -> raw floor approx 0.7810)
    p3_floor_raw = 0.159 + (-math.log(100.0 / 64.0 - 1.0) / 1.40) * 1.513
    is_pres_eligible = False

    if (b >= 8 or r >= 15) and not (b <= 1 and r == 0):
        if inn == 1:
            # Inn 1 Phase 7U has no EFS so preservation gate is False
            is_pres_eligible = False
        else:
            rrr_en = float(stint["required_rr_entry"]) if stint["required_rr_entry"] is not None else 8.25
            delta_rrr = float(stint["required_rr_change"]) if stint["required_rr_change"] is not None else 0.0
            t_prog = float(stint["target_progress_change"]) if stint["target_progress_change"] is not None else 0.0
            personal_rr = (r * 6.0 / b) if b > 0 else 0.0
            if (
                rrr_en <= 7.5
                and delta_rrr >= -0.5
                and t_prog >= 0.20
                and personal_rr >= rrr_en
            ):
                is_pres_eligible = True

    if is_pres_eligible:
        p3_raw = max(p3_raw_unfloored, p3_floor_raw)
    else:
        p3_raw = p3_raw_unfloored

    z3 = (p3_raw - 0.159) / 1.513
    p3_score = max(
        SCORE_MIN,
        min(SCORE_MAX, 100.0 / (1.0 + math.exp(-1.40 * z3))),
    )
    adj_p3 = max(
        SCORE_MIN,
        min(SCORE_MAX, 50.0 + (p3_score - 50.0) * leverage_l),
    )

    # -------------------------------------------------------------
    # Step 7: Contribution Score & Raw Contribution
    # -------------------------------------------------------------
    contribution_score = round(
        max(SCORE_MIN, min(SCORE_MAX, 0.50 * adj_p2 + 0.50 * adj_p3)), 1
    )
    raw_contribution = round(0.50 * (z2 * leverage_l) + 0.50 * (z3 * leverage_l), 4)

    res.update(
        {
            "c_wkt": round(c_wkt, 2),
            "c_chase": round(c_chase, 2),
            "c_eff": round(c_eff, 2),
            "leverage_l": round(leverage_l, 4),
            "expected_runs": exp_runs,
            "expected_sr": exp_sr,
            "run_deviation": round(run_dev, 2),
            "sr_deviation": round(sr_dev, 2),
            "z_runs": round(z_runs, 4),
            "z_sr": round(z_sr, 4),
            "z_pace": round(z_pace, 4),
            "z_bnd": round(z_bnd, 4),
            "z_base": round(z_base, 4),
            "bonus_not_out": bonus_not_out,
            "p2_raw": round(p2_raw, 4),
            "z2": round(z2, 4),
            "p2_score": round(p2_score, 2),
            "adjusted_p2": round(adj_p2, 2),
            "expected_final_entry": None,
            "expected_final_exit": None,
            "expected_final_change": None,
            "par_win": None,
            "par_obs_delta": None,
            "delta_t_obs": None,
            "kappa_entry": None,
            "w_excess": None,
            "f_res": None,
            "kappa_res": None,
            "delta_t_res": None,
            "delta_t_sat": None,
            "accel": round(accel, 4),
            "r_eff": round(r_eff, 4) if r_eff is not None else None,
            "g_eff": round(g_eff, 4) if g_eff is not None else None,
            "v_max": round(v_max, 4) if v_max is not None else None,
            "f_chase": round(f_chase, 4) if f_chase is not None else None,
            "pen_cap": round(pen_cap, 4) if pen_cap is not None else None,
            "s_res": round(s_res, 4),
            "p3_raw_unfloored": round(p3_raw_unfloored, 4),
            "is_preservation_eligible": is_pres_eligible,
            "p3_raw": round(p3_raw, 4),
            "z3": round(z3, 4),
            "p3_score": round(p3_score, 2),
            "adjusted_p3": round(adj_p3, 2),
            "contribution_score": contribution_score,
            "raw_contribution": raw_contribution,
        }
    )

    return res

