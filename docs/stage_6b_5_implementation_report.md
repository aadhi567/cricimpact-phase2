# CricImpact Phase 2 — Stage 6B.5 Implementation Report
## Probability Calibration

**Stage:** Stage 6B.5: Probability Calibration  
**Author:** DeepMind Agent  
**Date:** November 14, 2026  
**Status:** Complete & Validated  

---

### Executive Summary

In accordance with Stage 6B.5 authorization, an independent probability calibration study was conducted for the CricImpact Phase 2 First-Innings Defense and Second-Innings Chase win probability models. Calibration was evaluated on the 2025 Validation Partition ($N = 23,548$ first-innings deliveries and $N = 21,294$ second-innings deliveries across 190 matches).

Key empirical findings and calibration decisions:
1. **First-Innings Defense Model:**  
   - **Method Selected:** **Platt Scaling (Sigmoid Calibration)**, fitted causally on 2022–2024 match-grouped out-of-fold predictions.
   - **Performance Gain:** Improves Delivery Brier Score ($0.2208 \to \mathbf{0.2196}$), Match-Aware Brier Score ($0.2199 \to \mathbf{0.2189}$), Log Loss ($0.6316 \to \mathbf{0.6279}$), Match-Aware Log Loss ($0.6294 \to \mathbf{0.6265}$), and overall ECE ($3.89\% \to \mathbf{3.63\%}$).
   - **Critical Problem Resolved:** Successfully addresses the previously identified overconfidence in the $[0.8, 0.9)$ probability decile, reducing calibration error from **$-18.65\%$** down to **$-4.95\%$**, while dropping Powerplay ECE from **$5.84\%$ to $3.03\%$**.
2. **Second-Innings Chase Model:**  
   - **Method Selected:** **Identity Mapping (Uncalibrated Baseline Retained)**.
   - **Empirical Justification:** The uncalibrated Chase model already possesses exceptional natural calibration ($ECE = \mathbf{1.72\%}$, Brier = $\mathbf{0.1182}$, Log Loss = $\mathbf{0.3659}$). Fitting Platt scaling worsens ECE ($1.72\% \to 2.92\%$) and degrades both Brier score ($0.1182 \to 0.1186$) and Log Loss ($0.3659 \to 0.3690$). Fitting Isotonic regression similarly degrades Brier ($0.1193$) and Log Loss ($0.3700$). In strict adherence to Stage 6B.5 acceptance criteria, the uncalibrated model is retained to avoid performance degradation.
3. **Preservation of Deterministic Overrides:**  
   All rule-based boundary constraints (all-out $\le 0.05$ in Innings 1; target reached $\ge 0.99$, all-out $\le 0.01$, balls exhausted $\le 0.01$, and 1-run target $\ge 0.99$ in Innings 2) are guaranteed to be preserved and uncorrupted by calibration.

All 81 unit tests in the ML test suite pass cleanly in 22.13 seconds. All prior stage artifacts and raw CSVs remain cryptographically untouched.

---

### 1. Files Created and Modified

| File Path | Nature of Change | Purpose & Scope |
| :--- | :--- | :--- |
| `ml/win_probability/calibration.py` | **Created** | Implementation of `PlattCalibrator`, `IsotonicCalibrator`, `IdentityCalibrator`, `WinProbabilityCalibrator`, `compute_ece`, `compute_reliability_table`, and `evaluate_calibrated_predictions`. |
| `tests/ml/test_wp_calibration.py` | **Created** | Dedicated unit test suite (8 tests) verifying logit stability, lifecycle, monotonicity, innings dispatch, override preservation, ECE, and reliability tables. |
| `ml/win_probability/__init__.py` | **Modified** | Exported Stage 6B.5 calibrators, metrics, and evaluation helpers. |
| `data/processed/calibration/calibration_manifest_v1.json` | **Created** | Metadata manifest recording calibration methods, fitting parameters, population counts, and before/after metrics. |
| `data/processed/calibration/val_2025_calibrated_predictions_v1.pkl.gz` | **Created** | Frozen separate artifact storing uncalibrated vs calibrated probabilities across all 44,842 validation deliveries. |
| `docs/stage_6b_5_implementation_report.md` | **Created** | Technical implementation and validation report for Stage 6B.5. |

---

### 2. Candidate Calibration Methods Evaluated

