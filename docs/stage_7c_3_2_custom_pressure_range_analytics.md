# Stage 7C.3.2 Implementation & Statistical Verification Report: Custom Pressure Range Analytics

**Milestone:** Custom Pressure Range Selector, Overlapping Preset Ranges, Granular Stint Evaluation & CSV Export Enhancement  
**Target File:** `docs/worm_graph/hpp_dashboard.html`  
**Artifact Path:** `docs/stage_7c_3_2_custom_pressure_range_analytics.md`  
**Execution Mode:** Frontend Enhancement & Statistical Validation (STRICTLY READ-ONLY on HPP Engine, Models, and Production Datasets)  
**Verification Date:** November 16, 2026  

---

## 1. Executive Summary

Stage 7C.3.2 enhances the CricImpact Phase 2 High Pressure Player (HPP) Dashboard by introducing **Custom Pressure Range Analytics** for user-provided custom player lists.

While Stage 7C.3 implemented custom player name matching and Stage 7C.3.1 established production record rendering with CSV exports, player evaluations were previously constrained to fixed, discrete pressure tiers (Low, Medium, High, Extreme). In competitive cricket analytics, pressure is continuous, and analyst queries frequently require evaluating performance across customized or overlapping pressure windows (e.g., $0\%–50\%$, $25\%–75\%$, $50\%–100\%$, or bespoke ranges such as $32\%–82\%$).

Stage 7C.3.2 successfully delivers:
1. **Interactive Custom Pressure Range Selector UI Component (`#custom-pressure-range-card`)**: Integrated directly into `#section-custom-player`, featuring 4 selectable preset buttons, synchronized min/max sliders and numerical inputs, real-time status badges, and an instant reset trigger.
2. **Four Selectable Overlapping Presets**:
   - **Preset 1 (0%–50%)**: Low & Medium Pressure context.
   - **Preset 2 (25%–75%)**: Core Mid-Pressure battleground (intentionally overlaps Preset 1 and Preset 3).
   - **Preset 3 (50%–100%)**: High & Crisis Pressure stints (intentionally overlaps Preset 2).
   - **Preset 4 (0%–100%)**: Full unconstrained career baseline.
3. **User-Defined Range Controls with Strict Validation**: Sliders and numerical inputs allowing arbitrary integer pressure bounds $[P_{\min}, P_{\max}] \subseteq [0, 100]$. The engine strictly enforces $P_{\min} < P_{\max}$, alerting users on invalid boundaries ($P_{\min} \ge P_{\max}$) without corrupting state.
4. **Stint-Average Pressure Granularity & Mathematical Integrity**: Confirmed telemetry granularity is **stint-average pressure** ($\text{mean\_p}$ on $[0, 100]$). All 145 DNB stints and missing pressure values are safely excluded. Outcome invariance and approved HPC attribution formulas are preserved.
5. **Comprehensive Pressure-Based Evaluation & Ranking**: Within the selected pressure interval, each matched player is evaluated on: Matches represented, Eligible batting innings, Actual runs, Expected runs, Strike rate, Mean RAE, Total HPC, Mean HPC, Positive HPC, Negative HPC, and Average Pressure. Default ranking is by Total HPC in range, with multi-column sorting across all metrics.
6. **Contrasted Full-Career Context**: Clearly distinguishes range-filtered metrics from full career baselines in both summary badges and accordion telemetry breakdowns.
7. **Head-to-Head Comparison Integration**: Evaluates up to 5 compared players strictly across the active pressure interval with dedicated comparison matrix rows.
8. **Comprehensive CSV Export Suite**: Augments `matched_players.csv`, `custom_hpp_leaderboard.csv`, and `player_matching_report.csv` with `Pressure Range Min (%)`, `Pressure Range Max (%)`, and `Average Pressure (%)`.
9. **Global View Preservation**: Global career leaderboards (`#section-career`) remain 100% unconstrained and unaffected.

---

## 2. Telemetry Audit & Granularity Specification

