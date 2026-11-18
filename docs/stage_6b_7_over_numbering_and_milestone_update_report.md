# CricImpact Stage 6B.7 — Over-Numbering and Prediction Milestone Update Report

**Project:** CricImpact Phase 2 — Advanced In-Play Win Probability  
**Stage:** 6B.7 Visual Presentation & Presentation Correction  
**Author:** AI Agent (Google DeepMind Antigravity)  
**Date:** 2026-11-14  
**Status:** COMPLETED & VERIFIED  

---

## Executive Summary

This report documents the implementation and verification of two focused presentation enhancements to the **CricImpact Historical Match Explorer (Stage 6B.7)**:
1. **Cricket Over and Ball Numbering Correction:** Eliminated impossible over notations (e.g. `Over 20.6 (Innings 2)`) across all user-facing visual interfaces, replacing raw ball indices with standard legal-delivery cricket notation (`0.1` to `19.6`, and `20.0` for completed innings). Extra deliveries (wides and no-balls) preserve the over state being attempted, and shortened or incomplete innings reflect the exact legal deliveries bowled without forcing 20 overs.
2. **Three Match Prediction Milestones Display:** Integrated a compact, responsive 3-card milestone summary above the worm graph displaying:
   - **Card 1: Pre-Match Prediction:** Causal Stage A (pre-toss & prior record) and Stage B (post-toss & confirmed XI) win probabilities for Team A and Team B. Fully populated for all 798 standard T20 matches; strictly displays "Not Available" for excluded matches with zero fabrication.
   - **Card 2: Innings Break Milestone:** Fixed end-of-innings-1 summary capturing first-innings score, completed overs, target, and first-innings final win probability (`points[innings_1_balls - 1]`).
   - **Card 3: Current State (Dynamic):** Live win probability, score, and chase equation that updates instantaneously during timeline scrubbing, automated playback, and turning-point marker clicks.

### Scope and Invariant Preservation
- **Frozen Models:** Stage 6B.1–6B.6 models (`first_innings_model`, `second_innings_model`, calibrators) were strictly untouched.
- **Predictions & Calibrations:** All 798 trajectory probability values and underlying prediction artifacts remain 100% bit-for-bit identical.
- **Cryptographic Hashes:** All 9 baseline cryptographic SHA-256 hashes matched pre-execution baselines.
- **Test Suite:** The full ML test suite grew from 92 to 97 tests with **97 passed (0 failures, 0 regressions)**.

---

## 1. Root Cause of the Original Over-Numbering Issue

### 1.1 Technical Origin
In cricket data structures (such as Cricsheet ball-by-ball records), deliveries are recorded with two fields:
- `overid`: 1-indexed over counter ($1, 2, \dots, 20$).
- `over_ball_num`: sequential delivery counter within the over ($1, 2, \dots, n$, where $n > 6$ if wides or no-balls occurred).

In the initial implementation of the worm graph generator, delivery coordinates were naively string-formatted as:
$$\text{display\_over\_ball} = f"\{\text{overid}\}.\{\text{over\_ball\_num}\}"$$
This created two critical notation anomalies:
1. **1-Based Over Shift:** In cricket scoring notation, Over 1 corresponds to `0.1` through `0.6` (0 overs completed + balls in progress). Formatting `overid = 1` as `1.1` shifted the entire over label by +1 full over.
2. **20th Over Overflow:** In the 20th over (`overid = 20`), the 6th delivery was labeled as `20.6` rather than `19.6`. A completed 20-over innings was thus erroneously displayed as `Over 20.6` instead of `20.0` or `19.6`.
3. **Extras Overflow:** In an over with extras, raw balls 7 or 8 were formatted as `1.7` or `20.10`, violating standard cricket notation.

---

## 2. Mathematical Formula and Implementation of Corrected Cricket Numbering

### 2.1 Formula Specification
For standard Twenty20 cricket, legal deliveries within an innings range from 1 to 120. Let $L \in [1, 120]$ denote the 1-based index of the legal delivery bowled in that innings so far. The standard cricket over and ball notation is defined by:

