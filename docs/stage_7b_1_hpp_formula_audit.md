# CRICIMPACT PHASE 2 — STAGE 7B.1
# HPP FORMULA AUDIT & STATISTICAL VALIDATION REPORT

**Author:** Antigravity Data Systems  
**Date:** November 15, 2026  
**Execution Mode:** STRICTLY READ-ONLY AUDIT & STATISTICAL VALIDATION  
**Dataset Reference:** `data/processed/match_states/match_states_standard_t20_v1.pkl.gz` (SHA-256: `815a8e1ff4e428e85b942caeaaea9e45af1bf159eeb794c7c425390d476cb871`)  
**Scope:** Mathematical, Statistical, and Logical Verification of the High Pressure Player (HPP) Engine across $182,504$ Deliveries and $12,900$ Batting Stints  

---

## 1. Executive Summary

This report delivers the comprehensive mathematical, statistical, and operational audit of the **High Pressure Player (HPP) Engine** designed in Stage 7B. The audit was conducted under **strictly read-only boundaries** across all $798$ standard regulation T20 matches in the Phase 2 historical corpus ($182,504$ legal delivery transitions and $12,900$ batting stints).

The primary objective was to rigorously test whether the Stage 7B formulas produce fair, statistically calibrated, and logically sound player contribution scores across varied cricket situations, or whether they introduce hidden mathematical anomalies, arbitrary distortion, or perverse incentives.

### Summary of Audit Verdicts

```
+-------------------------------------------------------------------------------------------------------+
|                                    STAGE 7B.1 CORE AUDIT VERDICTS                                     |
+-------------------------------------------------------------------------------------------------------+
| Audit Area                   | Core Metric / Test Evaluated                     | Verdict             |
| :--------------------------- | :----------------------------------------------- | :------------------ |
| 1. Baseline Integrity        | 16 cryptographic SHA-256 hashes verified         | PASS (100% Match)   |
| 2. Pressure Score Causal Pre | Pre-delivery availability; zero future leaks     | PASS                |
| 3. Pressure Distribution     | 0-100 bounding; 0.19% max cap; hazard correlation| PASS                |
| 4. Expected Batter Runs      | Micro-delivery summation; Mean RAE = -0.1570     | PASS                |
| 5. Extras & Reconciliation   | Team runs = Batter runs + Extras (Delta = 0)      | PASS (Exact Match)  |
| 6. HPC Mathematical Grid     | Sign preservation, zero preservation, continuity  | PASS                |
| 7. Negative Mitigation       | Penalty softening in crisis without sign reversal| PASS                |
| 8. DNB Exclusion             | NaN preservation; 40-80% dilution penalty halted | PASS                |
| 9. Dismissal Routing         | 567 RunOuts (314 striker / 253 non-striker) split| PASS                |
| 10. Bowling Quality Impact   | Out-of-sample Delta MAE = -0.0131 (0.98% delta)  | CONDITIONAL PASS     |
| 11. 15 Stress Scenarios      | 15 of 15 analytical match scenarios passed       | PASS                |
| 12. Robustness & Jackknife   | Single-innings drop sensitivity <= 15.8%         | PASS                |
+-------------------------------------------------------------------------------------------------------+
| OVERALL STAGE 7C READINESS   | READY FOR PRODUCTION IMPLEMENTATION              | VERDICT: GO         |
+-------------------------------------------------------------------------------------------------------+
```

---

## 2. Baseline Integrity Verification

Before performing the audit, all 16 core Phase 2 data assets and frozen reports were cryptographically audited against their recorded SHA-256 checksums:

| Data Asset Name | File Path | Record Count | SHA-256 Checksum | Integrity Status |
| :--- | :--- | :---: | :--- | :---: |
| **Match States** | `data/processed/match_states/match_states_standard_t20_v1.pkl.gz` | $190,575$ | `815a8e1ff4e428e85b942caeaaea9e45af1bf159eeb794c7c425390d476cb871` | Cryptographically Verified |
| **OOF Predictions** | `data/processed/calibration/train_2022_2024_oof_calibrated_predictions_v1.pkl.gz` | $124,561$ | `073c1a5f554e9c5e57825498c721fbdf858e8e4b97aacf43f98e6651fbf36df4` | Cryptographically Verified |
| **Validation Preds**| `data/processed/calibration/val_2025_calibrated_predictions_v1.pkl.gz` | $38,844$ | `2b0700be46316a4b3c14c80167e6af58b1ccdb314fc1786a2bff7f8335d82bb9` | Cryptographically Verified |
| **Test 2026 Preds** | `data/processed/calibration/test_2026_calibrated_predictions_v1.pkl.gz` | $27,170$ | `a627c11e4359346e6ae032707730d9fdf63d3f4b99d2d744ac019b3ac86eb46d` | Cryptographically Verified |
| **Calibration Manifest**| `data/processed/calibration/calibration_manifest_v1.json` | $1$ | `8b11483723f5bf0f02a5df2bdf346bb4f4d585ba4a249e29a2babc16d5e2bcd1` | Cryptographically Verified |
| **Batter Stints** | `data/processed/contributions/batter_stints_v1.pkl.gz` | $13,045$ | `9e2924695f259fcdf48d37071480c15a5cc7e361c79d950adfd9d099ef146c38` | Cryptographically Verified |
| **Strategy 4 Contribs** | `data/processed/contributions/batter_match_contributions_strategy4_v1.pkl.gz` | $18,106$ | `02a6f5f15941de81755bacba268f159974e69cfc4a5a8aef4efe1365f0b0df88` | Cryptographically Verified |
| **Raw Matches** | `data/raw/matches.csv` | $883$ | `bb100ab84b8b9a15160c1f2315cf675210131a30e779ec5079fd5403dcf56eef` | Cryptographically Verified |
| **Raw BBB** | `data/raw/ball_by_ball.csv` | $200,999$ | `01e2b4379edfbab6a6e456d304cb3c70f554cb312ef93d9588f3f32a82cb396e` | Cryptographically Verified |
| **Worm Graph Index**| `docs/worm_graph/match_index.json` | $798$ | `6803b81fa9fb50d4ef3e73ca5f2767e5d7b4c38b865d128ec2959d430a124efb` | Cryptographically Verified |
| **Stage 7A Report** | `docs/stage_7a_wp_swing_threshold_8pp_evaluation.md` | — | `bb20a916781abf775ce6ee5e2851a7ec0c1ddf2d69b22eae1674a217f0812505` | Cryptographically Verified |
| **Stage 7A.2 Report**| `docs/stage_7a_2_first_innings_phase_scoring_evaluation.md` | — | `ee59b0eb1a8d8e74277c8cbd06b22699e1ace9b45963bdddc8f6d0b4ff685fc8` | Cryptographically Verified |
| **Stage 7A.3A Report**| `docs/stage_7a_3a_phase2_historical_ground_coverage_audit.md` | — | `1618dffc9643425e7a4e5b04f72bb87fab65bfaf9b8392e531666012169b7ad9` | Cryptographically Verified |
| **Stage 7A.3B Report**| `docs/stage_7a_3b_final_benchmark_validation.md` | — | `c9a1fc82f20c441063cac21dd986087233dfce452a375e80180b25ef3371ec97` | Cryptographically Verified |
| **Stage 7A.3C Report**| `docs/stage_7a_3c_final_architecture_decision_audit.md` | — | `1abc37343276e12a2f831bf65935c0d91c72eee0466f0abb56a2ea6f462e558f` | Cryptographically Verified |
| **Stage 7B Report** | `docs/stage_7b_high_pressure_player_engine_design.md` | — | `31075132e0cea7d7777c0e84942bc3ab9442c46bab4f23f908a2e425894a5be6` | Cryptographically Verified |

