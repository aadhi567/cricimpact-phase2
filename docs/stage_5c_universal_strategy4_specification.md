# CricImpact Phase 2 — Stage 5C Revised Specification: Universal Strategy 4 ABC Evaluation & Causal Pre-Match Pipeline

**Document Status:** `APPROVED FOR IMPLEMENTATION (STAGE 5C AUTHORIZED)`  
**Specification Version:** `Stage 5C v2.1 (Final Authorized Decisions Included)`  
**Companion Documents:**
- Phase 1 Methodology Recovery & Compatibility Audit: [`stage_5c_abc_methodology_recovery.md`](file:///c:/Users/admin/Documents/CricImpact_Phase2/docs/stage_5c_abc_methodology_recovery.md)
- Detailed Implementation Plan & Sign-Off Record: [`stage_5c_implementation_plan.md`](file:///c:/Users/admin/Documents/CricImpact_Phase2/docs/stage_5c_implementation_plan.md)
- Upstream Stage 5B Primary Dataset Contract: [`match_state_specification.md`](file:///c:/Users/admin/Documents/CricImpact_Phase2/docs/match_state_specification.md), [`stage_5b_final_verification_report.md`](file:///c:/Users/admin/Documents/CricImpact_Phase2/docs/stage_5b_final_verification_report.md)

---

## 1. Purpose, Scope & Research Hypothesis

### 1.1 Research Objective
Evaluate **Strategy 4** (`v8.5.1-strategy4-hybrid` evolved into a competition-aware, walk-forward engine) as a **universal Average Batter Contribution (ABC) methodology** across all three Phase 2 T20 competition categories:
- **`IPL`**: `351` matches (`84,815` deliveries: `43,895` Inn 1 / `40,920` Inn 2; `2022–2026`, `68–72` matches/year; Inn 1 mean `186.49`, std `35.32`; Inn 2 mean `172.18`, std `33.59`)
- **`T20I`**: `419` matches (`99,294` deliveries: `52,037` Inn 1 / `47,257` Inn 2; `2022–2026`, `56–109` matches/year; Inn 1 mean `171.42`, std `36.81`; Inn 2 mean `150.93`, std `34.18`)
- **`OTHER_T20`**: `28` matches (`6,466` deliveries: `3,418` Inn 1 / `3,048` Inn 2; `comp_id=2670` *Mens T20 Emerging Teams Asia Cup 2024* [`15` matches] and `comp_id=3289` *Asia Cup Rising Stars 2025* [`13` matches]; Inn 1 mean `155.46`, std `43.89`; Inn 2 mean `138.46`, std `31.57`)

Across all `798` `STANDARD_T20` matches (`190,575` primary transitions) in [`match_states_standard_t20_v1.pkl.gz`](file:///c:/Users/admin/Documents/CricImpact_Phase2/data/processed/match_states/match_states_standard_t20_v1.pkl.gz), Strategy 4 MUST **prove** rather than assume generalization against the preserved **Phase 7U Comparison Baseline** before being adopted as the official Phase 2 ABC methodology feeding downstream Stage 6 Win Probability modeling.

### 1.2 Immutable Boundaries & Protections
1. **Frozen Phase 1 (`C:\Users\admin\Documents\contribution`):** Read-only reference only; never modified or imported at runtime.
2. **Immutable Upstream Phase 2 Assets:** `data/raw/`, Stage 4 (`ml/ingestion/`, `ml/validation/`, `data/validation/stage4_*`), Stage 5A specifications (`docs/match_*`, `docs/win_*`, `docs/stage_5a*`), and Stage 5B outputs (`ml/match_state/`, `data/processed/match_states/`, `data/validation/stage_5b/`) remain completely unmodified.
3. **No Premature Stage 6 Modeling or Git:** Zero Stage 6 Win Probability model training and zero Git repository initialization/commits during Stage 5C.
4. **Match Regime Scope (`v1`):** Stage 5C evaluates the **`798` verified `STANDARD_T20` matches** (`1,596` innings, all verified at `innings_ball_limit = 120` legal balls). The `31` `REVISED_OVERS_DLS` matches (of which `16` Inn 1 and `9` Inn 2 lack verified raw ball limits) and `54` other non-primary matches remain excluded from `v1` evaluation unless explicitly commissioned as an isolated Workstream B slice later.

---

## 2. Locked Methodology Decisions (Approved Rules)

The following rules resolve Phase 1 code-vs-documentation discrepancies and Phase 2 data edge cases and are **mandatory across all Stage 5C engines**:

| Rule ID | Topic | Approved Specification | Reference |
|:---|:---|:---|:---|
| **`ABC-R01`** | **Contribution per Batting Opportunity** | `round(total_positive_raw_contribution / batting_innings, 4)` (`tot_pos_raw / n`, strictly $\ge 0$ when `batting_innings > 0`; `NULL` when `0`). | [`season_aggregation.py:290`](file:///c:/Users/admin/Documents/contribution/src/season_aggregation.py#L290) |
| **`ABC-R02`** | **Death Over Contextual Split** | `(entry_over >= 16.0) \| (exit_over >= 16.0)` (inclusive of batters entering in middle overs and batting into death overs). | [`season_aggregation.py:331`](file:///c:/Users/admin/Documents/contribution/src/season_aggregation.py#L331) |
| **`ABC-R03`** | **`rr_gap_entry` in $C_{\text{chase}}$** | Retain `rr_gap_entry = 0.0` inside baseline $C_{\text{chase}}$ (`compute_context_and_leverage()` parity), **plus** run an explicit sensitivity audit wiring actual causal `rr_gap_entry = required_rr_entry - team_rr_entry`. | [`contribution_framework.py:1150`](file:///c:/Users/admin/Documents/contribution/src/contribution_framework.py#L1150) |
| **`ABC-R04`** | **`S_res` Partner-Wicket Quirk** | Preserve `wicket_resource_change < 0` (`wickets_lost_during_stay > 0`) in compatibility parity runs, **plus** report a mandatory **sensitivity audit** comparing partner-wicket penalty vs personal-dismissal attribution (`is_personal_dismissal`) across `IPL`, `T20I`, and `OTHER_T20`. | [`contribution_framework.py:1430`](file:///c:/Users/admin/Documents/contribution/src/contribution_framework.py#L1430) |
| **`ABC-R05`** | **DNB & Impact Subs (`is_impact`)** | Rostered `is_played == 1` players who never batted (`5,073` across `798` matches), including **`219` unused or bowling-only `is_impact == 1` Impact Subs** (`201` bowled-only + `18` neither), receive **`NULL` (`pd.NA`)** for all contribution metrics and **never** enter `batting_innings` or the ABC denominator. Only `is_played == 1` (plus Stage 5B crease batters) form `matches_played`; bench `is_played == 0` (`7,669` rows) are excluded. | Verified raw [`playing_eleven.csv`](file:///c:/Users/admin/Documents/CricImpact_Phase2/data/raw/playing_eleven.csv) (`18,100` `is_played==1`: `13,027` batted + `5,073` DNB) |
| **`ABC-R06`** | **`Retired Hurt` Stints** | Reconstruct each continuous crease tenure (`stint_id`) so hiatus deliveries, runs, and partner wickets never enter a returning batter's stay telemetry; then **aggregate returning stints cleanly into one batter-match contribution** (`SUM(runs)`, `SUM(balls_faced)`, `SUM(boundaries)`, hiatus-free resource/EFS deltas, terminal dismissal status). Non-resuming stints (`11 / 11` events in `STANDARD_T20`) score on observed stint telemetry ending at retirement (`not out`). | Stage 5B `11` `is_retired_hurt_event` rows (`0` resumed in `v1`) |
| **`ABC-R07`** | **Match `40709` `2.19.5` `Retire Out`** | Preserve `resolved_dismissed_player_id = pd.NA` and `is_dismissed_player_unresolved = True` with zero ID fabrication. Team wickets increment `+1` (`4 -> 5`). Neither crease batter (`3330` nor `7897`) is assigned a personal dismissal penalty (`dismissal_status = 'not out'`, `has_unresolved_dismissal_in_match = True`); `7897`'s crease stay cleanly ends at `ib=117`. | [`stage_5b_final_verification_report.md`](file:///c:/Users/admin/Documents/CricImpact_Phase2/docs/stage_5b_final_verification_report.md#L188-L198) |
| **`ABC-R08`** | **UAE Split Player IDs** | Matches `37087, 37092, 37095` (`comp_id=2670`, `OTHER_T20`) contain `6` `(match_id, player_id)` batting appearances (`player_id in {36153, 39444}`) absent from `playing_eleven.csv`. Always form match batter-roster union as `union(playing_eleven[is_played==1], stage5b_crease_batters)` so all `6` crease appearances (`13,033` total batted + `5,073` DNB = `18,106` rows) are scored properly and flagged `is_roster_missing_uae_split = True`. | Stage 5B `has_uae_split_player_id` + empirical audit |
| **`ABC-R09`** | **Batter Balls Faced & Boundaries** | Derive `balls_faced = count(~is_wide)` while `striker_id == player_id` (includes `793` `is_no_ball` deliveries per cricket law; differs from `is_legal_delivery`). Derive `fours = count(batter_runs == 4)` and `sixes = count(batter_runs == 6)` (avoids `is_boundary_four/six` anomalies). Zero-ball dismissals (`balls_faced == 0 & dismissal_status == 'out'`) are scored; non-striker DNB does not exist if present at crease (`0`-ball not out at non-striker end still counts only if `balls_faced == 0 and runs == 0 and status != 'out'` -> inspect empirically!). | Stage 5B schema & §11 item 7 of recovery audit |
| **`ABC-R10`** | **Zero Same-Match Outcome Dependence** | Scoring functions MUST NOT inspect `won_match`, `win_team_id_raw`, `target_batting_team_win`, `target_home_team_win`, or `matches.result`. Only post-hoc validation audits compare ABC against match outcomes. | Stage 5C leakage contract |

> **Sub-rule note on non-striker `0`-ball `not out` crease appearances:** Across Stage 5B, if a batter stands at the `non_striker_id` end without facing a single legal or no-ball (`balls_faced == 0`, `actual_runs == 0`, `dismissal_status == 'not out'`, e.g., end of 20th over / target chased from the other end), rule `ABC-R09` follows Phase 1 exact eligibility (`balls_faced == 0 and actual_runs == 0 and dismissal_status != 'out'` $\implies$ treated identically to non-scoring DNB / `NULL` unless explicitly flagged). Exact empirical count of any `0`-ball non-striker appearances in the `798` matches will be logged during `stint_builder` execution!

---

## 3. Stint-to-Batter-Match Grain Construction (`Stage 5C Layer 1`)

### 3.1 Input Lineage
Stage 5C constructs batter appearances solely from:
1. [`match_states_standard_t20_v1.pkl.gz`](file:///c:/Users/admin/Documents/CricImpact_Phase2/data/processed/match_states/match_states_standard_t20_v1.pkl.gz) (`190,575 × 101`, `798` matches)
2. [`playing_eleven.csv`](file:///c:/Users/admin/Documents/CricImpact_Phase2/data/raw/playing_eleven.csv) (`25,769` filtered rows; `18,100` `is_played == 1`)
3. [`teams.csv`](file:///c:/Users/admin/Documents/CricImpact_Phase2/data/raw/teams.csv), [`matches.csv`](file:///c:/Users/admin/Documents/CricImpact_Phase2/data/raw/matches.csv), [`competitions.csv`](file:///c:/Users/admin/Documents/CricImpact_Phase2/data/raw/competitions.csv) (competition metadata & team ID provenance only)

### 3.2 Exact Entry & Exit State Reconstruction
For each `(match_id, innings)` ordered strictly by `innings_ball_num = 1..M`:
1. A player `p` is **on-crease** at delivery `d` iff `p in {striker_id, non_striker_id}`.
2. A new continuous **stint** starts at the earliest delivery `d_start` after an interval where `p` was NOT on-crease (either initial entry or return after `Retired Hurt`).
3. A stint ends at delivery `d_end` where `p` is dismissed (`is_wicket_event & resolved_dismissed_player_id == p`), retires hurt (`is_retired_hurt_event & resolved_dismissed_player_id == p`), exits on `40709` `2.19.5` or stops appearing before subsequent deliveries (`max contiguous block`), or the innings concludes.
4. **Entry State** (evaluated immediately **before** delivery `d_start`):
   - `entry_legal_balls = legal_balls_completed_before[d_start]`
   - `entry_over_notation = (entry_legal_balls // 6) + (entry_legal_balls % 6) / 10.0` *(RF compatibility only)*
   - `entry_over_decimal = entry_legal_balls / 6.0` *(math/gates)*
   - `entry_team_score = score_before[d_start]`
   - `entry_wickets_lost = wickets_lost_before[d_start]`, `entry_wickets_remaining = 10 - entry_wickets_lost`
   - `entry_balls_remaining = legal_balls_remaining_before[d_start]` (`120 - entry_legal_balls`)
   - `entry_team_rr = entry_team_score * 6.0 / entry_legal_balls` (`0.0` if `entry_legal_balls == 0`)
   - Innings 2 only (`pd.NA` in Innings 1):
     - `target_runs = target_runs[d_start]`
     - `runs_required_entry = runs_required_before[d_start]`
     - `required_rr_entry = 0.0` if `runs_required_entry <= 0` else `(runs_required_entry * 6.0 / entry_balls_remaining if entry_balls_remaining > 0 else pd.NA)`
     - `rr_gap_entry = required_rr_entry - entry_team_rr` *(kept `0.0` inside baseline $C_{\text{chase}}$ per `ABC-R03`, logged verbatim for sensitivity)*
5. **Exit State** (evaluated immediately **after** delivery `d_end`):
   - `exit_legal_balls = legal_balls_completed_after[d_end]`
   - `exit_over_notation`, `exit_over_decimal`, `exit_team_score = score_after[d_end]`, `exit_wickets_lost = wickets_lost_after[d_end]`, `exit_wickets_remaining = wickets_remaining[d_end]`, `exit_balls_remaining = legal_balls_remaining[d_end]`
   - `overs_spent = (exit_legal_balls - entry_legal_balls) / 6.0`
   - `team_runs_added = exit_team_score - entry_team_score`
   - `window_team_rr = team_runs_added / overs_spent` (`0.0` if `overs_spent == 0`)
   - `wickets_lost_during_stay = exit_wickets_lost - entry_wickets_lost`
   - Innings 2 exit chase deltas: `runs_required_exit = runs_required_after[d_end]`, `required_rr_exit = required_run_rate[d_end]`, `required_rr_change = required_rr_entry - required_rr_exit`, `rr_gap_exit = required_rr_exit - (exit_team_score * 6.0 / exit_legal_balls)`, `rr_gap_change = rr_gap_entry - rr_gap_exit`, `target_progress_change = (runs_required_entry - runs_required_exit) / target_runs`.
6. **Multi-Stint Aggregation Rule (`ABC-R06`):** If a batter has $\ge 2$ stints (returning after `Retired Hurt`), batting totals sum across stints, `entry_*` comes from Stint 1, `exit_*` comes from Final Stint, while `team_runs_added`, `overs_spent`, `wickets_lost_during_stay`, $\Delta\text{EFS}$, and $\Delta T_{\text{obs}}$ **sum only across active on-crease stints** so hiatus overs/wickets are strictly excluded.

---

## 4. Two-Track Evaluation & Feature Architecture

Stage 5C strictly separates **Track A (Methodology Evaluation Engines)** from **Track B (Causal Pre-Match ABC Features for Stage 6 WP)**:

```
Stage 5B Primary Dataset (798 matches, 190,575 deliveries) + playing_eleven.csv
   │
   ▼
[Layer 1] Stint & Roster Builder (13,033 batted + 5,073 DNB = 18,106 batter-match rows)
   │
   ├──► [TRACK A: Evaluation & Benchmarking — TAGGED RETROSPECTIVE_EVALUATION_ONLY]
   │       ├── Engine B0: Phase 7U Comparison Baseline (all 798 matches across IPL/T20I/OTHER_T20)
   │       ├── Engine S4: Universal Competition-Aware Strategy 4 (walk-forward per category)
   │       ├── Engine P1-Ref (Audit Only): Phase 1 IPL Reference Replay (IPL 351 matches)
   │       └── Sensitivity Audits: S_res partner-wicket vs personal; rr_gap_entry=0 vs causal
   │
   └──► [TRACK B: Causal Pre-Match WP Feature Pipeline — STRICT source.match_date < target.match_date]
           └── Expanding & rolling prior batter/lineup ABC features (zero same-match / future leakage)
```

---

## 5. Comparison Engines Specification (`Track A`)

### 5.1 Engine B0 — Preserved Phase 7U Comparison Baseline (`IPL`, `T20I`, `OTHER_T20`)
Reproduces Phase 1's active non-IPL / Phase 7U engine verbatim across all three categories:
- `expected_runs = round(1.25 * balls_faced, 1)`, `expected_sr = 125.0`
- `expected_final_entry = expected_final_exit = expected_final_change = trajectory_deviation_change = NaN`
- `P1` (`compute_context_and_leverage`, `rr_gap_entry = 0.0` per `ABC-R03`, dual-slope `0.48 / 0.38`, bounds `[0.65, 1.35]`)
- `P2` (`compute_pillar2_batter_performance`, Phase 1 empirical anchors `19.8/21.6`, `125/50`, `-0.068/1.029`)
- `P3`:
  - **Inn 1:** `compute_dampened_p3_raw(..., expected_final_change=NaN, trajectory_deviation_change=NaN)` (Phase 7U heuristic fallback) + State-Preservation Floor (`64.0`)
  - **Inn 2:** `compute_dampened_p3_raw(..., strategy="model_e")` (`F_chase` saturation + target `165.0` / RRR `8.25` anchors + Preservation Floor `64.0`)
- Harmonized vs Legacy `raw_contribution`: Pending **Decision #4** (`0.5*(z2*L + z3*L)` recommended).

### 5.2 Engine S4 — Universal Competition-Aware Strategy 4 (`IPL`, `T20I`, `OTHER_T20`)

Strategy 4 MUST maintain **strict metadata & calibration separation across `competition_category`**: IPL models/curves/anchors NEVER bleed into T20I or `OTHER_T20`, and vice versa.

#### 5.2.1 Chronological Walk-Forward Competition Expectations
For a match $m$ in category $c \in \{\text{IPL}, \text{T20I}, \text{OTHER\_T20}\}$ on calendar date $d_m$:
- **Strict Causal Training Pool:** $\mathcal{H}(c, d_m) = \{m' \in \text{STANDARD\_T20} : \text{cat}(m') = c \land \text{match\_date}(m') < d_m\}$. Same-day fixtures ($d_{m'} = d_m$) are excluded to prevent double-header / same-day intra-round ordering ambiguity.
- **Category-Specific Empirical References computed strictly from $\mathcal{H}(c, d_m)$:**
  1. `par_curve_20(c, b)`: Mean Innings 1 team `score_after` at `legal_balls_completed_after = b` (`b = 0..120`, monotone smoothed/interpolated if sparse), yielding `PAR_120(c) = par_curve_20(c, 120)`.
  2. `w_hist(c, b)`: Mean Innings 1 `wickets_lost_after` at legal ball `b` (`6`-ball grid interpolated `0..120`).
  3. **Walk-Forward EFS Model (`ExpectedScoreRFModel`):** Trained on completed 1st-innings end-of-over (`1..19`) states inside $\mathcal{H}(c, d_m)$ using Phase 1's exact `7` features (`current_team_runs`, `wickets_lost_so_far`, `wickets_remaining`, `overs_completed` in cricket `over.ball` notation OR decimal consistently — kept uniform inside Phase 2!), hyperparameters (`n_estimators=100, max_depth=12, min_samples_split=10, min_samples_leaf=5, random_state=42`), and terminal-exit override (`exit_balls_remaining == 0 or exit_wickets_lost >= 10 -> exit_team_score`).
  4. **Walk-Forward Batter Models (`ExpectedRunsRFModel`, `ExpectedSRRFModel`):** Trained on prior stints inside $\mathcal{H}(c, d_m)$ using Phase 1's `11` features (`n_estimators=100, max_depth=8, min_samples_split=20, min_samples_leaf=10`, SR fit restricted to `balls_faced > 0`, predictions clamped $\ge 0.0$).
  5. **Competition Anchors & Standardization (`P1`, `P2`, `P3`):** Replace fixed IPL 2008–2026 constants (`PAR_120 = 166.5`, `target_center = 165.0`, `rrr_center = 8.25`, `P2 (19.8, 21.6, 125.0, -0.068, 1.029)`, `P3 (0.159, 1.513)`) dynamically with competition-category walk-forward priors (shrinkage-stabilized during early cold-start matches; exact schedule governed by **Decision #2**).

#### 5.2.2 Cold-Start & Small-Sample Safeguard Protocol (`IPL` early-2022, `T20I` early-2022, `OTHER_T20` all 28)
- **Minimum Sample Gate (`N_min`):** No Random Forest model (`ExpectedScore`, `ExpectedRuns`, `ExpectedSR`) is ever fit when $|\mathcal{H}(c, d_m)| < N_{\min}$ (proposed $N_{\min} = 30$ completed matches).
- **Mandatory `OTHER_T20` Rule:** `OTHER_T20` has only `15` matches in 2024 (`comp_id=2670`) and `13` matches in 2025 (`comp_id=3289`) — `max |\mathcal{H}| = 15 < 30`. Therefore:
  - **NEVER** fit ML RF models on `OTHER_T20`.
  - **NEVER** import IPL or T20I RF models/pars into `OTHER_T20`.
  - Apply explicit non-ML deterministic fallback (`Decision #3` governs exact fallback vs formal abstention flag `INSUFFICIENT_SAMPLE_EXPLORATORY`), strictly flagged `expectation_regime = 'LOW_SAMPLE_NO_ML'`.

#### 5.2.3 Innings 1 & Innings 2 Scoring under Universal Strategy 4
- **Innings 1:** Full Strategy 4 Hybrid (`Model T` attributable $\Delta\text{EFS}_{\text{attr}}$, competition-specific $\kappa_{\text{entry}}$ around $\text{PAR}_{120}(c)$, crease resource depletion $f_{\text{res}}$ using $w_{\text{hist}}(c, b)$, soft-knee saturation $\Delta T_{\text{sat}}$ ($\tau_{\text{knee}}=12, \tau_{\text{scale}}=8$), acceleration, $S_{\text{res}}$, and State Preservation Floor calibrated against category par/run-rate).
- **Innings 2 (Chase):** Previously unimplemented in Phase 1 Strategy 4; governed by **Decision #1** (upgrading P1/P2/ExpectedRuns/ExpectedSR & Model E anchors to competition-aware walk-forward values, plus optional $f_{\text{res}}$ ablation).

---

## 6. Track B: Strictly Causal Pre-Match ABC Feature Specification

For Stage 6 Win Probability modeling, **Track B** exports historical player & lineup strength features computed solely from prior matches (`source.match_date < target.match_date`):

1. **Candidate Engine Conditioning:** Track B supports parameterizing the historical per-match ABC source (`Phase 7U` vs `Universal Strategy 4`); the canonical Stage 6 recommendation waits for Track A's 10-criterion validation verdict!
2. **Per `(match_id, player_id)` Prior Features (strictly `d_m' < d_m`):**
   - `abc_prior_all_mean`, `abc_prior_all_std`: Expanding mean/std of prior scored `contribution_score` across all prior `STANDARD_T20` appearances (`pd.NA` if `batted_inns_prior_all == 0`).
   - `abc_prior_all_last10_mean`, `abc_prior_all_last5_mean`: Rolling last-$k$ prior innings mean.
   - `abc_prior_cat_mean`: Expanding mean restricted to the **same `competition_category`** (`IPL` stays `IPL`, `T20I` stays `T20I`, `OTHER_T20` stays `OTHER_T20`) — preventing category mixing while allowing diagnostic comparison against cross-category `abc_prior_all_mean`.
   - `pos_contrib_rate_prior`, `pos_raw_per_opp_prior`, `batted_inns_prior_all`, `batted_inns_prior_cat`, `matches_played_prior_all`, `dnb_prior_all`, `is_abc_cold_start` (`batted_inns_prior_all == 0`).
   - **Shrinkage-Adjusted Bayesian Prior (`abc_prior_shrunk`):** Shrinks noisy low-$N$ estimates (`1–4` prior innings) toward category/cohort neutral par `50.0`:
     $$\text{ABC}_{\text{shrunk}} = \frac{n \cdot \overline{\text{ABC}}_{\text{prior}} + m_0 \cdot 50.0}{n + m_0}, \qquad m_0 = 5$$
3. **Zero Same-Match Leakage Guarantee:** Verified via automated causal assertion `max(source_match_date) < target_match_date` on `100%` of feature rows, plus future-perturbation invariance tests.

---

## 7. Approved Implementation Decisions (Final Authorized Policy)

All five previously open technical decisions are finalized and approved as follows:

1. **Decision 1 — Strategy 4 Second-Innings (Chase) Adaptation:**
   - **Primary Model (Option 1B Approved):** Adapt `P1` target-centre and required-run-rate-centre calculations; adapt `P2` ExpectedRuns, ExpectedSR, and z-anchor calculations; adapt `P3` Model E z-anchor calculations using competition-aware, strictly walk-forward expectations. Preserve the existing Strategy 4 first-innings methodology.
   - **Sensitivity Variant (Option 1C):** Evaluate $f_{\text{res}}$ as a separate Option 1C sensitivity variant in `evaluation.py`. Do NOT combine variants or silently replace the primary formula.
2. **Decision 2 — Walk-Forward and Cold-Start Policy:**
   - **Policy (Option 2A Approved with Safeguards):** Require at least 30 strictly prior same-category matches before fitting competition-specific historical expectations.
   - Use deterministic `COLD_START_FALLBACK` before the minimum.
   - Use strictly chronological refitting (`source.match_date < target.match_date`). Never include current-match or future information.
   - $N_{\min} = 30$ does **NOT** automatically authorize Random Forest training. RF models require separate adequate sample size, chronological validation, and leakage checks. If RF requirements are not satisfied, use the documented non-ML fallback.
3. **Decision 3 — OTHER_T20:**
   - **Policy (Option 3A Approved with Clarification):** Do not train a separate `OTHER_T20` Random Forest. Do not silently borrow IPL or T20I expectation curves. Preserve Phase 7U as the compatibility comparison baseline.
   - Evaluate an experimental non-ML Strategy 4 adaptation using empirical shrinkage only when statistically defensible.
   - Evaluate `comp_id = 2670` (*Mens T20 Emerging Teams Asia Cup 2024*, `15` matches) and `comp_id = 3289` (*Asia Cup Rising Stars 2025*, `13` matches) separately.
   - Mark low-sample outputs `LOW_SAMPLE_EXPLORATORY_NO_ML`. Do not claim universal Strategy 4 validation for `OTHER_T20` without sufficient evidence. Preserve uncertainty and fallback provenance in the output.
4. **Decision 4 — Raw Contribution Methodology:**
   - **Policy (Forced Harmonization REJECTED):** Do NOT implement Option 4A's forced formula harmonization. Preserve the distinction between first-innings and chase methodology:
     - **IPL First Innings:** Reproduce the recovered Strategy 4 methodology: $c_{\text{raw}} = \operatorname{round}\bigl(0.50 \cdot \frac{\text{run\_deviation}}{10.0} + 0.50 \cdot p_{3,\text{raw}},\; 4\bigr)$.
     - **IPL Second Innings:** Implement and validate the separate Strategy 4 chase adaptation: $c_{\text{raw}} = \operatorname{round}\bigl(0.50 \cdot (z_2 \cdot L) + 0.50 \cdot (z_3 \cdot L),\; 4\bigr)$.
     - **T20I:** Evaluate competition-aware Strategy 4 adaptations for both innings (first innings with Strategy 4 recovered formula, second innings with chase adaptation).
     - **OTHER_T20:** Evaluate only defensible experimental Strategy 4 adaptations with explicit low-sample flags.
     - **Phase 7U:** Remains a separate comparison baseline ($0.50 \cdot (z_2 \cdot L) + 0.50 \cdot (z_3 \cdot L)$ everywhere).
     - Keep Phase 1 IPL first-innings parity calculations as diagnostic outputs.
     - Universal methodology means a consistent evaluation framework with context-appropriate calculations, not necessarily one identical formula for every innings.
5. **Decision 5 — Regime Scope & Promotion Gates:**
   - **Scope:** Stage 5C `v1` uses the **`798` `STANDARD_T20` matches only** (excluding `31` `REVISED_OVERS_DLS` and other non-primary regimes).
   - **Evaluation Gates:** Evaluate `IPL`, `T20I`, and `OTHER_T20` independently. Treat numerical thresholds as evaluation criteria, not automatic proof of generalisation. `OTHER_T20` cannot be promoted through an $N \ge 30$ requirement when only 28 matches are available. Clearly distinguish validated, exploratory, and insufficient-evidence outcomes.

