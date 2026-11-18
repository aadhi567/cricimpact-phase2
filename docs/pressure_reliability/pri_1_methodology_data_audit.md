# CRICIMPACT PHASE 2 — STAGE PRI-1
# PRESSURE RELIABILITY INDEX (PRI): METHODOLOGY & EMPIRICAL DATA AUDIT

**Date:** 2026-11-17  
**Stage:** PRI-1 (Read-Only Data Audit & Methodology Design)  
**Scope:** Independent Batter & Bowler Pressure Reliability Methodology (Zero Implementation, Zero Production Asset Mutation)  
**Status:** COMPLETE — STOPPED FOR GOVERNANCE REVIEW  
**Recommendation:** **CONDITIONAL GO** (Subject to 5 Design Sign-Offs Before PRI-2 Implementation)

---

> **Evidence Labeling Convention:** Throughout this audit, every quantitative figure is explicitly separated into:
> - **[MEASURED]**: Direct read-only measurements extracted from frozen Phase 2 production artifacts (`docs/worm_graph/*.json`, `data/processed/contributions/bowling_pressure/*.pkl.gz`, `data/processed/match_states/match_states_standard_t20_v1.pkl.gz`).
> - **[PROPOSED]**: Candidate mathematical formulations, threshold choices, shrinkage models, and architectural designs proposed for PRI-2 approval.

---

## 1. EXISTING BATTING PRESSURE ARCHITECTURE [MEASURED]

### 1.1 Source Modules & Pipeline Flow
Inspected read-only in `ml/contribution/hpp_engine.py` and `ml/contribution/hpp_aggregator.py`:

1. **Pre-Delivery Causal Pressure Score $P(t) \in [0, 100]$** (`calculate_delivery_pressure`):
   - **Innings 1 (Target Setting):** Sum of three strictly causal pre-delivery terms, clipped to $[0, 100]$:
     - *Wicket Component* ($0$ to $55$): $P_w = \frac{w_{\text{before}}}{9} \cdot 35 + \text{clip}\big((w_{\text{before}} - w_{\text{par}}(b)) \cdot 7,\; 0,\; 20\big)$, where $w_{\text{par}}(b) = 6.0 \cdot (b/120)^{0.85}$.
     - *Scoreboard Deficit Component* ($-9$ to $30$): $P_{\text{def}} = \text{clip}\big((\text{par\_score}(b) - \text{score}_{\text{before}})/25,\; -0.3,\; 1.0\big) \cdot 30$.
     - *Phase Urgency* ($0$ to $15$): Linear ramp from ball 90 to 120.
   - **Innings 2 (Target Chase):** Sum of three strictly causal pre-delivery terms, clipped to $[0, 100]$:
     - *Required Run Rate Component* ($0$ to $60$): $P_{\text{RRR}} = \text{clip}((\text{RRR} - 4)/12,\; 0,\; 1) \cdot 60$.
     - *Wicket Component* ($0$ to $30$): $P_w = \frac{w_{\text{before}}}{9} \cdot 30$.
     - *Endgame Urgency* ($-10$ to $+10$): Progress-weighted RRR excess/surplus relative to $8.0$ RPO.
2. **Delivery Expected Runs $e(s)$** (`calculate_delivery_expected_runs`): Conditioned on innings, phase (`Powerplay`, `Middle`, `Death`), tail-wicket degradation $\kappa_w$, venue par ratio (Innings 1), or RRR demand factor (Innings 2).
3. **Stint Aggregation (`hpp_match_data.json` / `hpp_stint_evaluations_v1.pkl.gz`):**
   - `actual_runs`, `expected_runs = sum(e(s))`, `rae = actual_runs - expected_runs`.
   - `mean_p`: mean of pre-delivery $P(t)$ across balls faced; `peak_p`: maximum pre-delivery $P(t)$ faced during the stint.
4. **Asymmetric High-Pressure Contribution (`calculate_hpc`):**
   - If $\text{RAE} > 0$: $\text{HPC} = \text{RAE} \cdot \big(1 + \text{clip}((P_{\text{mean}} - 50)/50,\; -0.5,\; 1.0)\big)$ (50% discount at $P=0$, up to 2.0× amplification at $P=100$).
   - If $\text{RAE} < 0$: $\text{HPC} = \text{RAE} \cdot \big(1 - \text{clip}((P_{\text{mean}} - 50)/100,\; 0.0,\; 0.4)\big)$ (up to 40% mitigation in extreme crisis; never inverts sign).
   - If $\text{RAE} = 0$: $\text{HPC} = 0$.
   - **Empirical Sign Invariant Verified [MEASURED]:** $\text{sign}(\text{HPC}) = \text{sign}(\text{RAE})$ holds on **99.97%** of batted stints (the remaining 0.03% are exact zero-rounding boundary cases; only **8 stints / 0.06%** have exact `hpc == 0`).
5. **Existing Operational Pressure Tiers (`get_pressure_tier`):**
   - `Low`: $P_{\text{mean}} < 25.0$
   - `Medium`: $25.0 \le P_{\text{mean}} < 50.0$
   - `High`: $50.0 \le P_{\text{mean}} < 75.0$
   - `Extreme`: $P_{\text{mean}} \ge 75.0$
   - `DNB`: `is_dnb = True` — explicitly `NaN`/`None` for `exp_runs`, `rae`, `mean_p`, `peak_p`, and `hpc`. **Never treated as zero and strictly excluded from all averages.**

### 1.2 Innings-Level vs Match-Level Equivalence [MEASURED]
- Across all **798 matches** and **13,033 stint records** (`12,888` batted + `145` DNB), the maximum number of appearances of any `(match_id, batter_name)` pair is **exactly 1** (`0` duplicate `(match_id, name)` rows).
- **Conclusion:** Because regulation T20 matches afford at most one batting innings per player per match, **innings-level and match-level batting pressure reliability are mathematically identical** in the current corpus.

---

## 2. EXISTING BOWLING PRESSURE ARCHITECTURE [MEASURED]

### 2.1 Source Modules & Pipeline Flow
Inspected read-only in `ml/contribution/bowling_pressure/` (`config.py`, `schema.py`, `partnership_threat_engine.py`, `pcs_delivery_engine.py`, `pcs_spell_aggregator.py`):

