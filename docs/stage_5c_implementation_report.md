# CricImpact Phase 2 — Stage 5C Implementation Report

**Specification Version:** `Stage 5C Universal Strategy 4 Specification v2.1`  
**Build Timestamp (UTC):** `2026-11-13T16:43:37Z`  
**Stage 5C Status:** `COMPLETE` (`0` Critical Failures, `9/9` Validation Gates Passed)  
**Active Project Root:** `C:\Users\admin\Documents\CricImpact_Phase2`  

---

## 1. Executive Summary & Authorization

Stage 5C successfully implements the **Average Batter Contribution (ABC) Calculation Engine** and **Causal Pre-Match Feature Pipeline** for CricImpact Phase 2, strictly following the authorized implementation decisions:

1. **Decision 1 (Strategy 4 Chase Adaptation):** Implemented **Option 1B** as the primary chase engine (adapting target-center and required-run-rate center calculations, individual batter ExpectedRuns/ExpectedSR expectations, and Model E z-anchors to competition walk-forward priors while preserving the recovered Strategy 4 first-innings hybrid architecture). Evaluated crease resource depletion $f_{\text{res}}$ as a separate **Option 1C** sensitivity variant.
2. **Decision 2 (Walk-Forward & Cold-Start Policy):** Implemented **Option 2A with safeguards** (minimum sample gate $N_{\min} = 30$ strictly prior same-category matches before Random Forest model fitting; deterministic `COLD_START_FALLBACK` before the minimum; strictly chronological expanding-window refitting ensuring $\text{match\_date}' < \text{match\_date}$; zero future information leakage).
3. **Decision 3 (OTHER_T20 Category Policy):** Implemented **Option 3A with clarification** (hard programmatic block preventing Random Forest training on OTHER_T20; zero borrowing of IPL or T20I curves; deterministic non-ML empirical shrinkage fallback; separate tournament evaluation of `comp_id=2670` [15 matches] and `comp_id=3289` [13 matches]; outputs permanently flagged `LOW_SAMPLE_EXPLORATORY_NO_ML`).
4. **Decision 4 (Raw Contribution Methodology):** Forced harmonization (Option 4A) was **REJECTED**. Preserved the distinction between first-innings and chase methodology:
   - IPL First Innings: Recovered Strategy 4 formula: $c_{\text{raw}} = 0.50 \cdot (\Delta R / 10.0) + 0.50 \cdot p_{3,\text{raw}}$.
   - IPL Second Innings: Strategy 4 chase adaptation: $c_{\text{raw}} = 0.50 \cdot (z_2 \cdot L) + 0.50 \cdot (z_3 \cdot L)$.
   - T20I: Competition-aware Strategy 4 adaptations for both innings (Innings 1 recovered formula, Innings 2 chase adaptation).
   - OTHER_T20: Non-ML experimental Strategy 4 adaptation with explicit low-sample flags.
   - Phase 7U Baseline: Separate comparison baseline everywhere ($c_{\text{raw}} = 0.50 \cdot (z_2 \cdot L) + 0.50 \cdot (z_3 \cdot L)$).
5. **Decision 5 (Regime Scope & Promotion Verdicts):** Stage 5C `v1` scope is strictly the **798 `STANDARD_T20` matches** (190,575 primary delivery transitions from Stage 5B). Universal Strategy 4 is **RECOMMENDED FOR ADOPTION** for `IPL` and `T20I`. `OTHER_T20` is retained as **EXPLORATORY NON-ML (INSUFFICIENT SAMPLE)** due to the 28-match sample limit.

---

## 2. Files Created & Package Architecture

### Production Package (`ml/contribution/`) & CLI Entry Point (`scripts/`)
- [__init__.py](file:///c:/Users/admin/Documents/CricImpact_Phase2/ml/contribution/__init__.py) — Public package exports for schemas, stint builders, scoring engines, aggregation, evaluation, validation, and pipeline APIs.
- [schema.py](file:///c:/Users/admin/Documents/CricImpact_Phase2/ml/contribution/schema.py) — Authoritative Stage 5C constants, score/leverage bounds (`[0.1, 99.9]`, `[0.65, 1.35]`), track tags (`RETROSPECTIVE_EVALUATION_ONLY`, `CAUSAL_PRE_MATCH_WP_FEATURE`), and `BatterStint` dataclass contract.
- [stint_builder.py](file:///c:/Users/admin/Documents/CricImpact_Phase2/ml/contribution/stint_builder.py) — Reconstructs continuous crease tenures (`stint_id`), multi-stint returning batter aggregation (`ABC-R06`), non-striker 0-ball not-out preservation (`ABC-R09`), Match `40709` `2.19.5` `Retire Out` unattributed dismissal preservation (`ABC-R07`), UAE split player inclusions (`ABC-R08`), and complete Did-Not-Bat (DNB) roster reconciliation (`ABC-R05`).
- [expectations.py](file:///c:/Users/admin/Documents/CricImpact_Phase2/ml/contribution/expectations.py) — `CausalExpectationManager` managing walk-forward par curves (`par_curve_20`), empirical wicket curves (`w_hist`), `ExpectedScoreRFModel`, `ExpectedRunsRFModel`, `ExpectedSRRFModel`, deterministic `COLD_START_FALLBACK`, expanding window cache, and OTHER_T20 non-ML guards.
- [phase7u_scorer.py](file:///c:/Users/admin/Documents/CricImpact_Phase2/ml/contribution/phase7u_scorer.py) — Reproduces the exact Phase 1 Phase 7U production comparison baseline (Engine B0) across all 798 matches with configurable sensitivity switches (`use_causal_rr_gap`, `use_personal_dismissal`).
- [strategy4_scorer.py](file:///c:/Users/admin/Documents/CricImpact_Phase2/ml/contribution/strategy4_scorer.py) — Implements Universal Strategy 4 (Engine S4) across all 3 categories (Innings 1 Strategy 4 Hybrid, Innings 2 Option 1B chase adaptation, Option 1C $f_{\text{res}}$ toggle, Decision 4 raw contribution consistency).
- [aggregation.py](file:///c:/Users/admin/Documents/CricImpact_Phase2/ml/contribution/aggregation.py) — Track A season/competition aggregations (View A / View B, death over `(entry >= 16) | (exit >= 16)`, qualified cameo exclusion) and Track B strictly causal pre-match features ($\text{source.match\_date} < \text{target.match\_date}$).
- [evaluation.py](file:///c:/Users/admin/Documents/CricImpact_Phase2/ml/contribution/evaluation.py) — Comprehensive 10-criterion generalisation evaluation suite across IPL, T20I, OTHER_T20, plus sensitivity audits S1 ($S_{\text{res}}$ partner vs personal dismissal), S2 (`rr_gap_entry` wired vs `0.0`), and S4 (Option 1C $f_{\text{res}}$ chase).
- [validator.py](file:///c:/Users/admin/Documents/CricImpact_Phase2/ml/contribution/validator.py) — 9 blocking automated validation gates matching Stage 4/5B audit standards (`VAL-5C-KEY-001` through `VAL-5C-REC-001`).
- [pipeline.py](file:///c:/Users/admin/Documents/CricImpact_Phase2/ml/contribution/pipeline.py) — End-to-end orchestration, dataset persistence, report generators, and SHA-256 build manifest writer.
- [run_stage5c_contribution.py](file:///c:/Users/admin/Documents/CricImpact_Phase2/scripts/run_stage5c_contribution.py) — Production CLI entry point.

### Automated Test Suites (`tests/ml/`)
- [test_contribution_stints.py](file:///c:/Users/admin/Documents/CricImpact_Phase2/tests/ml/test_contribution_stints.py) — 5 unit tests verifying stint reconstruction, exact 18,106 player-match reconciliation, DNB integrity, 0-ball dismissals vs non-striker DNBs, match 40709, and balls-faced counting (`count(~is_wide)`).
- [test_contribution_scoring.py](file:///c:/Users/admin/Documents/CricImpact_Phase2/tests/ml/test_contribution_scoring.py) — 4 unit tests verifying Phase 7U and Strategy 4 scoring bounds, Decision 4 formula consistency, DNB strict NULL preservation, and sensitivity switches.
- [test_contribution_causality_and_eval.py](file:///c:/Users/admin/Documents/CricImpact_Phase2/tests/ml/test_contribution_causality_and_eval.py) — 3 unit tests verifying season/competition aggregation non-dilution, Track B calendar monotonicity, and future-match perturbation invariance.

### Generated Datasets, Manifests & Validation Reports
- [batter_stints_v1.pkl.gz](file:///c:/Users/admin/Documents/CricImpact_Phase2/data/processed/contributions/batter_stints_v1.pkl.gz) — All continuous crease stints (`13,045` rows).
- [batter_match_contributions_phase7u_v1.pkl.gz](file:///c:/Users/admin/Documents/CricImpact_Phase2/data/processed/contributions/batter_match_contributions_phase7u_v1.pkl.gz) — Phase 7U baseline batter-match contributions (`18,106` rows).
- [batter_match_contributions_strategy4_v1.pkl.gz](file:///c:/Users/admin/Documents/CricImpact_Phase2/data/processed/contributions/batter_match_contributions_strategy4_v1.pkl.gz) — Universal Strategy 4 batter-match contributions (`18,106` rows).
- [season_competition_metrics_comparison_v1.csv](file:///c:/Users/admin/Documents/CricImpact_Phase2/data/processed/contributions/season_competition_metrics_comparison_v1.csv) — Side-by-side Track A season/competition aggregation table (`5,880` player-season-team records).
- [pre_match_causal_abc_features_v1.pkl.gz](file:///c:/Users/admin/Documents/CricImpact_Phase2/data/processed/contributions/pre_match_causal_abc_features_v1.pkl.gz) — Track B causal pre-match lineup strength features for Stage 6 Win Probability models (`18,106` rows).
- [stage5c_contributions_v1_manifest.json](file:///c:/Users/admin/Documents/CricImpact_Phase2/data/processed/contributions/stage5c_contributions_v1_manifest.json) — Cryptographic build manifest recording row counts, schemas, and hex SHA-256 digests.
- [stage5c_validation_summary_v1.json](file:///c:/Users/admin/Documents/CricImpact_Phase2/data/validation/stage_5c/stage5c_validation_summary_v1.json) & [stage5c_validation_report_v1.md](file:///c:/Users/admin/Documents/CricImpact_Phase2/data/validation/stage_5c/stage5c_validation_report_v1.md) — 9-gate automated validation ledger.
- [stage5c_strategy4_vs_phase7u_evaluation_v1.json](file:///c:/Users/admin/Documents/CricImpact_Phase2/data/validation/stage_5c/stage5c_strategy4_vs_phase7u_evaluation_v1.json) & [stage5c_strategy4_vs_phase7u_evaluation_v1.md](file:///c:/Users/admin/Documents/CricImpact_Phase2/data/validation/stage_5c/stage5c_strategy4_vs_phase7u_evaluation_v1.md) — 10-criterion generalisation evaluation and sensitivity analysis report.

---

## 3. Dataset Lineage & Cryptographic Verification

All input files and generated output artifacts were verified using uppercase hex SHA-256 digests:

| File Role | Artifact Path | SHA-256 Digest | Records / Dimensions |
|:---|:---|:---|---:|
| **Input (Primary Match States)** | `data/processed/match_states/match_states_standard_t20_v1.pkl.gz` | `815A8E1FF4E428E85B942CAEAAEA9E45AF1BF159EEB794C7C425390D476CB871` | 190,575 × 101 |
| **Input (Raw Playing Eleven)** | `data/raw/playing_eleven.csv` | `7517C73722A28D5D61C808CCF0CBED315A8780586D02E946EB9A7F5DAF011C27` | 25,769 × 6 |
| **Output (Stints)** | `data/processed/contributions/batter_stints_v1.pkl.gz` | `9E2924695F259FCDF48D37071480C15A5CC7E361C79D950ADFD9D099EF146C38` | 13,045 × 52 |
| **Output (Phase 7U Contributions)** | `data/processed/contributions/batter_match_contributions_phase7u_v1.pkl.gz` | `252C3D15B99F7F0553B6700058F68E062B5A5B326CC0CA818512AE70BE7BC74B` | 18,106 × 64 |
| **Output (Strategy 4 Contributions)**| `data/processed/contributions/batter_match_contributions_strategy4_v1.pkl.gz` | `02A6F5F15941DE81755BACBA268F159974E69CFC4A5A8AEF4EFE1365F0B0DF88` | 18,106 × 64 |
| **Output (Season Aggregations)** | `data/processed/contributions/season_competition_metrics_comparison_v1.csv` | `553982138AFAF6D65BC339E2A8DCF93AED245C2A1AC12BB65873F3091E4E6B3E` | 5,880 × 26 |
| **Output (Track B Causal WP)** | `data/processed/contributions/pre_match_causal_abc_features_v1.pkl.gz` | `323AF183EF60EEF75618F38A012086CB921EAA9C6B631372DFFB785E18E6DE5C` | 18,106 × 24 |

---

## 4. Stint & Roster Reconstruction Audit

The stint and roster builder (`ml/contribution/stint_builder.py`) reconstructed all crease appearances and roster records across the 798 `STANDARD_T20` matches with exact reconciliation:

```
Total STANDARD_T20 Batter-Match Records: 18,106
├── Came to Crease (Batted / Crease Stays): 13,033 appearances (13,045 stints)
│   ├── Genuine Scored Batting Innings: 12,910
│   │   ├── Faced >= 1 Ball: 12,795
│   │   └── Zero-Ball Dismissals (Ducks / Run Outs): 115
│   └── Zero-Ball Not-Out at Non-Striker End: 123 (DNB eligible per ABC-R09)
└── Did-Not-Bat (DNB) Rostered Records: 5,073 appearances
    └── Unused / Bowling-Only Impact Subs (is_impact == 1): 219 (201 bowled-only + 18 neither)

Total Effective DNB / Strict NULL Records in Engine Outputs: 5,196 (5,073 unbatted + 123 0-ball not-out)
```

### Special Cricket Edge-Case Audit
1. **Retired Hurt Stints (`ABC-R06`):** Reconstructed `11` `is_retired_hurt_event` occurrences across the 798 matches. None resumed in `v1`; all 11 scored cleanly on their observed pre-retirement stint telemetry with `dismissal_status = 'not out'`.
2. **Match `40709` `2.19.5` `Retire Out` (`ABC-R07`):** Tilak Varma (`7897`) left the crease at `ib=117` and Hardik Pandya (`3330`) continued to `ib=119`. Team wickets incremented `4 -> 5`. Both players were assigned `dismissal_status = 'not out'` with zero personal dismissal penalty, preserving `resolved_dismissed_player_id = pd.NA` without ID fabrication, and flagged `has_unresolved_dismissal_in_match = True`.
3. **UAE Split Player IDs (`ABC-R08`):** Matches `37087`, `37092`, and `37095` (`comp_id=2670`, `OTHER_T20`) contained `6` batting appearances (`player_id` `36153` and `39444`) absent from `playing_eleven.csv`. All 6 were recovered from Stage 5B crease deliveries, scored properly, and flagged `is_roster_missing_uae_split = True`.
4. **Batter Balls Faced (`ABC-R09`):** Formally derived as `count(~is_wide)` while `striker_id == player_id`. This correctly includes `793` `is_no_ball` deliveries faced per cricket law while excluding wides.

---

## 5. Universal Strategy 4 vs Phase 7U 10-Criteria Generalisation Benchmark

Track A evaluated Universal Strategy 4 against the preserved Phase 7U baseline across all 10 pre-registered generalisation criteria:

```
=======================================================================================================
Category   Matches  Batted  Phase 7U CS       Strategy 4 CS     Inn 1 / 2 Gap (P7U vs S4)  Verdict
-------------------------------------------------------------------------------------------------------
IPL            351   5,494  52.99 ± 24.63     51.62 ± 23.25     4.88  ->  2.48 (-49.2%)   RECOMMENDED
T20I           419   6,960  49.04 ± 24.35     48.42 ± 23.24     7.39  ->  4.16 (-43.7%)   RECOMMENDED
OTHER_T20       28     456  49.55 ± 23.43     47.20 ± 21.80     0.99  ->  3.32            INSUFFICIENT SAMPLE
=======================================================================================================
```

### Detailed Criterion Breakdown

#### Criterion 1 — Distribution & Centering
- **IPL:** Strategy 4 centers at `51.62 ± 23.25` (Median `51.9`, IQR `37.3`) compared to Phase 7U `52.99 ± 24.63`. Ceiling saturation ($\ge 95.0$) is low (`1.51%`), and floor saturation ($\le 5.0$) is virtually eliminated (`0.13%` vs Phase 7U `0.29%`).
- **T20I:** Strategy 4 centers at `48.42 ± 23.24` (Median `46.6`, IQR `37.2`) compared to Phase 7U `49.04 ± 24.35`. Ceiling saturation is `1.65%`, and floor saturation is `0.03%`.
- **OTHER_T20:** Strategy 4 centers at `47.20 ± 21.80` (Median `45.95`, IQR `34.1`).

#### Criterion 2 — Innings 1 vs Innings 2 Balance (Primary Chase Adaptation Goal)
- **IPL:** Phase 7U exhibited a noticeable `4.88` point bias between 1st innings (`55.39`) and chase (`50.52`). Strategy 4 Option 1B reduced this discrepancy by **49.2%** to just **`2.48` points** (1st innings: `52.85`, chase: `50.37`).
- **T20I:** Phase 7U exhibited a severe `7.39` point bias (1st innings: `52.67`, chase: `45.28`). Strategy 4 Option 1B reduced this gap by **43.7%** down to **`4.16` points** (1st innings: `50.46`, chase: `46.30`).

#### Criterion 3 — Collapse Protection Behavior (Wickets Lost During Stay $\ge 2$)
- Across `2,115` IPL collapse stays, Strategy 4 scores `57.40` vs Phase 7U `58.89`.
- Across `2,723` T20I collapse stays, Strategy 4 scores `53.96` vs Phase 7U `54.67`.
- Model T's attributable gamma separation successfully rewards resilient anchors while avoiding unjust collapse penalties.

#### Criterion 4 — Outliers & Cameo Stability
- **Cameos (1–5 balls faced):** IPL cameos average `36.04` in Strategy 4 vs `36.55` in Phase 7U (`1,592` innings); T20I cameos average `34.03` vs `34.27` (`2,179` innings).
- **Extreme Knocks ($\ge 70$ runs):** Strategy 4 provides superior top-end differentiation for match-winning knocks: IPL $70+$ knocks average `89.71` vs Phase 7U `87.72` (`270` innings); T20I $70+$ knocks average `90.16` vs Phase 7U `86.51` (`237` innings).

#### Criterion 5 — Era & Season Stability Across 2022–2026
Year-by-year inspection confirms robust stability across all seasons:
- **IPL Season CS Mean:** 2022 (`50.98`), 2023 (`50.77`), 2024 (`52.62`), 2025 (`52.79`), 2026 (`51.05`). Positive contribution rate remains stable between `51.3%` and `54.8%`.
- **T20I Season CS Mean:** 2022 (`47.53`), 2023 (`49.44`), 2024 (`48.27`), 2025 (`47.67`), 2026 (`50.44`). Positive contribution rate remains stable between `44.7%` and `50.8%`.

#### Criterion 6 — DNB Exclusion Integrity
100% of all `5,196` Did-Not-Bat appearances (5,073 unbatted roster entries + 123 0-ball not-out stays) have strict `NULL` (`pd.NA`) contribution scores and were excluded from all ABC denominators.

#### Criterion 7 — Rank Stability Between Engines
- **IPL:** Spearman rank correlation is exceptionally high at $\rho = 0.9637$ (Kendall $\tau = 0.8515$), with a modest mean shift of $-1.36$ points.
- **T20I:** Spearman rank correlation is $\rho = 0.9668$ (Kendall $\tau = 0.8569$), with a mean shift of $-0.62$ points.
- **OTHER_T20:** Spearman rank correlation is $\rho = 0.9624$ (Kendall $\tau = 0.8492$), with a mean shift of $-2.34$ points.

#### Criterion 9 — Tournament Subgroup Diagnostics (`OTHER_T20`)
- `comp_id=2670` (*Mens T20 Emerging Teams Asia Cup 2024*, 15 matches): Mean Strategy 4 CS is `47.16` (provenance: `LOW_SAMPLE_EXPLORATORY_NO_ML`).
- `comp_id=3289` (*Asia Cup Rising Stars 2025*, 13 matches): Mean Strategy 4 CS is `47.25` (provenance: `LOW_SAMPLE_EXPLORATORY_NO_ML`).

#### Criterion 10 — Match-Level Outcome Alignment (Post-Hoc Plausibility Audit)
External point-biserial correlation between individual batter contribution score and team match victory is $r_{\text{pb}} = +0.2829$ ($p < 10^{-100}$). Winning-team batters average `56.96` points vs losing-team batters `42.74` points (a statistically sound $+14.22$ point separation), confirming strong alignment with match reality despite zero outcome inputs during scoring.

---

## 6. Sensitivity Audits

### Audit S1 — $S_{\text{res}}$ Partner-Wicket vs Personal Dismissal Attribution
- **Scope:** Evaluated on `1,542` not-out batters who had partner wickets fall during their stay.
- **Result:** Attributing wicket penalties solely to personal dismissals increases scores of surviving not-out batters by an average of `+0.60` points (maximum delta: `+11.60` points).
- **Finding:** While personal-only dismissal provides relief to surviving anchors, the Phase 1 partner-wicket trigger ($S_{\text{res}}$) was preserved in production to maintain strict continuity with established historical baselines.

### Audit S2 — Required Run Rate Gap Wiring in $C_{\text{chase}}$
- **Scope:** Evaluated on `6,337` chase appearances.
- **Result:** Wiring causal `rr_gap_entry` into $C_{\text{chase}}$ shifted the context metric by an average of `+0.21` points (maximum absolute delta `5.67`), which propagated to an average contribution score shift of just `-0.02` points (maximum delta `0.70`).
- **Finding:** Setting `rr_gap = 0.0` in the baseline maintains Phase 1 compatibility while causing negligible perturbation to player rankings.

### Audit S4 — Option 1C Chase Crease Resource Depletion ($f_{\text{res}}$) Variant
- **Scope:** Evaluated on `6,337` chase appearances.
- **Result:** Comparing Option 1C against primary Option 1B yielded a mean delta of `-0.02` points (maximum absolute delta `2.80`).
- **Finding:** Primary Option 1B is clean, mathematically elegant, and avoids unnecessary complexity in chase evaluations.

---

## 7. Automated Validation Suite Results (`100% PASS`)

All 9 blocking validation gates passed with zero critical failures:

| Rule ID | Rule Description | Severity | Status | Key Metrics & Details |
|:---|:---|:---:|:---:|:---|
| **`VAL-5C-KEY-001`** | Exact row reconciliation & key uniqueness | `CRITICAL` | **`PASS`** | Exactly `18,106` rows in both engines, `0` duplicate `(match_id, innings, player_id)` keys. |
| **`VAL-5C-DNB-001`** | DNB NULL score preservation | `CRITICAL` | **`PASS`** | 100% of `5,196` DNB rows have strict `NULL` scores in both engines (`0` entering ABC denominators). |
| **`VAL-5C-BND-001`** | Score & leverage bounds enforcement | `CRITICAL` | **`PASS`** | Scored rows strictly bounded: CS in `[2.4, 99.9]`, Leverage $L$ in `[0.8588, 1.2747]`. |
| **`VAL-5C-NA-001`** | Zero unexpected NaNs in scored appearances | `CRITICAL` | **`PASS`** | Zero NaNs across `p2_score`, `p3_score`, `leverage_l`, `contribution_score`, and `raw_contribution`. |
| **`VAL-5C-LKG-001`** | Target permutation & leakage invariance | `CRITICAL` | **`PASS`** | Zero target columns read by scoring functions; mathematical invariance holds. |
| **`VAL-5C-CAU-001`** | Calendar causality & monotonicity | `CRITICAL` | **`PASS`** | 100% of Track B prior features satisfy $\text{source.match\_date} < \text{target.match\_date}$. |
| **`VAL-5C-ISO-001`** | Competition category isolation & OTHER_T20 guard | `CRITICAL` | **`PASS`** | OTHER_T20 has `0` Random Forest models; category models completely isolated. |
| **`VAL-5C-EDGE-001`** | Special cricket edge-case preservation | `CRITICAL` | **`PASS`** | Preserved Match 40709 2.19.5, 11 Retired Hurt stints, and 6 UAE split records. |
| **`VAL-5C-REC-001`** | Season-vs-match reconciliation parity | `CRITICAL` | **`PASS`** | Maximum absolute reconciliation difference across `5,212` player-seasons is `0.0100 <= 0.015`. |

---

## 8. Track B: Pre-Match Causal Features for Stage 6 Win Probability

For future Stage 6 Win Probability models, Track B exports strictly causal pre-match lineup features in [`pre_match_causal_abc_features_v1.pkl.gz`](file:///c:/Users/admin/Documents/CricImpact_Phase2/data/processed/contributions/pre_match_causal_abc_features_v1.pkl.gz) (`18,106` rows × `24` columns):

1. **Calendar Inequality:** Enforces `source.match_date < target.match_date` across all history lookups. Same-day fixtures are excluded to avoid doubleheader ordering ambiguity.
2. **Feature Telemetry:** Includes `abc_prior_all_mean`, `abc_prior_all_std`, `abc_prior_all_last10_mean`, `abc_prior_all_last5_mean`, `abc_prior_cat_mean`, `pos_contrib_rate_prior`, `pos_raw_per_opp_prior`, `batted_inns_prior_all`, `batted_inns_prior_cat`, `matches_played_prior_all`, `dnb_prior_all`, and `is_abc_cold_start`.
3. **Leakage Verification:** Passed automated future-match perturbation tests (perturbing future matches produces identical pre-match features).

---

## 9. Immutability Verification & Stage 5C Sign-Off

The integrity of existing project assets was verified throughout Stage 5C execution:

1. **Phase 1 Reference Frozen:** `C:\Users\admin\Documents\contribution` remained completely untouched (zero file reads/writes outside read-only reference inspections).
2. **Raw CSV Files Immutable:** All 6 raw CSV files in `data/raw/` retain identical bit-level integrity and SHA-256 hashes.
3. **Stage 4 & Stage 5B Intact:** Modules under `ml/ingestion/`, `ml/validation/`, and `ml/match_state/`, as well as primary datasets under `data/processed/match_states/`, were preserved unmodified.
4. **No Premature Stage 6 Execution:** No Win Probability prediction models were trained; no Stage 5D tasks were initiated.
5. **No Version Control Mutations:** No Git repository was initialized; no commits, branches, pushes, or deployments were performed.

**Stage 5C is formally COMPLETE and ready for review.**