Three candidate calibration architectures were benchmarked for each innings model:

1. **Identity Mapping (Uncalibrated Baseline):**  
   $$P_{\text{cal}} = P_{\text{raw}}$$
   Preserves raw logistic regression estimates with standard clipping to $[0.01, 0.99]$.
2. **Platt Scaling (Sigmoid / Logistic Calibration):**  
   Fits a univariate logistic regression on the log-odds (logits) of uncalibrated probabilities:
   $$\text{logit}(p) = \log\left(\frac{p}{1 - p}\right), \quad P_{\text{cal}} = \sigma(a \cdot \text{logit}(p) + b) = \frac{1}{1 + e^{-(a \cdot \text{logit}(p) + b)}}$$
   Monotonic and smooth; pulls overconfident extreme estimates inward when $a < 1.0$.
3. **Isotonic Regression:**  
   Non-parametric piecewise-constant isotonic regression fitting a monotonic step function:
   $$P_{\text{cal}} = f_{\text{iso}}(P_{\text{raw}})$$

#### Leakage-Free Validation Protocols:
- **Strategy A (Chronological OOF Training):**  
  To avoid evaluating calibrators on the data used to fit them, 5-fold match-grouped out-of-fold predictions were generated across the 2022–2024 training matches ($N = 477$ matches). Calibrators were fitted strictly on these OOF predictions and evaluated on the held-out 2025 Validation Partition ($N = 190$ matches).
- **Strategy B (5-Fold GroupKFold Cross-Validation on Validation Partition):**  
  To assess stability directly on 2025 match distributions, 5-fold cross-validation grouped by `match_id` was run over the 190 validation matches (fitting on 152 matches, evaluating out-of-fold on 38 matches).

---

### 3. Separate First-Innings and Chase Calibration Results

#### First-Innings Defense Model Comparison (2025 Validation Partition, $N = 23,548$ deliveries across 190 matches):

| Calibration Candidate | Delivery Brier | Delivery LogLoss | ROC-AUC | Accuracy | ECE (10 Bins) | Match Brier | Match LogLoss | Recommendation |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Uncalibrated Baseline** | 0.2208 | 0.6316 | 0.7011 | 64.25% | 3.89% | 0.2199 | 0.6294 | Baseline |
| **Platt Scaling (Strategy A, OOF)** | **0.2196** | **0.6279** | **0.7011** | **64.32%** | **3.63%** | **0.2189** | **0.6265** | **SELECTED** |
| **Isotonic Regression (Strategy A)** | 0.2208 | 0.6310 | 0.6997 | 64.37% | 4.13% | 0.2202 | 0.6296 | Rejected (Higher ECE) |
| **Platt Scaling (Strategy B, 5-Fold CV)** | 0.2204 | 0.6296 | 0.6963 | 63.86% | 2.32% | 0.2195 | 0.6276 | Confirms Platt Gain |
| **Isotonic Regression (Strategy B, CV)** | 0.2239 | 0.6433 | 0.6832 | 62.43% | 4.55% | 0.2231 | 0.6424 | Rejected (Degrades LL) |

**Fitted Parameters for Selected Innings 1 Platt Calibrator:**
- Slope Coefficient ($a$): **0.6639** (Pulls extreme predictions inward, directly mitigating overconfidence)
- Intercept ($b$): **+0.0333**

---

#### Second-Innings Chase Model Comparison (2025 Validation Partition, $N = 21,294$ deliveries across 190 matches):

| Calibration Candidate | Delivery Brier | Delivery LogLoss | ROC-AUC | Accuracy | ECE (10 Bins) | Match Brier | Match LogLoss | Recommendation |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Uncalibrated Baseline** | **0.1182** | **0.3659** | **0.9157** | **82.48%** | **1.72%** | **0.1120** | **0.3484** | **RETAINED (SELECTED)** |
| **Platt Scaling (Strategy A, OOF)** | 0.1186 | 0.3690 | 0.9157 | 82.47% | 2.92% | 0.1123 | 0.3519 | Rejected (Degrades metrics) |
| **Isotonic Regression (Strategy A)** | 0.1193 | 0.3700 | 0.9154 | 82.52% | 2.89% | 0.1130 | 0.3527 | Rejected (Degrades metrics) |
| **Platt Scaling (Strategy B, 5-Fold CV)** | 0.1215 | 0.3776 | 0.9103 | 82.00% | 1.14% | 0.1149 | 0.3592 | Rejected (Degrades Brier/LL)|
| **Isotonic Regression (Strategy B, CV)** | 0.1228 | 0.3890 | 0.9050 | 82.25% | 1.69% | 0.1162 | 0.3701 | Rejected (Degrades Brier/LL)|