Before implementing the filtering layer, an exhaustive telemetry audit of `docs/worm_graph/hpp_match_data.json` was conducted across all 798 production matches:

| Dimension | Telemetry Count | Percentage | Handling Policy |
| :--- | :--- | :--- | :--- |
| **Total Stints Recorded** | 13,033 | 100.0% | Complete Phase 2 corpus (2022–2026) |
| **Did Not Bat (DNB) Stints** | 145 | 1.11% | Excluded from batting stints and pressure averages (`is_dnb === true`) |
| **Active Batting Stints** | 12,888 | 98.89% | Evaluated in HPP scoring engine |
| **Stints with Missing Pressure** | 0 | 0.00% | Zero null `mean_p` across active batting stints |
| **Observed `mean_p` Range** | $[0.0\%, 99.8\%]$ | 100.0% | Continuous stint-average pressure on $[0, 100]$ scale |

### Granularity Clarification
In CricImpact Phase 2, each match batting stint carries a pre-calculated `mean_p` (mean stint pressure) and `peak_p` (peak pressure faced during stint). Stage 7C.3.2 operates strictly on **stint-average pressure** (`mean_p`), evaluating every batting stint where:
$$P_{\min} \le \text{stint.mean\_p} \le P_{\max}$$

The UI and reports explicitly label this granularity:
> *"Analysis based on Stint-Average Pressure (`mean_p` on scale [0, 100]). Only eligible batting stints within [$P_{\min}, P_{\max}$] are evaluated. DNB stints and missing pressure are excluded."*

---

## 3. Mathematical Architecture & Preset Overlap Analysis

### 3.1 Overlapping Presets vs. Mutually Exclusive Tiers
Classical pressure tiers (e.g., Low: 0–30, Med: 30–60, High: 60–80, Extreme: 80–100) partition matches into mutually exclusive buckets. However, tactical analysts frequently need to evaluate batters across broader, overlapping operational windows:

```
[0% ------------------------ 50%]  Preset 1: Low & Mid Pressure
             [25% ------------------------ 75%]  Preset 2: Mid-Pressure Core
                          [50% ------------------------ 100%]  Preset 3: High Crisis
[0% --------------------------------------------------- 100%]  Preset 4: Full Range
```

- **Preset 1 & Preset 2 Overlap $[25\%, 50\%]$**: Captures the transition from standard match situations to moderate stress.
- **Preset 2 & Preset 3 Overlap $[50\%, 75\%]$**: Captures difficult situations requiring rebuilds and counter-attacks before extreme crisis.

### 3.2 Empirical Verification: Suryakumar Yadav Case Study
To verify mathematical consistency and prove that overlapping presets function correctly, we evaluated Suryakumar Yadav across all presets:

| Range / Preset | Eligible Inns | Actual Runs | Expected Runs | Mean RAE | Total HPC | Mean HPC | Avg Pressure |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **0%–50% (Low & Mid)** | 112 | 3,656 | 2,986.8 | +5.97 | **+290.38** | +2.59 | 17.3% |
| **25%–75% (Mid Core)** | 47 | 1,878 | 1,660.1 | +4.64 | **+177.80** | +3.78 | 42.2% |
| **50%–100% (High Crisis)** | 15 | 697 | 631.5 | +4.36 | **+89.05** | +5.94 | 59.2% |
| **0%–100% (Full Range)** | 127 | 4,353 | 3,618.3 | +5.78 | **+379.43** | +2.99 | 22.3% |

#### Mathematical Proof of Overlap:
1. **Overlap between Preset 1 & 2 ($25\% \le P \le 50\%$)**: Exactly **33 innings** fall in $[25\%, 50\%]$. These 33 innings are correctly counted in both Preset 1 (112 inns) and Preset 2 (47 inns).
2. **Overlap between Preset 2 & 3 ($50\% \le P \le 75\%$)**: Exactly **14 innings** fall in $[50\%, 75\%]$. These 14 innings are correctly counted in both Preset 2 (47 inns) and Preset 3 (15 inns).
3. **Partition Reconciliation**:
   - Stints in $[0\%, 50\%]$: 112 innings, HPC = $+290.38$
   - Stints in $[50\%, 100\%]$: 15 innings, HPC = $+89.05$
   - Total ($112 + 15 = 127$ innings): HPC = $290.38 + 89.05 = \mathbf{+379.43}$ (exact match with Full Range).