$$\text{over\_number} = \left\lfloor \frac{L - 1}{6} \right\rfloor$$

$$\text{ball\_number} = ((L - 1) \pmod 6) + 1$$

$$\text{formatted\_over\_ball} = \text{over\_number} \,.\, \text{ball\_number}$$

### 2.2 Numerical Verification Table

| Legal Delivery ($L$) | Over Number ($\lfloor (L-1)/6 \rfloor$) | Ball Number ($((L-1) \bmod 6) + 1$) | Correct Cricket Notation |
| :---: | :---: | :---: | :---: |
| **1** (First ball of innings) | $\lfloor 0 / 6 \rfloor = 0$ | $(0 \bmod 6) + 1 = 1$ | `0.1` |
| **2** | $\lfloor 1 / 6 \rfloor = 0$ | $(1 \bmod 6) + 1 = 2$ | `0.2` |
| **6** (Final ball of 1st over) | $\lfloor 5 / 6 \rfloor = 0$ | $(5 \bmod 6) + 1 = 6$ | `0.6` |
| **7** (First ball of 2nd over) | $\lfloor 6 / 6 \rfloor = 1$ | $(6 \bmod 6) + 1 = 1$ | `1.1` |
| **12** (Final ball of 2nd over) | $\lfloor 11 / 6 \rfloor = 1$ | $(11 \bmod 6) + 1 = 6$ | `1.6` |
| **13** (First ball of 3rd over) | $\lfloor 12 / 6 \rfloor = 2$ | $(12 \bmod 6) + 1 = 1$ | `2.1` |
| **119** (Penultimate ball) | $\lfloor 118 / 6 \rfloor = 19$ | $(118 \bmod 6) + 1 = 5$ | `19.5` |
| **120** (Final legal ball of 20th over) | $\lfloor 119 / 6 \rfloor = 19$ | $(119 \bmod 6) + 1 = 6$ | `19.6` |

For completed innings or innings summaries, completed overs notation is defined as:
$$\text{completed\_overs} = \lfloor C / 6 \rfloor \,.\, (C \pmod 6)$$
Where $C$ is the total legal balls completed. When $C = 120$, completed overs format is strictly `20.0`.

### 2.3 Edge Case Demonstration

#### A. Deliveries in the Same Over (Extras: Wides & No-Balls)
Under MCC Law 21 (No ball) and Law 22 (Wide ball), extra deliveries do not count as legal balls in the over. In `df_match_states`, `legal_balls_remaining_before` does not decrement on an extra delivery:
- If `legal_balls_remaining_before` is 118 (attempting legal ball 3 of over 1), $L = 120 - 118 + 1 = 3 \rightarrow \mathbf{0.3}$.
- If a bowler bowls a wide on ball 3, the next delivery still has `legal_balls_remaining_before = 118`, so $L$ remains 3, and the next delivery is also labeled $\mathbf{0.3}$.
- The user sees `Over 0.3 (Wide)` followed by `Over 0.3 (Legal)`. The over counter does not prematurely advance.

#### B. Shortened and Incomplete Innings (All-Out / Target Reached)
Innings that terminate before 120 legal balls (e.g. bowled out, rain curtailment, or chase achieved) compute notation from actual legal balls bowled:
- **85 Legal Balls Bowled (All-Out):**
  - Final legal delivery: $L = 85 \rightarrow \lfloor 84 / 6 \rfloor = 14$, $(84 \bmod 6) + 1 = 1 \rightarrow \mathbf{14.1}$.
  - Completed overs display: $85 \text{ balls} = \mathbf{14.1 \text{ ov}}$ (14 overs and 1 ball).
  - It is **never** artificially forced or padded to 20.0 overs.
- **84 Legal Balls Bowled (Target Reached at Over End):**
  - Final delivery: $L = 84 \rightarrow \mathbf{13.6}$.
  - Completed overs display: $\mathbf{14.0 \text{ ov}}$.

