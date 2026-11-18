# CricImpact Phase 2 — Stage 6A Revision 1: Target Variable Formulation & State Construction

**Document:** Stage 6A Target and State Construction Specification (Revision 1.0)  
**Status:** Approved Specification (Planning & Design Only — Stage 6A)  
**Author:** AI Architecture & Data Science Agent  
**Date:** November 2026  
**Project Root:** [`C:\Users\admin\Documents\CricImpact_Phase2`](file:///c:/Users/admin/Documents/CricImpact_Phase2)  
**Companion Documents:**
- [`stage_6a_win_probability_specification.md`](file:///c:/Users/admin/Documents/CricImpact_Phase2/docs/stage_6a_win_probability_specification.md)
- [`stage_6a_feature_dictionary.md`](file:///c:/Users/admin/Documents/CricImpact_Phase2/docs/stage_6a_feature_dictionary.md)
- [`stage_6a_training_and_evaluation_plan.md`](file:///c:/Users/admin/Documents/CricImpact_Phase2/docs/stage_6a_training_and_evaluation_plan.md)
- [`stage_6a_data_readiness_report.md`](file:///c:/Users/admin/Documents/CricImpact_Phase2/docs/stage_6a_data_readiness_report.md)
- [`stage_6a_risk_and_leakage_register.md`](file:///c:/Users/admin/Documents/CricImpact_Phase2/docs/stage_6a_risk_and_leakage_register.md)
- [`stage_6a_implementation_plan.md`](file:///c:/Users/admin/Documents/CricImpact_Phase2/docs/stage_6a_implementation_plan.md)
- [`stage_6a_revision_1_report.md`](file:///c:/Users/admin/Documents/CricImpact_Phase2/docs/stage_6a_revision_1_report.md)

---

## 1. Mathematical Formulation of Target Variables

Supervised machine learning requires unambiguous, leak-free target labels. In cricket, predicting match outcomes requires rigorous handling of perspective (batting vs bowling side) and reference frames (Home/Away or Team A/Team B).

### 1.1 Ground Truth Outcome Definition
Ground-truth match outcomes are derived from `matches.win_team_id` in `data/raw/matches.csv` (and preserved as `win_team_id_raw` in Stage 5B `match_states_standard_t20_v1.pkl.gz`).

Across the **798 STANDARD_T20 matches**, `win_team_id_raw` is **100% complete with 0 missing values** (`isna().sum() == 0`). Every match in the standard corpus was resolved decisively with a recognized winning team.

### 1.2 Primary In-Play Target: Batting Team Win (`target_batting_team_win`)
To ensure that state features (`score_before`, `wickets_remaining_before`, `current_run_rate_before`, and `runs_required_before`) always align with the perspective of the side taking action, the core training objective is formulated from the perspective of the **current batting team**:

$$y_{\text{bat}}(m, i, b) = \begin{cases} 
1 & \text{if } \text{batting\_team\_id}(m, i, b) = \text{win\_team\_id}(m) \\ 
0 & \text{if } \text{bowling\_team\_id}(m, i, b) = \text{win\_team\_id}(m) \\ 
\text{pd.NA} & \text{if } \text{win\_team\_id}(m) \text{ is NULL (Tied / No Result / Abandoned)} 
\end{cases}$$

- **Innings 1 Meaning:** $y_{\text{bat}} = 1$ denotes that the team batting first successfully defends its total.
- **Innings 2 Meaning:** $y_{\text{bat}} = 1$ denotes that the chasing team successfully reaches the target.
- **Empirical Class Balance in Standard Corpus:**
  - Innings 1 deliveries ($N = 99,350$): Batting team wins $49,641$ deliveries ($49.97\%$), loses $49,709$ deliveries ($50.03\%$).
  - Innings 2 deliveries ($N = 91,225$): Chasing team wins $43,884$ deliveries ($48.11\%$), loses $47,341$ deliveries ($51.89\%$).
  - Overall balance across all 190,575 standard deliveries is virtually 50/50 ($49.07\%$ batting team wins), preventing prior class-imbalance bias.

### 1.3 Match-Fixed Perspective Target: Home Team Win (`target_home_team_win`)
For UI presentation, tracking, and match-level evaluation, predictions are projected onto a fixed match frame:

$$y_{\text{home}}(m) = \begin{cases} 
1 & \text{if } \text{win\_team\_id}(m) = \text{home\_team\_id}(m) \\ 
0 & \text{if } \text{win\_team\_id}(m) = \text{away\_team\_id}(m) \\ 
\text{pd.NA} & \text{if } \text{win\_team\_id}(m) \text{ is NULL} 
\end{cases}$$

- **Class Balance:** Home team wins 416 matches ($52.13\%$) and loses 382 matches ($47.87\%$) across the 798 standard fixtures.

### 1.4 Dynamic Reference Conversion & Strict Complementarity
For any user-selected Team A (e.g. `home_team_id` or `team_batting_first_id`), the delivery-grain prediction $\hat{p}_{\text{bat}}(b) = \hat{P}(y_{\text{bat}} = 1 \mid \mathcal{S}_b)$ is converted deterministically:

$$\hat{P}(\text{Team A Wins} \mid \mathcal{S}_b) = \begin{cases} 
\hat{p}_{\text{bat}}(b) & \text{if } \text{batting\_team\_id}(b) = A \\ 
1.0 - \hat{p}_{\text{bat}}(b) & \text{if } \text{bowling\_team\_id}(b) = A 
\end{cases}$$

$$\hat{P}(\text{Team B Wins} \mid \mathcal{S}_b) = 1.0 - \hat{P}(\text{Team A Wins} \mid \mathcal{S}_b)$$

This conversion satisfies the fundamental probability axiom:
$$\forall b, \quad \hat{P}(\text{Team A Wins} \mid \mathcal{S}_b) + \hat{P}(\text{Team B Wins} \mid \mathcal{S}_b) \equiv 1.0000$$

---

## 2. Treatment of Non-Standard Match Regimes

The raw cricket dataset contains 883 matches across 7 distinct regimes established in Stage 5A. The Stage 6 Win Probability Engine applies explicit inclusion, exclusion, and quarantine policies:

| Match Regime | Matches | Eligible for Standard Training? | Target Status | Handling Policy |
| :--- | :---: | :---: | :---: | :--- |
| **`STANDARD_T20`** | **798** | **YES (`is_primary_wp_train_eligible = True`)** | Decisive (`1` or `0`) | Core training and evaluation corpus. Verified 20-over regulation without interruptions, revised targets, or scoring anomalies. |
| **`REVISED_OVERS_DLS`** | 31 | **NO** (`is_primary_wp_train_eligible = False`) | Decisive (`1` or `0`) | **Excluded from primary training.** Retained in an isolated secondary test slice (`is_dls_eval_slice_eligible = True`) to evaluate model robustness under rain reductions. |
| **`TIED_SUPER_OVER`** | 8 | **NO** (`is_primary_wp_train_eligible = False`) | Decisive (`1` or `0` post-SO) | Excluded from standard 20-over training. In regulation play, the 20th over ends tied ($P = 0.50$). Training on post-SO binary labels injects retrospective bias into regulation states. |
| **`NO_RESULT_ABANDONED`** | 16 | **NO** (`is_primary_wp_train_eligible = False`) | Unresolved (`pd.NA`) | Excluded completely. Contains 0 balls or minimal play. Binary classification targets are undefined. |
| **`INCOMPLETE_OR_UNRESOLVED`** | 4 | **NO** (`is_primary_wp_train_eligible = False`) | Incomplete | Excluded. Includes match `50407` (anomalous over sequence) and matches with unverified innings limits. |
| **`UNRECORDED_OVER_REDUCTION`**| 14 | **NO** (`is_primary_wp_train_eligible = False`) | Truncated | Excluded. Match truncated without official DLS target documentation. |
| **`MULTI_REGIME_COMPLEX`** | 12 | **NO** (`is_primary_wp_train_eligible = False`) | Mixed | Excluded. Confounding multiple anomalies (DLS + Super Over + unrecorded interruptions). |

**Mandatory Rule:** Under no circumstances may an un-won match, an abandoned fixture, or a match with an unverified ball limit be labeled as a loss ($0$) or a win ($1$). Unresolved matches are excluded from training to prevent severe target contamination.

---

## 3. Information State Construction

To prevent data leakage, training instances must represent valid temporal information states. We define three distinct operational state types across the match lifecycle:

```
                               Match Timeline
------------------------------------------------------------------------------------>
[Stage A State]             [Stage B State]                 [Live Delivery States]
Pre-Match Baseline          Post-Toss + Confirmed XI        Ball 0.1 to Finish
(T - 24h to T - 1h)         (T - 15m)                       (b = 1 ... N)
```

### 3.1 Pre-Match States (Strictly Two Stages: A and B)

1. **Stage A State ($\mathcal{S}_{\text{Pre-A}}$):**
   - Timing: Hours or days before match start ($T - 24\text{h}$ to $T - 1\text{h}$).
   - Information Set: Historical team ratings, venue scoring par, category baselines, unweighted squad ABC ratings.
   - Lineup & Toss: Completely unannounced.
2. **Stage B State ($\mathcal{S}_{\text{Pre-B}}$):**
   - Timing: Approximately 15 minutes before match start ($T - 15\text{min}$).
   - Pre-condition: **BOTH official playing XI AND toss information (winner + decision) MUST be confirmed.**
   - Information Set: $\mathcal{S}_{\text{Pre-A}} \cup$ Confirmed 11 players per side from `playing_eleven.csv`, lineup-aggregated prior ABC features, toss winner ID, toss decision (`bat` vs `field`), and designation of Batting First vs Bowling First sides.
   - If either lineup or toss is missing: Retain Stage A and mark Stage B as `PENDING`.
   - **There is NO Stage C pre-match prediction.**

### 3.2 Live Delivery-Grain States ($\mathcal{S}_b$)
For every delivery $b \in \{1, \dots, N\}$ in match $m$:
- The state $\mathcal{S}_b$ evaluates all features **strictly as of `_before` delivery $b$**.
- Specifically:
  - `score_before`: cumulative runs prior to delivery $b$.
  - `wickets_lost_before`: cumulative wickets prior to delivery $b$.
  - `legal_balls_completed_before`: legal deliveries completed prior to delivery $b$.
  - `runs_required_before`: target runs minus `score_before`.
- Features must NEVER include:
  - `batter_runs`, `extras_type`, `is_wicket_event` from delivery $b$.
  - `score_after` or `wickets_lost_after` of delivery $b$.
  - Any future delivery event $b+k$.
- The outcome target attached to $\mathcal{S}_b$ is the eventual final match winner $y_{\text{bat}}(m)$.

### 3.3 Mid-Innings Transition Mechanics
The transition between Innings 1 and Innings 2 is a critical structural boundary:
- **Trigger:** Innings 1 completes (either 120 legal balls bowled or 10 wickets lost).
- **Final Innings 1 Score:** $S_1 = \text{score\_after}$ on the final delivery of Innings 1.
- **Chase Target:** $T = S_1 + 1$ (deterministic in standard regulation matches).
- **Chase Resource Initialization:**
  - $R_{\text{req}} = T$.
  - $B_{\text{rem}} = 120$.
  - $W_{\text{rem}} = 10$.
  - $\text{RRR} = \frac{T}{20.0}$.
- **Probability Continuity Axiom:**
  The probability that Team 1 successfully defends its total at the end of Innings 1 must equal the probability that Team 2 fails its chase at the start of Innings 2:
  $$P(\text{Team 1 Wins} \mid \text{End of Innings 1}) \equiv 1.0 - P(\text{Team 2 Wins} \mid \text{Start of Innings 2})$$
  This guarantees a seamless transition across the innings break without discontinuous probability jumps.

### 3.4 Terminal Boundary States
At the exact conclusion of the match:
- If target achieved in Innings 2 ($R_{\text{req}} \le 0$): $P(\text{Chasing Team Wins}) \equiv 1.0000, \quad P(\text{Defending Team Wins}) \equiv 0.0000$.
- If 10 wickets lost or 120 balls completed with runs required $> 0$: $P(\text{Chasing Team Wins}) \equiv 0.0000, \quad P(\text{Defending Team Wins}) \equiv 1.0000$.

---

## 4. Delivery Clustering & Match-Level Grouping Rules

### 4.1 The Fundamental Clustering Problem
The primary standard dataset contains **190,575 delivery transitions across 798 matches** (average of $238.8$ deliveries per match).

**Critical Machine Learning Principle:**  
The 190,575 deliveries are **NOT independent observations**. They represent 190,575 correlated state transitions belonging to 798 discrete time series.

### 4.2 Rejection of Random Splitting
If standard random row-level splitting (e.g. `train_test_split(df, test_size=0.20)`) is applied:
1. Deliveries from the *same innings of the same match* will appear simultaneously in both the training set and the test set.
2. The model will memorize the target variable directly from neighboring deliveries, producing artificially inflated test AUC ($> 0.99$) and near-zero log loss.
3. When deployed on unseen future matches, the model will suffer catastrophic generalization collapse.

### 4.3 Mandatory Grouping and Splitting Contract
All dataset splitting and cross-validation must strictly respect **match-level clustering**:
1. **Never split deliveries from the same match:** All deliveries belonging to `match_id` $M$ must reside entirely in the Training set, entirely in the Validation set, or entirely in the Test set.
2. **Never split playing XI records from the same match:** All player records for match $M$ must share the match's split assignment.
3. **Temporal Partitioning:** Splits must be partitioned chronologically by `match_date`, guaranteeing that no training observation occurs after a validation or test observation.