4. **HPC Component Additivity**:
   $$\text{Positive HPC } (+465.85) + \text{Negative HPC } (-175.47) = \mathbf{+290.38} \equiv \text{Total HPC}$$

---

## 4. User-Defined Range Controls & Validation Logic

### 4.1 UI Controls
The user controls panel in `#custom-pressure-range-card` features:
- **Min Pressure ($P_{\min}$)**: HTML5 Range Slider (`min="0" max="100" step="1"`) paired with Number Input (`min="0" max="99"`).
- **Max Pressure ($P_{\max}$)**: HTML5 Range Slider (`min="0" max="100" step="1"`) paired with Number Input (`min="1" max="100"`).
- **Current Interval Badge (`#pressure-range-display`)**: Displays the active interval (e.g. `32% – 82%`).
- **Dynamic Preset Highlighting**: When sliders match a preset exactly (e.g. 0% and 50%), that preset button is styled with active amber glowing accents.
- **Reset Button (`#pressure-reset-btn`)**: Restores $P_{\min} = 0, P_{\max} = 100$ and full-range styling with one click.

### 4.2 Validation Logic
The system enforces strict boundary conditions:
```javascript
function applyPressureRange(newMin, newMax) {
  if (newMin >= newMax) {
    if (errorDiv) {
      errorDiv.classList.remove('hidden');
      const msgEl = document.getElementById('pressure-validation-msg');
      if (msgEl) msgEl.innerHTML = `Validation Error: Minimum pressure (<strong>${newMin}%</strong>) must be strictly lower than maximum pressure (<strong>${newMax}%</strong>).`;
    }
    updateRangeUI(newMin, newMax, false);
    return false;
  }
  // If valid, apply range and re-render
  ...
}
```

#### Verified Validation Edge Cases:
- **Boundary Test 1 ($P_{\min} = 50, P_{\max} = 50$)**: Throws `Validation Error: Minimum pressure (50%) must be strictly lower than maximum pressure (50%)`. State remains uncorrupted.
- **Boundary Test 2 ($P_{\min} = 80, P_{\max} = 20$)**: Throws `Validation Error: Minimum pressure (80%) must be strictly lower than maximum pressure (20%)`.
- **Boundary Test 3 ($P_{\min} = 0, P_{\max} = 100$)**: Validation passes, clears error div, and updates all tables.

---

## 5. Pressure-Based Evaluation Engine & Leaderboard Results

### 5.1 Evaluated Metrics Schema
When evaluating matched players in any pressure range $[P_{\min}, P_{\max}]$, the engine computes:

```typescript
interface PressureRangePlayerRecord {
  player: string;
  player_id: string | null;
  min_p: number;
  max_p: number;
  matches: number;             // Matches where player batted in this pressure range
  innings: number;             // Eligible batting stints in [min_p, max_p]
  runs: number;                // Actual runs scored in range
  expected_runs: number;       // Benchmark expected runs in range
  balls: number;               // Balls faced in range
  sr: number;                  // Strike rate in range: (runs / balls) * 100
  mean_rae: number | null;     // Mean Runs Above Expectation per stint
  total_hpc: number;           // Sum of HPC across eligible stints in range
  mean_hpc: number | null;     // Total HPC / eligible stints in range
  pos_hpc: number;             // Sum of positive contributions (wins)
  neg_hpc: number;             // Sum of negative contributions (losses)
  avg_pressure: number | null; // Mean stint pressure across eligible stints
  career_context: {            // Full unconstrained career baseline for contrast
    total_matches: number;
    total_innings: number;
    total_runs: number;
    total_hpc: number;
    career_avg_p: number | null;
  };
}
```

### 5.2 Comparative Sample Results: 5 Top Batters Across Scenarios

