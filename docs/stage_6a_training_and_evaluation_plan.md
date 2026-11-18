# CricImpact Phase 2 — Stage 6A Revision 1: Training & Evaluation Plan

**Document:** Stage 6A Training & Evaluation Plan (Revision 1.0)  
**Status:** Approved Plan (Planning & Design Only — Stage 6A)  
**Author:** AI Architecture & Data Science Agent  
**Date:** November 2026  
**Project Root:** [`C:\Users\admin\Documents\CricImpact_Phase2`](file:///c:/Users/admin/Documents/CricImpact_Phase2)  
**Companion Documents:**
- [`stage_6a_win_probability_specification.md`](file:///c:/Users/admin/Documents/CricImpact_Phase2/docs/stage_6a_win_probability_specification.md)
- [`stage_6a_feature_dictionary.md`](file:///c:/Users/admin/Documents/CricImpact_Phase2/docs/stage_6a_feature_dictionary.md)
- [`stage_6a_target_and_state_construction.md`](file:///c:/Users/admin/Documents/CricImpact_Phase2/docs/stage_6a_target_and_state_construction.md)
- [`stage_6a_data_readiness_report.md`](file:///c:/Users/admin/Documents/CricImpact_Phase2/docs/stage_6a_data_readiness_report.md)
- [`stage_6a_risk_and_leakage_register.md`](file:///c:/Users/admin/Documents/CricImpact_Phase2/docs/stage_6a_risk_and_leakage_register.md)
- [`stage_6a_implementation_plan.md`](file:///c:/Users/admin/Documents/CricImpact_Phase2/docs/stage_6a_implementation_plan.md)
- [`stage_6a_revision_1_report.md`](file:///c:/Users/admin/Documents/CricImpact_Phase2/docs/stage_6a_revision_1_report.md)

---

## 1. Chronological Match-Level Dataset Partitioning

To mirror real-world deployment where future matches are predicted using models trained exclusively on past seasons, the dataset is partitioned using strict **chronological, match-level boundaries**.

### 1.1 Partition Definitions & Empirical Verification

Across the 798 `STANDARD_T20` matches in `match_states_standard_t20_v1.pkl.gz`, the chronological distribution is strictly validated as follows:

| Partition | Calendar Years | Date Range (Min to Max) | Matches | Deliveries | Pct Matches | Pct Deliveries |
| :--- | :---: | :---: | ---: | ---: | ---: | ---: |
| **Training Set** | 2022 – 2024 | 2022-01-22 to 2024-12-30 | **477** | **114,677** | $59.77\%$ | $60.17\%$ |
| **Validation Set** | 2025 | 2025-01-02 to 2025-12-19 | **190** | **44,842** | $23.81\%$ | $23.53\%$ |
| **Test Set** | 2026 | 2026-01-07 to 2026-11-01 | **131** | **31,056** | $16.42\%$ | $16.30\%$ |
| **Total Standard Corpus** | 2022 – 2026 | 2022-01-22 to 2026-11-01 | **798** | **190,575** | $100.00\%$ | $100.00\%$ |

#### Non-Overlapping Verification
- $\max(\text{Train Date}) = \text{2024-12-30} < \min(\text{Val Date}) = \text{2025-01-02}$ (Gap: 3 days).
- $\max(\text{Val Date}) = \text{2025-12-19} < \min(\text{Test Date}) = \text{2026-01-07}$ (Gap: 19 days).
- Zero match overlap exists across partitions. Every delivery of any given match belongs exclusively to one partition.

### 1.2 Competition Category Representation Across Partitions

| Partition | IPL Matches | T20I Matches | OTHER_T20 Matches | Total Matches |
| :--- | ---: | ---: | ---: | ---: |
| **Training (2022–2024)** | 213 ($44.7\%$) | 249 ($52.2\%$) | 15 ($3.1\%$) | **477** |
| **Validation (2025)** | 68 ($35.8\%$) | 109 ($57.4\%$) | 13 ($6.8\%$) | **190** |
| **Test (2026)** | 70 ($53.4\%$) | 61 ($46.6\%$) | **0 ($0.0\%$)** | **131** |
| **Total** | **351** | **419** | **28** | **798** |

**Critical Empirical Finding on OTHER_T20:**  
OTHER_T20 matches exist solely in 2024 (15 matches) and 2025 (13 matches). There are **zero OTHER_T20 matches in 2026**. Consequently, the 2026 Test Set evaluates IPL and T20I generalization. OTHER_T20 is evaluated exclusively as an exploratory diagnostic slice in the 2025 Validation Set.

---

## 2. Rejection of Ordinary GroupKFold in Favor of Chronological Grouped Validation

Ordinary `GroupKFold` randomly shuffles matches across folds without regard to time. In cricket analytics, this introduces severe **temporal snooping**:
- Training on a 2024 match while validating on a 2022 match leaks future league-wide scoring trends, tactical shifts (e.g. the IPL Impact Player rule introduced in 2023), and future batter development into past predictions.
- **Mandatory Policy:** Ordinary random `GroupKFold` is **strictly rejected**.
- **Approved Validation Scheme:** When internal cross-validation is needed within the 2022–2024 training split, it must use **Expanding-Window Chronological Grouped Validation**:
  - Fold 1: Train on 2022 matches ($N=168$), Validate on 2023 matches ($N=127$).
  - Fold 2: Train on 2022–2023 matches ($N=295$), Validate on 2024 matches ($N=182$).
  - Final Model Fitting: Train on complete 2022–2024 corpus ($N=477$), Validate and Calibrate on 2025 ($N=190$), Benchmark on 2026 ($N=131$).

---

## 3. Delivery-Level vs Match-Level Weighting Framework

There are 190,575 primary delivery transitions across 798 matches. A standard 20-over chase that goes down to the wire contains up to 245 deliveries (with extras), whereas a one-sided blowout or quick chase may terminate in 80 deliveries. 

To prevent matches with more recorded deliveries from unintentionally dominating evaluation results, we establish an explicit dual-weighting framework:

### 3.1 Weighting Regimes

1. **Unweighted Delivery Loss ($w_{m, b} = 1.0$):**
   - Every delivery transition has equal loss weight.
   - **Role:** **Primary objective during model fitting.** Live operational systems serve predictions delivery-by-delivery to end users; minimizing expected loss across the distribution of live queries is the operational requirement.
2. **Equal-Match Weighting ($w_{m, b} = \frac{1}{N_m}$):**
   - Each match $m$ receives equal weight $1.0$, normalized by the number of deliveries $N_m$ in that match:
     $$\text{Loss}_{\text{match-weighted}} = \frac{1}{M} \sum_{m=1}^M \left( \frac{1}{N_m} \sum_{b=1}^{N_m} \mathcal{L}(\hat{p}_{m, b}, y_m) \right)$$
   - **Role:** **Primary gating criterion for model selection.** Ensures that model hyperparameter selection is not distorted by elongated matches with high ball counts.
3. **Match-Clustered Uncertainty Estimation:**
   - Confidence intervals and standard errors for all evaluation metrics (Brier Score, Log Loss, ROC-AUC) must be clustered by `match_id` using Huber-White sandwich estimators or 1,000-iteration **Match-Level Block Bootstrap** (resampling entire matches with replacement).

---

## 4. Model Candidates & Dependency Readiness

An audit of the Phase 2 virtual environment (`.venv`, Python 3.13.14) confirms:
- `scikit-learn` version **1.9.1** is installed and verified.
- `lightgbm` is **NOT installed**.
- In strict adherence to Stage 6A scope rules, **no new packages are installed during Stage 6A**.

### Candidate Evaluation

1. **Logistic Regression with Splines (`sklearn.linear_model.LogisticRegression`):**
   - Regularized logistic regression with cubic B-spline expansions (`SplineTransformer`) on non-linear continuous features (`balls_remaining`, `wickets_remaining`, `rrr_minus_crr`).
   - *Status:* Fully supported in existing `.venv`.
   - *Role:* Baseline benchmark and calibration reference.
   - *Latency:* Theoretical estimate: $< 5$ sec train, $< 0.1$ ms inference.
2. **Histogram Gradient Boosting (`sklearn.ensemble.HistGradientBoostingClassifier`):**
   - Scikit-learn's native implementation of histogram-based gradient boosting (sharing the identical algorithm and binning structure as LightGBM).
   - Natively supports early stopping, categorical features, missing-value handling, and monotonic constraints.
   - Zero compilation or external C++ runtime dependencies on Windows Python 3.13.
   - *Status:* Fully supported in existing `.venv`.
   - *Role:* **Primary Production Model Candidate for Stage 6B.**
   - *Latency:* Theoretical estimate: $< 25$ sec train, $< 0.3$ ms inference.
3. **Random Forest (`sklearn.ensemble.RandomForestClassifier`):**
   - Ensemble of 200 fully-grown trees with bootstrap subsampling.
   - *Status:* Fully supported in existing `.venv`.
   - *Role:* Secondary benchmark.
   - *Latency:* Theoretical estimate: $\sim 60$ sec train, $\sim 2.0$ ms inference.
4. **LightGBM Classifier (`lightgbm.LGBMClassifier`):**
   - Proposed alternative candidate; requires user approval to install wheel in Stage 6B.

*All latency figures are theoretical estimates and will be empirically measured during Stage 6B.*

---

## 5. Multi-Tier Evaluation Metrics Suite

Performance is evaluated across four distinct tiers:

### 5.1 Probabilistic Accuracy (Primary Gating Objectives)
1. **Brier Score (Mean Squared Probability Error):**
   $$\text{BS} = \frac{1}{N} \sum_{i=1}^N (\hat{p}_i - y_i)^2$$
   - Target benchmark: $\text{BS} \le 0.160$ on 2026 Test Set (vs naive prior $0.250$).
2. **Log Loss / Binary Cross-Entropy:**
   $$\text{LL} = -\frac{1}{N} \sum_{i=1}^N \left[ y_i \ln(\hat{p}_i) + (1 - y_i) \ln(1 - \hat{p}_i) \right]$$
   - Target benchmark: $\text{LL} \le 0.480$ on 2026 Test Set.

### 5.2 Probability Calibration
1. **Expected Calibration Error (ECE):**
   $$\text{ECE} = \sum_{m=1}^{10} \frac{|B_m|}{N} \left| \text{acc}(B_m) - \text{conf}(B_m) \right|$$
   - Target benchmark: $\text{ECE} \le 0.030$ ($3.0\%$).
2. **Maximum Calibration Error (MCE):**
   - Target benchmark: $\text{MCE} \le 0.060$ ($6.0\%$).
3. **Binned Reliability Diagram:** Visual 10-bin calibration curve with $y = x$ reference.

### 5.3 Discrimination & Utility
1. **ROC-AUC:** Target benchmark: $\text{ROC-AUC} \ge 0.850$.
2. **Accuracy at $\tau = 0.50$:** Target benchmark: $\ge 76.0\%$ overall; $\ge 88.0\%$ in Death Overs.

---

## 6. Segment-Wise Evaluation Slices

The test set is segmented along six analytical axes to ensure robust performance across all phases:

| Segmentation Axis | Slices Evaluated | Critical Quality Standard |
| :--- | :--- | :--- |
| **1. Lifecycle Stage** | Stage A Pre-Match, Stage B Pre-Match, Innings 1 Live, Innings 2 Chase. | Monotonically improving Brier Score across stages. |
| **2. Competition Category** | IPL ($N=70$ in 2026), T20I ($N=61$ in 2026), OTHER_T20 (2025 Val only). | Consistent calibration across both tournament styles. |
| **3. Innings Phase** | Powerplay (overs 1–6), Middle (overs 7–15), Death (overs 16–20). | Powerplay $\text{BS} \le 0.200$; Death $\text{BS} \le 0.100$. |
| **4. Wickets in Hand** | High ($8–10$), Medium ($4–7$), Low ($0–3$). | Stable response to sudden multi-wicket collapses. |
| **5. Required Run Rate** | Comfortable ($< 7.0$), Standard ($7.0–10.0$), Pressure ($10.0–14.0$), Extreme ($> 14.0$). | Monotonic sensitivity to required scoring deficit. |
| **6. Prediction Grain** | Pre-Match, End-of-Over Checkpoints ($N=30,129$), Ball-by-Ball ($N=190,575$). | Consistency across reporting granularities. |

---

## 7. Probability Calibration Protocol

Raw tree outputs can suffer from calibration distortion in the wings ($p < 0.05$ and $p > 0.95$). Post-hoc calibration is mandatory:

### 7.1 Evaluated Methods
- **Platt Scaling (Sigmoid Logistic):** 2-parameter logistic mapping $P_{\text{cal}} = \sigma(A \cdot f(x) + B)$. Preserves monotonicity strictly.
- **Isotonic Regression:** Non-parametric piecewise constant isotonic mapping.

### 7.2 Strict Calibration Isolation Rules
- **Rule 1 (Validation Isolation):** Calibrators are fit **exclusively on the 2025 Validation Set**.
- **Rule 2 (Test Set Blindness):** The 2026 Test Set is strictly blind during calibrator selection and fitting.
- **Rule 3 (Complementarity Preservation):** The calibrator is fit on $y_{\text{bat}}$. Calibrated bowling probability is defined as $1.0 - P_{\text{cal}}(y_{\text{bat}})$, guaranteeing $\sum P = 1.0000$.
- **Rule 4 (Lifecycle-Specific Calibration):** Calibration curves are evaluated separately for:
  1. Stage A pre-match predictions.
  2. Stage B pre-match predictions.
  3. First-innings live delivery states.
  4. Second-innings chase delivery states.