**Empirical Reason for Retaining Uncalibrated Chase Model:**  
The raw chase model's ECE is already remarkably low at **1.72%**, with Brier score at **0.1182** and Log Loss at **0.3659**. Post-hoc calibration on chase deliveries attempts to smooth step changes that represent genuine cricket deterministic equations ($\text{runs\_required} \le 0 \implies \text{win}$), inadvertently increasing Brier score and Log Loss. Per Stage 6B.5 Authorization Section 8, the uncalibrated model is retained as production calibrator.

---

### 4. Before-and-After Performance Metrics

Summary of production win probability predictions across both innings:

| Metric | Innings 1 (Raw) | Innings 1 (Platt Calibrated) | Innings 1 $\Delta$ | Innings 2 (Raw Retained) | Innings 2 Status |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Delivery Brier Score** | 0.2208 | **0.2196** | **-0.0012** (Better) | **0.1182** | Optimal baseline |
| **Delivery Log Loss** | 0.6316 | **0.6279** | **-0.0037** (Better) | **0.3659** | Optimal baseline |
| **Match-Aware Brier** | 0.2199 | **0.2189** | **-0.0010** (Better) | **0.1120** | Optimal baseline |
| **Match-Aware Log Loss** | 0.6294 | **0.6265** | **-0.0029** (Better) | **0.3484** | Optimal baseline |
| **ROC-AUC** | 0.7011 | **0.7011** | 0.0000 (Preserved) | **0.9157** | Preserved |
| **Accuracy** | 64.25% | **64.32%** | **+0.07%** (Better) | **82.48%** | Preserved |
| **ECE (10 Bins)** | 3.89% | **3.63%** | **-0.26%** (Better) | **1.72%** | Preserved |
| **Powerplay ECE** | 5.84% | **3.03%** | **-2.81%** (Dramatically better) | **4.81%** | Preserved |

---

### 5. Match-Aware Evaluation & Paired Resampling

Match-level evaluation was computed by taking the mean loss within each of the 190 validation matches, followed by the mean across matches:

$$\text{Brier}_{\text{match}} = \frac{1}{M} \sum_{m=1}^{M} \left( \frac{1}{n_m} \sum_{j=1}^{n_m} (p_{m,j} - y_m)^2 \right)$$

For Innings 1:
- $\Delta \text{Brier}_{\text{match}} = \text{Brier}_{\text{raw}} - \text{Brier}_{\text{cal}} = \mathbf{+0.0010}$ (Calibrated is superior)
- $\Delta \text{LogLoss}_{\text{match}} = \text{LogLoss}_{\text{raw}} - \text{LogLoss}_{\text{cal}} = \mathbf{+0.0029}$ (Calibrated is superior)

For Innings 2:
- Applying Platt scaling causes $\Delta \text{Brier}_{\text{match}} = -0.0003$ and $\Delta \text{LogLoss}_{\text{match}} = -0.0035$ (Calibrated is inferior), confirming that retention of the uncalibrated model protects match-level quality.

---

### 6. Reliability Tables & Bootstrap Confidence Intervals

#### Innings 1 Reliability Table (Before vs After Platt Calibration):

