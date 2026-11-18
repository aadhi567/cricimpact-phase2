# CricImpact Phase 2 — Stage 6A Revision 1: Stage 6B Implementation Plan

**Document:** Stage 6B Implementation Roadmap & Engineering Plan (Revision 1.0)  
**Status:** Approved Implementation Plan (Planning & Design Only — Stage 6A)  
**Author:** AI Architecture & Data Science Agent  
**Date:** November 2026  
**Project Root:** [`C:\Users\admin\Documents\CricImpact_Phase2`](file:///c:/Users/admin/Documents/CricImpact_Phase2)  
**Companion Documents:**
- [`stage_6a_win_probability_specification.md`](file:///c:/Users/admin/Documents/CricImpact_Phase2/docs/stage_6a_win_probability_specification.md)
- [`stage_6a_feature_dictionary.md`](file:///c:/Users/admin/Documents/CricImpact_Phase2/docs/stage_6a_feature_dictionary.md)
- [`stage_6a_target_and_state_construction.md`](file:///c:/Users/admin/Documents/CricImpact_Phase2/docs/stage_6a_target_and_state_construction.md)
- [`stage_6a_training_and_evaluation_plan.md`](file:///c:/Users/admin/Documents/CricImpact_Phase2/docs/stage_6a_training_and_evaluation_plan.md)
- [`stage_6a_data_readiness_report.md`](file:///c:/Users/admin/Documents/CricImpact_Phase2/docs/stage_6a_data_readiness_report.md)
- [`stage_6a_risk_and_leakage_register.md`](file:///c:/Users/admin/Documents/CricImpact_Phase2/docs/stage_6a_risk_and_leakage_register.md)
- [`stage_6a_revision_1_report.md`](file:///c:/Users/admin/Documents/CricImpact_Phase2/docs/stage_6a_revision_1_report.md)

---

## 1. Objective & Execution Boundaries

This document defines the actionable implementation plan for **Stage 6B: Win Probability Model Implementation & Evaluation**. 

### Strict Stage 6A / 6B Boundary
- **Stage 6A (Current State):** Specification, authoritative feature dictionary, target formulation, chronological training plan, data-readiness audit, risk register, and implementation roadmap. **ZERO CODE WRITTEN IN `ml/win_probability/`. ZERO MODEL TRAINING.**
- **Stage 6B (Upcoming Stage):** Writing production Python code under `ml/win_probability/`, training models, calibrating on 2025 Validation, generating evaluation reports, and authoring unit tests under `tests/ml/`. **REQUIRES EXPLICIT USER APPROVAL BEFORE COMMENCING.**

---

## 2. Proposed Source Modules & Test Suites for Stage 6B

Stage 6B will introduce a modular, production-grade package under `ml/win_probability/` and accompanying test suites under `tests/ml/`:

```
ml/
└── win_probability/
    ├── __init__.py                  # Public API exports and pipeline entry points
    ├── schema.py                    # Dataclasses & validation contracts for states, features, and outputs
    ├── team_strength.py             # Causal lineup aggregator for Stage 5C Track B ABC features
    ├── venue_priors.py              # Historical ground par scores with empirical Bayesian shrinkage
    ├── feature_extractor.py         # 42-feature delivery-grain & pre-match extraction engine
    ├── pre_match_model.py           # Stage A and Stage B pre-match probability models
    ├── innings1_model.py            # First-Innings Defense Model (HistGradientBoosting)
    ├── chase_model.py               # Second-Innings Chase Model (HistGradientBoosting)
    ├── calibrator.py                # Platt Scaling / Isotonic probability calibrator
    ├── worm_graph.py                # Historical Worm Graph trajectory generator & annotator
    ├── evaluator.py                 # Multi-tier evaluation engine (Brier, LogLoss, ECE, Slices)
    └── pipeline.py                  # CLI & orchestration script (train, calibrate, evaluate)

tests/
└── ml/
    ├── test_wp_schema.py            # Schema boundary and complementarity tests
    ├── test_wp_leakage.py           # Temporal causality and target-invariance tests
    ├── test_wp_features.py          # Feature extraction and imputation tests
    ├── test_wp_pre_match.py         # Stage A and Stage B pre-match model tests
    ├── test_wp_live_models.py       # Innings 1 and Chase model logic tests
    ├── test_wp_calibrator.py        # Calibration and complementarity tests
    └── test_wp_worm_graph.py        # Worm graph trajectory reconstruction tests
```

---

## 3. Sequential Stage 6B Sub-Stages and Approval Gates

Stage 6B execution is decomposed into eight strictly sequenced sub-stages, each protected by an explicit verification gate:

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                              Stage 6B Implementation Flow                              │
├────────────────────┬────────────────────┬────────────────────┬────────────────────────┤
│ Sub-Stage 6B.1     │ Sub-Stage 6B.2     │ Sub-Stage 6B.3     │ Sub-Stage 6B.4         │
│ Feature & Target   │ Pre-Match Models   │ First-Innings      │ Chase Model            │
│ Construction       │ (Stage A & B)      │ Defense Model      │ (Second Innings)       │
├────────────────────┼────────────────────┼────────────────────┼────────────────────────┤
│ Sub-Stage 6B.5     │ Sub-Stage 6B.6     │ Sub-Stage 6B.7     │ Sub-Stage 6B.8         │
│ Probability        │ Chronological      │ Historical Worm    │ Final Model            │
│ Calibration Layer  │ Evaluation Suite   │ Graph Generation   │ Acceptance & Sign-Off  │
└────────────────────┴────────────────────┴────────────────────┴────────────────────────┘
```

### Sub-Stage 6B.1 — Feature & Target Construction
- **Goal:** Implement `schema.py`, `team_strength.py`, `venue_priors.py`, and `feature_extractor.py`.
- **Outputs:** Serialized feature matrices for Training (2022–2024, $N=114,677$), Validation (2025, $N=44,842$), and Test (2026, $N=31,056$).
- **Gate 6B.1:** Automated feature-target invariance check passes (`test_wp_leakage.py`); zero target leakage columns in feature matrices; zero duplicate keys.

### Sub-Stage 6B.2 — Pre-Match Models (Stage A & Stage B)
- **Goal:** Implement `pre_match_model.py`.
- **Outputs:**
  - Stage A model predicting initial win probability from historical team/venue priors.
  - Stage B model updating probability from confirmed XI lineup ABC and toss info.
  - Out-of-fold Stage B prediction generator for training-set live model features.
- **Gate 6B.2:** Strict out-of-fold validation confirmed; $P_A + P_B \equiv 1.0000$; Stage B pending logic verified when XI or toss is missing.

### Sub-Stage 6B.3 — First-Innings Defense Model
- **Goal:** Implement `innings1_model.py` using `HistGradientBoostingClassifier`.
- **Outputs:** Model predicting $P(\text{Batting Team Wins})$ from Innings 1 states ($N = 99,350$ standard deliveries).
- **Gate 6B.3:** Innings 1 validation log loss improves over naive baseline; monotonicity constraints verified (higher score increases win prob, wickets lost decreases win prob).

### Sub-Stage 6B.4 — Second-Innings Chase Model
- **Goal:** Implement `chase_model.py` using `HistGradientBoostingClassifier`.
- **Outputs:** Model predicting $P(\text{Chasing Team Wins})$ from Innings 2 states ($N = 91,225$ standard deliveries).
- **Gate 6B.4:** Terminal boundary conditions verified ($P=1.0$ when runs required $\le 0$; $P=0.0$ when all out or overs exhausted).

### Sub-Stage 6B.5 — Probability Calibration Layer
- **Goal:** Implement `calibrator.py` fitting Platt Scaling (Logistic Sigmoid) and Isotonic Regression exclusively on the 2025 Validation Set.
- **Outputs:** Calibrated probability mapping function preserving strict complementarity.
- **Gate 6B.5:** ECE reduced on 2025 Validation set; 2026 Test set remains strictly blind.

### Sub-Stage 6B.6 — Chronological Multi-Tier Evaluation Suite
- **Goal:** Implement `evaluator.py` computing Brier Score, Log Loss, ROC-AUC, ECE, and segment slices (Competition, Phase, Wickets, RRR, Closeness).
- **Outputs:** Comprehensive evaluation report across 2022–2024 train, 2025 val, and 2026 test.
- **Gate 6B.6:** Acceptance standards satisfied on 2026 Test set ($\text{BS} \le 0.160, \text{LL} \le 0.480, \text{ECE} \le 0.030$).

### Sub-Stage 6B.7 — Historical Worm Graph Reconstruction
- **Goal:** Implement `worm_graph.py` generating turn-by-turn match trajectory datasets for all 798 completed matches.
- **Outputs:** Standard JSON/Parquet worm graph files containing dual-team curves, turning points, and event annotations.
- **Gate 6B.7:** Continuous probability transition across innings break verified; turning points ($|\Delta P| \ge 0.10$) accurately identified.

### Sub-Stage 6B.8 — Final Model Acceptance & Artifact Registry
- **Goal:** Package model weights, feature extractors, calibrator objects, and manifest into `models/win_probability/`.
- **Outputs:** `stage_6b_implementation_report.md` and `stage_6b_manifest.json` with full SHA-256 hashes.
- **Gate 6B.8:** Full regression test pass (`pytest tests/ml/`); immutability of Stage 4, 5A, 5B, 5C confirmed.

---

## 4. Acceptance Criteria & Gating Verification Standards

Stage 6B will be accepted only if it satisfies all of the following empirical criteria:

| Metric / Check | Required Acceptance Standard | Verification Method |
| :--- | :--- | :--- |
| **Brier Score (Overall Test 2026)** | $\text{BS} \le \mathbf{0.160}$ | Programmatic calculation on 2026 Test Set |
| **Log Loss (Overall Test 2026)** | $\text{LL} \le \mathbf{0.480}$ | Programmatic calculation on 2026 Test Set |
| **Expected Calibration Error (ECE)** | $\text{ECE} \le \mathbf{0.030}$ ($3.0\%$) | 10-bin calibration evaluation on Test Set |
| **ROC-AUC (Overall Test 2026)** | $\text{ROC-AUC} \ge \mathbf{0.850}$ | Scikit-learn ROC-AUC score |
| **Strict Complementarity** | $|P(\text{Team A}) + P(\text{Team B}) - 1.0| < 10^{-6}$ | Asserted on every single predicted delivery |
| **Temporal Causality** | 100% adherence to $\text{source.date} < \text{target.date}$ | Verified via `test_wp_leakage.py` |
| **Out-of-Fold Pre-Match Fitting** | Zero in-sample pre-match anchor contamination | Verified via pipeline assertions |
| **Zero Prior Stage Mutation** | Raw CSVs, Stage 5B, Stage 5C hashes remain identical | SHA-256 hash match against manifests |
| **Test Suite Coverage** | $100\%$ pass rate across all `tests/ml/test_wp_*.py` | `pytest tests/ml/` |

---

## 5. Prerequisite Sign-Off

Stage 6B implementation code will NOT be authored until the user provides explicit authorization following review of the Stage 6A Revision 1 specifications.