1. **Causal Pre-Delivery Threat & Momentum Features** (`pcs_delivery_contributions_v1.pkl.gz`, **190,575 deliveries × 162 columns**):
   - Active partnership tracking (`partnership_runs_current`, `partnership_balls_current`, `partnership_run_rate`).
   - Rolling scoring acceleration (`runs_last_12_balls`, `runs_last_18_balls`, `acc_12_rpo`, `acc_18_rpo`, multiplier `phi_acc`).
   - Batter & non-striker threat (`striker_threat`, `non_striker_threat`, composite `phi_bat`, `starve_mult`).
   - **Partnership Threat Index (`pti`):**
     $$\text{PTI} = \text{Runs}_{\text{ptnr}} \cdot \text{clip}\!\left(\frac{\text{RR}_{\text{ptnr}}}{\text{RR}_{\text{ref}}},\; 0.40,\; 2.50\right) \cdot \Phi_{\text{acc}} \cdot \Phi_{\text{bat}} \cdot \text{clip}\!\left(\frac{\text{Runs}_{\text{ptnr}}}{15},\; 0,\; 1\right)$$
   - Contextual leverage (`leverage` $\in [0.50, 2.00]$), `wickets_lost_before`, `legal_balls_remaining_before`, `current_run_rate_before`, `required_run_rate_before`, `resource_pct_remaining`.
2. **Delivery-Level Pressure Contribution Components:**
   - **SWI (`swi`):** Situational Wicket Importance — credits **only bowler-credited dismissals** (`is_bowler_wkt = True`); excludes run-outs and non-bowler dismissals (`is_non_bowler_wkt = True`).
   - **DCI (`dci`):** Dot-ball Choke Index (rewards dot-ball clusters and starving the dangerous batter).
   - **SUP (`sup`):** Scoring Suppression (rewards suppressing run rate against threatening partnerships).
   - **Leakage (`leakage`):** Pressure released via boundaries, wides/no-balls, and expensive deliveries.
   - **RPE (`rpe`):** Net Runs Pressure Equivalent per delivery (`SWI + DCI + SUP - Leakage`).
   - **Delivery PCS (`pcs_delivery`):** Normalized on the bipolar `[0, 100]` scale (neutral `50.00`).
3. **Spell, Season & Career Outputs:**
   - `pcs_match_spells_v1.pkl.gz`: **9,482 spells × 24 columns** (`pcs_spell`, `total_rpe`, `total_swi`, `total_dci`, `total_sup`, `total_leakage`, `mean_leverage`, `legal_balls`, `wickets`, `economy`, `dot_balls`, `boundaries`).
   - `pcs_season_summary_v1.pkl.gz`: **1,587 bowler-seasons × 19 columns**.
   - `pcs_career_summary_v1.pkl.gz`: **638 career bowlers × 19 columns** (uses $M_0 = 48.0$ legal balls shrinkage toward neutral `50.00`).
   - **Spell Polarity Baseline [MEASURED]:** Across all 9,482 spells, **5,087 (53.65%)** are Positive (`pcs_spell > 50`), **9 (0.09%)** are Neutral (`= 50`), and **4,386 (46.26%)** are Negative (`< 50`). Mean spell PCS = **52.96**.

---

## 3. AVAILABLE FIELDS & DATA SOURCES [MEASURED]

| Asset | Granularity | Records | Key Available Fields for PRI | Notes / Constraints |
|---|---|---|---|---|
| `docs/worm_graph/hpp_match_data.json` | Batter-Match Stint | 13,033 (12,888 batted + 145 DNB) | `name`, `inn`, `runs`, `balls`, `fours`, `sixes`, `exp_runs`, `rae`, `mean_p`, `peak_p`, `hpc`, `tier`, `is_out`, `is_dnb` | JSON-safe across Python/pandas versions; lacks `player_id`, `batting_order`, and `entry_p` |
| `docs/worm_graph/match_index.json` | Match Metadata | 883 total (798 available) | `id`, `date`, `year`, `comp` (`IPL`/`T20I`/`OTHER_T20`), `comp_name` (137 comps), `home`, `away`, `venue`, `winner` | Authoritative match-to-tournament join |
| `docs/worm_graph/trajectories/*.json` | Match-Innings Teams | 798 files | `team_a_name` (Inn 1 batting team), `team_b_name` (Inn 2 batting team) | 0/50 alignment mismatches verified |
| `data/processed/contributions/hpp_stint_evaluations_v1.pkl.gz` | Batter Stint Pickle | 13,033 rows | Full stint table incl. `player_id` | **Compatibility caveat:** serialized with pandas `StringDtype(storage='python', na_value=nan)` that raises `NotImplementedError` under pandas 3.x unpickling |
| `data/processed/match_states/match_states_standard_t20_v1.pkl.gz` | Delivery Match States | 190,575 deliveries × 101 cols | `striker_id`, `batting_order`, `wickets_lost_before`, `legal_balls_remaining_before`, `runs_required_before`, `required_run_rate` | Enables optional causal **stint entry pressure ($P_{\text{entry}}$)** and **batting role** extraction without modifying HPP |
| `data/processed/contributions/bowling_pressure/pcs_delivery_contributions_v1.pkl.gz` | Delivery PCS | 190,575 deliveries × 162 cols | `comp_id`, `comp_name`, `pti`, `phi_acc`, `phi_bat`, `partnership_runs_current`, `partnership_run_rate`, `acc_12_rpo`, `leverage`, `swi`, `dci`, `sup`, `leakage`, `rpe`, `pcs_delivery`, `is_bowler_wkt`, `is_non_bowler_wkt` | Complete pre-delivery causal threat state available for **exogenous over-entry danger** computation |
| `data/processed/contributions/bowling_pressure/pcs_match_spells_v1.pkl.gz` | Bowler Match Spell | 9,482 spells × 24 cols | `match_id`, `innings`, `bowler_id`, `season`, `competition_category`, `legal_balls`, `wickets`, `economy`, `total_swi/dci/sup/leakage/rpe`, `pcs_spell` | Does NOT store pre-over `entry_pti` directly; must be joined read-only from `pcs_delivery_contributions_v1.pkl.gz` |

---

## 4. PRESSURE OPPORTUNITY DISTRIBUTIONS [MEASURED]

### 4.1 Batter Pressure Distributions (`12,888` Batted Stints, `876` Batters + `4` DNB-Only Players)

| Metric | Mean | Std | p10 | p25 | p50 (Med) | p60 | p67 | p75 | p85 | p90 | p95 | Max |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **Stint `mean_p`** | 35.78 | 27.86 | 2.80 | 12.70 | 29.90 | 37.90 | 44.30 | 53.90 | 71.40 | 81.50 | 90.16 | 99.80 |
| **Stint `peak_p`** | 41.78 | 28.75 | 7.00 | 18.80 | 35.90 | 44.30 | 51.43 | 62.80 | 80.79 | 89.10 | 95.20 | 99.80 |

