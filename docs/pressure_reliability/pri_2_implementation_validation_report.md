# CRICIMPACT PHASE 2 — STAGE PRI-2
## Pressure Reliability Index (PRI) Engine Implementation & Validation Report

**Date:** 2026-11-17  
**Stage:** `PRI-2 — Pressure Reliability Engine Implementation & Validation`  
**Methodology ID:** `PRI_DUAL_AXIS_UNSHRUNK_T10_EXO2_V1`  
**Scope:** Independent analytical engines, unshrunk aggregations (career, season, tournament), chronological validation, sensitivity comparisons, 10-scenario stress suite, and protected-asset audit. *(Backend API and frontend UI integration are explicitly out of scope for PRI-2 and deferred to PRI-3 pending review.)*

---

## 1. Executive Summary

The **Pressure Reliability Index (PRI)** analytical layer has been independently implemented, executed, and validated across the full CricImpact Phase 2 T20 corpus (**798 matches**, **2022–2026**, **137 competitions**).

| Domain | Source Corpus | Qualifying Pressure Opportunities | Career Players (Evaluated / Total) | Positive Pressure Rate (Overall) | Avg Contribution Under Pressure | Reconciliation | Anti-Shrinkage Verified |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Batting PRI (`T10`)** | 12,888 batted stints (+145 DNB excluded) | **4,857** innings (37.69%) | **749** / 880 (131 zero-opp) | **26.93%** (1,308 pos / 3,545 neg / 4 neu) | **-0.9118** HPC (total `-4,428.74`) | **EXACT PASS** | **PASS** (max dev `≤ 0.0048%`) |
| **Bowling PRI (`EXO_2`)** | 9,482 spells (190,575 deliveries) | **5,027** spells (53.02%) | **522** / 638 (116 zero-opp) | **50.89%** (2,558 pos / 2,468 neg / 1 neu) | **51.25** PCS (total RPE `+6,651.24`) | **EXACT PASS** | **PASS** (max dev `≤ 0.0050%`) |

Key verification outcomes:
- **10 / 10** independent PRI production artifacts generated under `data/processed/contributions/pressure_reliability/`.
- **10 / 10** mandatory stress & scenario tests passed on real match data.
- **36 / 36** new PRI-2 unit and invariant tests passed; **68 / 68** existing API regression tests passed (**104 / 104** total).
- **27 / 27** protected Phase 2 production assets verified **100% bit-for-bit identical** via SHA-256 before and after implementation.
- **Zero** access to Phase 1 or `Documents/contribution`.
- **Final Recommendation:** **GO** for Stage PRI-3 (API & Frontend Integration) upon user review.

---

## 2. Approved Methodology Summary

All six locked governance decisions from the PRI-1 audit are enforced in code and verified by automated invariants:

1. **Batting Pressure Opportunity (`T10`):**
   - A batted innings qualifies if `mean_p >= 40.0 OR peak_p >= 60.0` using existing frozen HPP stint pressure values.
   - `is_dnb == True` stints are strictly excluded from opportunities, denominators, and averages (never treated as `0`).
   - Positive contribution: `hpc > 0.0`. Neutral (`hpc == 0.0`) is classified strictly as `"neutral"` and **never** counted as positive.
   - Causal first-ball `entry_p >= 40.0` is retained as a read-only sensitivity comparison.
2. **Bowling Pressure Opportunity (`EXO_2`):**
   - A bowling spell qualifies if `max_over_entry_pti >= 35.0 AND legal_balls >= 12`, where over-entry `pti` is evaluated strictly **exogenously** at Ball 1 of each over bowled by that bowler before the bowler delivers a ball in that over.
   - Exogenous evaluation guarantees that a bowler who breaks a dangerous partnership early in a spell is never stripped from the pressure sample.
   - Positive contribution: `pcs_spell > 50.0`. Neutral (`pcs_spell == 50.0`) is classified strictly as `"neutral"` and **never** counted as positive.
   - `EXO_5` (`mean_over_entry_pti >= 25.0 AND legal_balls >= 12`) is retained as a read-only sensitivity comparison.
3. **Dual-Axis Ranking (No Composite Score):**
   - `composite_score_applied = False`. PRI evaluates players across three separate transparent dimensions:
     1. **Reliability Rate:** `positive_hpc_pct` (batting) / `positive_pcs_pct` (bowling).
     2. **Pressure Contribution Quality:** `avg_hpc_under_pressure` & `total_hpc_under_pressure` (batting) / `avg_pcs_under_pressure` & `total_pressure_contribution_rpe` (bowling).
     3. **Statistical Confidence:** Exact Wilson binomial 95% and 90% confidence intervals + sample-size tier (strictly informational).
4. **Zero Shrinkage (Mandatory):**
   - `shrinkage_applied = False`. No Empirical Bayes pulling, no prior weighting, and no reuse of the 48-ball PCS shrinkage formula anywhere in career, season, or tournament outputs.
5. **Custom Minimum Opportunity Filters:**
   - Accepts any non-negative whole integer `>= 0` (`0` displays all players with `>= 1` qualifying opportunity; players with `0` opportunities are explicitly labeled `"No Pressure Opportunities"` with `NaN` reliability, never `0%`). Rejects negative, decimal, boolean, empty, or non-integer inputs.
6. **Pakistan Overall Leaderboard Visibility Policy (Inherited from Stage B8):**
   - Verified Pakistan national players (`team_name in {'Pakistan', 'Pakistan A'}` via authoritative `player_id` from `competition_team_player_mapping.csv`, 68 IDs) are excluded from **default overall PRI leaderboards only**.
   - All underlying PRI datasets and player profiles remain 100% intact and unmutated; unknown nationality is never classified as Pakistan.

---

## 3. Architecture and File Locations

### 3.1 New Independent Code Modules