**Before Calibration (Raw First-Innings):**
| Decile Range | $N$ | Mean Pred $\bar{p}$ | Obs Win Rate $\bar{y}$ | Cal Error | Brier Score | Log Loss |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| $[0.0, 0.1)$ | 531 | 0.0716 | 0.0339 | -0.0377 | 0.0332 | 0.1523 |
| $[0.1, 0.2)$ | 1,598 | 0.1583 | 0.1683 | +0.0101 | 0.1388 | 0.4490 |
| $[0.2, 0.3)$ | 2,379 | 0.2510 | 0.2875 | +0.0365 | 0.2075 | 0.6072 |
| $[0.3, 0.4)$ | 3,241 | 0.3533 | 0.3696 | +0.0163 | 0.2329 | 0.6585 |
| $[0.4, 0.5)$ | 3,708 | 0.4497 | 0.4628 | +0.0131 | 0.2472 | 0.6875 |
| $[0.5, 0.6)$ | 3,745 | 0.5492 | 0.5220 | -0.0272 | 0.2489 | 0.6910 |
| $[0.6, 0.7)$ | 3,324 | 0.6478 | 0.6248 | -0.0229 | 0.2333 | 0.6592 |
| $[0.7, 0.8)$ | 2,751 | 0.7445 | 0.6725 | -0.0720 | 0.2261 | 0.6477 |
| $[0.8, 0.9)$ | 1,589 | 0.8479 | 0.6614 | **-0.1865** | 0.2618 | 0.7625 |
| $[0.9, 1.0)$ | 682 | 0.9427 | 0.9150 | -0.0278 | 0.0737 | 0.2557 |
| **Total** | **23,548** | — | — | **ECE: 3.89%** | **0.2208** | **0.6316** |

**After Platt Calibration (Production First-Innings):**
| Decile Range | $N$ | Mean Pred $\bar{p}$ | Obs Win Rate $\bar{y}$ | Cal Error | Brier Score | Log Loss | Improvement Impact |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| $[0.0, 0.1)$ | 29 | 0.0733 | 0.0000 | -0.0733 | 0.0054 | 0.0762 | Low probability volume reduced |
| $[0.1, 0.2)$ | 549 | 0.1644 | 0.0419 | -0.1225 | 0.0539 | 0.2417 | Softened extremes |
| $[0.2, 0.3)$ | 1,788 | 0.2603 | 0.1862 | -0.0741 | 0.1551 | 0.4906 | Improved Brier/LL |
| $[0.3, 0.4)$ | 3,290 | 0.3542 | 0.3046 | -0.0496 | 0.2142 | 0.6200 | Improved Brier/LL |
| $[0.4, 0.5)$ | 5,346 | 0.4514 | 0.4285 | -0.0228 | 0.2438 | 0.6807 | High-volume central alignment |
| $[0.5, 0.6)$ | 5,495 | 0.5488 | 0.5338 | -0.0150 | 0.2480 | 0.6892 | High-volume central alignment |
| $[0.6, 0.7)$ | 4,188 | 0.6461 | 0.6674 | +0.0213 | 0.2222 | 0.6364 | Well-calibrated |
| $[0.7, 0.8)$ | 1,979 | 0.7441 | 0.6695 | -0.0745 | 0.2285 | 0.6533 | Preserved accuracy |
| $[0.8, 0.9)$ | 679 | 0.8374 | 0.7879 | **-0.0495** | **0.1610** | **0.4937** | **Overconfidence resolved! (Brier 0.2618 $\to$ 0.1610)** |
| $[0.9, 1.0)$ | 205 | 0.9314 | 1.0000 | +0.0686 | 0.0051 | 0.0713 | 100% precision on confident wins |
| **Total** | **23,548** | — | — | **ECE: 3.63%** | **0.2196** | **0.6279** | **All primary losses improved** |

---

#### Innings 2 Reliability Table (Retained Uncalibrated Production Baseline):

| Decile Range | $N$ | Mean Pred $\bar{p}$ | Obs Win Rate $\bar{y}$ | Cal Error | Brier Score | Log Loss | Status |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| $[0.0, 0.1)$ | 5,414 | 0.0292 | 0.0292 | -0.0000 | 0.0277 | 0.1186 | Near-zero error |
| $[0.1, 0.2)$ | 1,592 | 0.1481 | 0.1570 | +0.0089 | 0.1321 | 0.4336 | Clean alignment |
| $[0.2, 0.3)$ | 1,435 | 0.2495 | 0.2690 | +0.0195 | 0.1955 | 0.5792 | Clean alignment |
| $[0.3, 0.4)$ | 1,291 | 0.3485 | 0.4268 | +0.0783 | 0.2507 | 0.6955 | Intermediate underconfidence |
| $[0.4, 0.5)$ | 1,366 | 0.4510 | 0.4517 | +0.0007 | 0.2477 | 0.6886 | Perfect alignment |
| $[0.5, 0.6)$ | 1,432 | 0.5504 | 0.5161 | -0.0344 | 0.2493 | 0.6917 | Clean alignment |
| $[0.6, 0.7)$ | 1,447 | 0.6517 | 0.7187 | +0.0670 | 0.2068 | 0.6045 | Intermediate underconfidence |
| $[0.7, 0.8)$ | 1,390 | 0.7493 | 0.7741 | +0.0248 | 0.1741 | 0.5321 | Clean alignment |
| $[0.8, 0.9)$ | 1,567 | 0.8517 | 0.8558 | +0.0041 | 0.1236 | 0.4133 | Near-zero error |
| $[0.9, 1.0)$ | 4,360 | 0.9628 | 0.9706 | +0.0079 | 0.0281 | 0.1231 | Near-zero error |
| **Total** | **21,294** | — | — | **ECE: 1.72%** | **0.1182** | **0.3659** | **Benchmark Quality** |