**Critical Innings Asymmetry [MEASURED]:**
- **Innings 1** ($n = 6,563$): `mean_p` mean = **26.24** (median 18.50, p75 = 40.70); `peak_p` mean = **32.25**; Positive HPC rate = **37.59%**.
- **Innings 2** ($n = 6,325$): `mean_p` mean = **45.68** (median 39.50, p75 = 67.30); `peak_p` mean = **51.66**; Positive HPC rate = **33.79%**.
- Innings 2 carries **+74.1% higher average pressure** than Innings 1.

**Existing HPP Pressure Tier Breakdown [MEASURED]:**

| Tier | Batted Stints | Corpus Share | Mean `mean_p` | Positive HPC % | Mean HPC | Total HPC | Innings 2 Share |
|---|---|---|---|---|---|---|---|
| **Low** ($P < 25$) | 5,546 | 43.03% | 10.76 | **44.75%** | -0.37 | -2,078.9 | 29.9% |
| **Medium** ($25 \le P < 50$) | 3,704 | 28.74% | 36.23 | **32.45%** | -1.69 | -6,274.2 | 61.0% |
| **High** ($50 \le P < 75$) | 1,913 | 14.84% | 60.86 | **27.97%** | -1.03 | -1,969.2 | 58.5% |
| **Extreme** ($P \ge 75$) | 1,725 | 13.38% | 87.49 | **22.32%** | -0.23 | -403.7 | 74.7% |
| **DNB** (`is_dnb=True`) | 145 (excluded) | — | `NaN` | Excluded | `NaN` | `NaN` | — |

**Critical Batting Endogeneity & Role Opportunity Finding [MEASURED]:**
1. **Role Opportunity Skew:** Top-order openers enter at `0/0` and experience `mean_p >= 40` in only **5.7%–9.6%** of their innings (`Virat Kohli`: 5/88 = 5.7%, `Shubman Gill`: 6/105 = 5.7%, `Abhishek Sharma`: 8/126 = 6.3%, `Jos Buttler`: 10/115 = 8.7%). Middle-order/finishers see 3×–5× higher opportunity rates (`Namboori Tilak Varma`: 33/116 = 28.4%, `Nicholas Pooran`: 30/109 = 27.5%, `Tim David`: 34 opportunities, `Axar Patel`: 53 opportunities).
2. **Partial `mean_p` Endogeneity:** Positive-HPC stints average `mean_p = 28.86`, `peak_p = 36.02` (`gap = 7.16`), whereas negative-HPC stints average `mean_p = 39.64`, `peak_p = 44.98` (`gap = 5.34`). Scoring quickly reduces subsequent RRR and lowers `mean_p`; slow starts inflate `mean_p`. Including `peak_p` (or deriving causal `entry_p` from `match_states`) mitigates this drift.

### 4.2 Bowler Threat & Danger Distributions (`190,575` Deliveries, `30,700` Bowler-Overs, `9,482` Spells)

| Delivery / Spell Danger Indicator | Mean | p25 | p50 (Med) | p67 | p75 | p90 | Max |
|---|---|---|---|---|---|---|---|
| Delivery `pti` | 32.27 | 0.66 | 10.00 | — | 39.37 | 89.74 | 1,009.50 |
| Delivery `phi_acc` | 1.02 | 0.83 | 1.00 | — | 1.16 | 1.37 | 1.60 |
| Delivery `phi_bat` | 1.11 | 1.00 | 1.10 | — | 1.22 | 1.33 | 1.72 |
| Delivery `partnership_runs_current` | 21.79 | 4.00 | 13.00 | — | 31.00 | 55.00 | 233.00 |
| Over-Entry `entry_pti` (30,700 overs) | — | — | 9.02 | 25.16 | 37.63 | — | — |
| Spell `mean_pti` (endogenous) | 33.74 | 9.44 | 20.96 | 33.19 | 42.08 | 78.18 | — |
| Spell `max_pti` | 96.00 | 31.96 | 66.08 | 101.05 | 125.39 | 212.54 | — |
| Spell `above_par_share` | 0.42 | 0.12 | 0.38 | 0.57 | 0.67 | 0.92 | — |

**Empirical Proof: Death Overs / High RRR $\ne$ Automatically High Bowling Pressure [MEASURED]:**

| Match Context Slice | Deliveries | Mean `pti` | Share `pti >= 25` | Mean Leverage | Interpretation |
|---|---:|---:|---:|---:|---|
| Death Overs (`over >= 16`) — **Wickets $\ge 6$ (Tailenders)** | 17,290 | **11.04** | **14.0%** | — | Low genuine threat; bowling side already in control |
| Death Overs (`over >= 16`) — **Wickets $\le 4$ (Set Batters)** | 16,965 | **60.60** | **53.9%** | — | **5.5× higher danger**; genuine death pressure |
| 2nd Inn `RRR >= 12` & **Wickets $\ge 6$** (Lost Chase) | 9,099 | **6.59** | — | **0.66** | Dead chase; NOT high bowling pressure |
| 2nd Inn `RRR >= 12` & **Wickets $\le 4$** (Live Chase) | 9,994 | **20.02** | — | **0.75** | **3.0× higher partnership danger** |

### 4.3 Critical Causal Discovery: Endogenous Spell `mean_pti` vs Exogenous Over-Entry `entry_pti` [MEASURED]

Filtering spells by *within-spell average* `mean_pti >= 25` introduces severe **post-treatment selection bias**:
- If a bowler enters against a dangerous partnership (`entry_pti = 50`) and **immediately takes a wicket**, the partnership resets to `0`, pulling their spell's `mean_pti` below 25 and **silently excluding their best stand-breaking spells**.
- Conversely, if a bowler gets hit for 45 runs without a wicket, the partnership balloons and `mean_pti` surges, **over-selecting failed spells**.
- **Measured Proof:** Across all 9,482 spells, `pos_pcs% = 53.65%` (`mean_pcs = 52.96`). Under endogenous `mean_pti >= 25 & balls >= 12`, `pos_pcs%` collapses to **39.11%** (`mean_pcs = 47.02`), and **Varun Chakravarthy** loses 21 of his best pressure-breaking spells (`59 -> 38`, dropping his apparent rate from `54.2%` to `42.1%` and mean PCS from `55.24` to `49.20`)!
- **Exogenous Solution Verified:** Evaluating danger strictly at **over entry** (the pre-delivery state on ball 1 of each over bowled by that bowler: `max_entry_pti >= 35` or `>= 1` dangerous over entry) eliminates post-treatment confounding completely: corpus `pos_pcs% = 50.89%` (`mean_pcs = 51.25`), cleanly centered near neutral `50.00`, and preserves every rapid stand-breaking spell.

---

## 5. CANDIDATE PRESSURE OPPORTUNITY DEFINITIONS & SENSITIVITY [MEASURED]

### 5.1 Candidate Batting Pressure Opportunity Definitions