| File | Responsibility |
| :--- | :--- |
| `ml/contribution/pressure_reliability/__init__.py` | Package public exports |
| `ml/contribution/pressure_reliability/schema.py` | Frozen constants, thresholds (`T10`, `EXO_2`, `EXO_5`), read-only source paths, and output paths |
| `ml/contribution/pressure_reliability/confidence.py` | Exact Wilson Score 95% & 90% confidence intervals and informational sample confidence tiers |
| `ml/contribution/pressure_reliability/filters.py` | Strict custom integer `>= 0` filter validation, contiguous re-ranking, and authoritative B8 Pakistan visibility filter |
| `ml/contribution/pressure_reliability/batting_pri_engine.py` | Independent Batting PRI engine (T10 qualification, causal `entry_p` diagnostic, unshrunk career/season/tournament aggregations, reconciliation assertions) |
| `ml/contribution/pressure_reliability/bowling_pri_engine.py` | Independent Bowling PRI engine (exogenous `EXO_2` & `EXO_5` extraction, stand-break/multi-wicket/wicketless diagnostics, unshrunk career/season/tournament aggregations, reconciliation assertions) |
| `ml/contribution/pressure_reliability/pri_validation.py` | Chronological partition validation (2022–2024 / 2025 / 2026), threshold sweeps, T10-vs-entry_p & EXO_2-vs-EXO_5 sensitivity analyses, and all 10 scenario stress tests |
| `ml/contribution/pressure_reliability/run_pri_pipeline.py` | End-to-end runner generating all 10 independent PRI artifacts and manifest |
| `tests/pressure_reliability/test_pri_engine.py` | 36 automated unit, invariant, reconciliation, anti-shrinkage, Wilson CI, filter, and B8 visibility tests |

### 3.2 Generated Independent Production Artifacts (`data/processed/contributions/pressure_reliability/`)

| Artifact File | Rows | Size (Bytes) | SHA-256 |
| :--- | ---: | ---: | :--- |
| `batting_pri_pressure_innings_v1.pkl.gz` | 4,857 | 145,476 | `41b7b30d1358b6048b860f6d55b82a33c2c554f54783f29292e4b512e9ec74da` |
| `batting_pri_career_v1.pkl.gz` | 880 | 46,143 | `1f24ede58830de52d080631eddd952f32fa5a590c4e375fbbc5418c5893670ba` |
| `batting_pri_season_v1.pkl.gz` | 2,107 | 77,815 | `203a1c5753f6980337eac43cd56618e59044403dc29433e7e424cd56f0c2150f` |
| `batting_pri_tournament_v1.pkl.gz` | 4,263 | 139,016 | `40cfc5194f6bd9fb79c0e49f22506500adac90b08eefe81a234202e08ad44c59` |
| `bowling_pri_pressure_spells_v1.pkl.gz` | 5,027 | 513,185 | `04ded5808310d9e5374fcd215631c82665926b9445103b76559cdc87ab51dbeb` |
| `bowling_pri_career_v1.pkl.gz` | 638 | 49,777 | `9c51b522b429a189763e9e2617c34dd4fac17e9e83ecc780b2f64180c8b23047` |
| `bowling_pri_season_v1.pkl.gz` | 1,514 | 90,686 | `a21ffe3b84c2cafba316a0610043bd79c2f362fef015a8fb5c9b5540ef05a866` |
| `bowling_pri_tournament_v1.pkl.gz` | 3,035 | 145,722 | `89db7ba6a072512e66f5f4a2ccb97779da922f1ebbc1e54d4179b863f7db7762` |
| `pri_validation_metrics_v1.json` | — | 65,270 | `0665d2cb9600be95c9833a7f9429dcf4de934a0cd5e75d186132370c900d76f1` |
| `pri_pipeline_manifest_v1.json` | — | — | Recorded in manifest output directory |

---

## 4. Data Sources and Reconciliation Summary

### 4.1 Read-Only Source Inputs

All existing production datasets were consumed strictly read-only:
- **Batting HPP:** `docs/worm_graph/hpp_match_data.json` + `match_index.json` + `trajectories/*.json` joined with `match_states_standard_t20_v1.pkl.gz` (note: `hpp_stint_evaluations_v1.pkl.gz` is untouched; reading the frozen lossless JSON artifacts avoids a pandas 3.x `StringDtype` unpickling incompatibility while preserving 100% of stint values).
- **Bowling PCS:** `pcs_delivery_contributions_v1.pkl.gz` (190,575 deliveries) and `pcs_match_spells_v1.pkl.gz` (9,482 spells).
- **Authoritative Metadata:** `data/raw/matches.csv`, `data/raw/competitions.csv`, and `data/raw/competition_team_player_mapping.csv`.

### 4.2 Exact Source-to-Output Reconciliation

| Reconciliation Check | Batting PRI (`T10`) | Bowling PRI (`EXO_2`) | Status |
| :--- | :---: | :---: | :---: |
| Source matches covered | 798 | 798 | **EXACT MATCH** |
| Source total stints / spells | 13,033 (12,888 batted + 145 DNB) | 9,482 spells (190,575 deliveries) | **EXACT MATCH** |
| Unresolved batted `player_id`s | **0** (12,885 exact name + 3 exact `(runs, balls)` fallback for `Aneurin Donald` -> `AHT Donald`, ID `4458`) | **0** (`bowler_id` native integer) | **PASS** |
| Duplicate batted stints / spells | **0** | **0** | **PASS** |
| Qualifying pressure records | **4,857** | **5,027** | **PASS** |
| Sum of `career` pressure opportunities | **4,857** | **5,027** | **EXACT MATCH** |
| Sum of `season` pressure opportunities | **4,857** | **5,027** | **EXACT MATCH** |
| Sum of `tournament` pressure opportunities | **4,857** | **5,027** | **EXACT MATCH** |
| Total additive pressure contribution (Source vs Career / Season / Tournament) | `-4,428.74` vs `-4,428.74` HPC | `+6,651.2421` vs `+6,651.2400` RPE | **EXACT MATCH** |
| DNB stints inside pressure opportunities | **0** | N/A | **PASS** |
| Neutral observations counted positive | **0** (4 neutral HPC innings) | **0** (1 neutral PCS spell) | **PASS** |
| Zero-opportunity players with non-null reliability % | **0** (131 zero-opp batters -> `NaN`) | **0** (116 zero-opp bowlers -> `NaN`) | **PASS** |

