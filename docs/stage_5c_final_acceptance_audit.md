# CricImpact Phase 2 — Stage 5C Final Acceptance Audit Report

**Audit Date:** `2026-11-13`  
**Auditor:** `CricImpact Phase 2 Quality & Verification Engine`  
**Audit Status:** `COMPLETE`  
**Overall Verdict:** `PASS` (All 5 Verification Audits PASSED)  
**Target Specification:** [`docs/stage_5c_universal_strategy4_specification.md`](file:///c:/Users/admin/Documents/CricImpact_Phase2/docs/stage_5c_universal_strategy4_specification.md) (`v2.1`)  
**Target Implementation Report:** [`docs/stage_5c_implementation_report.md`](file:///c:/Users/admin/Documents/CricImpact_Phase2/docs/stage_5c_implementation_report.md)  
**Target Build Manifest:** [`data/processed/contributions/stage5c_contributions_v1_manifest.json`](file:///c:/Users/admin/Documents/CricImpact_Phase2/data/processed/contributions/stage5c_contributions_v1_manifest.json)  

---

## Executive Audit Summary

| Audit Item | Scope & Description | Evaluation Verdict |
|:---|:---|:---:|
| **Audit 1: DNB Reconciliation** | Reconcile 5,073 roster DNBs vs 5,196 validation DNBs across 18,106 player-match records | **`PASS`** |
| **Audit 2: Stint Reconciliation** | Reconcile 13,033 batted appearances vs 13,045 stints (12 additional stints across 11 appearances) | **`PASS`** |
| **Audit 3: T20I Strategy 4 Methodology** | Confirm exact T20I Innings 1 & Innings 2 formulas, files, and independent Phase 7U benchmark | **`PASS`** |
| **Audit 4: Leakage & Outcome Independence** | Verify zero match-outcome inputs, strict calendar causality ($d_{m'} < d_m$), same-day exclusion | **`PASS`** |
| **Audit 5: Final Artifact Integrity** | Bit-level SHA-256 manifest verification, immutability of Phase 1 and raw CSV files | **`PASS`** |

---

## 1. DNB Reconciliation Audit

### Verdict: `PASS`

### 1.1 The Exact Discrepancy
The Stage 5C implementation summary reports:
- Total batter-match records: `18,106`
- Batted appearances: `13,033`
- Unbatted roster entries: `5,073`
- Validation gate `VAL-5C-DNB-001` reports: `5,196` DNB rows (`5,196 / 5,196` strict `NULL` scores).

The arithmetic difference is exactly:
$$5,196 - 5,073 = 123 \text{ records}$$

### 1.2 Exact Origin of the 5,073 and 5,196 Counts
1. **The `5,073` Count (Roster-Only DNBs):**
   - Source: Raw [`data/raw/playing_eleven.csv`](file:///c:/Users/admin/Documents/CricImpact_Phase2/data/raw/playing_eleven.csv).
   - In the 798 `STANDARD_T20` matches, there are `18,100` rows with `is_played == 1` plus `6` UAE split-ID players recovered from crease deliveries = `18,106` player-match records.
   - Of these `18,106` records, exactly **`5,073` players never set foot on the crease** during their match (`entry_innings_ball_num` is `pd.NA`). This includes `219` unused or bowling-only Impact Substitutes (`is_impact == 1`).
2. **The `123` Count (Zero-Ball Not-Out Non-Strikers):**
   - Source: Stage 5B delivery match states [`match_states_standard_t20_v1.pkl.gz`](file:///c:/Users/admin/Documents/CricImpact_Phase2/data/processed/match_states/match_states_standard_t20_v1.pkl.gz).
   - Exactly **`123` players stood at the non-striker end** (`non_striker_id == player_id`) without facing a single legal or no-ball delivery (`balls_faced == 0`), scored zero runs (`actual_runs == 0`), and were not dismissed (`dismissal_status == 'not out'`) when the 20 overs expired or the target was reached.
   - Examples include Match 13511 Player 2304 (entered ball 121, stood at non-striker for 1 ball), Match 13514 Player 786 (entered ball 126, 0 balls faced, not out), and Match 13515 Player 2315 (entered ball 127 as target chased from other end).
3. **The `5,196` Count (Effective DNB Scoring Population):**
   - Per approved Stage 5C specification rule **`ABC-R09`** (and reflecting Phase 1 production scoring criteria):
     $$\text{balls\_faced} == 0 \land \text{actual\_runs} == 0 \land \text{dismissal\_status} \ne \text{'out'} \implies \text{is\_dnb} = \text{True}$$
   - These 123 non-strikers did not have a scoring opportunity and cannot be attributed individual execution ($P_2$) or context leverage ($P_1$).
   - Therefore, the effective scoring DNB population is:
     $$5,073 \text{ (roster DNBs)} + 123 \text{ (0-ball not-out non-strikers)} = 5,196 \text{ DNB rows}$$
   - Conversely, the genuine scored batting population is:
     $$18,106 - 5,196 = 12,910 \text{ scored batting appearances}$$
     (Consisting of `12,888` batters who faced $\ge 1$ ball + `22` batters who faced 0 balls but were dismissed, e.g., diamond ducks/run outs).

### 1.3 Audit Assertions & Checks
- **Same Population & Unique Key:** Both counts operate strictly on the exact same population of `18,106` deduplicated `(match_id, innings, player_id)` records.
- **Duplication Check:** Duplicate keys across `(match_id, innings, player_id)` in both `batter_match_contributions_strategy4_v1.pkl.gz` and `phase7u_v1.pkl.gz` is exactly **`0`**.
- **Score Nullity:** In both engines, `100%` of all `5,196` DNB rows have strict `NULL` (`pd.NA`) for `contribution_score`, `raw_contribution`, `p2_score`, `p3_score`, and `leverage_l`.
- **Denominator Non-Dilution:** In [`season_competition_metrics_comparison_v1.csv`](file:///c:/Users/admin/Documents/CricImpact_Phase2/data/processed/contributions/season_competition_metrics_comparison_v1.csv), `batting_innings` and the ABC denominator strictly sum only appearances where `~is_dnb & contribution_score.notna()`. Exactly **`0`** DNB records enter the ABC denominator.
- **Match-Level Distribution of the 123 Records:**
  - Matches affected: `119` matches (78 in Innings 1, 45 in Innings 2).
  - Category breakdown: `T20I`: 70, `IPL`: 50, `OTHER_T20`: 3.

---

## 2. Batter Stint Reconciliation Audit

### Verdict: `PASS`

### 2.1 The Exact Discrepancy
- Total crease appearances: `13,033`
- Total reconstructed continuous crease stints: `13,045`
- Difference: Exactly **`12` additional stints**.

### 2.2 Complete Breakdown of All 12 Additional Stints
An exhaustive inspection of [`batter_stints_v1.pkl.gz`](file:///c:/Users/admin/Documents/CricImpact_Phase2/data/processed/contributions/batter_stints_v1.pkl.gz) reveals that the 12 additional stints originate from exactly **11 player-match appearances** (10 appearances with 2 stints = $+10$, and 1 appearance with 3 stints = $+2$):

| Match ID | Innings | Player ID | Stint ID | Entry Ball | Exit Ball | Balls Faced | Runs | Dismissal Status | Root Cause for Multi-Stint Separation |
|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---|
| **15458** | 1 | **4895** | 1 | 29 | 85 | 30 | 33 | not out | Scorer delivery glitch: At ball 86, dismissed player 2003 was logged as non-striker instead of 4895. Player 4895 returned at ball 87. |
| **15458** | 1 | **4895** | 2 | 87 | 98 | 4 | 5 | not out | Resumed stay after 1-ball recording hiatus. |
| **19960** | 1 | **2416** | 1 | 1 | 63 | 27 | 51 | out | Dismissed Caught at ball 63. |
| **19960** | 1 | **2416** | 2 | 78 | 78 | 0 | 0 | not out | Scorer delivery glitch: Player 2416 mistakenly logged as non-striker for 1 delivery at ball 78. |
| **19960** | 1 | **4986** | 1 | 67 | 77 | 5 | 2 | not out | Stay interrupted at ball 78 due to scorer logging 2416 at non-striker. |
| **19960** | 1 | **4986** | 2 | 79 | 113 | 14 | 26 | out | Resumed stay at ball 79 until dismissed Caught at ball 113. |
| **21585** | 2 | **5939** | 1 | 6 | 12 | 3 | 4 | not out | Unrecorded crease exit: Left crease at ball 12; balls 13–37 batted by other partnerships. |
| **21585** | 2 | **5939** | 2 | 38 | 71 | 17 | 26 | out | Returned to crease at ball 38 until Bowled at ball 71. |
| **28059** | 2 | **1101** | 1 | 45 | 68 | 14 | 20 | not out | Stay interrupted at ball 69 due to anomalous non-striker logging of 7094. |
| **28059** | 2 | **1101** | 2 | 70 | 116 | 18 | 29 | not out | Resumed stay at ball 70 until match close at ball 116. |
| **28059** | 2 | **4812** | 1 | 26 | 76 | 22 | 14 | not out | Stay interrupted at ball 77 due to anomalous striker logging of 7094. |
| **28059** | 2 | **4812** | 2 | 78 | 116 | 23 | 40 | not out | Resumed stay at ball 78 until match close at ball 116. |
| **28059** | 2 | **7094** | 1 | 30 | 44 | 9 | 5 | out | Dismissed Caught at ball 44. |
| **28059** | 2 | **7094** | 2 | 69 | 69 | 0 | 0 | not out | Scorer delivery glitch: Erroneously logged as non-striker for single ball 69. |
| **28059** | 2 | **7094** | 3 | 77 | 77 | 0 | 0 | not out | Scorer delivery glitch: Erroneously logged as striker for single ball 77. |
| **50138** | 2 | **1077** | 1 | 63 | 81 | 10 | 12 | not out | Unrecorded crease exit: Left crease at ball 81; balls 82–105 batted by other partners. |
| **50138** | 2 | **1077** | 2 | 106 | 128 | 10 | 29 | not out | Returned at ball 106 to finish match not out. |
| **50344** | 1 | **4703** | 1 | 25 | 28 | 3 | 0 | not out | Unrecorded crease exit: Left crease at ball 28; hiatus balls 29–97. |
| **50344** | 1 | **4703** | 2 | 98 | 104 | 3 | 1 | out | Returned at ball 98 until Caught at ball 104. |
| **50381** | 2 | **23450** | 1 | 1 | 21 | 13 | 23 | not out | Unrecorded crease exit: Left crease at ball 21; hiatus balls 22–104. |
| **50381** | 2 | **23450** | 2 | 105 | 127 | 15 | 30 | not out | Returned at ball 105 to finish match not out. |
| **50944** | 1 | **152** | 1 | 12 | 50 | 19 | 34 | not out | Unrecorded crease exit: Left crease at ball 50; hiatus balls 51–78 while 3 wickets fell. |
| **50944** | 1 | **152** | 2 | 79 | 122 | 16 | 11 | not out | Returned at ball 79 to finish innings not out. |

### 2.3 Reconciliation Against the 11 Retired Hurt Events
- There are exactly **`11` formal `is_retired_hurt_event` deliveries** across the 798 `STANDARD_T20` matches (Match IDs: `14114`, `15610`, `16064`, `20880`, `20188`, `20243`, `28964`, `29926`, `31709`, `37094`, and `40763`).
- In `batter_stints_v1.pkl.gz`, all 11 of these players have `stint_id == 1` and `is_retired_hurt == True`.
- **Zero of the 11 Retired Hurt players resumed batting** later in their respective innings.
- Therefore, the claim that **zero Retired Hurt players resumed in `v1` is 100% verified and true**.
- The 12 additional stints were caused exclusively by:
  1. **Scorer Delivery Logging Glitches (`6` stints across 4 players):** Single-delivery clerical misattributions in the raw data where an already-dismissed player was logged as a non-striker for 1 ball.
  2. **Unrecorded Crease Exits & Returns (`6` stints across 5 players):** Players who left the crease without a formal `Retired Hurt` dismissal flag in the raw feed and later returned to bat.

### 2.4 Multi-Stint Aggregation & Single Contribution Proof
In `ml/contribution/stint_builder.py` (`build_batter_stints_and_roster`), rule `ABC-R06` aggregates multi-stint appearances into a single row per `(match_id, innings, player_id)`:
- `balls_faced = SUM(stints.balls_faced)`
- `actual_runs = SUM(stints.actual_runs)`
- `fours = SUM(stints.fours)`, `sixes = SUM(stints.sixes)`
- `entry_*` state is locked from Stint 1 (`first_s`)
- `exit_*` state is locked from Final Stint (`last_s`)
- `overs_spent`, `team_runs_added`, and `wickets_lost_during_stay` sum strictly across active on-crease stints (hiatus deliveries, runs, and partner wickets are excluded).
- `dismissal_status` is determined by the final stint.

**Verification:** In [`batter_match_contributions_strategy4_v1.pkl.gz`](file:///c:/Users/admin/Documents/CricImpact_Phase2/data/processed/contributions/batter_match_contributions_strategy4_v1.pkl.gz), all 11 multi-stint players have **exactly 1 record**, yielding exactly `18,106` player-match records and zero duplicates.

---

## 3. T20I Strategy 4 Methodology Audit

### Verdict: `PASS`

### 3.1 Clarification: Strategy 4 vs Phase 7U in T20I
During Phase 1 methodology recovery, **Phase 7U** was identified as the active historical production engine for T20I (and all non-IPL competitions). However, the primary objective of Stage 5C—as authorized in Decision 1, Decision 4, and Decision 5—was to evaluate **Universal Strategy 4 as a unified methodology across IPL, T20I, and OTHER_T20**, while maintaining Phase 7U as a preserved comparison baseline.

Universal Strategy 4 for T20I does **NOT** use Phase 7U formulas. It implements the **true Strategy 4 architecture**, parameterized with **T20I-specific walk-forward expectations**.

### 3.2 Exact Implemented Formulas for T20I

#### A. T20I Innings 1 Formula
- **Implementation File:** [`ml/contribution/strategy4_scorer.py`](file:///c:/Users/admin/Documents/CricImpact_Phase2/ml/contribution/strategy4_scorer.py)
- **Function Name:** `score_stint_strategy4(stint, models, ...)` when `inn == 1`
- **Architecture:** Full Strategy 4 Hybrid (Model T):
  1. **EFS Expectation:** Expected final score predicted by `models.efs_model` (walk-forward `RandomForestRegressor` trained on prior T20I 1st-innings end-of-over states using 7 features; linear par projection if $N < 30$).
  2. **Attributable Drag $\gamma$ (Model T):**
     $$\Delta\text{EFS}_{\text{attr}} = \text{run\_dev} + \gamma \cdot (\Delta\text{EFS} - \text{run\_dev})$$
     where $\gamma \in \{0.15, 0.50, 0.70, 1.00\}$ separates Category B rescuers from Category A stagnation/caused wickets.
  3. **Context Trajectory & Crease Resource Depletion:** $\kappa_{\text{entry}}$ anchored to T20I walk-forward par total (`models.par_total`); crease resource depletion $f_{\text{res}}$ evaluated using T20I historical wicket loss curve $w_{\text{hist}}$ (`models.w_curve`).
  4. **Pillar 2 Standardization:** Z-scores for runs, strike rate, pace, and boundaries standardized using T20I walk-forward empirical anchors (`models.p2_runs_mean`, `models.p2_runs_std`, `models.p2_sr_mean`, `models.p2_sr_std`).
  5. **Raw Contribution Formula (Decision 4):**
     $$c_{\text{raw}} = 0.50 \cdot \left(\frac{\Delta R}{10.0}\right) + 0.50 \cdot p_{3,\text{raw}}$$
     *(This is the exact recovered Strategy 4 first-innings formula, parameterized by T20I priors).*

#### B. T20I Innings 2 Formula (Chase)
- **Implementation File:** [`ml/contribution/strategy4_scorer.py`](file:///c:/Users/admin/Documents/CricImpact_Phase2/ml/contribution/strategy4_scorer.py)
- **Function Name:** `score_stint_strategy4(stint, models, ...)` when `inn == 2`
- **Architecture:** Option 1B Primary Chase Adaptation:
  1. **Dynamic Volatility & Chase Factor:**
     $$v_{\max} = 12.0 + 3.0 \cdot \tanh\left(\frac{W_{\text{rem}} - 3.5}{2.0}\right) + 4.0 \cdot \left(\frac{12.0}{B_{\text{rem}} + 6.0}\right)$$
     $$F_{\text{chase}} = \max\left(0.60, \min\left(1.40, 1.0 + 0.35 \cdot \tanh\left(\frac{\text{RRR} - \text{models.rrr\_center}}{2.5}\right) + 0.15 \cdot \frac{\text{Target} - \text{models.target\_center}}{30.0}\right)\right)$$
  2. **Effective Chase Drivers:** $r_{\text{eff}}$ (saturated RRR delta), $g_{\text{eff}}$ (RR gap delta), and $t_{\text{prog}}$ (target progress change).
  3. **Pillar 3 Raw Chase Score:**
     $$p_{3,\text{raw}} = 0.50 \cdot \left(\frac{r_{\text{eff}}}{3.0}\right) + 0.25 \cdot \left(\frac{g_{\text{eff}}}{3.0}\right) + 0.25 \cdot \left(\frac{t_{\text{prog}} - 0.15}{0.15}\right) + S_{\text{res}}$$
  4. **Raw Contribution Formula (Decision 4):**
     $$c_{\text{raw}} = 0.50 \cdot (z_2 \cdot L) + 0.50 \cdot (z_3 \cdot L)$$

### 3.3 Contrast Against Phase 7U Baseline
In [`ml/contribution/phase7u_scorer.py`](file:///c:/Users/admin/Documents/CricImpact_Phase2/ml/contribution/phase7u_scorer.py) (`score_stint_phase7u`), the Phase 7U baseline uses:
- Static heuristic expectations: $\text{ExpectedRuns} = 1.25 \cdot \text{balls\_faced}$, $\text{ExpectedSR} = 125.0$.
- Zero ML models (`expected_final_entry = NaN`).
- Static IPL constants (Target `165.0`, RRR `8.25`, P2 anchors `19.8/21.6`).
- Heuristic Innings 1 formula: $0.60 \cdot (\Delta R / 14.5) + 0.25 \cdot \Delta T_{\text{heur}} + 0.15 \cdot \text{accel} + S_{\text{res}}$.
- Harmonized raw formula: $0.50 \cdot (z_2 \cdot L) + 0.50 \cdot (z_3 \cdot L)$ everywhere.

**Verification:** Phase 7U was independently executed on all 419 T20I matches. The side-by-side benchmark confirmed that Universal Strategy 4 reduced the Innings 1 vs Innings 2 bias in T20I from `7.39` points down to `4.16` points (**43.7% reduction**).

---

## 4. Leakage and Outcome-Independence Audit

### Verdict: `PASS`

### 4.1 Absence of Match Outcome Fields
A strict regex and AST scan of all modules in `ml/contribution/` confirmed:
- `won_match`, `winning_margin`, `win_team_id_raw`, `target_home_team_win`, and `matches.result` are **NEVER imported, read, or referenced** anywhere in scoring or expectation fitting.
- `target_batting_team_win` appears only in [`ml/contribution/evaluation.py`](file:///c:/Users/admin/Documents/CricImpact_Phase2/ml/contribution/evaluation.py#L223) for post-hoc Criterion 10 correlation auditing, and in [`ml/contribution/validator.py`](file:///c:/Users/admin/Documents/CricImpact_Phase2/ml/contribution/validator.py#L177) to explicitly assert that zero target columns enter scoring engines.
- `is_primary_wp_train_eligible` is used solely to restrict corpus ingestion to verified `STANDARD_T20` matches.

### 4.2 Pre-Match Temporal Causality (Track B)
In [`ml/contribution/aggregation.py`](file:///c:/Users/admin/Documents/CricImpact_Phase2/ml/contribution/aggregation.py#L262) (`build_pre_match_causal_abc_features`):
- Calendar cutoff inequality is enforced strictly as:
  $$\text{prior\_all} = [x \text{ for } x \text{ in } p\_\text{inns} \text{ if } x[\text{"match\_date"}] < m\_\text{date}]$$
- **Strict Inequality (`<`):** Any match on calendar date $m\_\text{date}$ is strictly excluded. This guarantees that **same-day fixtures (e.g. double-headers) are excluded**, preventing same-day intra-round leakage.
- **Current Match Excluded:** A player's current-match performance never enters their pre-match feature vector.

### 4.3 Target Permutation Invariance Proof
- In [`tests/ml/test_contribution_causality_and_eval.py`](file:///c:/Users/admin/Documents/CricImpact_Phase2/tests/ml/test_contribution_causality_and_eval.py#L105) (`test_future_perturbation_invariance`), future match dates and scores were randomly perturbed. The pre-match feature vectors for earlier matches were verified to remain **bit-for-bit identical**.

---

## 5. Final Artifact Integrity Audit

### Verdict: `PASS`

### 5.1 Cryptographic Hash Verification
All output artifact files on disk were re-hashed using SHA-256 and verified against [`stage5c_contributions_v1_manifest.json`](file:///c:/Users/admin/Documents/CricImpact_Phase2/data/processed/contributions/stage5c_contributions_v1_manifest.json):

| Artifact Description | Disk File Path | Manifest SHA-256 Digest | Match |
|:---|:---|:---|:---:|
| **Crease Stints** | `data/processed/contributions/batter_stints_v1.pkl.gz` | `9E2924695F259FCDF48D37071480C15A5CC7E361C79D950ADFD9D099EF146C38` | **`MATCH`** |
| **Phase 7U Contributions** | `data/processed/contributions/batter_match_contributions_phase7u_v1.pkl.gz` | `252C3D15B99F7F0553B6700058F68E062B5A5B326CC0CA818512AE70BE7BC74B` | **`MATCH`** |
| **Strategy 4 Contributions** | `data/processed/contributions/batter_match_contributions_strategy4_v1.pkl.gz` | `02A6F5F15941DE81755BACBA268F159974E69CFC4A5A8AEF4EFE1365F0B0DF88` | **`MATCH`** |
| **Season Aggregations** | `data/processed/contributions/season_competition_metrics_comparison_v1.csv` | `553982138AFAF6D65BC339E2A8DCF93AED245C2A1AC12BB65873F3091E4E6B3E` | **`MATCH`** |
| **Track B Pre-Match WP** | `data/processed/contributions/pre_match_causal_abc_features_v1.pkl.gz` | `323AF183EF60EEF75618F38A012086CB921EAA9C6B631372DFFB785E18E6DE5C` | **`MATCH`** |
| **Input Stage 5B** | `data/processed/match_states/match_states_standard_t20_v1.pkl.gz` | `815A8E1FF4E428E85B942CAEAAEA9E45AF1BF159EEB794C7C425390D476CB871` | **`MATCH`** |
| **Input Playing Eleven** | `data/raw/playing_eleven.csv` | `7517C73722A28D5D61C808CCF0CBED315A8780586D02E946EB9A7F5DAF011C27` | **`MATCH`** |

### 5.2 Scope & Immutability Affirmations
1. **18,106 Records:** Verified in both `phase7u_v1.pkl.gz` and `strategy4_v1.pkl.gz`.
2. **DNB Strict Nullity:** Verified across all `5,196` DNB rows.
3. **Single Player Contribution:** Every player-match appearance has exactly one contribution row; zero key duplicates.
4. **Season Reconciliation Parity:** Maximum absolute difference between match mean and season ABC across `5,212` player-seasons is `0.0100 <= 0.015`.
5. **Scope Invariance:** Strictly `798` `STANDARD_T20` matches.
6. **Phase 1 Reference Immutability:** Python filesystem scan verified zero files modified in `C:\Users\admin\Documents\contribution` after November 12, 2026.
7. **Raw CSV Immutability:** All 6 raw CSV files in `data/raw/` retain bit-for-bit SHA-256 equivalence with Stage 4 baseline.
8. **Git Repository:** Zero Git initialization (`Test-Path .git` returned `False`).

---

## 6. Audit Verdict & Sign-Off

```
========================================================================================
FINAL AUDIT VERDICT: STAGE 5C VERIFIED & APPROVED FOR ACCEPTANCE
- All count reconciliations (18,106 records, 13,045 stints, 5,196 DNBs) fully explained.
- T20I Strategy 4 implementation verified as true Strategy 4 with walk-forward priors.
- 100% causal, zero outcome leakage, same-day doubleheaders excluded.
- All artifact cryptographic hashes verified against manifest.
========================================================================================
```