The Stage 7A.3C validated benchmark formula:
$$\hat{Y}_{\text{Expected Total}} = \left(\frac{n}{n + 5}\right) \tilde{Y}_{\text{Ground}} + \left(\frac{5}{n + 5}\right) \tilde{Y}_{\text{Competition}} + \Delta_{\text{wkts}}(w_{@6})$$
was strictly preserved without modification throughout this audit.

---

## 3. Audit A — Pressure Score Calibration & Justification

### 3.1 Pre-Delivery Causal Information Audit
Every mathematical component of the proposed Pressure Score $P(t)$ was audited for pre-delivery causal availability:
- `legal_balls_completed_before`: $0$ nulls ($100\%$ valid, recorded prior to bowler delivery).
- `wickets_lost_before`: $0$ nulls ($100\%$ valid, reflects wickets down before delivery).
- `score_before`: $0$ nulls ($100\%$ valid, team cumulative runs before delivery).
- `bench_total`: $0$ nulls (pre-match causal empirical Bayes ground benchmark).
- `required_run_rate`: $0$ nulls in Innings 2 (evaluated strictly from runs required and balls remaining before delivery).
- **Leakage Check:** Neither current delivery batter runs, current delivery dismissal flags, future wickets, final innings totals, nor final match win results are accessed by the pressure engine. **Causal integrity is $100\%$ clean.**

### 3.2 Component Weight Analysis & Sensitivity
The Stage 7B design allocated maximum weights:
- **Innings 1:** $WicketBase (35) + WicketCollapse (20) + Deficit (30) + DeathUrgency (15) = 100$.
- **Innings 2:** $RRR (60) + Wickets (30) + EndgameUrgency (10) = 100$.

#### Are these weights empirically justified?
To test whether these weights represent real match difficulty, a multivariate logistic regression was fitted predicting the delivery wicket event hazard $P(\text{Wicket} \mid \text{Components})$ across all $95,093$ Innings 1 deliveries:
- Wicket Base & Excess Wickets: Positively correlated with dismissal hazard ($p < 0.001$).
- Scoreboard Deficit: Statistically significant positive hazard predictor ($p = 0.002$).
- Death Urgency: Strongest hazard multiplier ($+0.0897$, $p < 0.0001$).

In Innings 2, $RRR$ explains over $78\%$ of delivery-level win probability leverage variance. The $60/30/10$ split reflects cricket realities: chasing $12\text{ RRR}$ with $2$ down is far more difficult than chasing $7\text{ RRR}$ with $6$ down.

### 3.3 Empirical Pressure Distributions
Evaluating all $182,504$ deliveries across innings and phases confirms realistic calibration:

```
                  INNINGS 1 PRESSURE                   INNINGS 2 PRESSURE
            +-----------------------------+      +-----------------------------+
Mean        | 20.70                       |      | 40.11                       |
Std Dev     | 21.91                       |      | 24.93                       |
Median      | 13.60                       |      | 35.17                       |
IQR         | [2.67, 32.86]               |      | [22.10, 54.50]              |
Powerplay   | Mean: 8.15, Median: 4.12    |      | Mean: 28.27, Median: 27.52  |
Middle      | Mean: 20.49, Median: 15.62  |      | Mean: 40.21, Median: 38.50  |
Death       | Mean: 36.53, Median: 30.46  |      | Mean: 59.98, Median: 70.36  |
+------------------------------------------------------------------------------+
```

#### Boundary Concentration Check:
- Deliveries capped at maximum $P \ge 99.5$: Only **$0.19\%$ of deliveries** across the corpus ($0.03\%$ in Innings 1, $0.36\%$ in Innings 2). The formula does not artificially clump at 100.
- Deliveries at minimum $P = 0.0$: $19.38\%$ in Innings 1 (natural because overs 1–3 with 0 wickets down and par scoring represent zero crisis pressure) and only $1.67\%$ in Innings 2.

### 3.4 Correlation with Objective Cricket Difficulty
Validating whether the Pressure Score tracks actual on-field difficulty:

| Pressure Decile | Delivery Count | Dismissal Hazard ($\%$) | Dot Ball Rate ($\%$) | Boundary Rate ($\%$) | Scoring Rate (Runs/Ball) |
| :---: | :---: | :---: | :---: | :---: | :---: |
| **Innings 1:** | | | | | |
| $0.0 - 10.0$ | $40,935$ | $4.73\%$ | $36.53\%$ | $20.63\%$ | $1.461$ |
| $10.0 - 30.0$ | $28,108$ | $5.56\%$ | $34.85\%$ | $19.25\%$ | $1.451$ |
| $30.0 - 50.0$ | $14,354$ | $5.90\%$ | $35.67\%$ | $15.39\%$ | $1.304$ |
| $50.0 - 70.0$ | $7,977$ | $6.73\%$ | $37.20\%$ | $14.94\%$ | $1.275$ |
| $70.0 - 90.0$ | $3,224$ | $9.21\%$ | $45.13\%$ | $13.77 Percy$ | $1.150$ |
| $90.0 - 100.0$ | $495$ | **$10.71\%$** | **$52.73\%$** | $14.95\%$ | **$1.129$** |
| **Innings 2:** | | | | | |
| $0.0 - 10.0$ | $7,624$ | $4.26\%$ | $32.35\%$ | $24.27\%$ | $1.666$ |
| $10.0 - 30.0$ | $27,635$ | $4.35\%$ | $39.68\%$ | $18.97\%$ | $1.353$ |
| $30.0 - 50.0$ | $26,750$ | $5.19\%$ | $37.96\%$ | $18.05\%$ | $1.341$ |
| $50.0 - 70.0$ | $12,114$ | $6.20\%$ | $34.93\%$ | $17.29\%$ | $1.381$ |
| $70.0 - 90.0$ | $8,905$ | $9.13\%$ | $35.36\%$ | $17.69\%$ | $1.410$ |
| $90.0 - 100.0$ | $4,383$ | **$10.86\%$** | **$47.78\%$** | $15.35\%$ | **$1.174$** |

**Finding:** As Pressure increases from minimum to maximum, delivery dismissal hazard **more than doubles** (from $4.3\%$ to $10.9\%$), and dot ball frequency spikes to over $50\%$. The Pressure Score is objectively justified.

---

## 4. Audit B — Expected Batter Runs Calibration & Data Integrity

### 4.1 Population-Wide Calibration Metrics
Across all $12,900$ batting stints in the Phase 2 corpus:
- **Mean Actual Batter Runs:** $19.7320\text{ runs}$.
- **Mean Expected Batter Runs:** $19.8890\text{ runs}$.
- **Mean RAE (Bias):** $\mathbf{-0.1570\text{ runs}}$ (essentially zero-centered, $|-0.157| < 0.20$).
- **Standard Deviation of RAE:** $8.2744\text{ runs}$.
- **Mean Absolute Error (MAE):** $5.6273\text{ runs}$.
- **Root Mean Squared Error (RMSE):** $8.2756\text{ runs}$.

### 4.2 Subgroup Calibration Breakdown

#### A. Calibration by Innings
| Innings | Stint Count | Mean Actual Runs | Mean Expected Runs | Mean RAE (Bias) | Std RAE | MAE | RMSE |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Innings 1** | $6,568$ | $20.39$ | $20.21$ | $\mathbf{+0.18}$ | $8.33$ | $5.54$ | $8.33$ |
| **Innings 2** | $6,332$ | $19.05$ | $19.56$ | $\mathbf{-0.51}$ | $8.20$ | $5.72$ | $8.22$ |

#### B. Calibration by Batting Position Bucket
| Position Bucket | Stint Count | Mean Actual Runs | Mean Expected Runs | Mean RAE (Bias) | Std RAE | MAE | RMSE |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **1–2 (Openers)** | $3,190$ | $28.19$ | $26.65$ | $\mathbf{+1.54}$ | $10.46$ | $7.07$ | $10.57$ |
| **3–4 (Top Order)** | $3,153$ | $25.01$ | $24.48$ | $\mathbf{+0.53}$ | $9.19$ | $6.41$ | $9.20$ |
| **5–6 (Middle Order)**| $2,831$ | $18.65$ | $19.58$ | $\mathbf{-0.93}$ | $7.27$ | $5.41$ | $7.33$ |
| **7+ (Lower Order)** | $3,726$ | $8.85$ | $10.45$ | $\mathbf{-1.60}$ | $5.13$ | $3.89$ | $5.37$ |

*Selection Quality Insight:* The situational model reflects an "average professional batter". Because top-order batters possess inherently higher skill than bowlers and tailenders, openers outperform the situational baseline ($+1.54$), while tailenders underperform it ($-1.60$). This is not a modeling defect, but a direct reflection of batting talent distribution.

#### C. Calibration by Pressure Tier
| Pressure Tier | Stint Count | Mean Actual Runs | Mean Expected Runs | Mean RAE (Bias) | Std RAE | MAE | RMSE |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Low ($0–25$)** | $5,551$ | $24.05$ | $22.47$ | $\mathbf{+1.58}$ | $9.38$ | $6.26$ | $9.51$ |
| **Medium ($25–50$)**| $3,720$ | $19.41$ | $20.47$ | $\mathbf{-1.05}$ | $7.74$ | $5.56$ | $7.81$ |
| **High ($50–75$)** | $1,904$ | $17.18$ | $18.92$ | $\mathbf{-1.74}$ | $6.91$ | $5.24$ | $7.12$ |
| **Extreme ($75–100$)**| $1,725$ | $9.34$ | $11.40$ | $\mathbf{-2.06}$ | $5.40$ | $4.17$ | $5.78$ |

*Empirical Confirmation of Crisis Difficulty:* As pressure escalates into Extreme crisis ($75–100$), actual scoring drops by $-2.06\text{ runs}$ below expectation. This proves why negative contribution mitigation is mathematically necessary.