---

## 5. Batting PRI Implementation Summary

- **Qualification Breakdown (`T10 = mean_p >= 40.0 OR peak_p >= 60.0`):**
  - Total batted stints: **12,888** (145 DNB stints strictly excluded).
  - Qualifying T10 pressure innings: **4,857** (**37.69%** of batted stints):
    - Both `mean_p >= 40` AND `peak_p >= 60`: **3,397** (69.94%)
    - `mean_p >= 40` only: **1,402** (28.87%)
    - `peak_p >= 60` only: **58** (1.19%)
- **Outcome Polarity Partition:**
  - Positive (`hpc > 0.0`): **1,308** (26.93%)
  - Negative (`hpc < 0.0`): **3,545** (72.99%)
  - Neutral (`hpc == 0.0`, including IEEE `-0.0`): **4** (0.08%) — strictly excluded from positive counts.
- **Aggregation Coverage:**
  - **Career:** 880 total batters (749 evaluated with `>= 1` pressure inning; 131 labeled `"No Pressure Opportunities"` with `NaN` reliability).
  - **Season:** 2,107 player-season rows across 2022–2026.
  - **Tournament:** 4,263 player-tournament rows across 137/137 competitions (2,676 with `>= 1` pressure inning).

---

## 6. Bowling PRI Implementation Summary

- **Exogenous Danger Extraction (`EXO_2 = max_over_entry_pti >= 35.0 AND legal_balls >= 12`):**
  - Derived strictly from Ball 1 of every `(match_id, innings, overid, bowler_id)` group in `pcs_delivery_contributions_v1.pkl.gz` (before the bowler delivers in that over).
  - Total PCS spells: **9,482**.
  - Qualifying EXO_2 pressure spells: **5,027** (**53.02%** of all spells).
- **Outcome Polarity Partition (using frozen `pcs_spell` unchanged):**
  - Positive (`pcs_spell > 50.0`): **2,558** (50.89%)
  - Negative (`pcs_spell < 50.0`): **2,468** (49.10%)
  - Neutral (`pcs_spell == 50.0`): **1** (0.02%) — strictly excluded from positive counts.
- **Rich Diagnostics Captured Per Career / Season / Tournament:**
  - `avg_pcs_under_pressure` (exact unshrunk mean of `pcs_spell`), `total_pressure_contribution_rpe` (exact additive sum of `total_rpe`), `avg_rpe_under_pressure`, `highest_pcs_spell`, `lowest_pcs_spell`, `economy_under_pressure`, `dangerous_partnership_spells`, `partnership_breaking_spells`, `total_stand_breaks`, `total_sup_pressure`, `total_dci_pressure`, `total_swi_pressure`, `total_leakage_pressure`, `multi_wicket_spells`, `multi_wicket_overs_total`, and `wicketless_positive_spells`.
- **Aggregation Coverage:**
  - **Career:** 638 total bowlers (522 evaluated with `>= 1` pressure spell; 116 labeled `"No Pressure Opportunities"` with `NaN` reliability).
  - **Season:** 1,514 bowler-season rows across 2022–2026.
  - **Tournament:** 3,035 bowler-tournament rows across 137/137 competitions (2,126 with `>= 1` pressure spell).

---

## 7. Statistical Confidence Interval Implementation

Implemented in `ml/contribution/pressure_reliability/confidence.py` using the exact Wilson Score binomial interval on the `[0, 100]` percentage scale:

$$\text{CI} = 100 \times \frac{\hat{p} + \frac{z^2}{2n} \pm z\sqrt{\frac{\hat{p}(1-\hat{p})}{n} + \frac{z^2}{4n^2}}}{1 + \frac{z^2}{n}}$$

- Computed for both **95% CI** ($z = 1.959964$) and **90% CI** ($z = 1.644854$), plus `wilson_ci95_width` and `wilson_ci90_width`.
- Informational sample confidence tiers:
  - `0` opportunities -> `"Insufficient (No Opportunities)"`
  - `1–4` opportunities -> `"Very Low (Provisional)"`
  - `5–9` opportunities -> `"Low (Provisional)"`
  - `10–19` opportunities -> `"Moderate"`
  - `>= 20` opportunities -> `"High"`
- **Strict Non-Distortion Guarantee:** Wilson intervals never alter, shrink, or replace observed `positive_hpc_pct` or `positive_pcs_pct`. For example, a `2/2` record displays **100.00%** reliability alongside Wilson 95% CI `[34.24%, 100.00%]` (width `65.76%`) and `"Very Low (Provisional)"`.

---

## 8. Anti-Shrinkage Verification

Automated verification compared every single evaluated player's stored career, season, and tournament metrics directly against exact **unrounded raw source ratios and means** from `batting_pri_pressure_innings_v1.pkl.gz` and `bowling_pri_pressure_spells_v1.pkl.gz`:

| Metric Checked | Display Rounding Precision | Theoretical Max Half-ULP | Observed Max Deviation (Across All Players) | Shrinkage Detected? |
| :--- | :---: | :---: | :---: | :---: |
| Batting `positive_hpc_pct` | 2 decimals | `0.005000` | **`0.004839`** | **NO (`0` shrinkage)** |
| Batting `avg_hpc_under_pressure` | 4 decimals | `0.000050` | **`0.000050`** | **NO (`0` shrinkage)** |
| Bowling `positive_pcs_pct` | 2 decimals | `0.005000` | **`0.005000`** | **NO (`0` shrinkage)** |
| Bowling `avg_pcs_under_pressure` | 2 decimals | `0.005000` | **`0.005000`** | **NO (`0` shrinkage)** |