### 2.4 Consistent Application Across Visual Components
The corrected notation is applied across all 7 user-facing display surfaces in `docs/worm_graph/worm_graph.html`:
1. **Chart X-Axis Labels:** Milestones rendered at `I1 Start`, `Ov 5`, `Ov 10`, `Ov 15`, `Inn 1 End`, `I2 Start`, `Ov 5`, `Ov 10`, `Ov 15`, `Final`.
2. **Hover Tooltips:** `#tt-over` displays `Over ${p.over_ball} (Innings ${p.innings})`.
3. **Event Markers:** Wickets, fours, sixes, and milestone tooltips display `Over ${p.over_ball}`.
4. **Turning-Point Descriptions:** Match-defining moments panel displays exact synchronized `Over ${m.over_ball}`.
5. **Timeline Scrubber:** `#current-ball-label` displays `Ball ${index + 1} / ${total} (Over ${p.over_ball})`.
6. **Current Delivery Milestone Card:** `#ms-live-ball-state` displays `Ball ${p.match_ball_index} / ${total} (Over ${p.over_ball})`.
7. **Innings-Break Milestone Card:** `#ms-break-id` displays `Inn 1 End (Over ${endPt.over_ball})`.

---

## 3. Match Prediction Milestones Architecture

### 3.1 Overview and Placement
A dedicated 3-column milestone dashboard (`#prediction-milestones-container`) was embedded directly above the worm graph chart and live probability header:

```
+---------------------------------------------------------------------------------------------------+
|  [Select Match: 50375 - MI vs RCB]  [Filter: IPL]  [Year: 2026]  [Methodology: Frozen Platt]      |
+---------------------------------------------------------------------------------------------------+
|                                 MATCH PREDICTION MILESTONES                                       |
|  +-----------------------------+ +-----------------------------+ +-----------------------------+  |
|  | 1. PRE-MATCH MILESTONES     | | 2. INNINGS BREAK MILESTONE  | | 3. CURRENT LIVE PREDICTION  |  |
|  | Stage A: 55.4% / 44.6%      | | Score: 166/7 (20.0 ov)      | | Inn 2 | 165/8 (Over 19.6)   |  |
|  | Stage B: 55.6% / 44.4%      | | Target: 167                 | | Need 2 runs from 1b         |  |
|  | Prior Models (Pre-Play)     | | Break Prob: 49.6% / 50.4%   | | Live Prob: 6.6% / 93.4%     |  |
|  +-----------------------------+ +-----------------------------+ +-----------------------------+  |
+---------------------------------------------------------------------------------------------------+
|                                   WIN PROBABILITY WORM GRAPH                                      |
|  100% |                                                                                           |
|       |   Mumbai Indians % [Blue]            Royal Challengers Bengaluru % [Red]                  |
|    0% |___________________________________________________________________________________________|
|       I1 Start     Ov 5     Ov 10    Ov 15   Inn 1 End   I2 Start    Ov 5     Ov 10    Ov 15   Final |
+---------------------------------------------------------------------------------------------------+
```

### 3.2 Card Specifications and Data Sources

#### Card 1: Pre-Match Prediction (Static per Match)
- **Purpose:** Displays pre-play model predictions grounded in Stage 6B.2 prior models.
- **Stage A (Pre-Toss & Prior Record):** Calculated using venue historical averages, team historical prior win rates, and pace/spin ratios before coin toss.
- **Stage B (Post-Toss & Confirmed XI):** Incorporates toss winner, toss decision, confirmed playing XI relative batting ABC edges, and bowling unit phase strike rates.
- **Data Source:** Extracted via `WinProbabilityFeatureExtractor` across all 798 standard T20 matches using causal ABC features (`pre_match_causal_abc_features_v1.pkl.gz`), match states, and lineups.
- **Orientation:** Exact Team A (batting 1st) alignment ($P_{\text{Team A}} = P_{\text{Home}}$ if Team A is Home, else $1.0 - P_{\text{Home}}$).
- **Graceful Fallback:** Excluded matches (85 matches) display `Not Available` with muted styling. Zero fabrication or substitution.