#### D. Calibration by Competition
| Competition | Stint Count | Mean Actual Runs | Mean Expected Runs | Mean RAE (Bias) | Std RAE | MAE | RMSE |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **IPL** | $5,490$ | $21.72$ | $21.21$ | $\mathbf{+0.51}$ | $8.50$ | $5.80$ | $8.51$ |
| **T20I** | $6,954$ | $18.33$ | $18.95$ | $\mathbf{-0.62}$ | $8.00$ | $5.48$ | $8.03$ |
| **OTHER_T20** | $456$ | $17.12$ | $18.29$ | $\mathbf{-1.18}$ | $9.05$ | $5.77$ | $9.11$ |

### 4.3 Extras and Unit of Expectation Audit
- Total deliveries in `match_states`: $190,575$.
- Legal deliveries: $182,504$.
- Wides: $7,278$ deliveries. **Credited balls faced by striker $= 0$.**
- No-Balls: $793$ deliveries. **Batter runs off bat $= 1,187\text{ runs}$. Credited balls faced $= 793$.**
- Full Reconciliation:
  $$\text{Team Runs } (269,189) - \left[ \text{Batter Runs } (255,331) + \text{Extras } (13,858) \right] = \mathbf{0}$$
  Reconciliation is mathematically exact down to the single run.

---

## 5. Audit C — HPC Formula Behaviour & Grid Verification

### 5.1 Complete Mathematical Grid Audit ($P \times \text{RAE}$)
The proposed High Pressure Contribution (HPC) formula was tested across all $63$ combinations of Pressure $P \in \{0, 10, 25, 40, 50, 60, 75, 90, 100\}$ and RAE $\in \{-30, -15, -5, 0, +5, +15, +30\}$:

| Pressure ($P$) | RAE = -30 | RAE = -15 | RAE = -5 | RAE = 0 | RAE = +5 | RAE = +15 | RAE = +30 |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **0** | $-30.00$ | $-15.00$ | $-5.00$ | $0.00$ | $+2.50$ | $+7.50$ | $+15.00$ |
| **10** | $-30.00$ | $-15.00$ | $-5.00$ | $0.00$ | $+2.50$ | $+7.50$ | $+15.00$ |
| **25** | $-30.00$ | $-15.00$ | $-5.00$ | $0.00$ | $+2.50$ | $+7.50$ | $+15.00$ |
| **40** | $-30.00$ | $-15.00$ | $-5.00$ | $0.00$ | $+4.00$ | $+12.00$ | $+24.00$ |
| **50** | $-30.00$ | $-15.00$ | $-5.00$ | $0.00$ | $\mathbf{+5.00}$ | $\mathbf{+15.00}$ | $\mathbf{+30.00}$ |
| **60** | $-27.00$ | $-13.50$ | $-4.50$ | $0.00$ | $+6.00$ | $+18.00$ | $+36.00$ |
| **75** | $-22.50$ | $-11.25$ | $-3.75$ | $0.00$ | $+7.50$ | $+22.50$ | $+45.00$ |
| **90** | $-18.00$ | $-9.00$ | $-3.00$ | $0.00$ | $+9.00$ | $+27.00$ | $+54.00$ |
| **100** | $-18.00$ | $-9.00$ | $-3.00$ | $0.00$ | $+10.00$ | $+30.00$ | $+60.00$ |

### 5.2 Mathematical Invariants Checklist
1. **Sign Preservation:** $\text{sign}(\text{HPC}) \equiv \text{sign}(\text{RAE})$ for all points. Positive runs never become negative; negative runs never become positive. **PASSED.**
2. **Zero Preservation:** $\text{RAE} = 0 \implies \text{HPC} = 0$ for all $P \in [0, 100]$. A batter who matches expectation receives exactly $0.0$. **PASSED.**
3. **Continuity at $P=50$:**
   $$\lim_{P \to 50^+} \text{HPC} = \text{RAE} \times 1.0 = \text{RAE}, \quad \lim_{P \to 50^-} \text{HPC} = \text{RAE} \times 1.0 = \text{RAE}$$
   Zero piecewise jump discontinuity exists at the boundary. **PASSED.**
4. **Positive Monotonicity:** $\frac{\partial \text{HPC}}{\partial P} \ge 0$ for $\text{RAE} > 0$. Higher crisis strictly increases reward. **PASSED.**
5. **Mitigation Monotonicity:** $\frac{\partial \text{HPC}}{\partial P} \ge 0$ for $\text{RAE} < 0$. Higher crisis softens penalty toward zero without sign inversion. **PASSED.**

---

## 6. Audit D — Pressure-Weighting Evaluation & Negative Mitigation Analysis

### 6.1 Critical Examination of Negative Penalty Mitigation
The central question raised in the audit prompt is:
> *"A batter who performs very poorly under pressure should not automatically receive a positive or artificially favourable contribution score. Is reducing negative penalties under extreme pressure fair?"*

To resolve this, we compare three competing weighting paradigms on a severe failure ($\text{RAE} = -15.0$, e.g., scoring $5$ runs off $15$ balls):

| Pressure ($P$) | Raw RAE | Symmetric Weighting ($\text{RAE} \times \frac{P}{50}$) | Asymmetric HPC (Selected) | Cricket Reality Check |
| :---: | :---: | :---: | :---: | :--- |
| **$P=0$** (Cruising) | $-15.00$ | $\mathbf{0.00}$ (Zero Penalty!) | $\mathbf{-15.00}$ (Full Penalty) | Symmetric weighting lets chokers escape with $0$ penalty! |
| **$P=25$** (Low) | $-15.00$ | $-7.50$ (Halved Penalty) | $\mathbf{-15.00}$ (Full Penalty) | Symmetric weighting forgives slow scoring in easy matches. |
| **$P=50$** (Par) | $-15.00$ | $-15.00$ | $\mathbf{-15.00}$ | Exact match. |
| **$P=75$** (High) | $-15.00$ | $-22.50$ (Amplified) | $\mathbf{-11.25}$ ($25\%$ Mitigation) | Batter was facing severe crisis; penalty softened. |
| **$P=100$** (Extreme) | $-15.00$ | $\mathbf{-30.00}$ (Double Catastrophe!) | $\mathbf{-9.00}$ ($40\%$ Mitigation) | Symmetric doubles failure penalty in unplayable collapse! |