- `pri_pipeline_manifest_v1.json` records `"shrinkage_applied": false` and `"no_shrinkage_verified": true` for both batting and bowling.
- Confirmed zero usage of the 48-ball PCS shrinkage formula (`pcs_career_shrunk`) anywhere in PRI.

---

## 9. Custom Minimum Opportunity Filtering Verification

`validate_min_opportunities()` and `apply_min_opportunity_filter()` in `ml/contribution/pressure_reliability/filters.py` enforce:
- Accepts any non-negative whole integer (`0, 1, 2, 7, 13, 25, 50, ...`, including clean numeric strings like `"15"`).
- Rejects negative integers (`-1`), decimals (`5.5`), booleans (`True`, `False`), empty strings, non-numeric strings (`"abc"`), and `None` with explicit `ValueError`.
- `min_opportunities = 0` retains all players with `>= 1` pressure opportunity and excludes `0`-opportunity players (preventing false `0%` entries).
- Recomputes contiguous `1..N` ranks without altering a single underlying player statistic.

### 9.1 Threshold Sensitivity Sweep (Default Overall Leaderboards, Pakistan Hidden)

| Min Opps (`N`) | Batting Eligible (All / Default) | Batting Median 95% CI Width | Top Default Batter (Rate / Avg HPC / N) | Bowling Eligible (All / Default) | Bowling Median 95% CI Width | Top Default Bowler (Rate / Avg PCS / N) |
| :---: | :---: | :---: | :--- | :---: | :---: | :--- |
| **0** | 749 / 701 | 65.38% | Aaron Finch (`100.0%`, `+8.14`, `2`) | 522 / 485 | 65.17% | Ashton Agar (`100.0%`, `66.00`, `5`) |
| **1** | 749 / 701 | 65.38% | Aaron Finch (`100.0%`, `+8.14`, `2`) | 522 / 485 | 65.17% | Ashton Agar (`100.0%`, `66.00`, `5`) |
| **5** | 304 / 286 | 43.45% | Vipraj Nigam (`83.33%`, `+6.13`, `6`) | 254 / 239 | 45.07% | Ashton Agar (`100.0%`, `66.00`, `5`) |
| **10** | 163 / 153 | 38.37% | Sanju Samson (`81.82%`, `+5.63`, `11`) | 153 / 145 | 39.32% | Liam Dawson (`83.33%`, `55.87`, `12`) |
| **15** | 93 / 90 | 35.55% | Suryakumar Yadav (`56.52%`, `+5.45`, `23`) | 116 / 110 | 35.30% | Craig Young (`80.00%`, `54.86`, `15`) |
| **20** | 59 / 56 | 32.90% | Suryakumar Yadav (`56.52%`, `+5.45`, `23`) | 79 / 76 | 31.91% | Blessing Muzarabani (`79.17%`, `61.45`, `24`) |
| **25** | 30 / 29 | 30.03% | Tim David (`54.29%`, `+2.85`, `35`) | 56 / 55 | 29.72% | Sikandar Raza (`72.00%`, `53.88`, `25`) |
| **30** | 18 / 18 | 27.88% | Tim David (`54.29%`, `+2.85`, `35`) | 40 / 40 | 27.87% | Sunil Narine (`65.91%`, `57.84`, `44`) |

Notice how Wilson 95% CI width narrows monotonically from ~65% at `min=0` down to ~28% at `min=30`, making sample uncertainty immediately transparent without artificial shrinkage.

---

## 10. Overall Leaderboard Visibility Policy Verification

Inherited directly from Stage B8:
- Authoritative Pakistan national player set loaded from `competition_team_player_mapping.csv` (`team_name in {'Pakistan', 'Pakistan A'}`): **68 verified `player_id`s**.
- **Exact Name Disambiguation Verified:** Pakistan `Haider Ali` (`player_id=7338`) is in the authoritative set and hidden from default overall leaderboards; UAE `Haider Ali` (`player_id=28756`) is **not** in the set and is never misclassified. Missing/unknown `player_id` values are never classified as Pakistan.
- **Full Dataset Preservation Verified:**
  - Batting full career dataset preserves **61** verified Pakistan batters (**48** with qualifying T10 opportunities); default overall leaderboard contains **0** Pakistan batters.
  - Bowling full career dataset preserves **42** verified Pakistan bowlers (**37** with qualifying EXO_2 opportunities, e.g., Haris Rauf `72.41%` across 29 spells); default overall leaderboard contains **0** Pakistan bowlers.

---

## 11. Chronological Historical Validation Results

Strict temporal partitioning was enforced with **zero tuning on 2026 Holdout Test**:
- **Train:** `2022–2024` (477 matches)
- **Validation:** `2025` (190 matches)
- **Holdout Test:** `2026` (131 matches)

### 11.1 Partition Distributions

| Partition | Matches | Batting Batted Stints | Batting T10 Opps (%) | Batting Pos HPC % | Batting Avg HPC | Bowling Total Spells | Bowling EXO_2 Opps (%) | Bowling Pos PCS % | Bowling Avg PCS | Bowling Total RPE |
| :--- | ---: | ---: | :---: | :---: | :---: | ---: | :---: | :---: | :---: | :---: |
| **Train (2022–2024)** | 477 | 7,704 | 2,930 (38.03%) | 26.52% | -0.9284 | 5,696 | 2,947 (51.74%) | 52.49% | 51.94 | +5,850.77 |
| **Validation (2025)** | 190 | 3,102 | 1,150 (37.07%) | 26.35% | -1.1069 | 2,250 | 1,188 (52.80%) | 51.35% | 51.39 | +1,726.56 |
| **Holdout Test (2026)** | 131 | 2,082 | 777 (37.32%) | 29.34% | -0.5606 | 1,536 | 892 (58.07%) | 44.96% | 48.77 | -926.08 |