#### Card 2: Innings Break Milestone (Static per Match)
- **Purpose:** Captures the state of the match at the completion of Innings 1.
- **First-Innings Score & Overs:** e.g. `166/7 (20.0 ov)`.
- **Target for Innings 2:** `167` (or $S_1 + 1$).
- **State Identifier:** `Inn 1 End (Over 19.6, Ball 123)`.
- **Break Win Probability:** Captured directly from the final legal delivery of the first innings (`points[innings_1_balls - 1]`), strictly reflecting the First Innings LightGBM model probability after Platt calibration.

#### Card 3: Current State (Dynamic on Scrub/Play)
- **Purpose:** Synchronizes in real time with the active delivery observation.
- **Ball State:** e.g. `Ball 254 / 254 (Over 19.6)`.
- **Current Score:** e.g. `Inn 2 | 165/8`.
- **Chase Equation:** Dynamic contextual state (`Need 2 runs from 1b` in Innings 2, or `X legal balls left` in Innings 1).
- **Live Win Probabilities:** Formatted with team-specific brand colors (`#004BA0` Mumbai Indians vs `#D11919` Royal Challengers Bengaluru).
- **Zero UI Jitter:** Implemented via lightweight DOM text updates triggered by `updateReadout()`.

---

## 4. Verification and Test Results

### 4.1 Unit Test Expansion (`tests/ml/test_wp_worm_graph.py`)
Five new dedicated unit test suites were implemented covering all Part 4 requirements:

1. `test_cricket_over_numbering_formula`:
   - Validates $L = 1 \rightarrow \mathbf{0.1}$, $L = 6 \rightarrow \mathbf{0.6}$, $L = 7 \rightarrow \mathbf{1.1}$, $L = 12 \rightarrow \mathbf{1.6}$, $L = 13 \rightarrow \mathbf{2.1}$, $L = 120 \rightarrow \mathbf{19.6}$.
   - Validates completed overs notation ($120 \rightarrow \mathbf{20.0}$, $85 \rightarrow \mathbf{14.1}$, $84 \rightarrow \mathbf{14.0}$, $0 \rightarrow \mathbf{0.0}$).
   - Validates exception handling on $L \le 0$.
2. `test_cricket_over_numbering_with_extras_and_shortened`:
   - Validates that across all 254 balls of showcase match 50375, over numbers strictly remain in $[0, 19]$ and ball numbers in $[1, 6]$.
   - Validates that wide and no-ball deliveries retain identical over-ball labels as the subsequent legal ball attempt.
3. `test_milestone_dataclasses_and_invariants`:
   - Validates `PreMatchMilestone`, `InningsBreakMilestone`, and `MatchPredictionMilestones`.
   - Confirms probability boundary enforcement ($[0, 1]$), strict complementarity ($\sum = 1.0$), and `to_dict()` serialization.
4. `test_match_50375_milestone_extraction`:
   - Validates milestone extraction on match 50375: First-innings score 166/7, target 167, overs 20.0, and strict parity between innings break milestone probability and final ball of Innings 1.
5. `test_match_index_milestones_and_excluded_integrity`:
   - Validates all 883 matches in `match_index.json`: all 798 standard T20 matches have valid Stage A & Stage B probabilities summing to 1.0; all 85 excluded matches have `available: false` and null probabilities with zero fabrication.

### 4.2 Automated Test Execution Output
```
============================= test session starts =============================
platform win32 -- Python 3.13.14, pytest-9.2.0, pluggy-1.7.0
rootdir: C:\Users\admin\Documents\CricImpact_Phase2
plugins: anyio-4.15.1
collected 12 items

tests\ml\test_wp_worm_graph.py ............                              [100%]

============================= 12 passed in 7.97s ==============================
```

Full ML regression suite execution:
```
pytest tests/ml/ -q
........................................................................ [ 74%]
.........................                                                [100%]
97 passed in 89.66s (0:01:29)
```
- **Total Tests:** 97
- **Passed:** 97
- **Failed:** 0
- **Regression:** Zero tests failed, modified, or weakened.

---

## 5. Artifact Protection and Cryptographic Verification