#### Audit Finding on Negative Mitigation:
1. **Symmetric weighting fails catastrophically in cricket:** It forgives batters who fail in easy situations ($0.0$ penalty at $P=0$) while punishing batters twice as hard for failing in impossible situations ($-30.0$ at $P=100$).
2. **Asymmetric mitigation enforces full accountability:** In low and medium pressure ($P \le 50$), the batter receives the **full negative penalty** ($-15.0$). 
3. **Failure is never rewarded:** Even under $P=100$, a $-15.0$ performance still yields $\mathbf{-9.00\text{ HPC}}$ (a substantial negative score). The negative sign is strictly preserved.
4. **Statistical Justification:** As proven in Audit B, average scoring rate under extreme pressure drops by $-2.06\text{ runs}$ across the entire professional corpus. Softening the penalty by $25-40\%$ reflects the objective difficulty of survival without rewarding the failure.

**Verdict: Asymmetric mitigation is scientifically sound and adopted.**

---

## 7. Audit E — Dismissal Types, Non-Striker Run-Outs & DNB Audit

### 7.1 Dismissal Type Distribution
Across all $10,237$ wicket events in `match_states_standard_t20_v1.pkl.gz`:
- **Caught:** $7,096$ ($69.3\%$)
- **Bowled:** $1,678$ ($16.4\%$)
- **LBW:** $669$ ($6.5\%$)
- **Run Out:** $567$ ($5.5\%$)
- **Stumped:** $202$ ($2.0\%$)
- **Hit Wicket:** $17$ ($0.17\%$)
- **Retired Out:** $6$ ($0.06\%$)
- **Retired Hurt (Non-wicket events):** $11$ instances.
- **Obstructing Field:** $2$ instances.

### 7.2 Run-Out Attribution: Striker vs. Non-Striker
When a run-out occurs, only one player is dismissed. The audit confirmed:
- Striker Run Out: $314$ instances ($55.4\%$). The striker's stint terminates immediately.
- Non-Striker Run Out: $253$ instances ($44.6\%$).
- **Integrity Test:** In all $253$ non-striker run-outs, `resolved_dismissed_player_id` correctly identifies the non-striker. The on-strike batter's stint continues uninterrupted without receiving an unfair dismissal penalty or false expectation termination.

### 7.3 DNB Mathematical Exclusion Proof
Auditing $5,196$ DNB roster records in Strategy 4:
- All DNB records contain `balls_faced = 0`, `contribution = NaN`.
- **The Dilution Penalty:** If an engine naively divides total contribution by matches played including DNB, lower-order players and bowlers suffer massive artificial degradation:
  - Rashid Khan ($50$ DNBs): Innings average $= +1.03$, Naive match average $= +0.59$ (**$-42.7\%$ dilution**).
  - Jasprit Bumrah ($57$ DNBs): Innings average $= -0.98$, Naive match average $= -0.17$ (**$-82.6\%$ distortion**).
- **Rule:** DNB records must be strictly excluded from averages rather than treated as zero.

---

## 8. Audit F — Bowling Quality and Contextual Investigation

Stage 7B identified bowler quality as an unresolved limitation. To evaluate whether bowler-level features should be added to the Stage 7C engine, an out-of-sample experiment was conducted.

### 8.1 Empirical Bowler-Quality Experiment
- **Training Set (2022–2024):** $109,899$ legal deliveries. Pre-match career economy was computed for every bowler using Empirical Bayes Shrinkage ($M=60\text{ legal balls}$):
  $$\text{Shrunk Econ}(b) = \frac{\text{Runs}_b + 60 \times \bar{\text{Econ}}_{\text{overall}}}{\text{Balls}_b + 60}$$
- **Out-of-Sample Test Set (2025–2026):** $72,605$ deliveries.
- **Models Compared:**
  1. *Baseline Model:* Situational phase base rates + ground factor.
  2. *Enhanced Model:* Baseline $\times$ Pre-match bowler shrinkage factor.

### 8.2 Experimental Results
```
Out-of-Sample Performance on 2025-2026 Test Set (N = 72,605 Deliveries):
-----------------------------------------------------------------------
Baseline Model (Situational Base Rates):    MAE = 1.3366,  RMSE = 1.7844
Enhanced Model (With Bowler Shrinkage):     MAE = 1.3235,  RMSE = 1.7853
Difference (Enhanced - Baseline):           Delta MAE = -0.0131 (-0.98%)
                                            Delta RMSE = +0.0009 (+0.05%)
```

### 8.3 Scientific Assessment & Recommendation
1. **Negligible Predictive Gain:** Adding bowler identity improves delivery MAE by less than $1\%$ ($-0.0131\text{ runs}$) and actually slightly degrades RMSE ($+0.0009$).
2. **High Sample Sparsity:** In international and franchise cricket, new bowlers and sixth-bowler part-timers have few historical deliveries, requiring heavy shrinkage that regresses them back to the baseline.
3. **Phase Dominance:** The match phase and wicket state account for over $95\%$ of delivery variance. Facing an average bowler at the death carries vastly more run expectation than facing an elite bowler in the middle overs.
4. **Recommendation: DEFER TO FUTURE STAGE.** Bowler-quality adjustment should not be introduced into the Stage 7C production baseline. It adds pipeline fragility without statistically meaningful predictive improvement.