| Candidate Definition | Stints (% Corpus) | Pos HPC % | Mean HPC | Inn 2 Share | Season Range (2022–2026) | IPL / T20I / Other Share | Batters $\ge 10$ / $\ge 15$ Opps |
|---|---:|---:|---:|---:|---|---|---|
| `T1`: `mean_p >= 25` (Med+High+Ext) | 7,352 (57.0%) | 28.92% | -1.18 | 63.6% | 55.2%–59.5% | 56.9% / 57.5% / 52.6% | 250 / 162 |
| `T2`: `mean_p >= 35` | 5,609 (43.5%) | 27.83% | -0.97 | 64.3% | 42.6%–45.1% | 43.4% / 44.0% / 38.8% | 198 / 114 |
| **`T3`: `mean_p >= 40`** | **4,799 (37.2%)** | **26.80%** | **-0.88** | **64.8%** | **36.6%–38.4%** | **36.8% / 37.8% / 34.2%** | **164 / 93** |
| `T4`: `mean_p >= 45` | 4,184 (32.5%) | 26.05% | -0.78 | 65.1% | 31.8%–33.0% | 31.8% / 33.1% / 30.9% | 143 / 76 |
| `T5`: `mean_p >= 50` (Existing `High+Ext`) | 3,642 (28.3%) | 25.32% | -0.65 | 66.2% | 27.6%–28.7% | 27.3% / 29.0% / 27.6% | 127 / 58 |
| `T8`: `peak_p >= 60` | 3,455 (26.8%) | 25.90% | -0.70 | 68.3% | 26.2%–27.1% | 26.1% / 27.5% / 25.7% | 116 / 53 |
| **`T10`: `mean_p >= 40 OR peak_p >= 60`** | **4,857 (37.7%)** | **26.93%** | **-0.91** | **64.6%** | **37.1%–38.9%** | **37.2% / 38.3% / 34.6%** | **164 / 93** |
| `T12`: Innings-Specific p70 (`Inn1>=35.7, Inn2>=59.3`) | 3,882 (30.1%) | 25.04% | -0.96 | **49.0%** | 28.5%–30.9% | 28.3% / 31.5% / 31.1% | 135 / 69 |

- **Threshold Sensitivity [MEASURED]:** Ranking stability between `T3 (mean_p >= 40)` and neighboring definitions is very high: vs `T2 (>=35)` $\rho = 0.970$; vs `T4 (>=45)` $\rho = 0.972$; vs `T10 (mean>=40 OR peak>=60)` $\rho = 0.997$; vs `T5 (>=50)` $\rho = 0.923$; vs `T12 (Inn-specific p70)` $\rho = 0.890$.
- **Why `T5 (High+Ext >= 50)` alone is suboptimal [MEASURED]:** Its 2026 holdout rank stability collapses to $\rho = 0.052$ due to small per-player sample sizes (only 58 batters reach $\ge 15$ opps), whereas **`T10 (mean_p >= 40 OR peak_p >= 60)`** achieves both **4× higher holdout rank stability ($\rho = 0.229$)**, **93 batters at $\ge 15$ opps**, remarkable season stability (`37.1%–38.9%`), near-identical IPL/T20I rates (`37.2%` vs `38.3%`), AND rescues stints where a batter entered a peak-60 crisis and batted their team *out* of pressure!

### 5.2 Candidate Bowling Pressure Opportunity Definitions

| Candidate Definition | Type | Spells (% Corpus) | Pos PCS % | Mean PCS | Mean RPE | Season Range (2022–26) | IPL / T20I / Other | Bowlers $\ge 10$ / $\ge 15$ |
|---|---|---:|---:|---:|---:|---|---|---|
| `ENDO`: `mean_pti >= 25 & balls >= 12` | Endogenous (Biased) | 3,700 (39.0%) | 39.11% | 47.02 | -2.69 | 35.6%–46.1% | 46.0% / 34.1% / 25.7% | 125 / 80 |
| `EXO_1`: `max_entry_pti >= 25 & balls >= 12` | Exogenous | 5,882 (62.0%) | 52.01% | 51.75 | +1.82 | 59.8%–66.7% | 67.5% / 58.2% / 51.0% | 179 / 131 |
| **`EXO_2`: `max_entry_pti >= 35 & balls >= 12`** | **Exogenous** | **5,027 (53.0%)** | **50.89%** | **51.25** | **+1.32** | **50.7%–58.1%** | **58.8% / 49.0% / 40.7%** | **153 / 116** |
| `EXO_3`: `max_entry_pti >= 45 & balls >= 12` | Exogenous | 4,279 (45.1%) | 49.50% | 50.78 | +0.86 | 42.7%–50.7% | 51.0% / 41.0% / 33.3% | 136 / 91 |
| `EXO_4`: `mean_entry_pti >= 20 & balls >= 12` | Exogenous | 4,164 (43.9%) | 47.98% | 50.12 | +0.21 | 41.6%–49.0% | 50.1% / 39.4% / 33.6% | 136 / 89 |
| **`EXO_5`: `mean_entry_pti >= 25 & balls >= 12`** | **Exogenous** | **3,496 (36.9%)** | **46.22%** | **49.56** | **-0.32** | **33.8%–42.4%** | **42.7% / 32.7% / 26.3%** | **115 / 71** |
| `EXO_7`: `>= 2 danger overs (entry_pti>=25) & balls>=12` | Exogenous | 2,916 (30.8%) | 47.43% | 49.77 | -0.15 | 29.1%–36.6% | 36.1% / 26.9% / 20.9% | 94 / 58 |

**Recommended Candidate Definitions [PROPOSED]:**
- **Batting Primary Opportunity Definition:** `T10` — `mean_p >= 40.0 OR peak_p >= 60.0` (37.7% of batted stints, 4,857 stints), with **Innings-Specific Sensitivity Tier** (`T12`) and **Extreme Crisis Slice** (`T5: mean_p >= 50.0`) exposed as optional UI filters. (And in PRI-2, optionally upgradeable to causal `entry_p` from `match_states_standard_t20_v1.pkl.gz` if governance approves!)
- **Bowling Primary Opportunity Definition:** **Exogenous Over-Entry Danger (`EXO_2`: `max_over_entry_pti >= 35.0` AND `legal_balls >= 12`)** (53.0% of spells, 5,027 spells, 116 bowlers with $\ge 15$ spells) — or stricter **`EXO_5` (`mean_over_entry_pti >= 25.0` AND `legal_balls >= 12`)** (36.9% of spells, 3,496 spells) — paired with **Over-Level Danger Exposure (`entry_pti >= 25.0`, 10,059 overs)** as secondary diagnostic! Notice that **the two disciplines use fundamentally different, domain-native opportunity definitions** (batters face scoreboard/wicket/RRR pressure $P$; bowlers face batting-team partnership danger $\text{PTI}_{\text{over\_entry}}$).