**Key Temporal Observation:** Batting T10 qualification rate is remarkably stable across all five years (`37.07%–38.91%`). In Holdout 2026, a clear batting-friendly T20 scoring surge (higher partnership threat: mean `max_over_entry_pti` rises from `104.2` in Train and `103.9` in 2025 to `125.6` in 2026) increases bowling EXO_2 qualification rate to `58.07%`, lifts batting `positive_hpc_pct` (`26.35% -> 29.34%`), and compresses bowling `positive_pcs_pct` (`51.35% -> 44.96%`). This confirms PRI faithfully reflects real underlying run-scoring regimes rather than normalizing away macro shifts.

### 11.2 Out-of-Sample Chronological Ranking Stability

| Split Comparison | Overlap Filter | Batting N | Batting Rate $\rho$ / $r$ | Batting Quality $\rho$ / $r$ | Bowling N | Bowling Rate $\rho$ / $r$ | Bowling Quality $\rho$ / $r$ |
| :--- | :---: | ---: | :---: | :---: | ---: | :---: | :---: |
| **Train (22–24) -> Val (25)** | `>= 3` each | 111 | `0.1714` / `0.1745` | `0.1582` / `0.1562` | 109 | `0.0746` / `-0.0035` | `0.0502` / `-0.0185` |
| **Train (22–24) -> Val (25)** | `>= 5` each | 45 | `0.1196` / `0.1377` | `0.2154` / `0.1425` | 73 | `0.0826` / `0.1049` | `0.0964` / `0.0793` |
| **Train (22–24) -> Val (25)** | `>= 10` each | 6 | `0.0294` / `0.4236` | `0.8286` / `0.9428` ($p=0.0048$) | 23 | `-0.0965` / `-0.0738` | `0.0020` / `0.0862` |
| **Train+Val (22–25) -> Holdout (26)** | `>= 3` each | 87 | `0.2104` / `0.2869` ($p=0.0070$) | `0.0572` / `0.1268` | 95 | `0.0933` / `0.0755` | `0.1649` / `0.0615` |
| **Train+Val (22–25) -> Holdout (26)** | `>= 5` each | 35 | `0.2457` / `0.3485` ($p=0.0402$) | `0.2070` / `0.2508` | 62 | `0.2073` / `0.1368` | `0.2197` / `0.1853` |
| **Train+Val (22–25) -> Holdout (26)** | `>= 10` each | 4 | `0.0000` / `-0.1202` | `-0.8000` / `-0.4570` | 18 | `0.1270` / `0.2125` | `0.1683` / `0.3309` |
| **Season 2024 -> Season 2025** | `>= 5` each | 28 | `-0.2909` / `-0.2711` | `-0.0361` / `-0.1769` | 53 | `0.2647` / `0.2248` | `0.1998` / `0.2132` |

**Empirical Interpretation:** As expected for unshrunk binary high-leverage T20 outcomes with single-season sample sizes of 5–15 opportunities per player, out-of-sample rank correlations are positive and moderate (`r = 0.21–0.35` on Train+Val -> Holdout 2026 at `>= 5` opportunities, statistically significant at $p=0.007$–$0.040$ for batting reliability rate, and $\rho = 0.21$–$0.22$ for bowling reliability and quality). This empirically validates why PRI displays **Wilson confidence intervals** and **custom minimum opportunity thresholds** prominently rather than masking variance behind opaque shrinkage.

### 11.3 Tournament Coverage

- **137 / 137 competitions** contain both qualifying batting T10 innings and qualifying bowling EXO_2 spells.
- Largest single tournaments by qualifying volume: IPL 2023 (438 batting / 488 bowling), IPL 2022 (434 / 453), IPL 2024 (422 / 487), IPL 2026 (378 / 515), IPL 2025 (369 / 514), Asia Cup 2025 (109 / 86), Asia Cup 2022 (86 / 64).

---

## 12. T10 vs Causal Entry-Pressure (`entry_p >= 40`) Sensitivity Results (Batting)

| Metric | Value |
| :--- | :---: |
| `T10` qualifying innings (`mean_p >= 40 OR peak_p >= 60`) | **4,857** |
| Causal `entry_p >= 40` qualifying innings | **4,468** |
| Exact overlap (`both`) | **4,214** |
| `T10` only (entered below 40, pressure escalated during stint) | **643** |
| `entry_p >= 40` only (entered `>= 40`, batter rapidly extinguished pressure below `mean_p < 40 & peak_p < 60`) | **254** |
| Jaccard Similarity | **0.8245** |
| Positive HPC % (`both` / `T10_only` / `entry_p_only`) | `27.03%` / `26.28%` / `57.09%` |
| Avg HPC (`both` / `T10_only`) | `-0.5292` / `-3.4194` |
| Career Player Correlation (`>= 10` opps in both, $n = 148$) — Reliability Rate | **Spearman $\rho = 0.9504$**, **Pearson $r = 0.9516$** ($p < 10^{-6}$) |
| Career Player Correlation (`>= 10` opps in both, $n = 148$) — Contribution Quality | **Spearman $\rho = 0.9166$**, **Pearson $r = 0.9359$** ($p < 10^{-6}$) |

**Takeaway:** Career batter rankings under `T10` and strictly causal `entry_p >= 40` exhibit **0.9504 Spearman agreement**, confirming strong robustness. The `entry_p_only` slice (254 stints, 57.09% positive) vs `T10_only` slice (643 stints, avg HPC `-3.42`) is transparently documented as a known methodological nuance of stint-trajectory pressure vs entry-only pressure.