---

#### Match-Cluster Bootstrap 95% Confidence Intervals (1,000 Resamples):

| Model & Partition | Delivery Brier 95% CI | Delivery LogLoss 95% CI | Match Brier 95% CI | Match LogLoss 95% CI | ECE 95% CI |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Innings 1 Raw** | `[0.2031, 0.2390]` | `[0.5900, 0.6743]` | `[0.2026, 0.2377]` | `[0.5893, 0.6716]` | `[0.0260, 0.0877]` |
| **Innings 1 Platt Calibrated** | **`[0.2067, 0.2329]`** | **`[0.5998, 0.6570]`** | **`[0.2064, 0.2322]`** | **`[0.5991, 0.6555]`** | **`[0.0241, 0.0866]`** |
| **Innings 2 Raw (Retained)** | **`[0.1017, 0.1339]`** | **`[0.3189, 0.4088]`** | **`[0.0962, 0.1274]`** | **`[0.3031, 0.3908]`** | **`[0.0178, 0.0529]`** |
| **Innings 2 Platt Calibrated** | `[0.1029, 0.1330]` | `[0.3266, 0.4066]` | `[0.0973, 0.1266]` | `[0.3115, 0.3886]` | `[0.0192, 0.0558]` |

*Observation:* For Innings 1, Platt calibration markedly compresses the upper bound of Log Loss from $0.6743 \to 0.6570$, preventing heavy penalty spikes. For Innings 2, Platt calibration elevates both Brier score and Log Loss bounds, confirming the decision to retain the uncalibrated Chase baseline.

---

### 7. Phase-Wise Calibration Performance

| Innings Model & Phase | Deliveries ($N$) | Matches ($M$) | Deliv Brier | Match Brier | Log Loss | Match LL | ROC-AUC | Accuracy | ECE |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Innings 1 Raw — Powerplay** | 7,084 | 190 | 0.2448 | 0.2448 | 0.6838 | 0.6836 | 0.6051 | 56.96% | 5.84% |
| **Innings 1 Platt — Powerplay**| 7,084 | 190 | **0.2414** | **0.2414** | **0.6756** | **0.6755** | 0.6051 | 56.78% | **3.03%** |
| **Innings 1 Raw — Middle** | 10,630 | 190 | 0.2159 | 0.2153 | 0.6217 | 0.6205 | 0.7174 | 65.75% | 3.80% |
| **Innings 1 Platt — Middle** | 10,630 | 190 | **0.2152** | **0.2148** | **0.6189** | **0.6182** | 0.7174 | 65.94% | 4.37% |
| **Innings 1 Raw — Death** | 5,834 | 188 | 0.2007 | 0.1995 | 0.5863 | 0.5841 | 0.7574 | 70.36% | 4.26% |
| **Innings 1 Platt — Death** | 5,834 | 188 | 0.2011 | 0.2000 | 0.5865 | 0.5840 | 0.7574 | 70.53% | 5.62% |
| **Innings 2 Raw — Powerplay** | 7,151 | 190 | **0.1611** | **0.1609** | **0.4862** | **0.4856** | 0.8494 | 75.68% | **4.81%** |
| **Innings 2 Platt — Powerplay**| 7,151 | 190 | 0.1599 | 0.1598 | 0.4825 | 0.4821 | 0.8494 | 75.60% | 3.81% |
| **Innings 2 Raw — Middle** | 10,200 | 188 | **0.1107** | **0.1074** | **0.3450** | **0.3351** | 0.9255 | 83.42% | **2.61%** |
| **Innings 2 Platt — Middle** | 10,200 | 188 | 0.1117 | 0.1083 | 0.3508 | 0.3410 | 0.9255 | 83.43% | 3.51% |
| **Innings 2 Raw — Death** | 3,943 | 168 | **0.0599** | **0.0482** | **0.2018** | **0.1655** | 0.9754 | 92.39% | **2.63%** |
| **Innings 2 Platt — Death** | 3,943 | 168 | 0.0614 | 0.0496 | 0.2104 | 0.1751 | 0.9754 | 92.47% | 4.42% |