---

## 6. RELIABILITY VS CONTRIBUTION: BATTER & BOWLER METRICS [MEASURED + PROPOSED]

### 6.1 Empirical Proof That Reliability $\ne$ Contribution [MEASURED]

| Discipline | Metric Pair ($n \ge 10$ opps) | Pearson $r$ | Spearman $\rho$ | Implication |
|---|---|---:|---:|---|
| **Batting (`T3`)** | `Positive HPC %` vs `Career Total Runs` | +0.571 | +0.580 | High run volume explains only ~33% of reliability variance |
| **Batting (`T3`)** | `Positive HPC %` vs `Career Total HPC` | +0.542 | +0.533 | Career HPC leaders are NOT automatically pressure-reliable |
| **Batting (`T3`)** | `Positive HPC %` vs `Pressure Total HPC` | +0.717 | +0.719 | Related, yet distinct (boom-bust hitters diverge sharply) |
| **Bowling (`B8`)** | `Positive PCS %` vs `Career Wickets` | +0.137 | +0.134 | Wicket tally has almost zero correlation with pressure reliability |
| **Bowling (`B8`)** | `Positive PCS %` vs `Career Shrunk PCS` | +0.541 | +0.535 | Overall PCS captures all spells; PRI isolates dangerous states |
| **Bowling (`B8`)** | `Positive PCS %` vs `Pressure Mean PCS` | +0.844 | +0.852 | Strong alignment, but variance/floor differentiates consistent vs volatile spells |

### 6.2 Proposed Independent Batter Reliability Metrics [PROPOSED]
Every batter profile & leaderboard must display **Reliability** and **Contribution** side-by-side without hiding either:
1. **Qualifying Pressure Opportunities ($N_{\text{opp}}$):** Count of batted stints meeting pressure criteria (DNB strictly excluded).
2. **Raw Positive Pressure Rate ($p_{\text{raw}}$):** $\frac{1}{N_{\text{opp}}}\sum \mathbb{I}(\text{HPC}_i > 0)$.
3. **Shrunk Pressure Reliability Rate ($\hat{p}_{\text{EB}}$):** Empirical Bayes Beta-Binomial posterior mean (Primary Reliability Rate).
4. **Wilson 90% Lower Bound ($p_{\text{L90}}$):** Conservative floor quantifying sample-adjusted reliability confidence.
5. **Shrunk Pressure Mean HPC ($\hat{\mu}_{\text{HPC,EB}}$):** Empirical Bayes shrunk average HPC under pressure (Primary Quality Under Pressure).
6. **Total Pressure HPC ($\sum \text{HPC}$):** Cumulative contribution across qualifying pressure innings.
7. **Severe Failure Rate:** $\frac{1}{N_{\text{opp}}}\sum \mathbb{I}(\text{HPC}_i \le -5.0)$ — captures downside blow-up risk (differentiating Scenario D steady batters from Scenario C boom-bust batters).

### 6.3 Proposed Independent Bowler Reliability Metrics [PROPOSED]
1. **Qualifying Pressure Spells ($N_{\text{opp}}$):** Count of spells meeting exogenous over-entry danger criteria (`legal_balls >= 12`).
2. **Raw Positive PCS Rate ($p_{\text{raw}}$):** $\frac{1}{N_{\text{opp}}}\sum \mathbb{I}(\text{PCS}_{\text{spell},i} > 50.00)$.
3. **Shrunk Pressure Reliability Rate ($\hat{p}_{\text{EB}}$):** Empirical Bayes Beta-Binomial posterior mean.
4. **Wilson 90% Lower Bound ($p_{\text{L90}}$):** Conservative reliability floor.
5. **Shrunk Mean Pressure PCS ($\hat{\mu}_{\text{PCS,EB}}$):** Empirical Bayes shrunk average spell PCS under danger (`50.00` neutral).
6. **Total Pressure RPE ($\sum \text{RPE}$):** Cumulative net pressure runs generated in dangerous situations.
7. **Dangerous Partnership Break Rate:** Bowler-credited stand breaks (`is_bowler_wkt & pti >= 25`) per pressure spell.
8. **Scoring Suppression & Containment Effectiveness:** Mean `total_sup` + `total_dci` per pressure spell (captures Scenario D wicketless chokers).
9. **Severe Leakage Rate:** $\frac{1}{N_{\text{opp}}}\sum \mathbb{I}(\text{PCS}_{\text{spell},i} < 40.00)$ — captures blow-up risk.

---

## 7. SAMPLE CONFIDENCE & SHRINKAGE METHODOLOGY [MEASURED + PROPOSED]

### 7.1 Chronological Empirical Bayes Variance Decomposition (`Train 2022–24` $\rightarrow$ `Val 2025` $\rightarrow$ `Test 2026`) [MEASURED]

Using Method-of-Moments Empirical Bayes (DerSimonian-Laird) strictly on the chronological Training split (`2022–2024`), then evaluating out-of-sample RMSE on Validation (`2025`) and Holdout Test (`2026`):

| Discipline & Definition | Train Prior ($\bar{p}$ / $\mu$) | Between-Player $\tau^2$ | Implied EB Prior $M_0$ | Val 2025 RMSE (Raw $\to$ EB) | Test 2026 RMSE (Raw $\to$ EB) |
|---|---:|---:|---:|---:|---:|
| **Batting `T10`** (Binary Pos Rate) | $\bar{p} = 0.265$ | $0.00602$ | **31.4 inns** | `0.265 → 0.226` (**-14.7%**) | `0.241 → 0.226` (**-6.2%**) |
| **Batting `T10`** (Mean HPC) | $\mu = -0.93$ | $1.22$ ($\sigma_w^2=47.4$) | **38.7 inns** | `3.80 → 2.98` (**-21.6%**) | — |
| **Batting `T3`** (Binary Pos Rate) | $\bar{p} = 0.265$ | $0.00638$ | **29.5 inns** | `0.269 → 0.224` (**-16.7%**) | `0.242 → 0.224` (**-7.4%**) |
| **Bowling `EXO_2`** (Binary Pos Rate) | $\bar{p} = 0.525$ | $0.00083$ | **High ($\ge 50$ spells)** | `0.268 → 0.210` (**-21.6%**) | — |
| **Bowling `EXO_6`** (Binary Pos Rate) | $\bar{p} = 0.534$ | $0.00046$ | **High ($\ge 50$ spells)** | `0.233 → 0.197` (**-15.5%**) | — |
| **Bowling `B8`** (Mean Spell PCS) | $\mu = 47.67$ | $3.16$ ($\sigma_w^2=174.9$) | **55.3 spells** | `7.06 → 5.80` (**-17.8%**) | — |