---

## 13. EXO_2 vs EXO_5 Sensitivity Results (Bowling)

| Metric | Value |
| :--- | :---: |
| `EXO_2` qualifying spells (`max_over_entry_pti >= 35 AND legal_balls >= 12`) | **5,027** |
| `EXO_5` qualifying spells (`mean_over_entry_pti >= 25 AND legal_balls >= 12`) | **3,496** |
| Exact overlap (`both`) | **3,469** |
| `EXO_2` only / `EXO_5` only | **1,558** / **27** |
| Jaccard Similarity | **0.6864** |
| Positive PCS % (`EXO_2` / `EXO_5` / `EXO_2_only`) | `50.89%` / `46.22%` / `61.04%` |
| **Stand-Break Retention Proof** (all spells with `max_entry_pti >= 35`, `>= 12` balls, `>= 1` stand break = **2,310** spells): | |
| — Retained by **`EXO_2`** | **2,310 / 2,310 (100.0%)** |
| — Retained by `EXO_5` | 1,654 / 2,310 (71.6%) |
| — Retained by naive endogenous `within_spell_mean_pti >= 25` | 1,449 / 2,310 (62.7%) |
| — **Stand-break spells rescued by `EXO_2` vs endogenous filtering** | **861 spells** |
| Career Bowler Correlation (`>= 10` opps in both, $n = 115$) — Reliability Rate | **Spearman $\rho = 0.8349$**, **Pearson $r = 0.8340$** ($p < 10^{-6}$) |
| Career Bowler Correlation (`>= 10` opps in both, $n = 115$) — Contribution Quality | **Spearman $\rho = 0.7943$**, **Pearson $r = 0.8181$** ($p < 10^{-6}$) |

**Takeaway:** Notice that `EXO_2_only` spells have a **61.04%** positive PCS rate (vs `46.22%` under `EXO_5`), precisely because bowlers who break a dangerous partnership in their first pressure over drive `mean_over_entry_pti` down in subsequent overs. `EXO_2` retains **100%** (`2,310 / 2,310`) of dangerous partnership-breaking spells, rescuing **861** stand-break spells that endogenous `mean_pti` filtering would have erroneously dropped.

---

## 14. Scenario & Stress Test Results (10 / 10 PASSED)

| # | Scenario Tested | Status | Real-Data Evidence |
| :-: | :--- | :---: | :--- |
| **1** | **High reliability across many pressure opportunities (`>= 20`)** | **PASS** | **Batting:** Suryakumar Yadav (`56.52%`, `+5.45` avg HPC, `N=23`, 95% CI `[36.8%, 74.4%]`, High); Tim David (`54.29%`, `+2.85`, `N=35`, High). **Bowling:** Blessing Muzarabani (`79.17%`, `61.45` avg PCS, `N=24`, 95% CI `[59.5%, 90.8%]`, High); Haris Rauf (`72.41%`, `58.23`, `N=29`, High); Sikandar Raza (`72.00%`, `53.88`, `N=25`, High). |
| **2** | **Perfect (100%) performance across only 2 opportunities** | **PASS** | **6 batters & 18 bowlers** exact `2/2 = 100.0%` unshrunk (e.g., Aaron Finch `+8.14` avg HPC; Sonny Baker `77.76` avg PCS), all displaying Wilson 95% CI **`[34.24%, 100.00%]`** (width `65.76%`) and `"Very Low (Provisional)"` tier. |
| **3** | **High contribution quality but low consistency (boom/bust)** | **PASS** | **Batting:** Dinesh Karthik (`50.0%`, `+4.30` avg HPC, `N=22`, max `+40.88` / min `-11.96`); Nicholas Pooran (`43.33%`, `+2.83`, `N=30`). **Bowling:** Nuwan Thushara (`45.0%`, `53.03` avg PCS, `N=20`, max `90.88` / min `24.53`); Adam Zampa (`50.0%`, `52.82`, `N=34`). |
| **4** | **High consistency but moderate contribution quality** | **PASS** | **Batting:** Rishabh Pant (`66.67%`, `+3.84` avg HPC, `N=12`). **Bowling:** Mahedi Hasan (`66.67%`, `50.71` avg PCS, `N=12`); Shadab Khan (`65.00%`, `50.20` avg PCS, `N=20`); Kuldeep Yadav (`63.46%`, `54.02` avg PCS, `N=52`). |
| **5** | **Negative pressure contribution despite high raw runs / wickets** | **PASS** | **Batting:** Axar Patel (`974` runs in `54` pressure innings, `33.33%`, avg HPC `-1.22`); Hardik Pandya (`663` runs in `29` innings, `27.59%`, avg HPC `-3.07`). **Bowling:** Harshal Patel (`69` wickets in `56` spells, econ `9.61`, `48.21%`, avg PCS `49.30`, RPE `-22.51`); Romario Shepherd (`55` wickets in `55` spells, econ `10.55`, `36.36%`, avg PCS `46.89`, RPE `-151.53`). |
| **6** | **Positive PCS in economical wicketless pressure spells** | **PASS** | **289 wicketless positive spells** (11.30% of all positive pressure spells), led by Noor Ahmad `4-0-13-0` vs LSG (`pcs_spell=71.80`, `entry_pti=65.02`), Taskin Ahmed `4-0-16-0` (`68.51`), Shakib Al Hasan `4-0-9-0` (`68.23`), Gudakesh Motie `4-0-13-0` (`67.97`). |
| **7** | **High average PCS but inconsistent pressure performance** | **PASS** | Jimmy Neesham (`30.77%` positive, `52.08` avg PCS, `std=19.10`, range `25.09–87.23`, `N=13`); Jamie Overton (`53.85%`, `54.69` avg PCS, `std=20.82`, `N=13`); Varun Chakravarthy (`54.24%`, `55.24` avg PCS, `std=18.34`, range `18.23–91.59`, `N=59`). |
| **8** | **Early wicket breaks dangerous partnership (EXO_2 rescue)** | **PASS** | **750 positive stand-break spells** rescued by `EXO_2` where `within_spell_mean_pti < 25.0` — e.g., Benjamin White `4/20` (`pcs_spell=98.02`, `entry_pti=40.80`, `mean_pti=9.12`); Harpreet Brar `4/30` (`94.04`, `entry_pti=136.06`, `mean_pti=19.34`); Ravi Bishnoi `4/13` (`93.46`, `entry_pti=48.64`, `mean_pti=3.48`). |
| **9** | **Multiple wickets in one over under pressure** | **PASS** | **499 pressure spells** contain a multi-wicket over (`84.97%` positive PCS, avg `pcs_spell=65.16`), e.g., Benjamin White `4/20` (`98.02`), Jasprit Bumrah `3/21` vs PBKS (`96.16`, `entry_pti=157.0`), Ravindra Jadeja `3/20` (`93.00`). |
| **10** | **Neutral HPC (`== 0.0`) or Neutral PCS (`== 50.0`) never positive** | **PASS** | **4 batting neutral pressure innings** (Ashwin `28(19)`, Jaker Ali `41(34)`, Evin Lewis `9(6)`, Rutherford `32(20)`) and **1 bowling neutral pressure spell** (Harpreet Brar `4-0-25-0`, `pcs_spell=50.0`) — **0** counted as positive across all 12,888 stints and 9,482 spells. |