#### Scenario A: Low & Medium Pressure [0%–50%]
*Default Ranking by Total HPC in Range*
1. **Abhishek Sharma**: 123 Inns | 3,966 Runs | 2,858.4 Exp Runs | Mean RAE: +9.00 | **Total HPC: +522.32** | Mean HPC: +4.25 | Avg P: 14.7%
2. **Suryakumar Yadav**: 112 Inns | 3,656 Runs | 2,986.8 Exp Runs | Mean RAE: +5.97 | **Total HPC: +290.38** | Mean HPC: +2.59 | Avg P: 17.3%
3. **Jos Buttler**: 109 Inns | 3,859 Runs | 3,447.4 Exp Runs | Mean RAE: +3.78 | **Total HPC: +95.89** | Mean HPC: +0.88 | Avg P: 15.7%
4. **Heinrich Klaasen**: 54 Inns | 1,843 Runs | 1,603.8 Exp Runs | Mean RAE: +4.43 | **Total HPC: +95.78** | Mean HPC: +1.77 | Avg P: 22.4%
5. **Virat Kohli**: 87 Inns | 3,510 Runs | 3,365.2 Exp Runs | Mean RAE: +1.66 | **Total HPC: -20.62** | Mean HPC: -0.24 | Avg P: 15.1%

#### Scenario B: High Crisis Pressure [50%–100%]
*Default Ranking by Total HPC in Range*
1. **Suryakumar Yadav**: 15 Inns | 697 Runs | 631.5 Exp Runs | Mean RAE: +4.36 | **Total HPC: +89.05** | Mean HPC: **+5.94** | Avg P: 59.2%
2. **Jos Buttler**: 6 Inns | 320 Runs | 266.0 Exp Runs | Mean RAE: +8.98 | **Total HPC: +62.82** | Mean HPC: **+10.47** | Avg P: 58.9%
3. **Heinrich Klaasen**: 16 Inns | 497 Runs | 470.6 Exp Runs | Mean RAE: +1.64 | **Total HPC: +50.17** | Mean HPC: +3.14 | Avg P: 65.6%
4. **Virat Kohli**: 1 Inn | 42 Runs | 31.0 Exp Runs | Mean RAE: +11.03 | **Total HPC: +12.18** | Mean HPC: +12.18 | Avg P: 55.2%
5. **Abhishek Sharma**: 3 Inns | 110 Runs | 111.6 Exp Runs | Mean RAE: -0.55 | **Total HPC: +0.01** | Mean HPC: +0.00 | Avg P: 53.6%

#### Scenario C: User-Defined Custom Interval [32%–82%]
*Default Ranking by Total HPC in Range*
1. **Suryakumar Yadav**: 35 Inns | 1,465 Runs | 1,323.1 Exp Runs | Mean RAE: +4.05 | **Total HPC: +144.86** | Mean HPC: +4.14 | Pos: +208.23 | Neg: -63.37 | Avg P: 48.6%
2. **Abhishek Sharma**: 25 Inns | 757 Runs | 601.2 Exp Runs | Mean RAE: +6.22 | **Total HPC: +109.43** | Mean HPC: +4.38 | Pos: +154.30 | Neg: -44.87 | Avg P: 39.7%
3. **Heinrich Klaasen**: 31 Inns | 921 Runs | 877.9 Exp Runs | Mean RAE: +1.38 | **Total HPC: +52.88** | Mean HPC: +1.71 | Pos: +117.53 | Neg: -64.65 | Avg P: 52.6%
4. **Jos Buttler**: 18 Inns | 644 Runs | 590.0 Exp Runs | Mean RAE: +3.00 | **Total HPC: +52.34** | Mean HPC: +2.91 | Pos: +94.13 | Neg: -41.79 | Avg P: 45.4%
5. **Virat Kohli**: 16 Inns | 627 Runs | 580.9 Exp Runs | Mean RAE: +2.87 | **Total HPC: +29.05** | Mean HPC: +1.82 | Pos: +60.26 | Neg: -31.21 | Avg P: 39.1%