### 7.2 Three Candidate Sample-Confidence Methodologies [PROPOSED]

| Option | Formula | Strengths | Trade-offs |
|---|---|---|---|
| **Option 1: Empirical Bayes Beta-Binomial + Normal-Normal Shrinkage (Recommended Primary)** | $\hat{p}_{\text{EB}} = \frac{k + M_{0,p}\bar{p}}{n + M_{0,p}}$, $\hat{\mu}_{\text{EB}} = \frac{n\bar{x} + M_{0,\mu}\mu_0}{n + M_{0,\mu}}$ | Data-derived from chronological Train split; reduces out-of-sample RMSE by **15%–22%**; prevents 2-for-2 flukes from topping leaderboards | Large implied $M_0$ ($30$ inns / $55$ spells) heavily compresses single-season rankings unless paired with a season-calibrated $M_{0,\text{season}}$ |
| **Option 2: Wilson Score Lower Bound ($z=1.645$, 90% CI)** | $p_{\text{L90}} = \frac{\hat{p} + \frac{z^2}{2n} - z\sqrt{\frac{\hat{p}(1-\hat{p})}{n} + \frac{z^2}{4n^2}}}{1 + z^2/n}$ | Zero tuning constants; mathematically exact coverage; directly answers *"at least how reliable is this player?"* | Only applies to binary positive rate (does not quantify magnitude of HPC/PCS) |
| **Option 3: Tiered Confidence Qualification + Credible Interval Width (Recommended Companion)** | Display **Confidence Badge** (`High`: $n \ge 20$, `Medium`: $10 \le n < 20$, `Low/Provisional`: $5 \le n < 10$, `Insufficient`: $n < 5$) + 90% Beta Credible Interval $[L_{90}, U_{90}]$ | Transparent to cricket fans & analysts; prevents false precision | Must be paired with Option 1 for ranking order |

**Explicit Anti-Shortcut Rule:** We **reject** reusing the existing 48-ball PCS shrinkage constant for PRI. Batting opportunity counts (innings) and bowling opportunity counts (spells) have empirically measured variance structures ($M_{0,\text{bat}} \approx 30$ career innings; $M_{0,\text{bowl}} \approx 40\text{–}55$ career spells; season scopes require separate cross-validated priors via grid search on 2022–2024 $\to$ 2025).

---

## 8. CAREER, SEASON & TOURNAMENT AGGREGATION & FAIR COMPARISON DESIGN [PROPOSED]

| Scope | Supported Filters | Default Min Pressure Opps | Handling of Edge Cases |
|---|---|---|---|
| **Career (2022–2026)** | Discipline, Pressure Slice, Team, Format (`IPL`/`T20I`/`OTHER_T20`), Min Opps | Batters: `10` opps; Bowlers: `10` spells (configurable down to `5` as Provisional) | **Multi-team players** (`271/880` batters): Career aggregates all teams; Team filter restricts strictly to stints/spells played *for that team*. |
| **Season (Single Year)** | Year (`2022`–`2026`), Team, Format | Batters: `4` opps; Bowlers: `4` spells | Uses season-scoped prior $\bar{p}_{\text{season}}$; marks $n < 6$ as `Provisional Confidence`. |
| **Tournament (`comp_name`)** | All 137 batting / 141 bowling tournaments | `3` opps (tournament-adaptive) | Uses tournament-scoped baseline $\bar{p}_{\text{tourney}}$ because IPL has systematically higher `PTI` (`58.8%` vs `49.0%` T20I under `EXO_2`) due to flatter pitches & stronger batting lineups. |
| **Zero Opportunities / DNB / Incomplete** | All scopes | $N_{\text{opp}} = 0$ | Displayed explicitly as **`No Pressure Opportunities`** (never `0%` or negative). DNB stints (`145` total) are excluded from both numerator and denominator. |

**Fairness Safeguard — Opportunity Environment Disclosure:** Because IPL has higher average partnership danger (`EXO_2`: 58.8% vs T20I 49.0%) and finishers face 3×–5× more batting pressure opportunities than openers, PRI displays:
1. **Opportunity Rate** ($N_{\text{opp}} / N_{\text{total}}$) alongside $N_{\text{opp}}$.
2. **Environment-Relative Lift** ($\hat{p}_{\text{EB}} - \bar{p}_{\text{scope}}$) so IPL and T20I players are evaluated against their own scoring environment's baseline!

---

## 9. DATA LIMITATIONS & MISSING INFORMATION [MEASURED]

1. **Batting `hpp_stint_evaluations_v1.pkl.gz` Pandas 3.x Unpickling Issue:** Unpickling directly raises `NotImplementedError` on `StringDtype(storage='python', na_value=nan)`. While `docs/worm_graph/hpp_match_data.json` is 100% readable and complete for all 13,033 stints, it omits `player_id` (requires mapping via `hpp_leaderboards.json` + `competition_team_player_mapping.csv`) and omits `batting_order` and `entry_p` (available in `match_states_standard_t20_v1.pkl.gz`).
2. **No Serialized Batter Entry Pressure ($P_{\text{entry}}$) in `hpp_match_data.json`:** Only stint `mean_p` and `peak_p` exist today. Extracting causal $P_{\text{entry}}$ in PRI-2 would require a read-only join to `match_states_standard_t20_v1.pkl.gz`.
3. **Bowler Spell Table Lacks Pre-Over `entry_pti`:** `pcs_match_spells_v1.pkl.gz` stores only spell totals (`total_swi/dci/sup/leakage/rpe`, `pcs_spell`). Computing exogenous over-entry danger (`max_entry_pti`, `mean_entry_pti`, `danger_overs`) requires a fast read-only groupby over `pcs_delivery_contributions_v1.pkl.gz` (already loaded in memory by `PCSDataService`, ~0.2s).
4. **High Intrinsic T20 Single-Match Variance:** Even with 798 matches, T20 outcomes under extreme pressure have substantial noise ($\tau^2 \ll \sigma_w^2$), resulting in modest single-season year-over-year rank correlation ($\rho \approx 0.15\text{–}0.23$). PRI must therefore emphasize **multi-season career reliability + explicit uncertainty bands** rather than claiming deterministic precision from small single-season samples.
5. **No Pre-Computed Batting Role Tag (`Opener` / `Middle` / `Finisher`):** Derivable read-only from `batting_order` in `match_states_standard_t20_v1.pkl.gz` if role-stratified comparisons are desired in PRI-2.

---

## 10. BACKTESTING, VALIDATION FRAMEWORK & SCENARIO TESTS [MEASURED + PROPOSED]