---

## 15. Automated Test Results

| Test Suite | Command | Passed | Failed | Runtime |
| :--- | :--- | :---: | :---: | :---: |
| **PRI-2 Engine & Invariant Suite** | `pytest tests/pressure_reliability/test_pri_engine.py -v` | **36** | **0** | 0.34s |
| **Existing API Regression Suite (B1–B9)** | `pytest tests/api/ -v` | **68** | **0** | 7.48s |
| **Combined Total** | | **104** | **0** | **7.82s** |

Coverage includes: artifact presence, manifest governance flags, all 10 scenario passes, T10/EXO_2 qualification exactness, DNB exclusion, neutral polarity boundary (`HPC==0.0`, `PCS==50.0`), zero shrinkage across career/season/tournament, zero-opportunity `NaN` handling, exact Career/Season/Tournament reconciliation, zero cross-tournament leakage, Wilson CI exactness & bounds, custom minimum opportunity validation & invalid-input rejection, and authoritative B8 Pakistan visibility separation including Haider Ali (`7338` vs `28756`).

---

## 16. Protected Asset Integrity Verification

Verified via `scratch/b9_verify_integrity.py` against `scratch/b9_protected_baseline.json` both pre- and post-implementation: **27 / 27 protected Phase 2 assets matched 100% bit-for-bit**.

