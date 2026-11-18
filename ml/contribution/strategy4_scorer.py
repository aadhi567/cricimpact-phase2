"""Stage 5C Universal Strategy 4 Scorer (Engine S4).

Implements the competition-aware Strategy 4 hybrid methodology:
- Innings 1: Full Strategy 4 Hybrid (Model T + Res-Adj Par + Damping + Preservation Floor).
- Innings 2: Strategy 4 Chase Adaptation (Option 1B primary; Option 1C f_res sensitivity).
- Competition-stratified walk-forward expectations from CausalExpectationManager.
- Preserves raw_contribution distinction per Decision 4:
  - Innings 1: 0.5 * (run_deviation / 10.0) + 0.5 * p3_raw
  - Innings 2: 0.5 * (z2 * L) + 0.5 * (z3 * L)
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np

from ml.contribution.expectations import (
    WindowExpectationModels,
    interpolate_w_hist,
)
from ml.contribution.schema import (
    ENGINE_STRATEGY4,
    FALLBACK_EXPECTED_SR,
    LEVERAGE_MAX,
    LEVERAGE_MIN,
    SCORE_MAX,
    SCORE_MIN,
    TRACK_A_TAG,
)


def score_stint_strategy4(
    stint: dict[str, Any],
    models: WindowExpectationModels,
    use_causal_rr_gap: bool = False,
    use_personal_dismissal: bool = False,
    use_chase_f_res: bool = False,  # Option 1C sensitivity variant
) -> dict[str, Any]:
    """Scores a single batter stint using Universal Strategy 4.

    Parameters
    ----------
    stint : dict[str, Any]
        Batter stint dictionary.
    models : WindowExpectationModels
        Category-specific walk-forward expectation models & parameters.
    use_causal_rr_gap : bool
        If True, wire causal rr_gap_entry into C_chase; else retain 0.0.
    use_personal_dismissal : bool
        If True, S_res applies only if batter is dismissed; else uses partner wicket fall.
    use_chase_f_res : bool
        Option 1C sensitivity variant: if True, scale chase drag by f_res.

    Returns
    -------
    dict[str, Any]
        Scored record with all pillar components and contribution_score.
    """
    res = dict(stint)
    res["engine_name"] = ENGINE_STRATEGY4
    res["track_tag"] = TRACK_A_TAG
    res["expectation_regime"] = models.regime
    res["is_cold_start_expectation"] = (models.n_prior_matches < 30)

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

    # -------------------------------------------------------------
    # Expected Runs & SR (RF model or deterministic fallback)
    # -------------------------------------------------------------
    phase_code = (
        0
        if float(stint["entry_over_decimal"]) <= 6.0
        else (1 if float(stint["entry_over_decimal"]) <= 15.0 else 2)
    )
    is_chase = 1 if inn == 2 else 0
    req_rr_clean = float(stint["required_rr_entry"]) if stint["required_rr_entry"] is not None else 0.0
    req_runs_clean = float(stint["runs_required_entry"]) if stint["runs_required_entry"] is not None else 0.0
    tgt_clean = (
        float(stint["target_runs"])
        if is_chase and stint["target_runs"] is not None
        else models.par_total
    )

    if models.runs_model is not None and models.sr_model is not None:
        X_b = np.array(
            [
                [
                    float(stint["batting_order"]),
                    float(stint["entry_over_decimal"]),
                    float(stint["entry_balls_remaining"]),
                    float(stint["entry_wickets_remaining"]),
                    float(stint["entry_team_score"]),
                    float(stint["entry_team_rr"]),
                    float(phase_code),
                    float(is_chase),
                    req_rr_clean,
                    req_runs_clean,
                    tgt_clean,
                ]
            ]
        )
        exp_runs = float(max(0.0, models.runs_model.predict(X_b)[0]))
        exp_runs = round(exp_runs, 1)
        exp_sr = float(max(0.0, models.sr_model.predict(X_b)[0]))
        exp_sr = round(exp_sr, 1)
    else:
        # Deterministic fallback
        exp_runs = round(1.25 * b, 1)
        exp_sr = FALLBACK_EXPECTED_SR

    run_dev = r - exp_runs
    sr_dev = sr - exp_sr

    # -------------------------------------------------------------
    # Pillar 1: Match Context & Dual-Slope Leverage
    # -------------------------------------------------------------
    entry_over = float(stint["entry_over_notation"])
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

    # Chase / Tempo Pressure Signal (C_chase) with category-adapted target/rrr center
    if inn == 1:
        if t_clamped <= 4.0:
            c_chase = 50.0
        else:
            team_rr_en = float(stint["entry_team_rr"])
            c_chase = 50.0 + 10.0 * math.tanh((7.5 - team_rr_en) / 2.0)
            c_chase = max(20.0, min(80.0, c_chase))
    else:
        tgt = float(stint["target_runs"]) if stint["target_runs"] is not None else models.target_center
        rrr_en = float(stint["required_rr_entry"]) if stint["required_rr_entry"] is not None else models.rrr_center
        rrr_clamped = max(0.0, min(24.0, rrr_en))
        if use_causal_rr_gap and stint.get("rr_gap_entry") is not None:
            gap = max(-4.0, min(8.0, float(stint["rr_gap_entry"])))
        else:
            gap = 0.0

        c_chase = (
            50.0
            + 22.0
            * math.tanh(
                0.55 * (rrr_clamped - models.rrr_center) / 2.5
                + 0.35 * (tgt - models.target_center) / 30.0
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
    # Pillar 2: Individual Batter Execution (with category z-anchors)
    # -------------------------------------------------------------
    if b == 0:
        z_sr = 0.0
        z_pace = 0.0
        z_bnd = 0.0
    else:
        z_sr = max(-3.0, min(3.5, (sr - models.p2_sr_mean) / models.p2_sr_std))
        r_ref = (
            float(stint["entry_team_rr"])
            if inn == 1
            else min(24.0, float(stint["required_rr_entry"]) if stint["required_rr_entry"] is not None else models.rrr_center)
        )
        z_pace = max(-3.0, min(3.5, (0.06 * sr - r_ref) / 3.5))
        z_bnd = max(-2.5, min(2.5, (bnd_pct - 45.0) / 30.0))

    z_runs = (r - models.p2_runs_mean) / models.p2_runs_std
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
    z2 = (p2_raw - models.p2_norm_mean) / models.p2_norm_std
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
    b_rem_exit = max(0, min(120, int(stint["exit_balls_remaining"])))
    w_rem_exit = max(0, min(10, int(stint["exit_wickets_remaining"])))
    c_base = (b_rem_exit / 120.0) * (10.0 / max(1.0, w_rem_exit + 2.0)) * 0.5

    # Wicket trigger: partner vs personal dismissal
    if use_personal_dismissal:
        wicket_fell = is_out
    else:
        wicket_fell = wkts_lost_during_stay > 0

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

    # Variables for output tracking
    efs_en = None
    efs_ex = None
    efs_chg = None
    par_win = None
    par_obs_delta = None
    delta_t_obs = None
    kappa_entry = None
    w_excess = None
    f_res = None
    kappa_res = None
    delta_t_res = None
    delta_t_sat = None
    r_eff = None
    g_eff = None
    v_max = None
    f_chase = None
    pen_cap = None
    is_pres_eligible = False

    if inn == 1:
        # ---------------------------------------------------------
        # Innings 1: Full Strategy 4 Hybrid
        # ---------------------------------------------------------
        # 1. Predict EFS at entry and exit
        en_legal = int(stint["entry_legal_balls"])
        ex_legal = int(stint["exit_legal_balls"])
        en_ov_dec = float(stint["entry_over_decimal"])
        ex_ov_dec = float(stint["exit_over_decimal"])
        en_score = int(stint["entry_team_score"])
        ex_score = int(stint["exit_team_score"])
        en_wkts = int(stint["entry_wickets_lost"])
        ex_wkts = int(stint["exit_wickets_lost"])
        en_rem_balls = int(stint["entry_balls_remaining"])
        ex_rem_balls = int(stint["exit_balls_remaining"])
        en_trr = float(stint["entry_team_rr"])
        ex_trr = (ex_score * 6.0 / ex_legal) if ex_legal > 0 else 0.0

        en_phase = 0 if en_ov_dec <= 6.0 else (1 if en_ov_dec <= 15.0 else 2)
        ex_phase = 0 if ex_ov_dec <= 6.0 else (1 if ex_ov_dec <= 15.0 else 2)

        if models.efs_model is not None:
            X_en = np.array([[en_score, en_wkts, 10 - en_wkts, en_ov_dec, en_rem_balls, en_trr, en_phase]])
            efs_en = float(models.efs_model.predict(X_en)[0])

            if ex_rem_balls == 0 or (10 - ex_wkts) == 0:
                efs_ex = float(ex_score)
            else:
                X_ex = np.array([[ex_score, ex_wkts, 10 - ex_wkts, ex_ov_dec, ex_rem_balls, ex_trr, ex_phase]])
                efs_ex = float(models.efs_model.predict(X_ex)[0])
        else:
            # Deterministic linear projection in cold start / OTHER_T20
            efs_en = float(en_score + en_rem_balls * (models.par_total / 120.0))
            if ex_rem_balls == 0 or (10 - ex_wkts) == 0:
                efs_ex = float(ex_score)
            else:
                efs_ex = float(ex_score + ex_rem_balls * (models.par_total / 120.0))

        efs_chg = efs_ex - efs_en

        # 2. Model T Attributable EFS
        drag_ext = efs_chg - run_dev
        partner_wkts = max(0, wkts_lost_during_stay - (1 if is_out else 0))

        # Attributable gamma
        if drag_ext >= 0 or partner_wkts == 0 or (b <= 1 and r == 0) or (b < 6 and r < 10):
            gamma = 1.00
        else:
            dot_pct = float(stint["dot_ball_pct"])
            sr_ratio = (sr / exp_sr) if exp_sr > 0 else 1.0
            if (dot_pct >= 50.0 and sr_ratio < 1.15) or (sr < 100.0 and b >= 10) or run_dev <= 0:
                gamma = 1.00  # Category A (caused)
            elif partner_wkts >= 3:
                gamma = 0.50  # Category C (severe collapse)
            elif (sr_ratio >= 1.25 or sr >= 150.0) and dot_pct < 45.0 and run_dev > 0:
                gamma = 0.15  # Category B (independent partner wickets)
            elif partner_wkts >= 2:
                gamma = 0.50  # Category C (2 partner wickets)
            else:
                gamma = 0.70  # General stagnation

        delta_efs_attr = run_dev + gamma * drag_ext
        z_efs = delta_efs_attr / 12.0

        # 3. Damped Context-and-Resource Adjusted Trajectory
        if efs_en <= models.par_total:
            kappa_entry = max(0.60, min(1.0, efs_en / models.par_total))
        else:
            kappa_entry = 1.0 + 0.25 * math.tanh((efs_en / models.par_total - 1.0) / 0.25)

        # Crease resource depletion factor f_res using w_hist
        w_hist_en = interpolate_w_hist(en_legal, models.w_curve)
        w_hist_ex = interpolate_w_hist(ex_legal, models.w_curve)
        w_excess = partner_wkts - max(0.1, w_hist_ex - w_hist_en)

        if w_excess >= 0:
            f_res = max(0.70, min(1.0, 1.0 - 0.05 * w_excess))
        else:
            f_res = 1.0 + 0.10 * math.tanh((-0.05 * w_excess) / 0.10)

        kappa_res = max(0.55, min(1.35, kappa_entry * f_res))

        # Par trajectory delta
        par_en = float(models.par_curve[min(120, en_legal)])
        par_ex = float(models.par_curve[min(120, ex_legal)])
        delta_t_obs = (ex_score - par_ex) - (en_score - par_en)
        team_runs_added = float(stint["team_runs_added"])
        par_win = team_runs_added - delta_t_obs
        delta_t_res = team_runs_added - kappa_res * par_win

        # Soft-knee saturation
        if delta_t_res < -12.0:
            delta_t_sat = -12.0 - 8.0 * math.tanh((abs(delta_t_res) - 12.0) / 8.0)
        else:
            delta_t_sat = delta_t_res

        p3_raw_unfloored = (
            0.50 * z_efs
            + 0.25 * (delta_t_sat / 10.0)
            + 0.25 * accel
            + s_res
        )

        # State Preservation Floor (Innings 1)
        p3_floor_raw = models.p3_norm_mean + (-math.log(100.0 / 64.0 - 1.0) / 1.40) * models.p3_norm_std
        if (b >= 8 or r >= 15) and not (b <= 1 and r == 0):
            window_trr = float(stint["window_team_rr"])
            personal_rr = (r * 6.0 / b) if b > 0 else 0.0
            if (
                efs_en >= 1.08 * models.par_total
                and efs_chg >= -2.5
                and window_trr >= 9.0
                and personal_rr >= 8.5
            ):
                is_pres_eligible = True

        if is_pres_eligible:
            p3_raw = max(p3_raw_unfloored, p3_floor_raw)
        else:
            p3_raw = p3_raw_unfloored

    else:
        # ---------------------------------------------------------
        # Innings 2: Strategy 4 Chase Adaptation (Option 1B Primary)
        # ---------------------------------------------------------
        w_rem_chase = float(w_rem_entry)
        b_rem_chase = float(b_rem_entry)
        rrr_chase = float(stint["required_rr_entry"]) if stint["required_rr_entry"] is not None else models.rrr_center

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

        # Option 1C sensitivity variant: if use_chase_f_res is enabled
        if use_chase_f_res:
            en_legal = int(stint["entry_legal_balls"])
            ex_legal = int(stint["exit_legal_balls"])
            w_hist_en = interpolate_w_hist(en_legal, models.w_curve)
            w_hist_ex = interpolate_w_hist(ex_legal, models.w_curve)
            partner_wkts = max(0, wkts_lost_during_stay - (1 if is_out else 0))
            w_excess = partner_wkts - max(0.1, w_hist_ex - w_hist_en)
            if w_excess >= 0:
                f_res = max(0.70, min(1.0, 1.0 - 0.05 * w_excess))
            else:
                f_res = 1.0 + 0.10 * math.tanh((-0.05 * w_excess) / 0.10)
            if r_eff < 0:
                r_eff = r_eff * f_res
            if g_eff < 0:
                g_eff = g_eff * f_res

        p3_raw_unfloored = (
            0.50 * (r_eff / 3.0)
            + 0.25 * (g_eff / 3.0)
            + 0.25 * ((t_prog_chg - 0.15) / 0.15)
            + s_res
        )

        p3_floor_raw = models.p3_norm_mean + (-math.log(100.0 / 64.0 - 1.0) / 1.40) * models.p3_norm_std
        if (b >= 8 or r >= 15) and not (b <= 1 and r == 0):
            rrr_en = float(stint["required_rr_entry"]) if stint["required_rr_entry"] is not None else models.rrr_center
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

    z3 = (p3_raw - models.p3_norm_mean) / models.p3_norm_std
    p3_score = max(
        SCORE_MIN,
        min(SCORE_MAX, 100.0 / (1.0 + math.exp(-1.40 * z3))),
    )
    adj_p3 = max(
        SCORE_MIN,
        min(SCORE_MAX, 50.0 + (p3_score - 50.0) * leverage_l),
    )

    # -------------------------------------------------------------
    # Step 7: Contribution Score & Raw Contribution (Decision 4)
    # -------------------------------------------------------------
    contribution_score = round(
        max(SCORE_MIN, min(SCORE_MAX, 0.50 * adj_p2 + 0.50 * adj_p3)), 1
    )

    # Decision 4: Preserves distinction between Innings 1 and Chase:
    # Innings 1: 0.5 * (run_dev / 10.0) + 0.5 * p3_raw
    # Innings 2: 0.5 * (z2 * L) + 0.5 * (z3 * L)
    if inn == 1:
        raw_contribution = round(0.50 * (run_dev / 10.0) + 0.50 * p3_raw, 4)
    else:
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
            "expected_final_entry": round(efs_en, 1) if efs_en is not None else None,
            "expected_final_exit": round(efs_ex, 1) if efs_ex is not None else None,
            "expected_final_change": round(efs_chg, 1) if efs_chg is not None else None,
            "par_win": round(par_win, 2) if par_win is not None else None,
            "par_obs_delta": round(delta_t_obs, 2) if delta_t_obs is not None else None,
            "delta_t_obs": round(delta_t_obs, 2) if delta_t_obs is not None else None,
            "kappa_entry": round(kappa_entry, 4) if kappa_entry is not None else None,
            "w_excess": round(w_excess, 2) if w_excess is not None else None,
            "f_res": round(f_res, 4) if f_res is not None else None,
            "kappa_res": round(kappa_res, 4) if kappa_res is not None else None,
            "delta_t_res": round(delta_t_res, 2) if delta_t_res is not None else None,
            "delta_t_sat": round(delta_t_sat, 2) if delta_t_sat is not None else None,
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