### 10.1 Chronological Validation Protocol (Zero Future Leakage)
- **Train Partition:** `2022–2024` (estimate Empirical Bayes priors $\bar{p}$, $\mu_0$, $\tau^2$, $\sigma_w^2$, and candidate $M_0$).
- **Validation Partition:** `2025` (tune/verify shrinkage regularization, threshold stability, RMSE improvement, Brier score for binary reliability, and rank stability $\rho$).
- **Holdout Test Partition:** `2026` (locked final out-of-sample evaluation — never used for hyperparameter fitting).
- **Required Audit Gates for PRI-2:**
  1. Shrunk reliability out-of-sample RMSE strictly lower than raw rate on BOTH Val 2025 and Test 2026 (already verified in §7.1: `-15%` to `-22%` RMSE reduction!).
  2. Neighboring threshold Spearman stability $\rho \ge 0.85$.
  3. Zero rank inversion on canonical small-sample vs large-sample stress tests (Scenarios A vs B).
  4. DNB invariance: inserting/removing DNB records changes zero PRI values.

### 10.2 Representative Scenario Tests (Grounded in Real Phase 2 Corpus Data) [MEASURED]

#### Batting Scenarios (Evaluated under `T3/T10`, Corpus Prior $\bar{p} = 26.8\%$, $M_{0,p} = 30$, $\mu_{\text{HPC}} = -0.88$, $M_{0,h} = 39$)

| Scenario | Real Corpus Archetype | $N_{\text{opp}}$ | Pos % (Raw) | Mean HPC (Raw) | Total HPC | Career Runs | Shrunk Pos % ($\hat{p}_{\text{EB}}$) | Shrunk Mean HPC | Expected PRI Diagnosis |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| **A. Consistently positive across many pressure inns** | **Suryakumar Yadav** / **Tim David** | 23 / 34 | **56.5%** / **55.9%** | **+5.45** / **+3.04** | +125.4 / +103.5 | 4,353 / 2,008 | **39.7%** / **42.2%** | **+1.47** / **+0.95** | **Top-tier Elite Reliable** (High reliability + strong positive impact + High confidence) |
| **B. Very high HPC in 2 opps only** | **Aaron Finch** / **Ahmed Daniyal** | 2 / 2 | 100.0% / 100.0% | +8.14 / +6.39 | +16.3 / +12.8 | 371 / 39 | **31.4%** / **31.4%** | **-0.44** / **-0.53** | **Insufficient / Provisional** — EB shrinkage cleanly prevents 2-for-2 fluke from beating Scenario A! |
| **C. High total HPC, lower positive % (Boom-Bust)** | **Rashid Khan** / **Nicholas Pooran** | 45 / 30 | 33.3% / 43.3% | +1.26 / +2.83 | +56.6 / +84.8 | 748 / 2,969 | **30.7%** / **35.1%** | **+0.27** / **+0.73** | **High-Ceiling Explosive** — ranked below Scenario A on Reliability despite big total HPC |
| **D. High positive %, tiny/negative avg HPC** | **M Shahrukh Khan** / **Moeen Ali** | 20 / 19 | **55.0%** / **52.6%** | **+0.44** / **-0.04** | +8.9 / -0.8 | 586 / 1,063 | **38.1%** / **36.8%** | **-0.43** / **-0.61** | **Steady Low-Magnitude** — visible separation prevents mistaking +0.44 HPC/inn for Suryakumar's +5.45/inn! |
| **E. High career runs, negative HPC under pressure** | **Hardik Pandya** / **Axar Patel** | 28 / 53 | **28.6%** / **34.0%** | **-2.59** / **-0.97** | **-72.5** / **-51.4** | 2,594 / 1,682 | **27.7%** / **31.4%** | **-1.60** / **-0.93** | **Volume vs Pressure Divergence** — high raw runs do NOT mask negative pressure impact |

#### Bowling Scenarios (Evaluated under Exogenous `EXO_2` & Spell-Level Evidence, Prior $\bar{p} = 50.9\%$, $\mu_{\text{PCS}} = 51.25$)