All 9 baseline artifacts recorded prior to the update were cryptographically verified using SHA-256 checksums:

| Artifact Path | Pre-Execution Baseline SHA-256 | Post-Update SHA-256 | Status |
| :--- | :--- | :--- | :---: |
| `data/processed/calibration/calibration_manifest_v1.json` | `8b11483723f5bf0f02a5df2bdf346bb4f4d585ba4a249e29a2babc16d5e2bcd1` | `8b11483723f5bf0f02a5df2bdf346bb4f4d585ba4a249e29a2babc16d5e2bcd1` | **MATCH** |
| `data/processed/calibration/val_2025_calibrated_predictions_v1.pkl.gz` | `2b0700be46316a4b3c14c80167e6af58b1ccdb314fc1786a2bff7f8335d82bb9` | `2b0700be46316a4b3c14c80167e6af58b1ccdb314fc1786a2bff7f8335d82bb9` | **MATCH** |
| `data/processed/calibration/test_2026_calibrated_predictions_v1.pkl.gz` | `a627c11e4359346e6ae032707730d9fdf63d3f4b99d2d744ac019b3ac86eb46d` | `a627c11e4359346e6ae032707730d9fdf63d3f4b99d2d744ac019b3ac86eb46d` | **MATCH** |
| `data/processed/calibration/test_2026_evaluation_manifest_v1.json` | `d0d62de97bd9ae2c184f66e289c86e6909b75c725109e7eb61b62fff7231d029` | `d0d62de97bd9ae2c184f66e289c86e6909b75c725109e7eb61b62fff7231d029` | **MATCH** |
| `data/processed/match_states/match_states_standard_t20_v1.pkl.gz` | `815a8e1ff4e428e85b942caeaaea9e45af1bf159eeb794c7c425390d476cb871` | `815a8e1ff4e428e85b942caeaaea9e45af1bf159eeb794c7c425390d476cb871` | **MATCH** |
| `data/processed/contributions/pre_match_causal_abc_features_v1.pkl.gz` | `323af183ef60eef75618f38a012086cb921eaa9c6b631372dffb785e18e6de5c` | `323af183ef60eef75618f38a012086cb921eaa9c6b631372dffb785e18e6de5c` | **MATCH** |
| `data/validation/stage_5b/stage5b_match_eligibility_v1.csv` | `98507e9c71aabd308a3590569eb304abd0c7b022c8aadb71f8d27876742e7b51` | `98507e9c71aabd308a3590569eb304abd0c7b022c8aadb71f8d27876742e7b51` | **MATCH** |
| Showcase Match 50375 (`50375.json`) | `5c55cb31311d93e8c9f50897260f35d827e93d5633f78a527f2a042850e2b4ba` | `5c55cb31311d93e8c9f50897260f35d827e93d5633f78a527f2a042850e2b4ba` | **MATCH** |
| Showcase Match 50138 (`50138.json`) | `ab809c54a624c299528d4086af36769334d264cc54ac06ca1739c83cce01b0f8` | `ab809c54a624c299528d4086af36769334d264cc54ac06ca1739c83cce01b0f8` | **MATCH** |

- **Trajectory Corpus Count:** Exactly 798 trajectory files remain intact in `docs/worm_graph/trajectories/`.
- **DOM References:** All 105 `document.getElementById` calls resolve to defined IDs with zero missing elements.

---

## 6. Conclusion and Final Sign-Off

The Stage 6B.7 Worm Graph over-numbering correction and match prediction milestone integration are complete, fully validated, and regression-free.

- **Presentation Accuracy:** Cricket notation strictly obeys legal delivery counting conventions (`0.1`–`19.6`, `20.0`), with correct extra preservation and shortened innings handling.
- **Milestones Completeness:** All 3 prediction milestone cards function seamlessly with exact causal provenance and instantaneous UI updates.
- **Model Integrity:** 100% frozen model, prediction, and calibration invariance maintained.

Execution is **STOPPED** at this point in accordance with instructions. Awaiting user authorization before proceeding to any subsequent stage.