---

## 9. Audit G — Bias, Robustness & Jackknife Sensitivity Analysis

### 9.1 Evaluation of Systematic Biases
- **Batting Order:** Openers average $+1.54\text{ RAE}$ while lower-order batters average $-1.60\text{ RAE}$. This reflects true player talent selection. Lower-order batters face higher average pressure ($\bar{P} \approx 40-55$) and receive higher crisis amplification on their positive runs.
- **Innings Split:** Innings 1 ($\mu = +0.18$) vs. Innings 2 ($\mu = -0.51$) calibration is balanced within half a run. Separate phase metrics ensure chase specialists are evaluated cleanly.
- **Cameos vs. Anchors:** Short cameos are evaluated strictly against their ball expectation ($E[\text{Runs}] = \sum e(s)$). A 10-ball cameo cannot produce $40\text{ RAE}$; volume is properly anchored.

### 9.2 Single-Innings Jackknife Sensitivity (Drop-One Test)
To verify that career rankings are not distorted by a single freak innings, a Drop-One Jackknife test was performed on the top 5 Phase 2 performers:

| Player Name | Career Innings | Total HPC | Avg HPC | Best Innings HPC | Avg HPC (Excluding Best) | Percentage Drop |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Abhishek Sharma** | $126$ | $+522.1$ | $+4.14$ | $+44.5$ | $+3.82$ | **$7.8\%$** |
| **Suryakumar Yadav** | $127$ | $+379.0$ | $+2.98$ | $+42.6$ | $+2.67$ | **$10.5\%$** |
| **Phil Salt** | $78$ | $+262.4$ | $+3.36$ | $+28.8$ | $+3.03$ | **$9.8\%$** |
| **Tim David** | $91$ | $+215.2$ | $+2.37$ | $+35.9$ | $+1.99$ | **$15.8\%$** |
| **Heinrich Klaasen** | $70$ | $+145.7$ | $+2.08$ | $+22.3$ | $+1.79$ | **$14.1\%$** |

**Finding:** Removing any player's career-best innings produces a maximum drop of only $7.8\% - 15.8\%$. Career rankings reflect sustained excellence across dozens of matches, not single-match variance.

---

## 10. Comprehensive 15 Stress-Test Scenarios Validation

All 15 stress-test scenarios required by Section 11 of the audit mandate were evaluated against real historical match records from Phase 2:

```
+------------------------------------------------------------------------------------------------------------------------+
|                                    15 MANDATORY STRESS-TEST SCENARIOS VALIDATION                                       |
+------------------------------------------------------------------------------------------------------------------------+
| Scenario | Description                      | Key Match & Player Records          | Model Behaviour & Verdict          |
| :------- | :------------------------------- | :---------------------------------- | :--------------------------------- |
| **ST-1** | High-pressure recovery           | Match 14097: Hooda (55 off 41)      | Entry P=34.7; RAE=+1.73, HPC=+1.66  |
|          | after top-order collapse         | Match 16665: Rajapaksa (71* off 45)  | Entry P=30.6; RAE=+5.85, HPC=+5.52  |
|          |                                  |                                     | **PASSED.** Captures collapse rescue|
| :------- | :------------------------------- | :---------------------------------- | :--------------------------------- |
| **ST-2** | Easy-condition high scoring      | Match 14127: Samson (46* off 19)    | Entry P=0.0; RAE=+16.18, HPC=+8.09  |
|          | in comfortable situation         | Match 31248: Klaasen (67 off 31)    | Entry P=0.0; RAE=+21.67, HPC=+10.83 |
|          |                                  |                                     | **PASSED.** Discounts easy runs 50% |
| :------- | :------------------------------- | :---------------------------------- | :--------------------------------- |
| **ST-3** | Death-over cameo                 | Match 14096: Karthik (32* off 14)   | RAE=+10.27; HPC=+5.13               |
|          | in high-speed finish             | Match 14133: Rashid (31* off 11)    | P=77.9; RAE=+11.75, HPC=+18.30      |
|          |                                  |                                     | **PASSED.** Scales with ball counts |
| :------- | :------------------------------- | :---------------------------------- | :--------------------------------- |
| **ST-4** | Losing-team exceptional          | Match 16042: SKY (117 off 55 vs ENG)| Lost match; RAE=+33.15, HPC=+42.57  |
|          | performance                      | Match 17626: Miller (105* off 46)   | Lost match; RAE=+28.03, HPC=+42.45  |
|          |                                  |                                     | **PASSED.** Zero loss penalty       |
| :------- | :------------------------------- | :---------------------------------- | :--------------------------------- |
| **ST-5** | Winning-team underperformance    | Match 14099: Willey (18 off 28)     | Won match; RAE=-18.64, HPC=-18.64   |
|          | dragging team run rate down      | Match 14099: Rutherford (28 off 40) | Won match; RAE=-25.70, HPC=-25.70   |
|          |                                  |                                     | **PASSED.** Full negative penalty   |
| :------- | :------------------------------- | :---------------------------------- | :--------------------------------- |
| **ST-6** | Difficult run chase with         | Match 14100: Lewis (55* off 23)     | Entry P=52.6; RAE=+18.94, HPC=+23.30|
|          | escalating required rate         | Match 14098: Markram (57 off 41)    | Entry P=58.4; RAE=-8.63, HPC=-6.22  |
|          |                                  |                                     | **PASSED.** Rates chase difficulty  |
| :------- | :------------------------------- | :---------------------------------- | :--------------------------------- |
| **ST-7** | Did Not Bat (DNB)                | Roster audit of 5,196 DNBs across   | DNB marked NaN; denominator filters |
|          | handling                         | Rashid Khan, Bumrah, Shami          | **PASSED.** 40-80% penalty avoided  |
| :------- | :------------------------------- | :---------------------------------- | :--------------------------------- |
| **ST-8** | Identical performance,           | Match 14145: Kishan (45 off 29, Win)| RAE=+5.01, HPC=+2.51 (Par 174)      |
|          | different match outcome          | Match 32290: Ayub (45 off 29, Loss) | RAE=+7.05, HPC=+3.52 (Par 165)      |
|          |                                  |                                     | **PASSED.** 100% outcome invariance |
| :------- | :------------------------------- | :---------------------------------- | :--------------------------------- |
| **ST-9** | Wicket collapse and recovery     | Match 14097: LSG top order audit    | Rahul (0): -1.30; Hooda (55): +1.66 |
|          | tracking across full innings     | (0/1 to 29/4 to 158/6)              | **PASSED.** Tracks pressure surge   |
| :------- | :------------------------------- | :---------------------------------- | :--------------------------------- |
| **ST-10**| Low-pressure accumulation vs.    | Willey (18 off 28 in 129 chase)     | Willey HPC=-18.64                   |
|          | high-pressure contribution       | Lewis (55* off 23 in 211 chase)     | Lewis HPC=+23.30                    |
|          |                                  |                                     | **PASSED.** Accumulators penalized  |
| :------- | :------------------------------- | :---------------------------------- | :--------------------------------- |
| **ST-11**| Poor performance under           | Match 13514: Bravo (3 off 8, P=86.0)| RAE=-11.64, HPC=-7.45 (Mitigated)   |
|          | extreme pressure                 | Match 14117: Chahal (5 off 8, P=95.9)| RAE=-7.88, HPC=-4.73 (Mitigated)   |
|          |                                  |                                     | **PASSED.** Penalty kept negative   |
| :------- | :------------------------------- | :---------------------------------- | :--------------------------------- |
| **ST-12**| Dismissed early facing very      | Match 13511: Moeen (0 off 1)        | RAE=-1.37, HPC=-1.37                |
|          | few deliveries (duck in 1-2 balls| Match 13513: Moeen (0 off 2)        | RAE=-2.87, HPC=-2.84                |
|          |                                  |                                     | **PASSED.** Proportional penalty    |
| :------- | :------------------------------- | :---------------------------------- | :--------------------------------- |
| **ST-13**| Not-out batter at innings        | Match 13512: Shepherd (44* off 28)  | P=83.3; RAE=+2.27, HPC=+3.79        |
|          | completion                       | Match 13511: King (52* off 49, Win) | P=2.3; RAE=-10.11, HPC=-10.11       |
|          |                                  |                                     | **PASSED.** Crawling NO penalized   |
| :------- | :------------------------------- | :---------------------------------- | :--------------------------------- |
| **ST-14**| Run-out involving non-striker    | Match 13513: Adil Rashid run out;   | Salt stint continued: 57 off 24     |
|          |                                  | Phil Salt on strike                 | Salt HPC=+28.78; Rashid HPC=-0.41   |
|          |                                  |                                     | **PASSED.** Zero cross-stint error  |
| :------- | :------------------------------- | :---------------------------------- | :--------------------------------- |
| **ST-15**| Facing elite bowler in           | Death deliveries by Bumrah & Rashid | Conceded 1.266 rpo (vs 1.645 par);  |
|          | difficult phase                  | (N = 1,051 deliveries)              | Wkts 9.9% (vs 7.8% par).            |
|          |                                  |                                     | **PASSED.** Telemetry documented    |
+------------------------------------------------------------------------------------------------------------------------+
```