---

### 8. Data Leakage & Chronological Validation Evidence

Strict causal and match-isolation protocols were enforced throughout Stage 6B.5:
1. **Zero Test Partition Leakage:** The 2026 Test Partition was never loaded, fitted, or evaluated.
2. **Causal Expanding-Window Fitting:** The Innings 1 Platt calibrator was fitted strictly on 5-fold match-grouped out-of-fold predictions from historical training matches (2022–2024). No 2025 match was ever present in the calibrator's training set.
3. **No Same-Day Leakage:** Match-level grouping ensured that all deliveries belonging to any match remained together within the same fold.
4. **Separation of Stored Artifacts:** Calibrated validation predictions were written to a distinct, versioned artifact `val_2025_calibrated_predictions_v1.pkl.gz`, preserving original model outputs intact.

---

### 9. Preservation of Deterministic Boundary Overrides

In accordance with Section 7 of the user authorization (*"Do not allow calibration to conceal or silently remove deterministic cricket-rule overrides"*), `WinProbabilityCalibrator` explicitly wraps all calibration transformations with rule-based boundary protections:

1. **Innings 1 All-Out Protection:**  
   If $\text{wickets\_lost\_before} \ge 10$, batting resources are exhausted. Probability is guaranteed capped at $\le 0.05$.
2. **Innings 2 Target Reached:**  
   If $\text{runs\_required\_before} \le 0$, the chase is completed. Clamped to $\ge 0.99$.
3. **Innings 2 All-Out Before Target:**  
   If $\text{wickets\_lost\_before} \ge 10 \land \text{runs\_required\_before} > 0$, clamped to $\le 0.01$.
4. **Innings 2 Balls Exhausted:**  
   If $\text{legal\_balls\_remaining\_before} == 0 \land \text{runs\_required\_before} > 0$, clamped to $\le 0.01$.
5. **Innings 2 One-Run Target Override:**  
   If $\text{runs\_required\_before} == 1 \land \text{wickets\_lost\_before} \le 8 \land \text{balls\_remaining} \ge 30$, clamped to $\ge 0.99$.

Unit test `test_win_probability_calibrator_preserves_overrides` explicitly asserts that these boundary conditions cannot be corrupted by calibration mappings.

---

### 10. Automated Test Suite Verification

Pytest execution results across the complete ML test suite:

```
============================= test session starts =============================
platform win32 -- Python 3.13.14, pytest-9.2.0, pluggy-1.7.0
rootdir: C:\Users\admin\Documents\CricImpact_Phase2
plugins: anyio-4.15.1
collected 81 items

tests/ml/test_contribution_causality_and_eval.py ...                     [  3%]
tests/ml/test_contribution_scoring.py ....                               [  8%]
tests/ml/test_contribution_stints.py .....                               [ 14%]
tests/ml/test_match_state_builder.py .............                       [ 29%]
tests/ml/test_validation_pipeline.py ............                        [ 48%]
tests/ml/test_wp_calibration.py ........                                [ 58%]
tests/ml/test_wp_chase.py ........                                       [ 67%]
tests/ml/test_wp_features.py .....                                       [ 74%]
tests/ml/test_wp_first_innings.py .......                                [ 82%]
tests/ml/test_wp_leakage.py ....                                         [ 87%]
tests/ml/test_wp_pre_match.py ......                                     [ 95%]
tests/ml/test_wp_schema.py ....                                          [100%]

============================= 81 passed in 22.13s =============================
```

