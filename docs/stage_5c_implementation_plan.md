# CricImpact Phase 2 — Stage 5C Implementation Plan: Universal Strategy 4 ABC Evaluation & Causal Pre-Match Pipeline

**Plan Status:** `APPROVED AND AUTHORIZED FOR IMPLEMENTATION`  
**Specification Reference:** [`stage_5c_universal_strategy4_specification.md`](file:///c:/Users/admin/Documents/CricImpact_Phase2/docs/stage_5c_universal_strategy4_specification.md) (`v2.1`)  
**Phase 1 Methodology Reference:** [`stage_5c_abc_methodology_recovery.md`](file:///c:/Users/admin/Documents/CricImpact_Phase2/docs/stage_5c_abc_methodology_recovery.md)  
**Primary Dataset Input:** [`match_states_standard_t20_v1.pkl.gz`](file:///c:/Users/admin/Documents/CricImpact_Phase2/data/processed/match_states/match_states_standard_t20_v1.pkl.gz) (`190,575 × 101`, `798` `STANDARD_T20` matches)

---

## 1. Inspected Baseline & Empirical Reconciliation

Inspection across Stage 5A Revision 1.1 docs, [`stage_5b_final_verification_report.md`](file:///c:/Users/admin/Documents/CricImpact_Phase2/docs/stage_5b_final_verification_report.md), [`stage_5c_abc_methodology_recovery.md`](file:///c:/Users/admin/Documents/CricImpact_Phase2/docs/stage_5c_abc_methodology_recovery.md), frozen Phase 1 scripts/models, and read-only queries against Phase 2 `STANDARD_T20` established the exact starting baseline:

| Metric / Slice | `IPL` | `T20I` | `OTHER_T20` | Total (`STANDARD_T20`) | Notes |
|:---|---:|---:|---:|---:|:---|
| **Matches** | `351` | `419` | `28` | **`798`** | `2022–2026`; `OTHER_T20` = `15` (`2670` [2024]) + `13` (`3289` [2025]) |
| **Deliveries** | `84,815` (`43,895` / `40,920`) | `99,294` (`52,037` / `47,257`) | `6,466` (`3,418` / `3,048`) | **`190,575`** | Verified `100%` against `120` legal ball cap |
| **Inn 1 Score Mean / Median / Std** | `186.49` / `187.0` / `35.32` | `171.42` / `171.0` / `36.81` | `155.46` / `153.5` / `43.89` | — | Sharp cross-competition & era shift vs Phase 1 IPL `166.5` |
| **Inn 2 Score Mean / Median / Std** | `172.18` / `172.0` / `33.59` | `150.93` / `150.0` / `34.18` | `138.46` / `144.0` / `31.57` | — | Phase 7U hardcoded `165.0` / `1.25` / `125.0` is mis-centered for all 3 |
| **Roster (`is_played == 1`)** | — | — | — | **`18,100`** | `13,027` batted + `5,073` DNB |
| **Impact Subs (`is_impact == 1`)** | `535` | `0` | `0` | **`535`** | `316` batted + **`219` DNB** (`201` bowled-only + `18` neither) |
| **UAE Split Crease Additions** | `0` | `0` | `6` | **`6`** | `matches 37087, 37092, 37095` (`comp_id=2670`), IDs `36153, 39444` missing from `playing_eleven` |
| **Total Player-Match Rows** | — | — | — | **`18,106`** | **`13,033` batted appearances + `5,073` DNB (`NULL`)** |
| **Special Events** | `40709` `2.19.5` `Retire Out` | `Retired Hurt` events | `3` UAE split matches | `11` RH, `1` unresolved ID | `0` returning `Retired Hurt` stints in `v1` (`11/11` `later_rows == 0`) |

All methodology rules **`ABC-R01` through `ABC-R10`** from [`stage_5c_universal_strategy4_specification.md`](file:///c:/Users/admin/Documents/CricImpact_Phase2/docs/stage_5c_universal_strategy4_specification.md) §2 are locked in.

---

## 2. Exact Files & Outputs to Be Created

All new code resides cleanly inside `ml/contribution/`, `scripts/`, and `tests/ml/`, leaving Stage 4, Stage 5A, Stage 5B, `data/raw/`, and frozen Phase 1 (`C:\Users\admin\Documents\contribution`) completely untouched.

### 2.1 Proposed Source Code (`ml/contribution/`) & Runner (`scripts/`)

| Path | Responsibility | Key Interfaces / Guarantees |
|:---|:---|:---|
| `ml/contribution/__init__.py` | Package surface & version tag (`Stage 5C v2`) | Exports pipeline, schema constants, and scorer functions |
| `ml/contribution/schema.py` | Output contracts, nullable dtypes, provenance enums | `BatterStintSchema`, `BatterMatchScoreSchema`, `SeasonMetricsSchema`, `PreMatchCausalABCSchema`, track labels (`RETROSPECTIVE_EVALUATION_ONLY` vs `CAUSAL_PRE_MATCH_WP_FEATURE`) |
| `ml/contribution/stint_builder.py` | Reconstruct stints, match-batter stays, & roster DNB union | Handles `~is_wide` balls, `batter_runs in {4, 6}`, `Retired Hurt` hiatus separation + multi-stint merge, `is_impact` DNB, `40709` `2.19.5` no-fabrication, `37087/37092/37095` UAE split preservation |
| `ml/contribution/expectations.py` | Competition-isolated causal expectations & Phase 7U baselines | Walk-forward `Par_20(c, b)`, `w_hist(c, b)`, `ExpectedScoreRF`, `ExpectedRunsRF`, `ExpectedSRRF` (`source.match_date < target.match_date`), cold-start `N_min` gate, `OTHER_T20` non-ML guard, `over.ball` consistency, optional isolated Phase 1 IPL reference comparator |
| `ml/contribution/phase7u_scorer.py` | Phase 7U baseline engine (`Engine B0`) | Exact P1/P2/P3 Model E & heuristic fallback across all `798` matches + `rr_gap_entry` & `S_res` sensitivity toggles |
| `ml/contribution/strategy4_scorer.py` | Universal Strategy 4 engine (`Engine S4`) | Competition-aware `Model T`, $\kappa_{\text{entry}}$, $f_{\text{res}}$, $\Delta T_{\text{sat}}$, Preservation Floor, Innings-2 adaptation (per Decision #1), `OTHER_T20` guard (per Decision #3), `rr_gap_entry` & `S_res` sensitivity toggles |
| `ml/contribution/aggregation.py` | View A/B Season & Causal Track B feature builders | Season/comp aggregation (`tot_pos_raw / n`, `(entry >= 16) \| (exit >= 16)` death gate, strict DNB exclusion) + Track B pre-match expanding/last-$k$/Bayesian-shrunk player & lineup ABC (`source.match_date < target.match_date`) |
| `ml/contribution/evaluation.py` | 10-criterion generalisation comparison & sensitivity suite | Compares `Strategy 4` vs `Phase 7U` across `IPL`, `T20I`, `OTHER_T20` + `S_res` partner-wicket audit + `rr_gap_entry` audit + Phase 1 IPL parity audit |
| `ml/contribution/validator.py` | Automated leakage, causality, boundary & parity validator | Runs deterministic validation checks (`PASS`/`WARNING`/`FAIL`) matching Stage 4/5B audit rigor |
| `ml/contribution/pipeline.py` | End-to-end deterministic runner & manifest emitter | Computes SHA-256 input/output digests, executes validation before persisting |
| `scripts/run_stage5c_contribution.py` | CLI runner for Stage 5C generation & evaluation | Thin CLI entrypoint invoking `ml.contribution.pipeline` |

### 2.2 Proposed Automated Test Modules (`tests/ml/`)

| Test File | Scope |
|:---|:---|
| `tests/ml/test_contribution_stints.py` | `~is_wide` vs `is_legal_delivery`, `0`-ball dismissals vs DNB vs `0`-ball non-striker, returning `Retired Hurt` hiatus isolation & match merge, `is_impact == 1` DNB `NULL`, `40709` `2.19.5` unattributed dismissal, `37087/37092/37095` UAE split union roster, `batter_runs in {4, 6}` boundary derivation |
| `tests/ml/test_contribution_scoring.py` | Phase 7U formula invariants, Strategy 4 formulas ($\kappa_{\text{entry}}, f_{\text{res}}, \Delta T_{\text{sat}}$, Model T $\gamma$, Preservation Floor), `[0.1, 99.9]` bounds, `over.ball` vs `overs_completed_decimal` guard, `rr_gap_entry` & `S_res` sensitivity toggles, `target_*` permutation invariance (`0.0` delta) |
| `tests/ml/test_contribution_causality_and_eval.py` | Future-match perturbation causality (`d_future` change yields `0` delta in prior matches), cross-category zero-contamination (`IPL` vs `T20I` vs `OTHER_T20`), `OTHER_T20` ML abstention guard (`N < 30`), season-vs-match reconciliation (`<= 0.005`), full synthetic E2E pipeline smoke test |

### 2.3 Proposed Versioned Output Artifacts

| Output Path | Grain / Contents | Track Tag / Protection |
|:---|:---|:---|
| `data/processed/contributions/batter_stints_v1.pkl.gz` | `(match_id, innings, stint_id, player_id)` + `5,073` DNB roster records | Base intermediate grain (`~18,106+` rows) |
| `data/processed/contributions/batter_match_contributions_phase7u_v1.pkl.gz` | `18,106` player-match scorecards (`13,033` batted + `5,073` DNB `NULL`) under Phase 7U baseline | `RETROSPECTIVE_EVALUATION_ONLY` |
| `data/processed/contributions/batter_match_contributions_strategy4_v1.pkl.gz` | `18,106` player-match scorecards (`13,033` batted + `5,073` DNB `NULL`) under Universal Strategy 4 | `RETROSPECTIVE_EVALUATION_ONLY` |
| `data/processed/contributions/season_competition_metrics_comparison_v1.csv` | `(player_id, season, competition_category, team_id, engine)` View A & View B metrics | `RETROSPECTIVE_EVALUATION_ONLY` |
| `data/processed/contributions/pre_match_causal_abc_features_v1.pkl.gz` | Track B `(match_id, team_id, player_id)` strictly pre-match (`d' < d`) causal ABC features (`all`, `same_category`, `last10`, `shrunk`, `is_cold_start`) | `CAUSAL_PRE_MATCH_WP_FEATURE` |
| `data/processed/contributions/stage5c_contributions_v1_manifest.json` | Input/output SHA-256 digests, config hash, decision flags, counts | Provenance manifest |
| `data/validation/stage_5c/stage5c_strategy4_vs_phase7u_evaluation_v1.md` & `.json` | Complete 10-criterion generalisation comparison across `IPL`, `T20I`, `OTHER_T20` + `S_res` & `rr_gap_entry` sensitivity audits + Phase 1 IPL reference comparison | Decision report |
| `data/validation/stage_5c/stage5c_validation_report_v1.md` & `.json` | Rule-by-rule Stage 5C validation summary (`PASS`/`WARNING`/`FAIL`) | Validation gate |
| `docs/stage_5c_implementation_report.md` | Final Stage 5C build summary & verified methodology recommendation | Stage summary report |

---

## 3. Step-by-Step Build Sequence (Post-Approval)

1. **Step 1 — Schema & Stint Builder (`schema.py`, `stint_builder.py`):** Implement exact delivery-to-stint aggregation and roster DNB reconstruction; pass `test_contribution_stints.py`; verify exact `13,033 + 5,073 = 18,106` partition and edge-case logs (`11` `Retired Hurt`, `219` `is_impact` DNBs, `6` UAE split batters, `40709` `2.19.5`).
2. **Step 2 — Causal Competition-Isolated Expectations (`expectations.py`):** Implement category-isolated chronological walk-forward curves (`Par_20`, `w_hist`), RFs (`ExpectedScore`, `ExpectedRuns`, `ExpectedSR`), cold-start `N_min` gate, `OTHER_T20` non-ML guard, and Phase 7U baseline baselines.
3. **Step 3 — Dual Scoring Engines (`phase7u_scorer.py`, `strategy4_scorer.py`):** Implement exact Phase 7U comparator and Universal Strategy 4 (per approved Decision #1, #3, #4) with sensitivity audit switches (`rr_gap_entry`, `S_res` personal vs partner wicket); pass `test_contribution_scoring.py`.
4. **Step 4 — Aggregations & Causal Track B (`aggregation.py`):** Build View A/B season-competition tables (`ABC-R01`, `ABC-R02`) and strictly pre-match causal player/lineup ABC tables (`d' < d`, zero same-match leakage).
5. **Step 5 — Evaluation, Validation & Orchestration (`evaluation.py`, `validator.py`, `pipeline.py`, `run_stage5c_contribution.py`):** Pass `test_contribution_causality_and_eval.py`, execute full `798`-match pipeline, generate the 10-criterion generalisation & sensitivity report across `IPL`, `T20I`, and `OTHER_T20`, and audit every gate before authoring `docs/stage_5c_implementation_report.md`.

---

## 4. Final Authorized Implementation Decisions

All five previously open technical decisions are finalized and approved as follows:

### Decision 1 — Strategy 4 Second-Innings Adaptation: Option 1B Approved
- **Primary Model (Option 1B):** Adapt `P1` target-centre and required-run-rate-centre calculations; adapt `P2` ExpectedRuns, ExpectedSR, and z-anchor calculations; adapt `P3` Model E z-anchor calculations using competition-aware, strictly walk-forward expectations. Preserve the existing Strategy 4 first-innings methodology.
- **Sensitivity Variant (Option 1C):** Evaluate $f_{\text{res}}$ as a separate Option 1C sensitivity variant in `evaluation.py`. Do NOT combine variants or silently replace the primary formula.

### Decision 2 — Walk-Forward & Cold-Start Policy: Option 2A Approved With Safeguards
- Require at least 30 strictly prior same-category matches before fitting competition-specific historical expectations.
- Use deterministic `COLD_START_FALLBACK` before the minimum.
- Use strictly chronological refitting (`source.match_date < target.match_date`). Never include current-match or future information.
- $N_{\min} = 30$ does **NOT** automatically authorize Random Forest training. RF models require separate adequate sample size, chronological validation, and leakage checks. If RF requirements are not satisfied, use the documented non-ML fallback.

### Decision 3 — OTHER_T20: Option 3A Approved With Clarification
- Do not train a separate `OTHER_T20` Random Forest.
- Do not silently borrow IPL or T20I expectation curves.
- Preserve Phase 7U as the compatibility comparison baseline.
- Evaluate an experimental non-ML Strategy 4 adaptation using empirical shrinkage only when statistically defensible.
- Evaluate `comp_id = 2670` (*Mens T20 Emerging Teams Asia Cup 2024*, `15` matches) and `comp_id = 3289` (*Asia Cup Rising Stars 2025*, `13` matches) separately.
- Mark low-sample outputs `LOW_SAMPLE_EXPLORATORY_NO_ML`.
- Do not claim universal Strategy 4 validation for `OTHER_T20` without sufficient evidence. Preserve uncertainty and fallback provenance in the output.

### Decision 4 — Raw Contribution Methodology: Forced Harmonization REJECTED
- Do NOT implement Option 4A's forced formula harmonization. Preserve the distinction between first-innings and chase methodology:
  - **IPL First Innings:** Reproduce the recovered Strategy 4 methodology: $c_{\text{raw}} = \operatorname{round}\bigl(0.50 \cdot \frac{\text{run\_deviation}}{10.0} + 0.50 \cdot p_{3,\text{raw}},\; 4\bigr)$.
  - **IPL Second Innings:** Implement and validate the separate Strategy 4 chase adaptation: $c_{\text{raw}} = \operatorname{round}\bigl(0.50 \cdot (z_2 \cdot L) + 0.50 \cdot (z_3 \cdot L),\; 4\bigr)$.
  - **T20I:** Evaluate competition-aware Strategy 4 adaptations for both innings (first innings with Strategy 4 recovered formula, second innings with chase adaptation).
  - **OTHER_T20:** Evaluate only defensible experimental Strategy 4 adaptations with explicit low-sample flags.
  - **Phase 7U:** Remains a separate comparison baseline ($0.50 \cdot (z_2 \cdot L) + 0.50 \cdot (z_3 \cdot L)$ everywhere).
  - Keep Phase 1 IPL first-innings parity calculations as diagnostic outputs.
  - Do not silently change the underlying methodology merely to force identical `raw_contribution` formulas. A universal methodology means a consistent evaluation framework with context-appropriate calculations, not necessarily one identical formula for every innings.

### Decision 5 — Regime Scope & Promotion Gates: STANDARD_T20 Scope Approved
- **Scope:** Stage 5C `v1` uses the **`798` `STANDARD_T20` matches only** (excluding `31` `REVISED_OVERS_DLS` and other non-primary regimes).
- **Evaluation Gates:** Evaluate `IPL`, `T20I`, and `OTHER_T20` independently. Retain the proposed pre-registered validation criteria as evaluation criteria, not automatic proof of generalisation. `OTHER_T20` cannot be promoted through a minimum $N \ge 30$ requirement when only 28 matches are available. Clearly distinguish validated, exploratory, and insufficient-evidence outcomes.

---

## 5. Risk Register & Mitigations

| Risk | Severity | Impact | Planned Mitigation |
|:---|:---|:---|:---|
| **Cold-Start Distribution Shift in Early 2022 (`IPL` & `T20I`)** | `HIGH` | Early 2022 matches use fallback expectations while late 2022–2026 use walk-forward RF + updated curves, creating regime discontinuities inside Season `2022` | Log `expectation_regime` (`COLD_START_FALLBACK` vs `WALK_FORWARD_COMP_RF`) on every row; check `2022` vs `2023–2026` drift explicitly in evaluation Criterion #5 & #9 |
| **`OTHER_T20` Severe Small Sample (`n = 28`, Std `43.89`)** | `HIGH` | Fitting ML or complex empirical curves on `13–15` matches overfits wildly (`Emerging Teams` `2670` & `Rising Stars` `3289`) | Hard programmatic block `assert N_prior >= 30` before any RF training; isolate `OTHER_T20` cleanly from `IPL`/`T20I`; flag low statistical power explicitly |
| **Cricket `over.ball` vs Decimal Overs Mixup (`VAL-5B` Risk)** | `HIGH` | Passing decimal `11.5` to cricket-notation splits (`11.3`) silently corrupts tree splits & over gates (`entry_over >= 16.0`) | Separate schema fields strictly (`entry_over_decimal` vs `entry_over_notation`); use continuous decimal inside Phase 2 math/walk-forward features (and only convert at frozen Phase 1 audit adapter boundary); unit test explicit ball-`3` / ball-`5` cases |
| **Temporal / Post-Match Leakage Into Track B WP Features** | `CRITICAL` | Same-day doubleheaders (`IPL`), exit-state leakage, or future par/z-anchors corrupt downstream Stage 6 WP validation | Enforce strict calendar cutoff `source.match_date < target.match_date`; assert `max(source_match_date) < target_match_date` in validator; run automated future-perturbation test |
| **UAE Split IDs (`37087, 37092, 37095`) Double-Counting / Drops** | `MEDIUM` | Naive inner join on `playing_eleven.csv` drops `6` real innings in `OTHER_T20`; naive outer join inflates DNB | Construct roster via deduplicated union `playing_eleven[is_played==1] ∪ stage5b_crease_batters`; reconcile exact total `18,106` (`13,033` batted + `5,073` DNB) |
| **`Retired Hurt` Returning Stints & `40709` `2.19.5` Misattribution** | `MEDIUM` | Merging returning stints across hiatus attributes partner wickets/runs scored off-crease; guessing `40709` ID fabricates dismissal | Reconstruct hiatus-free stints first (`stint_id`), merge per-stint deltas (`ABC-R06`), test synthetic multi-stint return case in pytest; enforce `resolved_dismissed_player_id == pd.NA` on `40709` (`ABC-R07`) |
| **`S_res` Partner-Wicket Quirk vs Personal Dismissal Bias** | `MEDIUM` | Penalizing not-out batters when a partner falls during their stay can skew `IPL` / `T20I` high-scoring stays (`ABC-R04`) | Run full side-by-side sensitivity audit (`partner_wicket` vs `personal_dismissal`) across all 3 categories in `evaluation.py` before final Stage 5C lock |

---

## 6. Proposed Validation & Generalisation Evaluation Methodology

### 6.1 Track A — Mandatory 10-Criterion Benchmark (`Strategy 4` vs `Phase 7U` across `IPL`, `T20I`, `OTHER_T20`)
`ml/contribution/evaluation.py` evaluates and reports all **10 criteria** separately for **`IPL` (`351`)**, **`T20I` (`419`)**, and **`OTHER_T20` (`28`)** (never pooled blindly):

1. **Pillar `P1`, `P2`, `P3` & `contribution_score` Distributions:** Mean, median, SD, IQR, skew, min/max, percentile quantiles (`p05, p25, p50, p75, p90, p95, p99`), and `% >= 95.0` / `% <= 5.0` ceiling/floor saturation rates (`Target: mean in [48, 52]`, reduced tail saturation).
2. **Innings 1 vs Innings 2 Score Balance:** Category-wise mean/median gap between 1st innings batting and 2nd innings chases (`|mean_inn1 - mean_inn2|`), plus variance ratio.
3. **Collapse Protection Behavior:** Stratify batters during multi-wicket collapses (`wickets_lost_during_stay >= 2` or `entry_wickets_lost >= 3`), comparing `Model T` Cat B (high-SR rescuers) vs Cat A (stagnators/caused), alongside `S_res` sensitivity impact (`ABC-R04`).
4. **High-Scoring & Low-Ball Outlier Stability:** Inspect distribution of tail cameos (`1 <= balls_faced <= 5`), `0`-ball dismissals, golden ducks, and `70+` / `200+ SR` extreme knocks (`220+` team totals in `IPL` 2024–2026).
5. **Era / Season Stability Across `2022–2026`:** Year-by-year mean/SD of `contribution_score` and `+ > 50` rate (`IPL` `2022..2026`; `T20I` `2022..2026`; `OTHER_T20` `2670 [2024]` vs `3289 [2025]`), isolating cold-start vs walk-forward periods.
6. **DNB Exclusion Integrity:** Exact proof of `5,073 / 5,073` strict `NULL` preservation (including `219` unused/bowling-only `is_impact == 1` subs), `0` DNB rows inside ABC denominators, and `368`-equivalent pure-DNB player-season preservation.
7. **Rank Stability & Extreme Anomaly Inspection:** Spearman $\rho$ & Kendall $\tau$ player ABC rank stability across `View A` and `View B` (`>= 5` and `>= 10` batted innings filters), plus top-10 biggest movers and top-10 extreme single-innings deltas (`Strategy 4 - Phase 7U`).
8. **Pre-Match Temporal Causality Proof:** Verify `max(source.match_date) < target.match_date` across `100%` of Track B features and `Par/w_hist/RF` walk-forward lookups, `0` outcome columns read, and exact invariance to target permutation.
9. **Competition-Specific Failure Modes:** Explicitly test `IPL` era inflation (`186.5` avg score vs `166.5` Phase 1 par + `is_impact` subs), `T20I` match heterogeneity (`Full Member` vs `Associate` heavy tails, std `36.81`), and `OTHER_T20` volatility & UAE split IDs (`n=28`, std `43.89`).
10. **Match-Level Plausibility & Outcome Alignment Audit (Post-Hoc Only):** Compare team summed positive raw contribution and top-batter contribution against `target_batting_team_win` (point-biserial correlation & winning-vs-losing team ABC separation — strictly as an external plausibility check, confirming zero outcome input).

### 6.2 Sensitivity Audits Included in Stage 5C Report
- **Audit S1 (`S_res` Partner-Wicket Attribution):** Compare Phase 1 partner-wicket trigger (`wickets_lost_during_stay > 0`) vs personal-dismissal-only trigger across `IPL`, `T20I`, and `OTHER_T20` (mean delta on not-out batters, top rank shifts).
- **Audit S2 (`rr_gap_entry` in $C_{\text{chase}}$):** Compare `rr_gap_entry = 0.0` (`compute_context_and_leverage()` baseline) vs causal `rr_gap_entry = required_rr_entry - entry_team_rr` on all `798` 2nd innings (score delta distribution in high/low chase gaps).
- **Audit S3 (`IPL` Phase 1 Compatibility Replay):** Audit Stage 5B `IPL` `351` matches under exact Phase 1 `166.5` constants/par vs `Phase 7U` vs `Universal Strategy 4` walk-forward RF to quantify the `2008–2026` vs `2022–2026` domain shift.

### 6.3 Automated Validation Gates (`ml/contribution/validator.py`)
Pipeline execution **fails cleanly without silent continuation** unless every `CRITICAL` gate passes:
- **`VAL-5C-KEY-001`:** Exact row reconciliation (`18,106` player-match = `13,033` batted + `5,073` DNB; zero duplicates on `(match_id, innings, player_id)`).
- **`VAL-5C-DNB-001`:** `100%` of `5,073` DNB rows (`219` `is_impact` DNBs included) have `pd.NA` in all contribution columns.
- **`VAL-5C-BND-001`:** `100%` of non-null `contribution_score`, `P2`, `P3`, `Adjusted_P2`, `Adjusted_P3` lie strictly within `[0.1, 99.9]`; leverage `L` strictly in `[0.65, 1.35]`.
- **`VAL-5C-NA-001`:** `0` unexpected `NaN`/`inf` values in scored stints (`13,033` batted rows).
- **`VAL-5C-LKG-001`:** Outcome permutation invariance (`delta == 0.0` when `win_team_id_raw` / `target_batting_team_win` shuffled).
- **`VAL-5C-CAU-001`:** Strict walk-forward & Track B calendar monotonicity (`source.match_date < target.match_date` everywhere; `0` same-day or future leaks).
- **`VAL-5C-ISO-001`:** Strict competition category isolation (training pool for category $c$ contains `0` matches outside $c$; `OTHER_T20` RF count == `0`).
- **`VAL-5C-EDGE-001`:** Verified exact preservation of `40709` `2.19.5` `resolved_dismissed_player_id == pd.NA`, `11` `Retired Hurt` events, `6` UAE split batters, and `~is_wide` vs `is_legal_delivery` balls faced.
- **`VAL-5C-REC-001`:** Season-vs-match reconciliation max difference `<= 0.005` on all non-null `average_contribution_score` rows.

---

## 7. Execution Authorization

**Status:** `STAGE 5C AUTHORIZED FOR EXECUTION`  
All five technical decisions have been finalized and approved by the user. Implementation proceeds under `ml/contribution/`, `tests/ml/`, and `scripts/`, generating versioned outputs under `data/processed/contributions/` and `data/validation/stage_5c/`. No models or outputs for Stage 5D or Stage 6 are created. Phase 1, raw CSVs, Stage 4, Stage 5A, and Stage 5B remain immutable.