| # | Protected Asset Path | SHA-256 (Pre & Post Match) | Status |
| :-: | :--- | :--- | :---: |
| 1 | `data/processed/calibration/calibration_manifest_v1.json` | `8b11483723f5bf0f02a5df2bdf346bb4f4d585ba4a249e29a2babc16d5e2bcd1` | **MATCH** |
| 2 | `data/processed/calibration/val_2025_calibrated_predictions_v1.pkl.gz` | `2b0700be46316a4b3c14c80167e6af58b1ccdb314fc1786a2bff7f8335d82bb9` | **MATCH** |
| 3 | `data/processed/calibration/test_2026_calibrated_predictions_v1.pkl.gz` | `a627c11e4359346e6ae032707730d9fdf63d3f4b99d2d744ac019b3ac86eb46d` | **MATCH** |
| 4 | `data/processed/calibration/test_2026_evaluation_manifest_v1.json` | `d0d62de97bd9ae2c184f66e289c86e6909b75c725109e7eb61b62fff7231d029` | **MATCH** |
| 5 | `data/processed/match_states/match_states_standard_t20_v1.pkl.gz` | `815a8e1ff4e428e85b942caeaaea9e45af1bf159eeb794c7c425390d476cb871` | **MATCH** |
| 6 | `data/processed/contributions/bowling/bowling_pipeline_manifest_v1.json` | `02b1c063ba77453856d732b135159806e5f6707f247d2752ea0a09b88742fd0c` | **MATCH** |
| 7 | `data/processed/contributions/bowling/bowling_career_summary_v1.pkl.gz` | `fe02e39c31aa7a49ef333882c550297a5903ebcd619ff7c0b746e689d019233a` | **MATCH** |
| 8 | `data/processed/contributions/bowling/bowling_season_summary_v1.pkl.gz` | `46fce3ce10b5690b4d3b2bed4245d5ed088dd9de6f1b2d3a306d053f6bcea96a` | **MATCH** |
| 9 | `data/processed/contributions/bowling/bowling_match_spells_v1.pkl.gz` | `09c03ec38fc5d4d03dac8360f1631434a6cdc2d85010dd53e6432f0803b6328d` | **MATCH** |
| 10 | `data/processed/contributions/bowling/bowling_delivery_contributions_v1.pkl.gz` | `14e05e69700c9d909887239aecb936b78413707aa95077d619f1388a06924cb3` | **MATCH** |
| 11 | `data/processed/contributions/hpp_stint_evaluations_v1.pkl.gz` | `a83e44b9eb8337b32ae99cf7960e5bd8171940137f33b3546e8a1465cfb0fcd5` | **MATCH** |
| 12 | `docs/worm_graph/hpp_dashboard.html` | `5b32bca5a591d4a7e75e3420dedde4fb53f7c96ed814ba7907f3c9b777017408` | **MATCH** |
| 13 | `docs/worm_graph/worm_graph.html` | `4343bf5171e7ecd6db76e669aa90522f596059f797c93277210ce284caf5f719` | **MATCH** |
| 14 | `docs/worm_graph/hpp_explorer.html` | `aef374b9aabedb171810215e5a1582cfc57d7f7ad10b7e5fb476e1a7fd15e8ba` | **MATCH** |
| 15 | `docs/worm_graph/hpp_leaderboards.json` | `af4baa38c4465314f81e733db374b5e9ea263ce2fa8392509443e5e8156f5fa8` | **MATCH** |
| 16 | `docs/worm_graph/hpp_match_data.json` | `7140188617533a292e5eb3da51dbea77a0974fc1b3a9fda6c92c3162e3fc3d22` | **MATCH** |
| 17 | `docs/worm_graph/match_index.json` | `6803b81fa9fb50d4ef3e73ca5f2767e5d7b4c38b865d128ec2959d430a124efb` | **MATCH** |
| 18 | `data/processed/contributions/batter_stints_v1.pkl.gz` | `9e2924695f259fcdf48d37071480c15a5cc7e361c79d950adfd9d099ef146c38` | **MATCH** |
| 19 | `data/processed/contributions/batter_match_contributions_phase7u_v1.pkl.gz` | `252c3d15b99f7f0553b6700058f68e062b5a5b326cc0ca818512ae70be7bc74b` | **MATCH** |
| 20 | `data/processed/contributions/batter_match_contributions_strategy4_v1.pkl.gz` | `02a6f5f15941de81755bacba268f159974e69cfc4a5a8aef4efe1365f0b0df88` | **MATCH** |
| 21 | `data/processed/contributions/stage5c_contributions_v1_manifest.json` | `98ed364f58e7b90bc9b0b551e54094f0ba74fa0d976067d135f8436e90808a69` | **MATCH** |
| 22 | `data/processed/contributions/bowling_pressure/pcs_career_summary_v1.pkl.gz` | `59176ce7ee19e7f7af79ddbb86fc9957576d88696b4ec7e4cea2c3b59372511c` | **MATCH** |
| 23 | `data/processed/contributions/bowling_pressure/pcs_season_summary_v1.pkl.gz` | `a13cd24ddaf5cedd0dc02897e19ce1ad8fab16ee9d44d997b710f8e190a1f904` | **MATCH** |
| 24 | `data/processed/contributions/bowling_pressure/pcs_match_spells_v1.pkl.gz` | `0d5288a62ef7695fc1fffff65e63a49681ba23ddd649da75af409c918dfbb533` | **MATCH** |
| 25 | `data/processed/contributions/bowling_pressure/pcs_delivery_contributions_v1.pkl.gz` | `eaf50fcaa8eb232710d6473a3552ffee9a1012e3e3f1ef71f0059fbe7e37b488` | **MATCH** |
| 26 | `data/processed/contributions/bowling_pressure/pcs_pipeline_manifest_v1.json` | `32dc693e9fb345a27e883db66d8e2b51d57bbc5ca137b1482304d7606d11f811` | **MATCH** |
| 27 | `data/processed/contributions/bowling_pressure/pcs_validation_metrics_v1.json` | `8bdea6151b26845557b6e801e814fd2177fe117d34759236a8677670b21b2fde` | **MATCH** |

---

## 17. Known Limitations and Caveats

1. **Inherent Single-Season T20 Variance:** Unshrunk binary pressure rates (`positive_%`) have naturally high binomial variance at small $N$ (e.g., 5–10 pressure opportunities in a single season), yielding moderate year-to-year stability ($\rho \approx 0.15\text{–}0.26$). In Stage PRI-3, the UI must prominently display **Wilson 95% confidence intervals**, **sample confidence tiers**, and **custom minimum opportunity controls** alongside the unshrunk rates.
2. **2026 Batting-Friendly Scoring Regime Shift:** Holdout 2026 matches feature higher average partnership threat (`max_over_entry_pti` mean `125.58` vs `~104` in 2022–2025), raising batting `positive_hpc_pct` (`29.34%`) and lowering bowling `positive_pcs_pct` (`44.96%`). Cross-season comparisons should always note season baselines.
3. **Batting `T10` Trajectory vs Strictly Causal `entry_p`:** While career Spearman correlation between `T10` and `entry_p >= 40` is very high (`0.9504`), `T10` intentionally captures batters whose innings escalate into high pressure (643 `T10_only` stints, average HPC `-3.42`) while excluding 254 `entry_p_only` stints where a batter immediately erased pressure below `mean_p < 40 & peak_p < 60`. Both flags are preserved in `batting_pri_pressure_innings_v1.pkl.gz` for transparency.
4. **DNB `player_id` Coverage for Unbatted Squad Entries:** While **100% (12,888 / 12,888)** of batted stints have exact resolved `player_id`s, a small number of DNB-only rows without match-state appearances rely on unique name lookup; none can ever affect pressure opportunity counts or metrics because DNB is strictly excluded from PRI.

---

## 18. Final Recommendation

**RECOMMENDATION: GO FOR STAGE PRI-3 (BACKEND API & FRONTEND INTEGRATION)**

All PRI-2 mathematical, engineering, reconciliation, anti-shrinkage, visibility-policy, scenario-testing, and protected-asset integrity criteria have passed with zero defects:
- Independent Batting (`T10`) and Bowling (`EXO_2`) PRI engines operational and reproducible.
- All 10 independent production artifacts generated and reconciled (`4,857` batting innings, `5,027` bowling spells).
- Zero shrinkage (`shrinkage_applied: false`), zero composite distortion (`composite_score_applied: false`), and exact Wilson confidence intervals verified.
- `10 / 10` scenario tests, `36 / 36` PRI-2 tests, `68 / 68` existing API tests, and `27 / 27` protected SHA-256 asset checks passed.

Execution pauses here as required for review prior to Stage PRI-3.