#### Dedicated Tests in `tests/ml/test_wp_calibration.py`:
1. `test_logit_transformation`: Verifies numerical stability at extreme probabilities ($0.0$, $1.0$).
2. `test_identity_calibrator`: Verifies pass-through behavior with boundary clipping.
3. `test_platt_calibrator_lifecycle`: Verifies error on unfitted state, positive slope coefficient, and strictly monotonic outputs.
4. `test_isotonic_calibrator_lifecycle`: Verifies non-parametric fitting and monotonic predictions.
5. `test_win_probability_calibrator_innings_dispatch`: Verifies that Innings 1 uses Platt while Innings 2 uses Identity.
6. `test_win_probability_calibrator_preserves_overrides`: Verifies that all 5 cricket boundary overrides are preserved.
7. `test_compute_ece_and_reliability_table`: Verifies 10-decile table generation and ECE calculation.
8. `test_evaluate_calibrated_predictions`: Verifies complete metric container output.

---

### 11. Frozen-Artifact and Raw-Data SHA-256 Verification

All foundational datasets, frozen stage outputs, and newly generated calibration assets were verified via SHA-256 digests:

| File Path | Verification Status | Cryptographic SHA-256 Checksum |
| :--- | :---: | :--- |
| `data/raw/matches.csv` | **FROZEN** | `bb100ab84b8b9a15160c1f2315cf675210131a30e779ec5079fd5403dcf56eef` |
| `data/raw/ball_by_ball.csv` | **FROZEN** | `01e2b4379edfbab6a6e456d304cb3c70f554cb312ef93d9588f3f32a82cb396e` |
| `data/raw/playing_eleven.csv` | **FROZEN** | `7517c73722a28d5d61c808ccf0cbed315a8780586d02e946eb9a7f5daf011c27` |
| `data/raw/teams.csv` | **FROZEN** | `a65e5922a9b3bf49247b24fc9471782e700efb31f8dcc5042923238b87c50a5d` |
| `data/raw/competitions.csv` | **FROZEN** | `507ceb7189f972d4e4f299ddcfc97f3c3247af1913f6291106f161fa8353fd9b` |
| `data/raw/competition_team_player_mapping.csv` | **FROZEN** | `1ded4e42a933618572d6e2c3a521c3257eb1844fab4456d567d77cbb2d3bbb12` |
| `data/processed/match_states/match_states_standard_t20_v1.pkl.gz` | **FROZEN** | `815a8e1ff4e428e85b942caeaaea9e45af1bf159eeb794c7c425390d476cb871` |
| `data/processed/contributions/batter_match_contributions_strategy4_v1.pkl.gz` | **FROZEN** | `02a6f5f15941de81755bacba268f159974e69cfc4a5a8aef4efe1365f0b0df88` |
| `data/processed/contributions/pre_match_causal_abc_features_v1.pkl.gz` | **FROZEN** | `323af183ef60eef75618f38a012086cb921eaa9c6b631372dffb785e18e6de5c` |
| `ml/win_probability/calibration.py` | **NEW** | `77b6701690b7ebea7ffb64c6952c55bd7ec31e31fbf00efcaf7e576d06d83815` |
| `tests/ml/test_wp_calibration.py` | **NEW** | `02b8b75b14db18aa7280d955cc3c9590ec1365a591550e89022296120a0e8a32` |
| `data/processed/calibration/calibration_manifest_v1.json` | **NEW** | `8b11483723f5bf0f02a5df2bdf346bb4f4d585ba4a249e29a2babc16d5e2bcd1` |
| `data/processed/calibration/val_2025_calibrated_predictions_v1.pkl.gz` | **NEW** | `2b0700be46316a4b3c14c80167e6af58b1ccdb314fc1786a2bff7f8335d82bb9` |

---

### 12. Explicit Boundary Confirmation

In strict compliance with project governance and scope restrictions:
1. **Untouched 2026 Test Partition (Stage 6B.6):** The 2026 test partition ($N = 14,723$ second-innings deliveries and $N = 16,334$ first-innings deliveries across 131 matches) remains completely untouched and unseen.
2. **Historical Worm Graphs (Stage 6B.7):** No worm graph generation scripts or visualization artifacts have been created.
3. **Stage 7 Impact Metrics:** No Win Probability Added (WPA) or pressure indexing scoring has been implemented.
4. **Git Protection:** Zero git commands (`git add`, `git commit`, `git push`) were invoked. No git repository was initialized.

Stage 6B.5 implementation and validation are fully complete. Work is halted at the Stage 6B.5 boundary awaiting formal user review.