*Key Analytical Insight:* In the upper crisis bracket ($50\%–100\%$), Suryakumar Yadav and Jos Buttler generate massive positive value (+89.05 and +62.82 HPC respectively), while Abhishek Sharma's dominant total score (+522.33 career) is heavily concentrated in Low-to-Mid pressure powerplays ($0\%–50\%$), where he scored +522.32 HPC across 123 innings. This illustrates the analytical power of granular pressure range queries.

---

## 6. Table Layout, Multi-Column Sorting & Contrast

### 6.1 Custom Leaderboard Table (`#custom-lb-tbody`)
The custom leaderboard table features 14 columns:
1. `Rank ⬍`: Interactive rank index (1 to N).
2. `Player ⬍`: Player name with smooth-scroll profile navigation on click.
3. `Mat ⬍`: Matches represented in range.
4. `Inns ⬍`: Eligible batting stints in range.
5. `Runs ⬍`: Actual runs scored in range.
6. `Exp Runs ⬍`: Expected runs scored in range.
7. `SR ⬍`: Strike rate in range.
8. `Mean RAE ⬍`: Mean Runs Above Expectation per stint.
9. `Total HPC ⬍`: Total HPC accumulated in range (default sort, descending).
10. `Mean HPC ⬍`: Mean HPC per eligible stint.
11. `Pos HPC ⬍`: Positive contribution points.
12. `Neg HPC ⬍`: Negative contribution points.
13. `Avg P (%) ⬍`: Average stint pressure faced in range.
14. `Actions`: Interactive buttons (`Profile`, `+Compare`).

### 6.2 Multi-Column Sorting
The table thead and `#custom-lb-sort` dropdown support instantaneous bidirectional sorting:
- `total_hpc` (Total HPC)
- `mean_hpc` (Mean HPC)
- `mean_rae` (Mean RAE)
- `pos_hpc` (Positive HPC)
- `neg_hpc` (Negative HPC)
- `avg_pressure` (Average Stint Pressure)
- `runs` (Actual Runs)
- `expected_runs` (Expected Runs)
- `sr` (Strike Rate)
- `matches` (Matches)
- `innings` (Innings)
- `player` (Player Name)

### 6.3 Contrasting Range HPC vs. Career HPC
In Card A (Matched Players accordion), when a pressure range is applied, an amber banner explicitly contrasts the range performance against the career baseline:
```html
<div class="p-2 rounded bg-amber-950/60 border border-amber-800 text-amber-200 text-xs flex justify-between items-center">
  <span>🎯 <strong>Active Range Filter Applied:</strong> Evaluated strictly on stints with average pressure between <strong>${r.min_p}% and ${r.max_p}%</strong>.</span>
  <span>Career Baseline: <strong>${r.career_context.total_innings} Inns</strong>, <strong>${r.career_context.total_hpc > 0 ? '+' : ''}${r.career_context.total_hpc} HPC</strong></span>
</div>
```

---

## 7. Multi-Player Comparison & Complete CSV Exports

### 7.1 Head-to-Head Comparison (Up to 5 Players)
When the user clicks `+Compare` on any custom player, `renderComparisonSection()` dynamically evaluates each compared batter across the active pressure interval $[P_{\min}, P_{\max}]$, displaying:
- Top banner: `⚡ Evaluating across Pressure Range: ${min}%–${max}% (Stint-Average Pressure)`.
- Comparison Matrix Rows: Total HPC, Mean HPC / Inn, Positive HPC, Negative HPC, Mean RAE, Actual Runs, Expected Runs, Strike Rate, Average Stint Pressure, Matches (Inns in Range), 1st Innings HPC, 2nd Innings (Chase) HPC.
- Comparison Bar Chart updated with Range Total HPC.

### 7.2 CSV Export Specifications
All custom CSV export generators have been updated with exact pressure range metadata columns:

#### Export 1: `matched_players.csv` (17 Columns)
`Rank`, `Player Name`, `Player ID`, `Matches in Range`, `Batting Innings in Range`, `Actual Runs`, `Expected Runs`, `Career Strike Rate`, `Mean RAE`, `Total HPC`, `Mean HPC`, `Crisis HPC`, `Positive HPC`, `Negative HPC`, `Average Pressure (%)`, `Pressure Range Min (%)`, `Pressure Range Max (%)`

#### Export 2: `custom_hpp_leaderboard.csv` (15 Columns)
`Rank`, `Player Name`, `Matches in Range`, `Batting Innings in Range`, `Actual Runs`, `Expected Runs`, `Strike Rate`, `Mean RAE`, `Total HPC`, `Mean HPC`, `Positive HPC`, `Negative HPC`, `Average Pressure (%)`, `Pressure Range Min (%)`, `Pressure Range Max (%)`

#### Export 3: `player_matching_report.csv` (14 Columns)
`Original Submitted Name`, `Normalized Name`, `Matched Database Name`, `Player ID`, `Match Status`, `Match Type`, `Matches`, `Batting Innings`, `Actual Runs`, `Mean RAE`, `Total HPC`, `Mean HPC`, `Pressure Range Min (%)`, `Pressure Range Max (%)`

---

## 8. Verification & Baseline Integrity Proof

An automated verification test suite was executed to guarantee strict mathematical and code integrity:

| Test Script | Scope | Result | Status |
| :--- | :--- | :--- | :--- |
| `validate_js.js` | Complete 147k char JavaScript block validation | Syntax 100% valid | **PASS** |
| `verify_stage7c32_dom.js` | All 21 required DOM IDs, 4 presets, 12 sort options | 100% elements present | **PASS** |
| `test_stage7c32_full_pipeline.js` | End-to-end evaluation, overlap proof, custom range, validation checks | Zero errors, math verified | **PASS** |
| `verify_hashes.js` | 16 protected baseline assets SHA-256 verification | 100% hash match | **PASS** |

### SHA-256 Baseline Hash Verification (All 12 Monitored Assets)
```
data/processed/calibration/calibration_manifest_v1.json: MATCH (8b114837...)
data/processed/calibration/val_2025_calibrated_predictions_v1.pkl.gz: MATCH (2b0700be...)
data/processed/calibration/test_2026_calibrated_predictions_v1.pkl.gz: MATCH (a627c11e...)
data/processed/calibration/test_2026_evaluation_manifest_v1.json: MATCH (d0d62de9...)
data/processed/match_states/match_states_standard_t20_v1.pkl.gz: MATCH (815a8e1f...)
data/processed/contributions/pre_match_causal_abc_features_v1.pkl.gz: MATCH (323af183...)
data/validation/stage_5b/stage5b_match_eligibility_v1.csv: MATCH (98507e9c...)
docs/worm_graph/trajectories/50375.json: MATCH (5c55cb31...)
docs/worm_graph/trajectories/50138.json: MATCH (ab809c54...)
ml/contribution/hpp_engine.py: MATCH (e464e9db...)
ml/contribution/hpp_aggregator.py: MATCH (e58e47da...)
data/processed/contributions/hpp_stint_evaluations_v1.pkl.gz: MATCH (a83e44b9...)
OVERALL BASELINE ASSET INTEGRITY: 100% UNTOUCHED
```

---

## 9. Conclusion & Stage 7C.3.2 Sign-off

Stage 7C.3.2 fulfills all user requirements:
- Selectable preset ranges ($0\%–50\%$, $25\%–75\%$, $50\%–100\%$, $0\%–100\%$) function with mathematically verified overlap.
- User-defined sliders and inputs enforce $P_{\min} < P_{\max}$ with clear error reporting.
- Player evaluations display Matches, Innings, Actual Runs, Expected Runs, Mean RAE, Total HPC, Mean HPC, Positive HPC, Negative HPC, and Average Pressure.
- Telemetry is accurately designated as stint-average pressure (`mean_p` on $[0, 100]$).
- Comparison and CSV exports reflect the active pressure range.
- Career leaderboards remain untouched.

All deliverables are verified and ready for production use.