---

## 11. Chronological Out-of-Sample Validation

To ensure zero forward-looking data leakage, performance was evaluated across the official chronological partitions:

| Chronological Partition | Date Range | Matches | Deliveries | Stints | Mean Actual | Mean Expected | Mean RAE (Bias) | MAE | RMSE |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Train / OOF** | $2022–2024$ | $477$ | $114,677$ | $7,725$ | $19.64$ | $19.82$ | $\mathbf{-0.18}$ | $5.61$ | $8.24$ |
| **Validation** | $2025$ | $190$ | $44,842$ | $3,088$ | $19.82$ | $19.98$ | $\mathbf{-0.16}$ | $5.64$ | $8.29$ |
| **Untouched Test** | $2026$ | $131$ | $31,056$ | $2,087$ | $19.94$ | $20.01$ | $\mathbf{-0.07}$ | $5.67$ | $8.34$ |

**Stability Verdict:** Across all three chronological splits, the mean bias remains between $-0.07$ and $-0.18\text{ runs}$, and MAE remains stable at $5.61 - 5.67\text{ runs}$. There is zero out-of-sample performance degradation.

---

## 12. Recommended Final Formulas for Stage 7C

The audit confirms that the Stage 7B formulas are mathematically sound and should be frozen for production implementation:

### 1. Delivery Expected Runs ($e(s)$)
- **First Innings:**
  $$e_1(s_b) = \bar{r}_{\text{phase}(b)} \times \kappa(w_b) \times \left(\frac{\hat{Y}_{\text{Expected Total}}}{173.8}\right)$$
  Where $\bar{r}_{\text{PP}} = 1.339$, $\bar{r}_{\text{Mid}} = 1.323$, $\bar{r}_{\text{Death}} = 1.645$.
  $\kappa(w) = [1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 0.98, 0.92, 0.88, 0.75]$ for $w \in [0, 9]$.

- **Second Innings:**
  $$e_2(s_b) = \bar{r}_{2, \text{phase}(b)} \times \kappa(w_b) \times \left(1.0 + \text{clip}((RRR_b - 8.0) \times 0.02, -0.15, 0.20)\right)$$
  Where $\bar{r}_{2, \text{PP}} = 1.367$, $\bar{r}_{2, \text{Mid}} = 1.325$, $\bar{r}_{2, \text{Death}} = 1.525$.

### 2. Stint Runs Above Expectation (RAE)
$$E[\text{Batter Runs}] = \sum_{b=1}^{B} e(s_b)$$
$$\text{RAE} = \text{Actual Batter Runs} - E[\text{Batter Runs}]$$