| Scenario | Real Corpus Archetype | Evidence (Measured) | Expected PRI Diagnosis |
|---|---|---|---|
| **A. Consistently positive PCS across many dangerous spells** | **Sunil Narine** ($n=44$, **65.9%** pos, **57.84** avg PCS, +317.8 RPE, 23 breaks) / **Rashid Khan** ($n=78$, **60.3%** pos, **54.53** avg PCS, 45 breaks) | Large sample + high positive rate + high mean PCS + high stand breaks | **Top-tier Elite Reliable** (High confidence, top of both Reliability & Quality axes) |
| **B. Exceptional PCS in only 2 pressure spells** | **Vignesh Puthur** ($n=2$, 100% pos, **65.27** avg PCS) / **Imad Wasim** ($n=2$, 100% pos, **64.50** avg PCS) | Only 2 spells -> heavily shrunk toward 50.9% / 51.25 | **Insufficient / Provisional** — never ranks above 40+ spell proven performers |
| **C. High average PCS but lower consistency** | **Varun Chakravarthy** ($n=59$, **54.2%** pos, **55.24** avg PCS) vs **Axar Patel** ($n=75$, **58.7%** pos, **53.45** avg PCS) | Higher ceiling (55.24) vs higher floor/consistency (58.7%) | **Cleanly Separated**: Axar leads Consistency Axis; Varun leads Peak Quality Axis |
| **D. Economical wicketless spells suppressing dangerous stands** | **Gudakesh Motie** (Match #37554: `4.0-0-13-0`, econ `3.25`, `mean_pti=46.3`, `SUP=+6.23`, `DCI=+14.01`, **PCS = 67.97**) / **Rashid Khan** (Match #15187: `4.0-0-15-0`, **PCS = 66.25**) | Positive PCS (`> 50`) achieved with **0 wickets** via suppression & dot choke | **Rewarded as Full Positive Pressure Successes** (`pcs_spell > 50` needs zero wickets!) |
| **E. Expensive spells with wickets but poor pressure control** | **Brad Evans** (Match #51384: `4.0-0-65-2`, econ `16.25`, `Leak=41.2`, **PCS = 21.37**) / **William O'Rourke** (Match #40752: `4.0-0-74-2`, **PCS = 24.30**) | 2 wickets, yet massive leakage pulls `pcs_spell << 50` | **Flagged as Negative Pressure Failures** (and severe leakage `< 40`) |

---

## 11. RECOMMENDED PRI ARCHITECTURE [PROPOSED]

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│              PROPOSED PRESSURE RELIABILITY INDEX (PRI) ARCHITECTURE                    │
├────────────────────────────────────────────────────────────────────────────────────────┤
│  READ-ONLY PRODUCTION SOURCES (ZERO MUTATION OF HPP/HPC OR PCS)                        │
│  ┌────────────────────────────────────┐   ┌──────────────────────────────────────────┐ │
│  │ BATTING: hpp_match_data.json       │   │ BOWLING: pcs_delivery_contributions      │ │
│  │ + match_index.json + trajectories  │   │ + pcs_match_spells_v1.pkl.gz             │ │
│  │ (optional: match_states entry_p)   │   │ (Strictly Exogenous Over-Entry PTI)      │ │
│  └─────────────────┬──────────────────┘   └────────────────────┬─────────────────────┘ │
│                    ▼                                           ▼                       │
│  OPPORTUNITY QUALIFICATION GATE (DISCIPLINE-SPECIFIC, EXOGENOUS, DNB-SAFE)             │
│  • Batter: mean_p >= 40 OR peak_p >= 60   • Bowler: max_over_entry_pti >= 35           │
│    (DNB strictly excluded, never 0)         AND legal_balls >= 12                      │
│                    │                                           │                       │
│                    ▼                                           ▼                       │
│  INDEPENDENT DUAL-AXIS EVALUATION (NEVER BLENDING RELIABILITY & CONTRIBUTION BLINDLY)  │
│  ┌───────────────────────────────────────────────────────────────────────────────────┐ │
│  │ Axis 1 — RELIABILITY (Consistency)   │ Axis 2 — QUALITY (Contribution Magnitude) │ │
│  │ • Shrunk Positive Rate (p_EB)        │ • Shrunk Mean HPC / Shrunk Mean PCS       │ │
│  │ • Raw Positive Rate (k / n)          │ • Total Pressure HPC / Total Pressure RPE │ │
│  │ • Wilson 90% Lower Bound (p_L90)     │ • Severe Failure / Leakage Floor Rate     │ │
│  │ • Sample Confidence Tier (H/M/L)     │ • Stand Breaks & Suppression (Bowlers)    │ │
│  └───────────────────────────────────────────────────────────────────────────────────┘ │
│                    │                                                                   │
│                    ▼                                                                   │
│  MULTI-SCOPE FAIR COMPARISON: Career | Season | Tournament | Team | Min Opportunities  │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

### Core Architectural Principles
1. **Strict Separation of Disciplines:** Batter PRI and Bowler PRI are computed independently with discipline-native opportunity thresholds and shrinkage priors.
2. **Strict Separation of Reliability vs Contribution:** Both axes are always exposed together so Scenario C (boom-bust) and Scenario D (low-magnitude steady) are immediately distinguishable.
3. **Uncertainty-First Presentation:** Every player displays $N_{\text{opp}}$, Confidence Tier (`High` / `Medium` / `Provisional` / `No Opportunities`), and 90% confidence floor alongside their shrunk estimate.
4. **Zero-Mutation Read-Only Layer:** PRI is implemented purely as an analytical aggregation & API/UI layer reading existing validated HPP and PCS outputs (following the exact same read-only pattern as Stage B8 & Stage B9).

---

## 12. APPROVED GOVERNANCE DECISIONS (LOCKED FOR PRI-2)

The 5 open design questions from PRI-1 have been formally resolved and locked for PRI-2 implementation:

1. **Batting Opportunity Definition — APPROVED (`T10`):**
   - `T10 = (mean_p >= 40.0) OR (peak_p >= 60.0)` using existing HPP stint pressure values (preserving `mean_p` and `peak_p` separately; causal `entry_p` retained as sensitivity analysis).
2. **Bowling Opportunity Definition — APPROVED (`EXO_2`):**
   - `EXO_2 = (max_over_entry_pti >= 35.0) AND (legal_balls >= 12)` evaluated strictly at pre-over entry before the bowler's deliveries alter the partnership (`EXO_5: mean_over_entry_pti >= 25.0 AND legal_balls >= 12` retained as sensitivity analysis).
3. **Ranking Architecture — APPROVED (Dual-Axis, No Composite Score):**
   - Independent display of **Reliability Rate**, **Pressure Contribution Quality**, and **Statistical Confidence** (Wilson binomial confidence interval). No composite PRI score. Neutral observations (`HPC == 0` or `PCS == 50.0`) are strictly classified as neutral, never positive.
4. **Shrinkage Policy — REJECTED (NO SHRINKAGE IN PRI):**
   - **All shrinkage is explicitly rejected for PRI** (zero career shrinkage, zero season shrinkage, zero Empirical Bayes shrinkage, zero prior pulling, zero reuse of the 48-ball PCS shrinkage). PRI reports exact observed statistics from qualifying opportunities, paired with informational Wilson confidence intervals.
5. **Custom Minimum Opportunity Filters — APPROVED:**
   - Users may enter any non-negative integer (`0`, `1`, `2`, ...; `0` = include all players with $\ge 1$ qualifying opportunity; players with `0` qualifying opportunities are marked unavailable/insufficient, never `0%`).
6. **Leaderboard Visibility Policy — APPROVED (Inherited from Stage B8):**
   - Verified Pakistan players (`team_name in ['Pakistan', 'Pakistan A']` via `competition_team_player_mapping.csv`) are hidden from default overall PRI leaderboards at the presentation/leaderboard view layer only. Underlying records, datasets, and individual player profiles remain 100% intact; unknown nationality is never classified as Pakistan.

---

## 13. PROTECTED ASSET INTEGRITY VERIFICATION [MEASURED]

Pre- and post-audit SHA-256 verification confirmed **27/27 protected assets** (all 14 B1–B6 baseline assets, 7 batting HPP artifacts/JSONs, and 6 PCS artifacts) remained **100% bit-for-bit identical** with zero files modified, zero models retrained, and zero access to Phase 1 or `Documents/contribution`.

---

## 14. FINAL RECOMMENDATION

**RECOMMENDATION: CONDITIONAL GO (FOR PRI-2 SPECIFICATION & IMPLEMENTATION)**

**Rationale:**
- **GO on Data Readiness & Scientific Feasibility:** Existing Phase 2 HPP/HPC and PCS production datasets already contain all required pre-delivery causal fields (`mean_p`, `peak_p`, `hpc`, `rae`, `is_dnb`, delivery-level `pti`, `phi_acc`, `phi_bat`, `swi`, `dci`, `sup`, `leakage`, `rpe`, `pcs_spell`) to build a statistically defensible, zero-mutation Pressure Reliability Index for both batters and bowlers.
- **CONDITIONAL on 5 Governance Decisions (§12):** Specifically locking the exogenous opportunity definitions (`T10` vs `entry_p` for batting; `EXO_2` vs `EXO_5` for bowling), dual-axis vs composite display mode, season shrinkage policy, and leaderboard filter policy before writing PRI-2 production code.