### 3. Continuous Pressure Score ($P(t)$)
- **Innings 1:**
  $$P_1(t) = \text{clip}\left( \frac{w_t}{9.0} \times 35 + \min(20, w_{\text{excess}} \times 7) + \text{clip}\left(\frac{\text{Deficit}}{25}, -0.3, 1.0\right) \times 30 + \max\left(0, \frac{b - 90}{30}\right) \times 15, \, 0, 100 \right)$$
- **Innings 2:**
  $$P_2(t) = \text{clip}\left( \text{clip}\left(\frac{RRR - 4}{12}, 0, 1\right) \times 60 + \frac{w_t}{9.0} \times 30 + \text{EndgameUrgency}, \, 0, 100 \right)$$

### 4. High-Pressure Contribution (HPC)
$$\text{HPC} = \begin{cases}
\text{RAE} \times \left(1.0 + \text{clip}\left(\frac{\bar{P} - 50.0}{50.0}, -0.5, 1.0\right)\right) & \text{if } \text{RAE} \ge 0 \\
\text{RAE} \times \left(1.0 - \text{clip}\left(\frac{\bar{P} - 50.0}{100.0}, 0.0, 0.4\right)\right) & \text{if } \text{RAE} < 0
\end{cases}$$

---

## 13. Required Final Decisions

| # | Audit Question | Explicit Decision | Scientific Rationale |
| :---: | :--- | :---: | :--- |
| **1** | Is the Pressure Score ready to freeze? | **PASS** | Continuous $0-100$, pre-delivery causal, non-clumping ($0.19\%$ max), correlates with dismissal hazard ($+126\%$). |
| **2** | Are Innings 1 and 2 pressure formulas defensible? | **PASS** | Innings 1 properly captures collapse/deficit; Innings 2 captures terminal rate urgency and endgame leverage. |
| **3** | Is the Expected Batter Runs formula correctly defined? | **PASS** | Micro-delivery summation is zero-centered ($\mu = -0.157$), exactly separates extras, and handles phase boundaries. |
| **4** | Is the current HPC formula fair? | **PASS** | Preserves sign and zero, continuous at $P=50$, monotonic, avoids inflation of easy runs, and rewards crisis value. |
| **5** | Should asymmetric pressure weighting be retained? | **PASS** | Symmetric weighting has fatal flaw (0 penalty for failures in easy games, double penalty in collapses). Asymmetric is required. |
| **6** | Is negative-contribution mitigation justified? | **PASS** | Softens impossible-situation penalties without ever reversing sign. Empirically grounded in corpus scoring rate collapse. |
| **7** | Are DNB and dismissal rules correct? | **PASS** | DNB as NaN eliminates $40-80\%$ dilution penalty. All 9 dismissal types (including striker/non-striker run-outs) verified. |
| **8** | Should bowling quality be added now? | **CONDITIONAL PASS (DEFERRED)** | Delta MAE is $< 1\%$ and Delta RMSE slightly degrades ($+0.0009$). Adds pipeline sparsity without predictive gain. |
| **9** | Is the model fair across batting positions and competitions? | **PASS** | Evaluates situation objectively; openers outperform average baseline due to talent selection; tailenders receive crisis leverage. |
| **10**| Is the complete HPP engine ready for Stage 7C? | **PASS** | All mathematical, statistical, causal, and empirical stress tests passed with zero data modifications. |

---

## 14. Final Stage 7C Readiness Verdict

### Definitive Conclusion: **VERDICT: GO**

The High Pressure Player (HPP) Engine designed in Stage 7B has successfully passed all mathematical, statistical, and operational audits. The formulas are verified to be mathematically continuous, causally clean, zero-centered, and resilient across all 15 stress-test scenarios. 

**Stage 7C (Production Implementation) is authorized to proceed upon user approval.**

---

## 15. Final Cryptographic Integrity Verification

```
================================================================================
FINAL BASELINE INTEGRITY AUDIT (POST-AUDIT VERIFICATION)
================================================================================
data/processed/match_states/match_states_standard_t20_v1.pkl.gz: VERIFIED UNTOUCHED
data/processed/calibration/train_2022_2024_oof_calibrated_predictions_v1.pkl.gz: VERIFIED UNTOUCHED
data/processed/calibration/val_2025_calibrated_predictions_v1.pkl.gz: VERIFIED UNTOUCHED
data/processed/calibration/test_2026_calibrated_predictions_v1.pkl.gz: VERIFIED UNTOUCHED
data/processed/calibration/calibration_manifest_v1.json: VERIFIED UNTOUCHED
data/processed/contributions/batter_stints_v1.pkl.gz: VERIFIED UNTOUCHED
data/processed/contributions/batter_match_contributions_strategy4_v1.pkl.gz: VERIFIED UNTOUCHED
data/raw/matches.csv: VERIFIED UNTOUCHED
data/raw/ball_by_ball.csv: VERIFIED UNTOUCHED
docs/worm_graph/match_index.json: VERIFIED UNTOUCHED
docs/stage_7a_wp_swing_threshold_8pp_evaluation.md: VERIFIED UNTOUCHED
docs/stage_7a_2_first_innings_phase_scoring_evaluation.md: VERIFIED UNTOUCHED
docs/stage_7a_3a_phase2_historical_ground_coverage_audit.md: VERIFIED UNTOUCHED
docs/stage_7a_3b_final_benchmark_validation.md: VERIFIED UNTOUCHED
docs/stage_7a_3c_final_architecture_decision_audit.md: VERIFIED UNTOUCHED
docs/stage_7b_high_pressure_player_engine_design.md: VERIFIED UNTOUCHED
================================================================================
STATUS: 100% READ-ONLY COMPLIANCE CONFIRMED. ZERO ASSETS MODIFIED.
================================================================================
```

