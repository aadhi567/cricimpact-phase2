# CricImpact Phase 2 — Stage 5C Preparation: Phase 1 ABC Methodology Recovery and Compatibility Audit

**Document Status:** `SUPERSEDED IN PART BY STAGE 5C v2.0` (Sections `1–12` remain the authoritative frozen record of Phase 1 ABC methodology recovery and compatibility audit; Sections `13–14` updated for **Universal Strategy 4 Evaluation**, see [`stage_5c_universal_strategy4_specification.md`](file:///c:/Users/admin/Documents/CricImpact_Phase2/docs/stage_5c_universal_strategy4_specification.md) and [`stage_5c_implementation_plan.md`](file:///c:/Users/admin/Documents/CricImpact_Phase2/docs/stage_5c_implementation_plan.md) — No Stage 5C Code Written)  
**Target Workspace (Phase 2):** `C:\Users\admin\Documents\CricImpact_Phase2`  
**Reference Workspace (Phase 1, Read-Only):** `C:\Users\admin\Documents\contribution`  
**Initial Recovery Date (UTC):** `2026-11-12` | **Revision `v2.0` Date (UTC):** `2026-11-12`

---

## Executive Summary

1. **Terminology Crosswalk:** The acronym **`ABC` ("Average Batter Contribution")** does **not** appear literally in Phase 1 source code, API payloads, or frontend components. In Phase 1 production code, data tables, FastAPI endpoints, and React UI, the concept is implemented as:
   - **Match-level batter contribution:** `contribution_score` (on a `[0.1, 99.9]` logistic scale centered at Par = `50.0`), alongside signed `raw_contribution` in z/macroeconomic units.
   - **Season / Career Average Batter Contribution (ABC):** `average_contribution_score` (season table/profile) and `average_contribution` (career/yearly/venue/home-away endpoints), defined as the arithmetic mean of non-null `contribution_score` over all genuine batting appearances (Did-Not-Bat `[DNB]` appearances strictly excluded).
   - **Accompanying Volume/Positive Contribution Metrics:** `total_positive_raw_contribution`, `Positive Contribution Rate` (`%` of batted innings with `contribution_score > 50.0`), `season_team_contribution_share`, and `contribution_per_batting_opportunity`.
2. **Active Production Engine Split in Phase 1:** Per [`scoring_engine_config.json`](file:///c:/Users/admin/Documents/contribution/data/scoring_engine_config.json), the active engine tag is **`v8.5.1-strategy4-hybrid`**. However, inspection of [`execute_phase_b_staging.py`](file:///c:/Users/admin/Documents/contribution/scratch/execute_phase_b_staging.py) and [`phase8_5_hyper_score_damping.py`](file:///c:/Users/admin/Documents/contribution/src/phase8_5_hyper_score_damping.py) proves that active IPL production is a **hybrid cutover**:
   - **IPL 1st Innings (`9,610` non-DNB rows):** Scored by **Phase 8.5 Strategy 4 (`v8.5.1-strategy4-hybrid`)**, using Resource-Adjusted Par Damping (standard 20-over) or Workstream B Overs-Scaled Par (rain-shortened) for Pillar 3, while keeping Pillar 1 Leverage $L$ and Pillar 2 from Phase 7U.
   - **IPL 2nd Innings (`9,208` non-DNB rows):** Bit-for-bit identical to **Phase 7U** (`compute_production_contribution()` in [`contribution_framework.py`](file:///c:/Users/admin/Documents/contribution/src/contribution_framework.py)).
   - **Non-IPL Datasets (T20I, SMAT, SA20) & Live Post-Match Updater:** [`ingest_competition_data.py`](file:///c:/Users/admin/Documents/contribution/scripts/ingest_competition_data.py), [`ingest_sa20.py`](file:///c:/Users/admin/Documents/contribution/scripts/ingest_sa20.py), [`regenerate_competition_contributions.py`](file:///c:/Users/admin/Documents/contribution/scripts/regenerate_competition_contributions.py), and [`post_match_processor.py`](file:///c:/Users/admin/Documents/contribution/app/services/post_match_processor.py) bypass Strategy 4 and the Random Forest ML models entirely—calling Phase 7U (`compute_production_contribution()`) with hardcoded heuristic baselines (`expected_runs = 1.25 * balls_faced`, `expected_sr = 125.0`, `trajectory_deviation_change = NaN`).
3. **Zero Outcome Leakage in Production Scoring:** Contrary to stale JSON specs referencing outcome leverage $L_{\text{out}}$, production Phase 7U and Strategy 4 have **zero dependency** on `won_match` or `winning_margin` (verified empirically in [`leakage_audit.json`](file:///c:/Users/admin/Documents/contribution/models/contribution/leakage_audit.json) and source code). However, for **Phase 2 Win Probability prediction**, post-match ABC cannot be used on the current match (it reads exit-state, full-stay, and partner-dismissal telemetry); only **strictly pre-match rolling historical ABC** computed prior to `match_date` is causally valid.

---

## 1. Phase 1 Source Files Inspected

Every formula, parameter, and discrepancy in this report is verified directly from the following read-only Phase 1 files:

### 1.1 Core Contribution & Context Scoring Engines

| File Path | Key Functions / Classes / Constants | Verified Lines | Role in Phase 1 |
|:---|:---|:---|:---|
| [`contribution_framework.py`](file:///c:/Users/admin/Documents/contribution/src/contribution_framework.py) | `PHASE5B_EMPIRICAL_PARAMS` (`382–394`), `compute_pillar2_batter_performance` (`472–518`), `P3_WICKET_ATTR_*_GAMMA` (`525–528`), `compute_attributable_team_state_efs` (`531–625`), `compute_season_aggregation` (`888–962`), `P3_STANDARDIZATION_*` (`972–974`), `compute_wicket_crisis_signal` (`977–1018`), `compute_chase_pressure_signal` (`1021–1065`), `compute_opening_opportunity_signal` (`1068–1086`), `compute_match_state_leverage_classification` (`1089–1111`), `leverage_model_b` (`1114–1134`), `compute_context_and_leverage` (`1137–1163`), `compute_chase_feasibility_signal` (`1166–1189`), `map_raw_to_p3_score` (`1192–1196`), `check_p3_preservation_eligibility` (`1209–1303`), `apply_p3_state_preservation_floor` (`1306–1330`), `compute_dampened_p3_raw` (`1351–1448`), `compute_production_contribution` (`1502–1769`) | `1–1771` | Phase 7U production scoring engine (SHA-256: `8C5CFBC613D583CB7B70887C9F8BCE489912C8370FCBD96EF56FBE7E9C8AA277`). Active for all 2nd innings and non-IPL pipelines. |
| [`phase8_5_hyper_score_damping.py`](file:///c:/Users/admin/Documents/contribution/src/phase8_5_hyper_score_damping.py) | `compute_damped_c_res_hybrid_raw_p3` (`341–443`), `RAIN_SHORTENED_MATCH_OVERS` (`523–531`), `get_cached_par_curve_20` (`536–549`), `compute_calibrated_rain_shortened_raw_p3` (`558–692`), `evaluate_phase8_5_unified_raw_p3` (`699–759`), `compute_phase8_5_unified_contribution` (`762–824`) | `1–824` | Active Strategy 4 (`v8.5.1-strategy4-hybrid`) engine for IPL 1st innings. |
| [`phase8_collapse_attribution_prototype.py`](file:///c:/Users/admin/Documents/contribution/src/phase8_collapse_attribution_prototype.py) | `HISTORICAL_IPL_PAR_TOTAL = 166.5` (`52`), `validate_expected_runs_input` (`59–96`), `HISTORICAL_WICKET_LOSS_CURVE` (`419–423`), `get_historical_wickets_lost_at_ball` (`426–438`) | `1–705` | Resource-adjusted par curve and DNB / NaN / negative `expected_runs` input validator. |
| [`scoring_engine_config.py`](file:///c:/Users/admin/Documents/contribution/src/scoring_engine_config.py) & [`scoring_engine_config.json`](file:///c:/Users/admin/Documents/contribution/data/scoring_engine_config.json) | `ScoringEngineVersion`, `get_active_scoring_engine` | `1–44` / `1–5` | Active engine pointer (`"v8.5.1-strategy4-hybrid"`). |
| [`staging_scoring_engine_adapter.py`](file:///c:/Users/admin/Documents/contribution/src/staging_scoring_engine_adapter.py) | Adapter routing between Phase 7U and Strategy 4 | `1–154` | Engine switch adapter for staging verification. |
| [`phase7c_rebalance.py`](file:///c:/Users/admin/Documents/contribution/src/phase7c_rebalance.py) | `PHASE5B_EMPIRICAL_PARAMS`, `PHASE7C_P3_PARAMS`, `compute_phase7c_p4_diagnostic` | `1–784` | Supplies P2/P4 helpers and diagnostic fallback inside `compute_production_contribution`. |

### 1.2 Upstream Match-State, Trajectory & Expected-Performance ML Pipelines

| File Path | Key Functions / Classes | Verified Lines | Role in Phase 1 |
|:---|:---|:---|:---|
| [`data_loader.py`](file:///c:/Users/admin/Documents/contribution/src/data_loader.py) | Cricsheet JSON parser (deliveries, innings, match info) | `1–384` | Raw IPL Cricsheet ingestion. |
| [`innings_context.py`](file:///c:/Users/admin/Documents/contribution/src/innings_context.py) | Innings totals, over completion, target metadata | `1–191` | Innings summary extraction. |
| [`match_state.py`](file:///c:/Users/admin/Documents/contribution/src/match_state.py) | Delivery-level state construction (`overs_completed` cricket float notation) | `1–244` | State builder feeding ML models & trajectory engine. |
| [`chase_context.py`](file:///c:/Users/admin/Documents/contribution/src/chase_context.py) | Target, `required_rr`, `rr_gap` | `1–93` | Second-innings chase metrics. |
| [`partnership.py`](file:///c:/Users/admin/Documents/contribution/src/partnership.py) | Entry/exit partnership runs & shares | `1–265` | Crease occupancy partner attribution. |
| [`context_engine.py`](file:///c:/Users/admin/Documents/contribution/src/context_engine.py) | Batter entry/exit delivery states (`batter_context.csv`) | `1–481` | Batter-innings grain construction. |
| [`expected_score_dataset.py`](file:///c:/Users/admin/Documents/contribution/src/expected_score_dataset.py) | `FEATURE_COLUMNS` (`29–37`), `identify_excluded_matches` (`75–118`), `sample_match_states` (`121–160`) | `1–305` | Training dataset builder for 1st-innings Expected Final Score RF. |
| [`expected_score_model.py`](file:///c:/Users/admin/Documents/contribution/src/expected_score_model.py) | `PHASE_MAPPING`, `SimpleProjectionBaseline`, `HistoricalAverageBaseline`, `ExpectedScoreRFModel` (`144–313`) | `1–313` | Phase 3 RF predicting `expected_final_entry` / `expected_final_exit`. |
| [`phase_expected_model.py`](file:///c:/Users/admin/Documents/contribution/src/phase_expected_model.py) | `PowerplayRFModel`, `MiddleRFModel`, `DeathRFModel` | `1–264` | Auxiliary phase checkpoint RFs (not directly used in Strategy 4 P3). |
| [`batter_trajectory.py`](file:///c:/Users/admin/Documents/contribution/src/batter_trajectory.py) | `compute_historical_par_curve` (`34–66`), `extract_batter_trajectories` (`69–400`) | `1–400` | Computes 1st-inn EFS trajectory & 2nd-inn chase entry/exit deltas. |
| [`expected_batter_model.py`](file:///c:/Users/admin/Documents/contribution/src/expected_batter_model.py) | `BATTER_FEATURE_COLUMNS` (`41–53`), `prepare_batter_model_features` (`58–105`), `ExpectedRunsRFModel` (`184–241`), `ExpectedSRRFModel` (`244–303`) | `1–342` | Phase 4A RFs predicting `expected_runs` and `expected_sr` at batter entry. |
| [`evaluate_batter_performance.py`](file:///c:/Users/admin/Documents/contribution/src/evaluate_batter_performance.py) | `batter_performance_dataset.csv` evaluation & generation | `1–679` | Produces `run_deviation` & `sr_deviation` feed. |
| [`batter_impact_signals.py`](file:///c:/Users/admin/Documents/contribution/src/batter_impact_signals.py) | Impact signal engineering & redundancy analysis | `1–380` | Prepares `batter_impact_signals.csv` (`wickets_lost_during_stay`, etc.). |

### 1.3 Aggregation, Cutover, Competition Pipelines, Backend API & UI

| File Path | Key Functions / Purpose | Verified Lines | Key Findings |
|:---|:---|:---|:---|
| [`season_aggregation.py`](file:///c:/Users/admin/Documents/contribution/src/season_aggregation.py) | `load_match_rosters` (`50–85`), `is_negligible_opportunity` (`88–123`), `compute_all_innings_phase5b` (`126–176`), `build_season_aggregations` (`183–367`) | `1–493` | Computes View A / View B season metrics. **Note:** `compute_all_innings_phase5b()` calls Phase 7U (`compute_production_contribution`), not Strategy 4. |
| [`execute_phase_b_staging.py`](file:///c:/Users/admin/Documents/contribution/scratch/execute_phase_b_staging.py) | `run_phase_b` (`30–244`) | `1–247` | Cutover builder applying `s4_score` / `s4_p3` / `s4_raw_p3` to IPL 1st innings and redefining 1st-inn `raw_contribution`. |
| [`execute_phase_c_and_d_cutover.py`](file:///c:/Users/admin/Documents/contribution/scratch/execute_phase_c_and_d_cutover.py) | `run_cutover` (`51–354`) | `1–354` | Atomic production commit & Chase invariance / DNB / row-count verification gates. |
| [`regenerate_production_pipeline.py`](file:///c:/Users/admin/Documents/contribution/scripts/regenerate_production_pipeline.py) | Production regeneration script | `1–133` | Rebuilds IPL pipeline outputs. |
| [`ingest_competition_data.py`](file:///c:/Users/admin/Documents/contribution/scripts/ingest_competition_data.py) | Multi-comp ingestion (`T20I`, `SMAT`) | `1–647` | Uses heuristic `expected_runs = 1.25 * balls`, `expected_sr = 125.0`, and Phase 7U `compute_production_contribution`. |
| [`ingest_sa20.py`](file:///c:/Users/admin/Documents/contribution/scripts/ingest_sa20.py) | SA20 ingestion (`360–426`, `479`) | `1–688` | Also uses `1.25`/`125.0` heuristics and calls Phase 7U `compute_production_contribution` despite Strategy 4 docstring. |
| [`post_match_processor.py`](file:///c:/Users/admin/Documents/contribution/app/services/post_match_processor.py) | Incremental post-match scorer (`409`) | `1–565` | Calls Phase 7U `compute_production_contribution` with `1.25`/`125.0` heuristic ML fallbacks. |
| [`data_service.py`](file:///c:/Users/admin/Documents/contribution/app/services/data_service.py) | `compare_players` (`3800–4349`), `get_player_home_away_career` (`10250–10550`), View A/B & career timelines | `1–12769` (targeted sections) | Backend consumer computing career/home-away `average_contribution` and `positive_contribution_rate`. Contains View B & positive-score discrepancies. |

### 1.4 JSON Specifications, Audits & Model Artifacts Inspected

- [`phase6_season_spec.json`](file:///c:/Users/admin/Documents/contribution/models/contribution/phase6/phase6_season_spec.json) (stale Phase 7D formula header retained)
- [`contribution_framework.json`](file:///c:/Users/admin/Documents/contribution/models/contribution/contribution_framework.json) (historical Phase 5A/5B spec)
- [`season_aggregation_spec.json`](file:///c:/Users/admin/Documents/contribution/models/contribution/season_aggregation_spec.json)
- [`leakage_audit.json`](file:///c:/Users/admin/Documents/contribution/models/contribution/leakage_audit.json), [`outcome_linkage_analysis.json`](file:///c:/Users/admin/Documents/contribution/models/contribution/outcome_linkage_analysis.json), [`phase6_small_opportunity_audit.json`](file:///c:/Users/admin/Documents/contribution/models/contribution/phase6/phase6_small_opportunity_audit.json)
- [`training_metadata.json`](file:///c:/Users/admin/Documents/contribution/models/expected_score/training_metadata.json), [`feature_names.json`](file:///c:/Users/admin/Documents/contribution/models/expected_batter/feature_names.json), [`metrics.json`](file:///c:/Users/admin/Documents/contribution/models/expected_batter/metrics.json)
- Active CSV schemas checked: IPL [`batter_match_contributions.csv`](file:///c:/Users/admin/Documents/contribution/data/processed/batter_match_contributions.csv) (`19,111 x 98`), [`phase6_season_metrics.csv`](file:///c:/Users/admin/Documents/contribution/models/contribution/phase6/phase6_season_metrics.csv) (`3,357 x 25`), T20I [`batter_match_contributions.csv`](file:///c:/Users/admin/Documents/contribution/data/processed/t20i/batter_match_contributions.csv) (`24,565 x 96`), SA20 [`batter_match_contributions.csv`](file:///c:/Users/admin/Documents/contribution/data/processed/sa20/batter_match_contributions.csv) (`2,031 x 96`).

---

## 2. Exact ABC Formula and Calculation Sequence

### 2.1 High-Level Pipeline Flow

```
Raw Deliveries (ball-by-ball) + Playing XI Rosters
   │
   ├─► Step 1: Batter-Innings Grain Construction (entry_state -> exit_state, batting stats)
   ├─► Step 2: Gate Check — Super Over (innings > 2) & Did-Not-Bat (DNB) => strict NULL
   ├─► Step 3: Upstream ML Predictions (Innings 1 EFS_entry / EFS_exit, par_curve, Expected Runs/SR)
   ├─► Step 4: Pillar 1 — Match Context & Dual-Slope Leverage L in [0.65, 1.35] (0% direct weight)
   ├─► Step 5: Pillar 2 — Individual Batter Execution P2 in [0.1, 99.9] (50% weight)
   ├─► Step 6: Pillar 3 — Team-State Impact P3 in [0.1, 99.9] (50% weight)
   │             ├─ 1st Innings Standard (20-ov): Strategy 4 Hybrid (Res-Adj Par + Damping + Model T + Preservation)
   │             ├─ 1st Innings Rain-Shortened:   Strategy 4 Workstream B (N-over DLS-scaled Par Curve)
   │             └─ 2nd Innings (Chase):          Phase 7U Model E Feasibility Saturation + Preservation
   ├─► Step 7: Match Contribution Score (0.1..99.9) & Raw Contribution (c_raw)
   └─► Step 8: Season / Career ABC = Arithmetic Mean of Non-Null Match `contribution_score`
```

### 2.2 Step-by-Step Mathematical Specification

#### Step 1 & 2 — Eligibility Gate (Super Over & DNB)
For a batter appearance row $r$ in match $m$, innings $I \in \{1, 2, \dots\}$:
- If $I > 2$ (Super Over): return `NULL` (`None`) for all contribution metrics.
- If `dnb is True` or `did_not_bat is True` or `is_dnb is True` or (`balls_faced` is `NaN` and `actual_runs` is `NaN`) or (`balls_faced == 0 and actual_runs == 0 and dismissal_status != "out"`): treat as **DNB**, return `NULL`. Note that a `0`-ball dismissal (e.g., diamond duck / non-striker run out) has `dismissal_status == "out"` and **is scored**.
- In Strategy 4 (`validate_expected_runs_input`), missing, `NaN`, infinite, or negative `expected_runs` also halts scoring and returns `None`.

#### Step 3 — Upstream ML & Trajectory Signals
Let $t_{\text{entry}}$ and $t_{\text{exit}}$ denote `entry_over` and `exit_over` in cricket notation (`over.ball`), converted to legal balls bowled $b_{\text{entry}}$ and $b_{\text{exit}}$:
$$b_{\text{entry}} = 6 \lfloor t_{\text{entry}} \rfloor + \operatorname{round}\bigl((t_{\text{entry}} - \lfloor t_{\text{entry}} \rfloor) \times 10\bigr)$$
- **Innings 1 (Complete 20-over matches, excluding `<19.5 overs & <10 wickets`):**
  - `expected_final_entry` ($\text{EFS}_{\text{entry}}$) and `expected_final_exit` ($\text{EFS}_{\text{exit}}$) predicted by `ExpectedScoreRFModel` (`models/expected_score/expected_score_rf.joblib`). If terminal exit (`exit_balls_remaining == 0` or `exit_wickets_lost >= 10`), $\text{EFS}_{\text{exit}} = \text{exit\_score}$.
  - $\Delta \text{EFS} = \text{expected\_final\_change} = \operatorname{round}(\text{EFS}_{\text{exit}} - \text{EFS}_{\text{entry}}, 1)$.
  - Historical par trajectory $\text{Par}_{20}(b)$ (`0..120` legal balls):
    $$\Delta T_{\text{obs}} = \text{trajectory\_deviation\_change} = \bigl(\text{exit\_score} - \text{Par}_{20}(b_{\text{exit}})\bigr) - \bigl(\text{entry\_score} - \text{Par}_{20}(b_{\text{entry}})\bigr)$$
- **Innings 2 (Chase):**
  - $\text{EFS}_{\text{entry}}, \text{EFS}_{\text{exit}}, \Delta\text{EFS}, \Delta T_{\text{obs}}$ are strictly `NaN` (`NULL`).
  - Uses `target`, `runs_required_entry`, `runs_required_exit`, `required_rr_entry`, `required_rr_exit`, $\Delta \text{RRR} = \text{RRR}_{\text{entry}} - \text{RRR}_{\text{exit}}$ (positive = relief), `rr_gap_change`, `target_progress_change`.
- **Batter Expected Performance (Both Innings 1 & 2 in IPL):**
  - `expected_runs` ($\hat{R}$) and `expected_sr` ($\widehat{\text{SR}}$) predicted by `ExpectedRunsRFModel` and `ExpectedSRRFModel` from entry state (`expected_final_score_at_entry` uses $\text{EFS}_{\text{entry}}$ in Innings 1, `target` in Innings 2, fallback `165.0`).
  - $\Delta R = \text{run\_deviation} = R_{\text{actual}} - \hat{R}$, $\Delta \text{SR} = \text{sr\_deviation} = \text{SR}_{\text{actual}} - \widehat{\text{SR}}$.

#### Step 4 — Pillar 1: Match Context & Leverage $L \in [0.65, 1.35]$
Source: `compute_context_and_leverage()` (`src/contribution_framework.py:1137–1163`).

1. **Wicket Crisis Signal ($C_{\text{wkt}} \in [10.0, 95.0]$):**
   Let $W_{\text{rem}} = \operatorname{clip}(\text{wickets\_remaining\_entry}, 1, 10)$, $W_{\text{lost}} = 10 - W_{\text{rem}}$, $t = \operatorname{clip}(\text{entry\_over}, 0, 20)$, $B_{\text{rem}} = \operatorname{clip}(\text{balls\_remaining\_entry}, 0, 120)$.
   - If $t \le 0.2$ and $W_{\text{lost}} = 0$: $C_{\text{wkt}} = 35.0$.
   - Otherwise:
     $$\text{loss\_rate} = \frac{W_{\text{lost}}}{\max(0.8, t)}, \qquad \text{scarcity} = \frac{B_{\text{rem}} / 6.0}{W_{\text{rem}}}$$
     $$C_{\text{wkt}} = 50.0 + 20.0 \tanh\!\left(0.55 \frac{\text{loss\_rate} - 0.30}{0.25} + 0.45 \frac{\text{scarcity} - 1.8}{0.8}\right) + \mathbf{1}_{[t \le 6.0 \,\land\, W_{\text{lost}} \ge 3]} \cdot \min\bigl(15.0, (W_{\text{lost}} - 2.0) \times 5.0\bigr)$$
     clipped to $[10.0, 95.0]$.

2. **Chase / Tempo Pressure Signal ($C_{\text{chase}}$):**
   - **Innings 1:** If $t \le 4.0$, $C_{\text{chase}} = 50.0$; else $\operatorname{clip}\bigl(50.0 + 10.0 \tanh((7.5 - \text{team\_rr\_entry}) / 2.0), 20.0, 80.0\bigr)$.
   - **Innings 2:** Let $\text{tgt} = \max(0, \text{target})$, $\text{RRR} = \operatorname{clip}(\text{required\_rr\_entry}, 0, 24)$, $\text{gap} = \operatorname{clip}(\text{rr\_gap\_entry}, -4, 8)$ *(Note: production caller `compute_context_and_leverage()` omits `rr_gap_entry`, so `gap = 0.0` in production)*:
     $$C_{\text{chase}} = \operatorname{clip}\!\left(50.0 + 22.0 \tanh\!\left(0.55 \frac{\text{RRR} - 8.25}{2.5} + 0.35 \frac{\text{tgt} - 165.0}{30.0} + 0.10 \cdot \mathbf{1}_{[t > 4.0]} \frac{\text{gap}}{2.5}\right),\, 10.0,\, 95.0\right)$$

3. **Composite Effective Context ($C_{\text{eff}}$) & Asymmetric Dual-Slope Leverage ($L$):**
   $$C_{\text{eff}} = \begin{cases} 0.65\, C_{\text{wkt}} + 0.35\, C_{\text{chase}}, & I = 1 \\ 0.55\, C_{\text{wkt}} + 0.45\, C_{\text{chase}}, & I = 2 \end{cases}$$
   $$L = \operatorname{clip}\!\left(1.0 + \alpha \cdot \frac{C_{\text{eff}} - 50.0}{50.0},\; 0.65,\; 1.35\right), \qquad \alpha = \begin{cases} 0.48, & C_{\text{eff}} \ge 50.0 \\ 0.38, & C_{\text{eff}} < 50.0 \end{cases}$$

#### Step 5 — Pillar 2: Individual Batter Execution ($P_2 \in [0.1, 99.9]$, 50% Weight)
Source: `compute_pillar2_batter_performance()` (`src/contribution_framework.py:472–518`, `849`, `855`, `1666–1670`):
Let $B = \text{balls\_faced}$, $R = \text{actual\_runs}$, $\text{SR} = \text{actual\_sr}$, $\text{bnd\%} = \text{boundary\_percentage}$. If $B = 0$, $z_{\text{sr}} = z_{\text{pace}} = z_{\text{bnd}} = 0.0$; else:
$$z_{\text{runs}} = \frac{R - 19.8}{21.6}, \qquad z_{\text{sr}} = \operatorname{clip}\!\left(\frac{\text{SR} - 125.0}{50.0}, -3.0, 3.5\right)$$
$$z_{\text{pace}} = \operatorname{clip}\!\left(\frac{0.06 \cdot \text{SR} - r_{\text{ref}}}{3.5}, -3.0, 3.5\right), \quad r_{\text{ref}} = \begin{cases} \text{team\_rr\_entry}, & I = 1 \\ \min(24.0, \text{required\_rr\_entry}), & I = 2 \end{cases}$$
$$z_{\text{bnd}} = \operatorname{clip}\!\left(\frac{\text{bnd\%} - 45.0}{30.0}, -2.5, 2.5\right), \qquad z_{\text{base}} = 0.7 \frac{\Delta R}{14.5} + 0.3 \operatorname{clip}\!\left(\frac{\Delta \text{SR}}{48.0}, -3.0, 3.0\right)$$
$$\text{bonus\_no} = \begin{cases} 0.25, & \text{dismissal\_status} \neq \text{"out"} \;\land\; B \ge 1 \\ 0.0, & \text{otherwise} \end{cases}$$
$$p_{2,\text{raw}} = 0.35\, z_{\text{runs}} + 0.25\, z_{\text{sr}} + 0.20\, z_{\text{pace}} + 0.10\, z_{\text{bnd}} + 0.10\, z_{\text{base}} + \text{bonus\_no}$$
$$z_2 = \frac{p_{2,\text{raw}} - (-0.068)}{1.029}, \qquad P_2 = \operatorname{clip}\!\left(\frac{100.0}{1.0 + e^{-1.40 z_2}},\; 0.1,\; 99.9\right)$$

#### Step 6 — Pillar 3: Team-State Impact ($P_3 \in [0.1, 99.9]$, 50% Weight)

Common dynamic wicket resource term $S_{\text{res}}$ (where $B_{\text{rem,exit}} = \text{balls\_remaining\_exit}$, $W_{\text{rem,exit}} = \text{wickets\_remaining\_exit}$, $B_{\text{match}} = 120$ for standard or $6N$ for rain-shortened):
$$S_{\text{res}} = \begin{cases} -\left(c_{\text{base}} - \min\bigl(0.7 c_{\text{base}},\; 0.02 \max(0, R - 15.0)\bigr)\right), & \text{wicket\_resource\_change} < 0 \\ 0.15 \cdot \dfrac{W_{\text{rem,exit}}}{10.0}, & \text{otherwise} \end{cases}$$
where $c_{\text{base}} = \dfrac{B_{\text{rem,exit}}}{B_{\text{match}}} \cdot \dfrac{10.0}{\max(1.0, W_{\text{rem,exit}} + 2.0)} \cdot 0.5$.

**Pathway 3A — 1st Innings Standard 20-Over (`Strategy 4 Hybrid`, `compute_damped_c_res_hybrid_raw_p3`):**
Triggered when $I = 1$, `trajectory_deviation_change` is not NaN, and `match_id` not in `RAIN_SHORTENED_MATCH_OVERS`.
1. **Model T Attributable EFS ($\Delta \text{EFS}_{\text{attr}}$):**
   Let $\text{drag}_{\text{ext}} = \Delta\text{EFS} - \Delta R$, and $\text{partner\_wkts} = \max(0, \text{wickets\_lost\_during\_stay} - \mathbf{1}_{[\text{out}]})$.
   If $\text{drag}_{\text{ext}} \ge 0$, $\text{partner\_wkts} = 0$, golden duck ($B \le 1 \land R = 0$), or minimal stay ($B < 6 \land R < 10$), then $\gamma = 1.00$. Otherwise:
   - Category A (`caused`): `(dots% >= 50 and sr_ratio < 1.15)` or `(actual_sr < 100 and B >= 10)` or `delta_r <= 0` $\implies \gamma = 1.00$.
   - Category C (`severe collapse`): `partner_wkts >= 3` $\implies \gamma = 0.50$.
   - Category B (`independent partner wickets`): `(sr_ratio >= 1.25 or actual_sr >= 150) and dots% < 45 and delta_r > 0` $\implies \gamma = 0.15$.
   - Category C (`2 partner wickets`): `partner_wkts >= 2` $\implies \gamma = 0.50$.
   - Else (`1 partner wicket, general stagnation`): $\gamma = 0.70$.
   $$\Delta \text{EFS}_{\text{attr}} = \Delta R + \gamma \cdot \text{drag}_{\text{ext}}, \qquad z_{\text{efs}} = \frac{\Delta \text{EFS}_{\text{attr}}}{12.0}$$
2. **Damped Context-and-Resource Adjusted Trajectory ($\Delta T_{\text{sat}}$):**
   - Entry pitch climate factor ($M_{\kappa} = 0.25$, $\text{PAR}_{120} = 166.5$):
     $$\kappa_{\text{entry}} = \begin{cases} \operatorname{clip}\!\left(\dfrac{\text{EFS}_{\text{entry}}}{166.5},\; 0.60,\; 1.0\right), & \text{EFS}_{\text{entry}} \le 166.5 \\[6pt] 1.0 + 0.25 \tanh\!\left(\dfrac{\text{EFS}_{\text{entry}} / 166.5 - 1.0}{0.25}\right), & \text{EFS}_{\text{entry}} > 166.5 \end{cases}$$
   - Crease resource depletion factor ($M_f = 0.10$, using `HISTORICAL_WICKET_LOSS_CURVE` $w_{\text{hist}}(b)$):
     $$W_{\text{excess}} = \text{partner\_wkts} - \max\bigl(0.1,\; w_{\text{hist}}(b_{\text{exit}}) - w_{\text{hist}}(b_{\text{entry}})\bigr)$$
     $$f_{\text{res}} = \begin{cases} \operatorname{clip}(1.0 - 0.05\, W_{\text{excess}}, 0.70, 1.0), & W_{\text{excess}} \ge 0 \\ 1.0 + 0.10 \tanh\!\left(\dfrac{-0.05\, W_{\text{excess}}}{0.10}\right), & W_{\text{excess}} < 0 \end{cases}$$
   - Combined multiplier and soft-knee trajectory saturation ($\tau_{\text{knee}} = 12.0, \tau_{\text{scale}} = 8.0$):
     $$\kappa_{\text{resource}} = \operatorname{clip}(\kappa_{\text{entry}} \cdot f_{\text{res}},\; 0.55,\; 1.35)$$
     $$\Delta R_{\text{team}} = \text{team\_score\_exit} - \text{team\_score\_entry}, \qquad \text{par}_{\text{win}} = \Delta R_{\text{team}} - \Delta T_{\text{obs}}, \qquad \Delta T_{\text{res}} = \Delta R_{\text{team}} - \kappa_{\text{resource}} \cdot \text{par}_{\text{win}}$$
     $$\Delta T_{\text{sat}} = \begin{cases} -\tau_{\text{knee}} - \tau_{\text{scale}} \tanh\!\left(\dfrac{|\Delta T_{\text{res}}| - \tau_{\text{knee}}}{\tau_{\text{scale}}}\right), & \Delta T_{\text{res}} < -12.0 \\ \Delta T_{\text{res}}, & \Delta T_{\text{res}} \ge -12.0 \end{cases}$$
3. **Acceleration & Composite Raw $P_3$:**
   $$\text{accel} = \operatorname{clip}\!\left(\frac{\text{window\_team\_rr} - \text{team\_rr\_entry}}{3.0},\; -3.0,\; 3.0\right)$$
   $$p_{3,\text{raw}} = 0.50\, z_{\text{efs}} + 0.25\, \frac{\Delta T_{\text{sat}}}{10.0} + 0.25\, \text{accel} + S_{\text{res}}$$

**Pathway 3B — 1st Innings Rain-Shortened (`Strategy 4 Workstream B`, `compute_calibrated_rain_shortened_raw_p3`):**
Triggered when $I = 1$ and (`trajectory_deviation_change` is `NaN` OR `match_id` in `RAIN_SHORTENED_MATCH_OVERS`).
For scheduled overs $N$ ($b_{\text{match}} = \max(18, \text{balls}(N))$, $n = b_{\text{match}}/6$):
$$\text{Par\_RR}(n) = 8.325 \left(1.0 + 0.35 \frac{\max(0, 20.0 - n)}{15.0}\right), \qquad \text{Par}_{\text{total}} = n \cdot \text{Par\_RR}(n)$$
$$\text{Par}_N(\text{window}) = \max\!\left(0.1,\; \text{Par}_{\text{total}} \frac{\text{Par}_{20}\!\bigl(\tfrac{b_{\text{exit}}}{b_{\text{match}}} 120\bigr) - \text{Par}_{20}\!\bigl(\tfrac{b_{\text{entry}}}{b_{\text{match}}} 120\bigr)}{\text{Par}_{20}(120)}\right)$$
With $\kappa_{\text{raw}} = \frac{\text{team\_score\_entry} + (\text{Par}_{\text{total}} - P_{\text{entry}})}{\text{Par}_{\text{total}}}$ (or $1.0$ at $b_{\text{entry}}=0$), damped as $\kappa_{\text{entry}}$, soft-knee saturated $\Delta T_{\text{sat}}$ ($\tau_{\text{knee}}=12, \tau_{\text{scale}}=8$), Phase 7N early-over blended $\text{RR}_{\text{eff}} = \alpha \cdot \text{team\_rr\_entry} + (1 - \alpha) \cdot 10.0$ where $\alpha = \min(1.0, b_{\text{entry}}/24.0)$ for $t_{\text{entry}} \le 4.0$:
$$p_{3,\text{raw}} = 0.50 \frac{\Delta T_{\text{sat}}}{10.0} + 0.30\,\text{accel}_{\text{eff}} + 0.20\,\frac{\Delta R_{\text{team}} - \text{overs\_spent} \cdot \text{Par\_RR}(n)}{10.0} + S_{\text{res}}$$

**Pathway 3C — 2nd Innings Chase (`Phase 7U`, `compute_dampened_p3_raw` with `strategy="model_e"`):**
- Feasibility capacity (`compute_chase_feasibility_signal`):
  $$V_{\max} = 12.0 + 3.0 \tanh\!\left(\frac{W_{\text{rem}} - 3.5}{2.0}\right) + 4.0 \frac{12.0}{B_{\text{rem}} + 6.0}, \qquad F_{\text{chase}} = \frac{1.0}{1.0 + \exp\!\bigl(4.0 (\text{RRR}_{\text{entry}}/\max(6.0, V_{\max}) - 1.25)\bigr)}$$
  $$\text{pen\_cap} = 4.0 + 6.0\, F_{\text{chase}}$$
- Soft negative RRR / RR-gap saturation:
  $$r_{\text{eff}} = \begin{cases} -\text{pen\_cap} \tanh(|\Delta\text{RRR}| / \text{pen\_cap}), & \Delta\text{RRR} < 0 \\ \min(12.0, \Delta\text{RRR}), & \Delta\text{RRR} \ge 0 \end{cases}, \qquad g_{\text{eff}} = \begin{cases} -\text{pen\_cap} \tanh(|\Delta\text{RR\_gap}| / \text{pen\_cap}), & \Delta\text{RRR} < 0 \\ \min(12.0, \Delta\text{RR\_gap}), & \Delta\text{RRR} \ge 0 \end{cases}$$
- Raw P3 composite:
  $$p_{3,\text{raw}} = 0.50 \frac{r_{\text{eff}}}{3.0} + 0.25 \frac{g_{\text{eff}}}{3.0} + 0.25 \frac{\Delta \text{target\_progress} - 0.15}{0.15} + S_{\text{res}}$$

**State-Preservation Floor (Phase 7Q Model B, Applied to Raw $P_3$ Across Pathways 3A, 3B, 3C):**
If eligible (no DNB, not golden duck, $B \ge 8$ or $R \ge 15$, plus for $I=1$: $\text{EFS}_{\text{entry}} \ge 180 \land \Delta\text{EFS} \ge -2.5 \land \text{window\_team\_rr} \ge 9.0 \land \text{personal\_rr} \ge 8.5$; for $I=2$: $\text{RRR}_{\text{entry}} \le 7.5 \land \Delta\text{RRR} \ge -0.5 \land \Delta\text{target\_progress} \ge 0.20 \land \text{personal\_rr} \ge \text{RRR}_{\text{entry}}$):
$$p_{3,\text{raw}} \leftarrow \max\bigl(p_{3,\text{raw}},\; p_{3,\text{floor}=64.0}\bigr), \qquad p_{3,\text{floor}=64.0} = 0.159 + \frac{-\ln(100/64.0 - 1)}{1.40} \times 1.513 \approx 0.7810$$
*(Note: In 3A/3B, `apply_p3_state_preservation_floor` reads `expected_final_entry` and `expected_final_change`, so in rain-shortened matches where EFS is `NaN`, the gate evaluates `False`.)*

**P3 Standardization:**
$$z_3 = \frac{p_{3,\text{raw}} - 0.159}{1.513}, \qquad P_3 = \operatorname{clip}\!\left(\frac{100.0}{1.0 + e^{-1.40 z_3}},\; 0.1,\; 99.9\right)$$

#### Step 7 — Final Match `contribution_score` & `raw_contribution`
$$\text{Adjusted\_P}_2 = \operatorname{clip}\bigl(50.0 + (P_2 - 50.0) \cdot L,\; 0.1,\; 99.9\bigr)$$
$$\text{Adjusted\_P}_3 = \operatorname{clip}\bigl(50.0 + (P_3 - 50.0) \cdot L,\; 0.1,\; 99.9\bigr)$$
$$\text{contribution\_score} = \operatorname{round}\Bigl(\operatorname{clip}\bigl(0.50\,\text{Adjusted\_P}_2 + 0.50\,\text{Adjusted\_P}_3,\; 0.1,\; 99.9\bigr),\; 1\Bigr)$$

> [!CAUTION]
> **Exact `raw_contribution` Implementation Divergence (Phase 7U vs Strategy 4 Staging):**
> - In **Phase 7U** (`compute_production_contribution()` line `1721`, used on all 2nd innings and all T20I/SA20/post-match runs):
>   $$c_{\text{raw}} = \operatorname{round}\bigl(0.50\,(z_2 \cdot L) + 0.50\,(z_3 \cdot L),\; 4\bigr)$$
>   where $z_k = -\frac{\ln(100 / \operatorname{clip}(P_k, 0.1, 99.9) - 1)}{1.40}$.
> - In **IPL Strategy 4 Cutover** (`execute_phase_b_staging.py` lines `80–81`, active in [`batter_match_contributions.csv`](file:///c:/Users/admin/Documents/contribution/data/processed/batter_match_contributions.csv) for all `9,610` active 1st-innings rows):
>   $$c_{\text{raw}} = \operatorname{round}\!\left(0.50 \cdot \frac{\text{run\_deviation}}{10.0} + 0.50 \cdot p_{3,\text{raw}},\; 4\right)$$
>   This omits both $z_2$ and leverage $L$ on 1st-innings `raw_contribution` while leaving 2nd-innings `raw_contribution` on Phase 7U! Verified directly in active CSVs (e.g., match `1426268`).

#### Step 8 — Season / Career ABC Formula
For player $p$ in scope $S$ (season-team, full career, or filtered subset) with non-null scored batting innings $\mathcal{B}(p, S) = \{r \in S : r.\text{contribution\_score is not NULL}\}$:
$$\text{ABC}(p, S) = \text{average\_contribution\_score}(p, S) = \frac{1}{|\mathcal{B}(p, S)|} \sum_{r \in \mathcal{B}(p, S)} r.\text{contribution\_score}$$
Rounded to `2` decimal places in `phase6_season_metrics.csv` and `DataService` APIs (note: `compute_season_aggregation` in `contribution_framework.py` rounds to `1` decimal place). When $|\mathcal{B}(p, S)| = 0$ (all DNB), returns `None` (`NULL`).

---

## 3. Constants, Weights, Empirical Parameters, and Normalization / Clipping Rules

### 3.1 Master Parameter Registry

| Component | Parameter / Constant | Verified Value | Code Location |
|:---|:---|:---|:---|
| **Final Blend** | `w_adjusted_p2`, `w_adjusted_p3` | `0.50`, `0.50` | `contribution_framework.py:1718`, `phase8_5_hyper_score_damping.py:810` |
| **Score Clamping** | Score & Adjusted Pillar Bounds | `[0.1, 99.9]`, Par = `50.0` | `contribution_framework.py:770, 1463, 1718` |
| **Logistic Slope** | `pillar_scale` ($k$) | `1.40` | `contribution_framework.py:393, 974, 1195` |
| **P1 / Leverage** | `alpha_low`, `alpha_high` | `0.38` ($C_{\text{eff}}<50$), `0.48` ($C_{\text{eff}}\ge 50$) | `contribution_framework.py:1118–1119` |
| **P1 / Leverage** | Bounds on Leverage $L$ | `[0.65, 1.35]`, Par = `1.0` at $C_{\text{eff}}=50$ | `contribution_framework.py:1127, 1134` |
| **P1 Weights** | `C_eff` mix ($C_{\text{wkt}} / C_{\text{chase}}$) | `0.65 / 0.35` (Inn 1), `0.55 / 0.45` (Inn 2) | `contribution_framework.py:1129–1130` |
| **P1 Signal Anchors** | `C_wkt` z-anchors; `C_chase` anchors | Loss rate `(0.30, 0.25)`, Scarcity `(1.8, 0.8)`; Target `(165.0, 30.0)`, RRR `(8.25, 2.5)` | `contribution_framework.py:1008–1010, 1058–1060` |
| **P2 Weights** | `runs, sr, pace, bnd, base` + `not_out` | `0.35, 0.25, 0.20, 0.10, 0.10` + `0.25` (if not out & $B\ge 1$) | `contribution_framework.py:515–517` |
| **P2 Standardization** | `pillar2_mean`, `pillar2_std` | `-0.068`, `1.029` | `contribution_framework.py:385–386` |
| **P2 Component Anchors** | Runs `(19.8, 21.6)`; SR `(125, 50)`; Pace `/3.5`; Bnd `(45, 30)`; Base `0.7*(dR/14.5)+0.3*(dSR/48)` | Clipped: `z_sr, z_pace in [-3, 3.5]`, `z_bnd in [-2.5, 2.5]`, `dSR/48 in [-3, 3]` | `contribution_framework.py:495–513` |
| **P3 Standardization** | `P3_STANDARDIZATION_MEAN`, `_STD` | `0.159`, `1.513` | `contribution_framework.py:972–973` |
| **P3 Model T ($\gamma$)** | `INDEPENDENT, COLLAPSE, STAGNATION, CAUSED` | `0.15`, `0.50`, `0.70`, `1.00` | `contribution_framework.py:525–528` |
| **P3 Strategy 4** | `HISTORICAL_IPL_PAR_TOTAL`, `m_kappa`, `m_f`, `tau_knee`, `tau_scale` | `166.5`, `0.25`, `0.10`, `12.0`, `8.0` | `phase8_collapse_attribution_prototype.py:52`, `phase8_5_hyper_score_damping.py:343–346` |
| **P3 Strategy 4 Clips** | `kappa_entry` ($EFS\le 166.5$), `wkt_drag`, `kappa_res`, `accel` | `[0.60, 1.0]`, `[0.70, 1.0]`, `[0.55, 1.35]`, `[-3.0, 3.0]` | `phase8_5_hyper_score_damping.py:387, 413, 418, 436` |
| **P3 Preservation** | `P3_PRESERVATION_FLOOR_DEFAULT` | `64.0` (raw floor $\approx 0.7810$) | `contribution_framework.py:1206` |
| **P3 Rain Workstream B** | `Par_RR` slope, `b_match` min, `par_20[120]` fallback | `8.325 * (1 + 0.35*(20-n)/15)`, `max(18, balls)`, `172.46` | `phase8_5_hyper_score_damping.py:547, 602, 606, 611` |
| **Model Validation Thresholds** | `EFS_chg / 12.0`, `traj / 10.0`, `chase / 3.0`, `t_prog (0.15, 0.15)` | Empirical scaling constants | `contribution_framework.py:1388–1445` |

### 3.2 `HISTORICAL_WICKET_LOSS_CURVE` (6-Ball Grid, Interpolated)
Source: `src/phase8_collapse_attribution_prototype.py:419–423` (derived from `1,217` clean IPL 1st innings):

| Ball | 0 | 6 | 12 | 18 | 24 | 30 | 36 | 42 | 48 | 54 | 60 | 66 | 72 | 78 | 84 | 90 | 96 | 102 | 108 | 114 | 120 |
|:---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **Avg Wkts Lost** | `0.00` | `0.22` | `0.44` | `0.67` | `0.90` | `1.14` | `1.39` | `1.62` | `1.86` | `2.11` | `2.37` | `2.64` | `2.92` | `3.20` | `3.49` | `3.63` | `4.10` | `4.47` | `4.88` | `5.38` | `5.93` |

### 3.3 Hardcoded `RAIN_SHORTENED_MATCH_OVERS` Dictionary
[`phase8_5_hyper_score_damping.py:523–531`](file:///c:/Users/admin/Documents/contribution/src/phase8_5_hyper_score_damping.py#L523-L531) hardcodes `26` historical IPL Cricsheet match IDs mapped to scheduled/completed overs (`3.4` to `19.2` overs). In Phase 2, these match IDs do not match raw `matches.csv` IDs; Workstream B would only trigger via `pd.isna(trajectory_deviation_change)` unless driven dynamically by Phase 2 `first_inn_revised_overs` / `second_inn_revised_overs`.

### 3.4 Code vs. Documentation & Cross-Pipeline Discrepancy Matrix

| Area | Stale Documentation / Spec / Naive Code | Actual Active IPL Production / Multi-Comp Behavior |
|:---|:---|:---|
| **Architecture & Outcome Linkage** | [`contribution_framework.json`](file:///c:/Users/admin/Documents/contribution/models/contribution/contribution_framework.json) & [`phase6_season_spec.json`](file:///c:/Users/admin/Documents/contribution/models/contribution/phase6/phase6_season_spec.json) describe `0.45 S_ind + 0.40 S_state + 0.15 S_res * L_out` or `0.25 P1 + 0.35 P2 + 0.40 P3`. | Production Phase 7U & Strategy 4 use **P1 as Leverage only (`0%` direct)**, `0.50*Adj(P2) + 0.50*Adj(P3)`, **ZERO `won_match`/`margin` dependency**. |
| **Symmetric vs Dual-Slope Leverage** | `compute_p1_leverage()` (`contribution_framework.py:1488`) uses symmetric slope `0.35`. | Production `leverage_model_b()` uses dual-slope **`0.48`** ($\ge 50$) / **`0.38`** ($< 50$). |
| **Active Engine: IPL vs T20I / SA20 / SMAT / Post-Match** | `scoring_engine_config.json` says `"v8.5.1-strategy4-hybrid"`; `ingest_sa20.py` docstring claims Strategy 4. | Only IPL 1st innings (`9,610` rows) in `batter_match_contributions.csv` uses Strategy 4. All IPL chases (`9,208`), **100% of T20I (`24,565`), SA20 (`2,031`), SMAT, and post-match updates** call Phase 7U (`compute_production_contribution`) with heuristic `expected_runs = 1.25 * balls`, `expected_sr = 125.0`. |
| **`raw_contribution` Definition** | Phase 7U docstring / code computes `0.5*(z2*L) + 0.5*(z3*L)`. | `execute_phase_b_staging.py:80–81` overwrote IPL 1st-inn `raw_contribution` to `0.5*(run_dev/10.0) + 0.5*raw_p3`; IPL 2nd inn keeps Phase 7U formula. |
| **Re-running `season_aggregation.py`** | `execute_phase_b_staging.py:101` passes Strategy 4 dataframe to `build_season_aggregations()`. | `build_season_aggregations()` calls `compute_all_innings_phase5b()` (`season_aggregation.py:202`), which invokes Phase 7U `compute_production_contribution()` (`contribution_framework.py:1692` takes `expected_final_change` branch before `score_state`), **silently reverting Strategy 4** if re-executed on raw inputs without external merge. *(Empirically verified: active `phase6_season_metrics.csv` matches Strategy 4 `batter_match_contributions.csv` within `<= 0.005` rounding across all `2,962` matched player-seasons.)* |
| **`rr_gap_entry` in $C_{\text{chase}}$** | `compute_chase_pressure_signal()` accepts `rr_gap_entry`. | `compute_context_and_leverage()` (`line 1150`) omits `rr_gap_entry`, forcing `gap = 0.0` in production. |

---

## 4. Expected-Performance ML Model Dependencies

Phase 1 uses **three active Random Forest artifacts** (plus three unused phase-checkpoint RFs under `models/expected_score_phase/`) to generate inputs for Pillars 2 and 3.

### 4.1 Model 1: `ExpectedScoreRFModel` (`models/expected_score/expected_score_rf.joblib`)
- **Role:** Predicts 1st-innings final team score (`expected_final_entry`, `expected_final_exit`) at the exact entry and exit state of each batter. Feeds $\Delta\text{EFS}$ (`50%` weight of raw P3 in Inn 1), $\kappa_{\text{entry}}$ in Strategy 4, Preservation Gate `efs_en >= 180.0`, and Feature #11 of Model 2/3.
- **Training Population ([`training_metadata.json`](file:///c:/Users/admin/Documents/contribution/models/expected_score/training_metadata.json)):** `1,217` clean 20-over IPL 1st innings (`974` train matches / `18,438` end-of-completed-over `1..19` samples; `243` test matches / `4,606` samples; excludes incomplete `<19.5 ov & <10 wkts`; `0.4794` season-split $R^2$, overall test MAE `16.69`).
- **Hyperparameters:** `RandomForestRegressor(n_estimators=100, max_depth=12, min_samples_split=10, min_samples_leaf=5, random_state=42)`.
- **Exact 7 Input Features (Strict Order):**
  1. `current_team_runs` (`int`)
  2. `wickets_lost_so_far` (`int`)
  3. `wickets_remaining` (`int = 10 - wickets_lost_so_far`)
  4. `overs_completed` (**WARNING:** trained on **cricket over.ball float notation** e.g. `11.3` rather than continuous `11.5`; see `batter_trajectory.py:106–117, 182` and `expected_score_dataset.py:45`)
  5. `balls_remaining_in_innings` (`int = 120 - legal_balls_bowled`)
  6. `current_team_rr` (`float = runs * 6.0 / legal_balls`, `0.0` when `legal_balls == 0`)
  7. `innings_phase` (`"POWERPLAY": 0, "MIDDLE": 1, "DEATH": 2`, inferred from completed overs)
- **Exit Override Rule (`batter_trajectory.py:202–203`):** If `exit_balls_remaining == 0` or `exit_wickets_lost >= 10`, override `preds_exit = exit_score` (exact observed final score).

### 4.2 Models 2 & 3: `ExpectedRunsRFModel` & `ExpectedSRRFModel` (`models/expected_batter/*.joblib`)
- **Role:** Predict batter's expected runs ($\hat{R}$) and expected strike rate ($\widehat{\text{SR}}$) at entry, producing `run_deviation` ($\Delta R$, used in `P2`'s `10%` `z_base` term, `Model T` $\Delta \text{EFS}_{\text{attr}}$, and IPL 1st-inn staged `raw_contribution`) and `sr_deviation` ($\Delta \text{SR}$, used in `P2`'s `z_base` term and `Model T` `sr_performance_ratio`).
- **Training Population ([`metrics.json`](file:///c:/Users/admin/Documents/contribution/models/expected_batter/metrics.json)):** `19,196` IPL batter innings across `1,243` matches (`19` seasons; train `15,401` / `994` matches; test `3,795` / `249` matches). `ExpectedSRRFModel` filters `balls_faced > 0` during fit (`expected_batter_model.py:271`). Runs $R^2 = 0.1789$ (MAE `14.55`), SR $R^2 = 0.0505$ (MAE `51.51`).
- **Hyperparameters:** `RandomForestRegressor(n_estimators=100, max_depth=8, min_samples_split=20, min_samples_leaf=10, random_state=42)`, predictions clamped $\ge 0.0$.
- **Exact 11 Input Features (`feature_names.json`):**
  1. `batting_position` (`int`, fillna `4`)
  2. `entry_over_num` (`float` cricket notation `entry_over`, fillna `0.0`)
  3. `entry_balls_remaining` (`int`, fillna `120`)
  4. `entry_wickets_remaining` (`int`, fillna `10`)
  5. `entry_team_runs` (`int`, fillna `0`)
  6. `entry_rr` (`float`, fillna `0.0`)
  7. `entry_phase_code` (`{"POWERPLAY": 0, "MIDDLE": 1, "DEATH": 2}`)
  8. `is_chase_code` (`int`, `1` if `innings == 2` else `0`)
  9. `required_rr_at_entry_clean` (`float`, `required_rr_entry` if chase else `0.0`)
  10. `runs_required_at_entry_clean` (`float`, `runs_required_entry` if chase else `0.0`)
  11. `expected_final_score_at_entry` (`float`: `target` if chase else `expected_final_entry`; fallback `165.0`)
- **Joblib Compatibility Check (Verified in Phase 2 `.venv`):** Phase 2 `.venv` runs `scikit-learn 1.9.1`, `pandas 2.3.3`, `numpy 2.5.4`, `joblib 1.6.0`. Test-loading all three `.joblib` artifacts in `.venv` succeeded with **0 warnings** (`expected_score_rf.joblib` $\to$ `RandomForestRegressor`; `expected_runs_model.joblib` & `expected_sr_model.joblib` $\to$ `dict{"model": RandomForestRegressor, "config": dict}`).

### 4.3 Heuristic Fallback When ML Models Are Absent (Non-IPL / Post-Match)
[`ingest_competition_data.py`](file:///c:/Users/admin/Documents/contribution/scripts/ingest_competition_data.py), [`ingest_sa20.py`](file:///c:/Users/admin/Documents/contribution/scripts/ingest_sa20.py), and [`post_match_processor.py`](file:///c:/Users/admin/Documents/contribution/app/services/post_match_processor.py) skip all three ML `.joblib` artifacts and substitute:
$$\hat{R}_{\text{heuristic}} = \operatorname{round}(1.25 \times B, 1), \qquad \widehat{\text{SR}}_{\text{heuristic}} = 125.0, \qquad \text{EFS}_{\text{entry}} = \text{EFS}_{\text{exit}} = \Delta \text{EFS} = \Delta T_{\text{obs}} = \text{NaN}$$
Verified directly in Phase 1 CSVs: **100%** of T20I (`24,565/24,565`) and SA20 (`2,031/2,031`) rows have `expected_final_entry = NaN` and `trajectory_deviation_change = NaN`, meaning 1st innings in T20I/SA20 hit the `compute_dampened_p3_raw` unmodelled/rain-shortened branch rather than the ML EFS branch!

---

## 5. Opportunity and Contextual Adjustments

1. **Context-as-Leverage Symmetry Break ($L \in [0.65, 1.35]$):** Pillar 1 amplifies or dampens *deviation from par (`50.0`)* via $50 + (P_k - 50) \cdot L$. Above-par innings (`>50`) under crisis ($L>1$) are boosted; below-par failures (`<50`) under crisis are penalized *more* severely; low-leverage innings ($L<1$) compress toward `50.0`.
2. **Short-Cameo Protection (No Artificial Balls-Faced Dampener in P2):** `compute_pillar2_batter_performance` omits any `sqrt(balls)` multiplier (`contribution_framework.py:482–483`). Phase 6A audit ([`phase6_small_opportunity_audit.json`](file:///c:/Users/admin/Documents/contribution/models/contribution/phase6/phase6_small_opportunity_audit.json)) confirmed `29.59%` of scored IPL innings are $\le 5$ balls (`5,655` innings, `933` high-positive), so cameo impact is protected in View A.
3. **Opening Opportunity Signal (`C_open`):** `compute_opening_opportunity_signal` (`38.0` if $t \le 0.2 \land W_{\text{rem}} \ge 10$; `42.0` if $t \le 2 \land W_{\text{rem}} \ge 9$; `48.0` if $t \le 6 \land W_{\text{rem}} \ge 8$; else `50.0`) is emitted as telemetry only — it does **not** enter $C_{\text{eff}}$ or $L$.
4. **View B Negligible-Opportunity Filter (`is_negligible_opportunity`):**
   - **Canonical Definition (`season_aggregation.py:88–123`):** Excludes an innings ONLY if ALL hold: `balls_faced <= 2`, `dismissal_status` not a dismissal (`out`/`bowled`/`caught`/`lbw`/`run out`/`stumped`), `|raw_contribution| <= 0.10`, and minimal state change (`|expected_final_change| <= 2.0` in Inn 1 or `|required_rr_change| <= 0.5` in Inn 2).
   - **DataService Fallback Discrepancy (`data_service.py:3972–3974` & `compare_players`):** If `"is_negligible"` column is absent, `DataService` falls back to `(balls_faced >= 10) | (actual_runs >= 20)` — a drastically stricter threshold than `balls <= 2`!
5. **Contextual Zone Classification (`context_zone`):** `EXTREME CRISIS` ($C_{\text{wkt}} \ge 65 \land C_{\text{chase}} \ge 60$), `COLLAPSE PRESSURE` ($C_{\text{wkt}} \ge 65$), `HIGH CHASE PRESSURE` ($C_{\text{chase}} \ge 60$), `LOW CONTEXT PRESSURE` ($C_{\text{wkt}} < 40 \land C_{\text{chase}} < 42$), else `NORMAL CONTEXT`. Used to filter **`high_pressure_contribution`** via `score_context >= 60.0` (which equals `c_eff >= 60.0`).

---

## 6. Positive Contribution Calculation

Phase 1 tracks three distinct "Positive Contribution" metrics with a **major backend/frontend discrepancy** to guard against:

1. **Cumulative Positive Raw Contribution (`total_positive_raw_contribution`):**
   - **Canonical (`season_aggregation.py:287`, `phase6_season_metrics.csv`, `data_service.py:compare_players:4105`):**
     $$\text{Total Positive Raw Contribution}(p, S) = \sum_{r \in \mathcal{B}(p, S)} \max\bigl(0.0,\; r.\text{raw\_contribution}\bigr)$$
   - **Note on IPL 1st vs 2nd innings scaling:** Because `execute_phase_b_staging.py` altered 1st-innings `raw_contribution`, summing `max(0, raw_contribution)` across a season mixes `(run_dev/10 + raw_p3)/2` in 1st innings with `(z2*L + z3*L)/2` in 2nd innings!
   - **CRITICAL Bug/Discrepancy in `DataService.get_player_home_away_career` (`data_service.py:10342–10344`) & `HomeAwayBreakdownView.jsx` (`line 276`):** Both compute `pos_scores = [s for s in valid_scores if s > 0]; sum(pos_scores)` — summing **`contribution_score`** (the `0.1–99.9` logistic scale, always `> 0`!) rather than `max(0, raw_contribution)`. Thus Home/Away `total_positive_contribution` is on the 0–100-per-innings scale (`~50 * innings`), completely incompatible with `total_positive_raw_contribution` (`~0.5 * innings`).
2. **Positive Contribution Rate (`%`):**
   - **Canonical (`data_service.py:10348`):** Percentage of scored innings beating par (`50.0`):
     $$\text{Positive Contribution Rate}(p, S) = \frac{|\{r \in \mathcal{B}(p, S) : r.\text{contribution\_score} > 50.0\}|}{|\mathcal{B}(p, S)|} \times 100\%$$
3. **Team Contribution Share (`season_team_contribution_share` / match `rectified_positive` share):**
   - Rectified-positive share (`contribution_framework.py:341–350`, `season_aggregation.py:293–296`):
     $$\text{Share}(p, S_{\text{team}}) = \frac{\sum_{r \in \mathcal{B}(p, S_{\text{team}})} \max(0.0, r.\text{raw\_contribution})}{\sum_{j \in \text{team}} \sum_{r \in \mathcal{B}(j, S_{\text{team}})} \max(0.0, r.\text{raw\_contribution})} \times 100.0$$
   - At match level (`compute_team_contribution_shares`), if the denominator $\le 10^{-6}$ (all batters $\le 0$), share divides uniformly (`100.0 / n`); at season level, returns `0.0` (or `None` if DNB).
   - View B (`qualified_team_contribution_share`) filters both numerator and denominator by `~is_negligible`.

---

## 7. Season Aggregation Formulas

Defined in [`build_season_aggregations`](file:///c:/Users/admin/Documents/contribution/src/season_aggregation.py#L183-L367) across key `(player, season, team)` and [`phase6_season_metrics.csv`](file:///c:/Users/admin/Documents/contribution/models/contribution/phase6/phase6_season_metrics.csv) (`3,357` rows = `2,989` batting + `368` pure DNB):

| Output Field | Formula (`batting_inns > 0`) | `batting_inns == 0` (DNB) | Notes / Discrepancies |
|:---|:---|:---|:---|
| `matches_played` | Unique `match_id` count on team roster | Same | IPL uses Cricsheet `info.players`; T20I/SA20 check roster CSVs. |
| `batting_innings` | `len(inns)` in `batter_match_contributions` (`innings <= 2`) | `0` | Includes `0`-ball dismissals; excludes pure DNBs. |
| `did_not_bat_matches` | `max(0, matches_played - batting_innings)` | `matches_played` | Informational only; never enters ABC denominator. |
| **`average_contribution_score` (ABC)** | `round(mean(contribution_score), 2)` | `None` (`NULL`) | `contribution_framework.py:951` rounds to `1` decimal; `season_aggregation.py:345` rounds to `2`. |
| `total_raw_contribution` | `round(sum(raw_contribution), 4)` | `0.0` | Signed sum over scored innings. |
| `total_positive_raw_contribution` | `round(sum(max(0.0, raw_contribution)), 4)` | `0.0` | Rectified positive sum. |
| `season_team_contribution_share` | `round(tot_pos_raw / team_pos_raw * 100, 2)` (else `0.0`) | `None` (`NULL`) | Team denominator summed across `(season, team)`. |
| `contribution_per_batting_opportunity` | **`season_aggregation.py:290`:** `round(tot_pos_raw / batting_inns, 4)` | `None` (`NULL`) | **Discrepancy:** `contribution_framework.py:924` computes **net** `tot_raw / num_batted` (can be negative), whereas `season_aggregation.py` & `data_service.py:4111` divide **`tot_pos_raw`** (strictly $\ge 0$). |
| `qualified_*` (View B) | Same formulas restricted to `~is_negligible` rows | `0` / `None` / `0.0` | `qualified_team_contribution_share` uses `team_qual_pos` denominator. |
| `first_innings_contribution` | `mean(cs)` where `innings == 1` (else `None`) | `None` | Unweighted match mean over valid 1st innings. |
| `chase_contribution` | `mean(cs)` where `innings == 2` (else `None`) | `None` | Unweighted match mean over valid chases. |
| `powerplay_contribution` | `mean(cs)` where `entry_over < 6.0` | `None` | Entry-over gated only. |
| `middle_over_contribution` | `mean(cs)` where `entry_over < 16.0 and exit_over >= 6.0` | `None` | Overlap window (`6..16`). Empty `exit_over` defaults to `entry_over`. |
| `death_over_contribution` | **`season_aggregation.py:331` & `data_service.py:4147`:** `(entry_over >= 16.0) \| (exit_over >= 16.0)` | `None` | **Discrepancy:** `contribution_framework.py:944` checks ONLY `entry_over >= 16.0`, missing finishers entering at over 13–15. |
| `high_pressure_contribution` | `mean(cs)` where `score_context >= 60.0` | `None` | Threshold `c_eff >= 60.0`. |

---

## 8. DNB and Missing-Data Rules

1. **DNB Definition (`batter` never came to crease):**
   - Triggered if `(balls_faced == 0 and actual_runs == 0 and dismissal_status != 'out')`, OR explicit `dnb`/`did_not_bat`/`is_dnb == True`, OR both `balls_faced` and `actual_runs` are `NaN`.
   - **Rule:** All contribution scores (`contribution_score`, `raw_contribution`, `adjusted_p2`, `adjusted_p3`, pillars, `leverage`, `c_*`) MUST be `NULL` (`None`). Verified `293 / 293` IPL match DNB rows and `368 / 368` pure-DNB player-seasons preserve `NULL` (`VAL-5B`-style cutover gate V2).
   - **Strict Non-Dilution:** DNB matches are NEVER converted to `0.0` or `50.0` and NEVER enter `batting_innings` or the ABC denominator.
2. **Zero-Ball Dismissals (Scored, NOT DNB):** A batter out without facing a legal delivery (`balls_faced == 0`, `dismissal_status == 'out'`, e.g., diamond duck or wide stumping) is scored (`P2` sets `z_sr = z_pace = z_bnd = 0.0`, `bonus_not_out = 0.0`, `z_runs = -19.8/21.6`). Note: `is_wide` stumping vs run out in Phase 2 raw data counts `balls_faced` carefully (see §11).
3. **Super Overs (`innings >= 3`):** Excluded from contribution calculations (`NULL`); `season_aggregation.py:131` filters `df_signals["innings"] <= 2`.
4. **Missing/Invalid `expected_runs` (`validate_expected_runs_input`):** In Strategy 4 (`phase8_collapse_attribution_prototype.py:59–96`), `None`, `NaN`, `+/-inf`, or `< 0.0` returns `(False, None, reason)` rather than silently imputing `0.0` into deltas.
5. **Unobserved Contextual Splits:** If a player has 0 qualifying appearances in a split (e.g., 0 Death-over appearances), that contextual ABC column MUST remain `NULL`, never `0.0` or `50.0`.
6. **Missing Entry/Exit Telemetry Defaults Inside `contribution_framework.py`:** Defaults `team_rr_entry -> 7.5`, `required_rr_entry -> 8.5` (`P1`/`P2`/`P4`) or `0.0` (`compute_context_and_leverage`), `dot_ball_percentage -> 30.0`, `sr_performance_ratio -> 1.0`. Under Phase 2, null/unavailable chase telemetry in curtailed matches must NOT silently substitute `8.5` (must follow Stage 5A `pd.NA` guards).

---

## 9. Phase 2 Field Mapping Table

Mapping every Phase 1 input needed to reproduce ABC onto Phase 2 [`match_states_standard_t20_v1.pkl.gz`](file:///c:/Users/admin/Documents/CricImpact_Phase2/data/processed/match_states/match_states_standard_t20_v1.pkl.gz) (`190,575 x 101`, verified in [`stage5b_feature_schema_v1.json`](file:///c:/Users/admin/Documents/CricImpact_Phase2/data/validation/stage_5b/stage5b_feature_schema_v1.json)) and immutable raw CSVs under `data/raw/`.

**Classification Legend:**
- `Available directly`
- `Derivable from Stage 5B`
- `Requires additional historical aggregation`
- `Missing from Phase 2 data`
- `Requires an external source`
- `Requires an exact Phase 1 model artifact`

| Phase 1 Input / Signal | Phase 1 Meaning & Usage | Phase 2 Source / Column(s) & Exact Derivation | Classification |
|:---|:---|:---|:---|
| `match_id`, `innings`, `season` | Primary match/innings/season keys | Stage 5B: `match_id`, `innings`, `season` (plus `comp_id`, `comp_name`, `competition_category`, `match_date`) | `Available directly` |
| `team`, `opponent` | Batting & bowling team names | Stage 5B has `batting_team_id`, `bowling_team_id`; join [`teams.csv`](file:///c:/Users/admin/Documents/CricImpact_Phase2/data/raw/teams.csv) on `(comp_id, team_id) -> team_name` (or `matches.home_team`/`away_team`) | `Derivable from Stage 5B` (IDs direct; names via `teams.csv` join) |
| `player` (canonical batter ID / name) | Batter identifier | Stage 5B has integer `striker_id`, `non_striker_id`, `resolved_dismissed_player_id` (NO name strings in Stage 5B). Join [`ball_by_ball.csv`](file:///c:/Users/admin/Documents/CricImpact_Phase2/data/raw/ball_by_ball.csv) / [`competition_team_player_mapping.csv`](file:///c:/Users/admin/Documents/CricImpact_Phase2/data/raw/competition_team_player_mapping.csv) | `Derivable from Stage 5B` (integer `player_id` direct; string names from raw CSVs) |
| Playing XI / Roster (`matches_played`, DNB detection) | Match roster to detect `dnb_matches` | Raw [`playing_eleven.csv`](file:///c:/Users/admin/Documents/CricImpact_Phase2/data/raw/playing_eleven.csv) (`match_id, team_id, player_id, is_played, is_impact, is_impact_off`). *Caution: `639` UAE rows missing from `playing_eleven` & 558 `is_impact` rows!* | `Requires additional historical aggregation` (raw roster join outside Stage 5B) |
| `batting_position` | 1..11 batter entry slot | Stage 5B `batting_order` (`1..13`), or appearance order of first crease appearance (`striker_id` / `non_striker_id`) | `Derivable from Stage 5B` |
| Batter Stay Boundaries (`entry_legal_balls`, `exit_legal_balls`) | Exact legal balls bowled when batter entered & exited crease | Identify first row where `player_id in {striker_id, non_striker_id}` (`legal_balls_completed_before`) and last row where active / dismissed (`legal_balls_completed_after` or retirement/end) | `Derivable from Stage 5B` |
| `entry_over`, `exit_over` (cricket `over.ball` float) | Required by Phase 1 RF & P1 `C_wkt` / `C_chase` / Workstream B | Convert `legal_balls`: `(b // 6) + (b % 6) / 10.0` (matches `overs_completed_notation` convention) | `Derivable from Stage 5B` |
| `actual_runs` ($R$) | Batter runs scored in stay | `sum(batter_runs)` where `striker_id == player_id` (within stint) | `Derivable from Stage 5B` |
| `balls_faced` ($B$) | Legal balls (+ no-balls?) faced by batter | *Check law:* In cricket/Cricsheet `balls_faced` excludes `wides` (`~is_wide`), includes `no-balls`; Phase 1 `batter_runs` on `is_no_ball` also counts. Derive `sum(~is_wide)` for `striker_id == player_id` | `Derivable from Stage 5B` |
| `actual_sr` | Strike rate `R / B * 100` | `(actual_runs / balls_faced) * 100.0` (`0.0` if `B == 0`) | `Derivable from Stage 5B` |
| `fours`, `sixes`, `boundary_percentage` | Boundary execution quality in `P2` | Count `(batter_runs == 4)` and `(batter_runs == 6)` (prefer `batter_runs` over `is_boundary_four`/`is_six` due to Stage 4 `VAL-EXT-004` warning); `(4*fours + 6*sixes) / actual_runs * 100` | `Derivable from Stage 5B` |
| `dot_balls`, `dot_ball_percentage` | Used in Phase 1 `Model T` (`dots% < 45` / `>= 50`) | Count `(team_runs == 0)` or `(batter_runs == 0 & is_legal_delivery)` while `striker_id == player_id` | `Derivable from Stage 5B` |
| `dismissal_status`, `dismissal_kind` | `"out"` vs `"not out"`, used in P2, Model T, Preservation, DNB | Derive from `is_wicket_event & (resolved_dismissed_player_id == player_id)`, `dismissal_type_canonical`. *Edge case: Match `40709` `2.19.5` missing dismissed ID; `Retired Hurt` (`is_retired_hurt_event=True`, `is_wicket_event=False`)!* | `Derivable from Stage 5B` |
| `team_score_entry`, `team_score_exit`, `team_runs_added` | Team runs at batter entry & exit | `score_before` at entry ball, `score_after` at exit ball, `score_after - score_before` | `Derivable from Stage 5B` |
| `wickets_remaining_entry`, `wickets_remaining_exit`, `wickets_lost_during_stay` | Wicket context in `P1`, `P3`, `S_res`, `Model T` | `10 - wickets_lost_before` (entry), `wickets_remaining` (exit), `wickets_lost_after(exit) - wickets_lost_before(entry)` | `Derivable from Stage 5B` |
| `balls_remaining_entry`, `balls_remaining_exit`, `overs_spent` | Legal balls remaining (`120 - L_b`) | `legal_balls_remaining_before` (entry), `legal_balls_remaining` (exit), `(b_exit - b_entry) / 6.0` | `Derivable from Stage 5B` |
| `team_rr_entry`, `window_team_rr` | CRR at entry & scoring rate during crease stay | `score_before * 6.0 / legal_balls_completed_before` (at entry, `0.0` if `0`); `(team_score_exit - team_score_entry) / overs_spent` | `Derivable from Stage 5B` |
| `target`, `runs_required_entry/exit`, `required_rr_entry/exit`, `required_rr_change`, `rr_gap_entry/exit/change`, `target_progress_change` | All Innings 2 chase context & relief deltas (`P1`, `P3 Model E`, `P4`) | Stage 5B Innings 2 columns: `target_runs`, `runs_required_before`/`after`, `required_run_rate` (compute pre-entry `6 * runs_required_before / legal_balls_remaining_before`), `rrr_minus_crr`, `(runs_required_entry - runs_required_exit) / target_runs`.Strictly `pd.NA` in Inn 1! | `Derivable from Stage 5B` |
| `wicket_resource_change` | Wickets lost during stay (negative count in Phase 1 `evaluate_batter_performance.py`, `-wkts_lost_during_stay`) or dismissal flag | `-(wickets_lost_after(exit) - wickets_lost_before(entry))` *(Note: `P3` only tests `< 0` vs `>= 0`; wait—in Phase 1, `wicket_resource_change < 0` fires if ANY wicket fell during stay, not only if THIS batter got out!)* | `Derivable from Stage 5B` |
| `expected_final_entry`, `expected_final_exit`, `expected_final_change` | Phase 3 `ExpectedScoreRFModel` predictions at Inn 1 entry & exit | Not in Phase 2 data. Must either run Phase 1 `expected_score_rf.joblib` over Stage 5B features OR train Phase 2 walk-forward EFS model | `Requires an exact Phase 1 model artifact` *(or Phase 2 historical re-fit)* |
| `expected_runs`, `expected_sr`, `run_deviation`, `sr_deviation` | Phase 4A `ExpectedRunsRFModel` / `ExpectedSRRFModel` predictions | Not in Phase 2 data. Must run `expected_runs_model.joblib` & `expected_sr_model.joblib` OR train Phase 2 models (or Phase 1 `1.25`/`125.0` non-IPL heuristic) | `Requires an exact Phase 1 model artifact` *(or Phase 2 historical re-fit)* |
| `par_curve_20` ($\text{Par}_{20}(b), b=0\dots 120$) & `entry_score_deviation`, `exit_score_deviation`, `trajectory_deviation_change` | Empirical 120-ball historical 1st-inn par score curve (`par_curve[120] = 166.5` / `172.46`) | Must either load Phase 1 IPL curve OR compute from Phase 2 historical `STANDARD_T20` 1st-inn cumulative `score_after` by `legal_balls_completed_after` | `Requires additional historical aggregation` |
| `HISTORICAL_WICKET_LOSS_CURVE` (`w_hist(0..120)`) | Empirical average wickets lost by legal ball | Hardcoded in Phase 1 (`0..5.93`) OR re-aggregated from Phase 2 historical 1st-innings `wickets_lost_after` | `Requires additional historical aggregation` |
| Phase 1 Empirical Z-Score & Slope Constants (`-0.068`, `1.029`, `0.159`, `1.513`, `19.8`, `21.6`, `166.5`) | Standardization constants calibrated on Phase 1 IPL (2008–2026) | Not present in Phase 2; must either copy Phase 1 constants verbatim or re-calibrate on Phase 2 historical splits | `Requires an exact Phase 1 model artifact` *(or Phase 2 calibration)* |
| `won_match`, `winning_margin`, `margin_type` | Match outcome audit columns (UNUSED in Phase 7U / Strategy 4 scoring!) | Stage 5B `target_batting_team_win`, `win_team_id_raw`, raw `matches.result` (for audit/evaluation ONLY, never scoring) | `Derivable from Stage 5B` |
| `stadium_name` / Cricsheet player string keys / `RAIN_SHORTENED_MATCH_OVERS` Phase 1 match map | Phase 1 IPL venue classifier & Cricsheet IDs | Stadium name missing (`venue_id`, `venue_country` only). Phase 1 rain dict uses Cricsheet IDs (`matches.csv` uses Stage 4/5 IDs, has `first_inn_revised_overs`) | `Missing from Phase 2 data` *(stadium name & Phase 1 ID mapping)* |
| Bye vs. Leg-Bye Breakdown on `extras_2_runs` (`36` corpus rows) | Delivery extra sub-classification | Raw data combines secondary extras without bye vs leg-bye flag (`is_extras_2_subtype_unresolved=True`). *Zero effect on batter runs or team total `team_runs`!* | `Missing from Phase 2 data` *(non-blocking for batter ABC)* |
| Dismissed Player ID on Match `40709` `2.19.5` (`Retire Out`) | Single unresolved wicket attribution | Raw `dismissed_player_id` is `pd.NA` (`is_dismissed_player_unresolved=True`); unresolvable without external scorecard | `Requires an external source` *(or Stage 5A non-attribution rule)* |

---

## 10. Missing / Unavailable Inputs

The following Phase 1 components or raw granularities are **absent** from Phase 2 [`data/raw/`](file:///c:/Users/admin/Documents/CricImpact_Phase2/data/raw/) and Stage 5B [`match_states_standard_t20_v1.pkl.gz`](file:///c:/Users/admin/Documents/CricImpact_Phase2/data/processed/match_states/match_states_standard_t20_v1.pkl.gz):

1. **Missing Pre-Trained Artifacts & Lookup Curves Inside Phase 2:** `models/` in Phase 2 currently contains `0` files. Phase 1's `expected_score_rf.joblib`, `expected_runs_model.joblib`, `expected_sr_model.joblib`, `par_curve_20` JSON/CSV (derived inside `batter_trajectory.py` from `match_state.csv`), and Phase 1's empirical standardization constants (`-0.068, 1.029, 0.159, 1.513, 166.5`) do not exist in Phase 2.
2. **No Batter-Innings Grain Table in Phase 2:** Stage 5B is strictly **delivery-transition grain** (`190,575` rows). Entry/exit state reconstruction, batter run/ball accumulation, partnership runs, and DNB detection must be built in Stage 5C.
3. **No Cricsheet String Match/Player Keys or Venue Stadium Strings:** Phase 2 uses provider integer IDs (`match_id`, `player_id`, `team_id`, `venue_id`) and omits stadium names (`venue_country` only). Phase 1's `PLAYER_NAME_ALIASES`, `src/venue_classifier.py`, and hardcoded `RAIN_SHORTENED_MATCH_OVERS` cannot join cleanly by name/ID without reconciliation.
4. **`playing_eleven.csv` Completeness Gaps:**
   - **UAE Split Player IDs (`639` deliveries):** `ball_by_ball.csv` references `player_id` values missing from `playing_eleven.csv` (`has_uae_split_player_id = True`).
   - **Impact Substitutes (`558` rows in `playing_eleven.csv`):** `is_impact` and `is_impact_off` mark 12th-player tactical subs (2023–2026 IPL), an entity that Phase 1's static Cricsheet `info.players` `11`-player roster did not distinguish cleanly (can inflate `matches_played` / `did_not_bat_matches` if an unused or bowling-only Impact Sub is counted identically to an XI starter).
5. **Unresolved Source Anomalies Excluded or Flagged in Stage 5B:**
   - **`match_id = 40709` `2.19.5` `Retire Out`:** Missing `dismissed_player_id` (`pd.NA`, never fabricated per Stage 5A). Affects attribution of `1` official dismissal between the two crease batters unless externally verified or kept unattributed.
   - **Excluded Regimes (`85` matches / `10,424` deliveries):** `match_states_standard_t20_v1.pkl.gz` excludes `31` `REVISED_OVERS_DLS`, `21` `NO_RESULT`, `19` `ABANDONED`, `9` `SUPER_OVER`, `4` `INCOMPLETE_OR_UNRESOLVED` (`14130`, `14164`, `41509`, `50407`), and `1` `TIED`. Workstream B (rain-shortened scoring) cannot run on `match_states_standard_t20_v1.pkl.gz` unless `REVISED_OVERS_DLS` matches are loaded separately from full-corpus reconstruction.
6. **`extras_2_runs` Subtype Breakdown (`36` rows):** Bye vs. leg-bye split on no-balls is unavailable, though `batter_runs` and `team_runs = runs + extras1_runs + extras_2_runs` are **100% exact**, so batter ABC is unaffected.

---

## 11. Compatibility Issues

| Category | Phase 1 Behavior | Phase 2 Reality & Failure Mode if Ported Naively |
|:---|:---|:---|
| **1. Data Grain Mismatch** | Contribution operates on **`(match_id, innings, player, stint)`** batter-innings grain (`19,111` IPL rows). | Stage 5B is **`(match_id, innings, innings_ball_num)`** delivery grain (`190,575` rows). Must aggregate delivery stints cleanly—**including two stints for a batter who leaves `Retired Hurt` and later returns to bat** (`12` `Retired Hurt` events exist in Phase 2). |
| **2. Population & Competition Shift** | **ML models & empirical constants (`166.5` par, `8.325` RPO, `19.8` avg runs, `125` SR, `-0.068/1.029`, `0.159/1.513`)** were calibrated exclusively on **IPL 2008–2026** (predominantly lower-scoring pre-Impact-Sub years). Meanwhile Phase 1 T20I/SA20 pipelines bypassed Strategy 4 & ML models! | Phase 2 contains **`798` `STANDARD_T20` matches across `2022-01-22` to `2026-11-01`**: **`419` `T20I` (`52.5%`)**, **`351` `IPL` (`44.0%`)**, **`28` `OTHER_T20` (`3.5%`)**. T20I scoring distributions (Associate + Full Member bilateral & WC) differ sharply from IPL 2022–2026 (post-Impact Sub `200+` totals). Applying IPL 2008–2026 fixed `166.5` par / RF models directly to modern IPL vs T20I induces severe **competition & era bias** (`P2`/`P3` inflation in IPL 2024–2026 vs deflation in low-scoring T20Is). |
| **3. Over Notation Bug Risk** | Phase 1 `ExpectedScoreRFModel` and `ExpectedRunsRFModel` ingest **`overs_completed` and `entry_over` in cricket `over.ball` float notation** (`11.3` = `11*6 + 3` balls) AND `compute_calibrated_rain_shortened_raw_p3` parses decimal-looking `17.5` as `17 overs, 5 balls` (`Phase 1` mixed `10`-base parsing). | Phase 2 Stage 5B explicitly separates `overs_completed_decimal` (`11.5`, for math/models) from `overs_completed_notation` (`11.3`, **forbidden in math** per `VAL-5B`). Passing `overs_completed_decimal` into a Phase 1 `.joblib` model silently corrupts `entry_over` / `overs_completed` tree splits (`x.5` means 5 balls in cricket notation vs 3 balls in decimal!). |
| **4. `Retired Hurt` & `Retire Out` Handling** | Standard Cricsheet parser treats wickets via `wicket` objects; returning `Retired Hurt` batters may create duplicate `(match_id, innings, player)` rows or get merged across hiatus overs (`exit_score - entry_score` would wrongly credit/blame the batter for runs & wickets during their absence!). | Phase 2 distinguishes `is_retired_hurt_event` (`+0` team wickets, `12` corpus events) vs `is_retire_out_event` (`+1` team wicket, `6` events). Naive `min(entry)..max(exit)` aggregation across a `Retired Hurt` gap breaks continuity and partner-wicket attribution! |
| **5. Player & Team ID Discontinuity** | Phase 1 keys on string `player` names (`"V Kohli"`, `"AJ Finch"`), resolving splits with hardcoded `PLAYER_NAME_ALIASES`. | Phase 2 keys on integer `player_id` & `team_id`, plus `639` delivery rows with UAE split player IDs (`has_uae_split_player_id=True`) where `playing_eleven` & `ball_by_ball` disagree on player IDs. |
| **6. `is_four` / `is_six` Raw Flag Quirk** | Phase 1 counts boundaries directly from `batter_runs == 4` / `6`. | Phase 2 Stage 4 `VAL-EXT-004` flagged discrepancies on raw `is_four`/`is_six` (e.g., overthrows or boundary flags). Must derive `fours`/`sixes` cleanly from `batter_runs` / verified boundary rule consistent with Phase 1. |
| **7. `balls_faced` & `is_no_ball` / `is_wide` Law** | Cricsheet batter `balls_faced` excludes `wides` and includes `no-balls` (wait: Phase 1 `actual_sr` uses `batter_balls` excluding wides). | In Phase 2 Stage 5B, `is_legal_delivery == False` excludes BOTH `is_wide` AND `is_no_ball` (`Overstep`, `other`). Official cricket batter `balls_faced` counts **`~is_wide`** (includes no-balls!), NOT `is_legal_delivery` (`~is_wide & ~is_no_ball`). Using `is_legal_delivery` instead of `~is_wide` inflates strike rate on no-balls (`batter_runs` scored on no-ball with 0 balls!). |
| **8. `wicket_resource_change` Definition Subtlety** | `compute_dampened_p3_raw` checks `wkt_res_chg < 0` to apply `S_res` wicket penalty! In Phase 1, `wicket_resource_change` = `-(wickets_lost_during_stay)`. | If a batter finishes **not out** (`dismissal_status == 'not out'`) at `120` balls but a *partner* got out during their stay (`wickets_lost_during_stay >= 1`), `wicket_resource_change < 0` in Phase 1 actually **penalizes the not-out batter with `S_res` wicket loss cost**! Verified directly in [`batter_match_contributions.csv`](file:///c:/Users/admin/Documents/contribution/data/processed/batter_match_contributions.csv) line 6 (`DJ Hooda`, `not out`, `wickets_lost_during_stay=1`, `wicket_resource_change=-1`). Preserving this quirk vs fixing to personal dismissal (`is_dismissed`) must be explicitly decided. |
| **9. `scikit-learn` & Runtime Environment** | Phase 1 `.joblib` RFs are `scikit-learn` `RandomForestRegressor` pickles (`expected_score_rf.joblib`, `expected_runs_model.joblib`, `expected_sr_model.joblib`). | Verified in Phase 2 `.venv` (`Python 3.13.14`, `sklearn 1.9.1`, `pandas 2.3.3`, `numpy 2.5.4`, `joblib 1.6.0`): all 3 artifacts deserialize cleanly with `0` warnings. However, `ExpectedScoreRFModel.load()` and `ExpectedBatterModel` wrappers exist only in Phase 1 `src/`, not Phase 2. |

---

## 12. Historical & Causal Leakage Risks and Mandatory Safeguards

> [!WARNING]
> **Critical Distinction for Phase 2 Win Probability Engine:**
> Phase 1 ABC (`contribution_score`) is a **post-match retrospective evaluation metric**, NOT an in-play or pre-match feature! Injecting same-match ABC or post-match Phase 1 models into Phase 2 WP models would cause catastrophic target & future leakage.

### 12.1 Five High-Severity Leakage Vectors

1. **Match-Internal Future Leakage (Same-Match ABC):**
   - Computing a batter's `contribution_score` uses their **exit state** (`exit_score`, `exit_wickets`, `expected_final_exit`, `actual_runs`, `balls_faced`, `dismissal_status`) and **partner wickets during stay**.
   - **Rule:** Same-match `contribution_score` can **NEVER** be used as a feature for delivery $b$ of that same match inside the Phase 2 Win Probability model.
2. **Temporal Target & Outcome Leakage Across Matches (`match_date`):**
   - Aggregating season or career ABC over the entire corpus (or future matches in the same season/series) leaks future form, tournament progression, and team strength into earlier matches.
   - **Rule:** When constructing pre-match batter strength / ABC features for match $m$ on date $d_m$, **only matches with strictly earlier dates ($d_{m'} < d_m$)** may enter rolling/expanding ABC (`shift(1)` after deterministic sort by `(match_date, match_id)`). For two matches on the exact same `match_date` (e.g., IPL double-headers or simultaneous T20Is), exclude same-day matches (`d_{m'} < d_m`) unless intra-day start times are verified.
3. **Upstream ML Model Train/Test Contamination (`ExpectedScore` / `ExpectedBatter`):**
   - Phase 1's frozen `.joblib` models (`expected_score_rf.joblib`, `expected_runs_model.joblib`, `expected_sr_model.joblib`) were trained on IPL `2008–2026` (overlapping `2022–2026` IPL matches in Phase 2!). Calling those frozen Phase 1 `.joblib` models on Phase 2 `2022–2026` IPL matches means the RF models saw those exact match outcomes (`final_team_score`, batter `runs`) in training!
   - Even if Phase 2 re-fits EFS/ExpectedBatter models on Phase 2 data, fitting on full corpus leaks future scoring regimes (`par_curve_20`, `HISTORICAL_WICKET_LOSS_CURVE`, `z2/z3` mean/std) into early validation folds.
   - **Rule:** If EFS / ExpectedBatter RFs or Par Curves are used to produce causal pre-match ABC features for WP training/validation, they **MUST be fit strictly inside expanding chronological windows / outer train folds** (never using `val`/`test` matches to fit RF trees, `par_curve_20`, or z-score standardization constants).
4. **End-of-Over / Exit-State Boundary Leakage in RF Training:**
   - Phase 1 `ExpectedScoreRFModel` excluded terminal states (`balls_remaining == 0`, `wickets_remaining == 0`) during fit and applied `is_terminal -> exit_score` at inference. Re-training on terminal states or unverified curtailed innings (`50` unverified innings in Stage 5B full corpus) corrupts projected par totals.
5. **Cross-Competition Metadata Contamination:**
   - Mixing IPL, T20I, and `OTHER_T20` into an unstratified Par Curve or single `competition_category`-blind ABC distorts baseline expectations (violating Stage 5A's strict competition-separation mandate).

---

## 13. Revised Phase 2 Implementation Architecture (Universal Strategy 4 Evaluation)

> [!NOTE]
> **Revision `v2.0` Update:** Following review of Sections `1–12`, the Stage 5C mandate was updated from *IPL-first Phase 1 reproduction* to evaluating **Strategy 4 as a competition-aware methodology across `IPL` (`351`), `T20I` (`419`), and `OTHER_T20` (`28`)** against the preserved **Phase 7U Comparison Baseline**, plus strictly causal Track B pre-match ABC generation. Full normative details live in [`stage_5c_universal_strategy4_specification.md`](file:///c:/Users/admin/Documents/CricImpact_Phase2/docs/stage_5c_universal_strategy4_specification.md) and [`stage_5c_implementation_plan.md`](file:///c:/Users/admin/Documents/CricImpact_Phase2/docs/stage_5c_implementation_plan.md).

To guarantee **zero modification** to Stage 4 (`ml/ingestion/`, `ml/validation/`), Stage 5A (`docs/match_*`, `docs/win_*`, `docs/stage_5a*`), Stage 5B (`ml/match_state/`, `data/processed/match_states/`, `data/validation/stage_5b/`), `data/raw/`, and frozen Phase 1 (`C:\Users\admin\Documents\contribution`), Stage 5C will reside under `ml/contribution/` in `C:\Users\admin\Documents\CricImpact_Phase2`:

### 13.1 Strict Track & Engine Isolation
1. **Track A — Evaluation & Comparative Benchmarking (`RETROSPECTIVE_EVALUATION_ONLY`, never fed directly as current-match WP features):**
   - **`Phase 7U Comparison Baseline`:** Preserves `expected_runs = round(1.25 * balls_faced, 1)`, `expected_sr = 125.0`, `trajectory_deviation_change = NaN` across all `798` `STANDARD_T20` matches (`IPL`, `T20I`, `OTHER_T20`) for controlled 10-criterion benchmarking.
   - **`Universal Competition-Aware Strategy 4`:** Strictly isolated by `competition_category`, using chronological walk-forward estimation (`source.match_date < target.match_date`) with deterministic cold-start gates (`N_min = 30`) and explicit non-ML small-sample safeguards for `OTHER_T20` (`n = 28`: `15` in `comp_id=2670`, `13` in `comp_id=3289`).
   - **`Phase 1 IPL Reference Audit` (`IPL` only):** Optional retrospective parity verification against frozen Phase 1 `v8.5.1-strategy4-hybrid` constants (`166.5` par) — never mixed into causal Track B features due to 2022–2026 overlap.
2. **Track B — Causal Walk-Forward Pre-Match ABC Engine (Future Stage 6 WP Features):**
   - Computes per-player and lineup pre-match ABC (`abc_prior_all_mean`, `abc_prior_cat_mean`, `abc_prior_last10_mean`, Bayesian-shrunk `abc_prior_shrunk`, `pos_contrib_rate_prior`, `batted_inns_prior_all`, `is_abc_cold_start`) strictly from earlier calendar dates (`source.match_date < target.match_date`).
   - Canonical WP engine assignment (Strategy 4 vs Phase 7U per category) awaits Track A's 10-criterion validation verdict.

### 13.2 Proposed Phase 2 Module Layout (`ml/contribution/`)
- [`ml/contribution/schema.py`](file:///c:/Users/admin/Documents/CricImpact_Phase2/ml/contribution/schema.py): Versioned schemas for stints, match scorecards, season/competition aggregations, and causal Track B features.
- [`ml/contribution/stint_builder.py`](file:///c:/Users/admin/Documents/CricImpact_Phase2/ml/contribution/stint_builder.py): Builds `(match_id, innings, stint_id, player_id)` stays from Stage 5B + `playing_eleven.csv` (`18,100` `is_played==1` [`5,073` DNB incl. `219` `is_impact==1` DNB] + `6` UAE split crease batters = `18,106` player-match records; `13,033` batted; `11` `Retired Hurt` events [`0` resumed in `v1`]; `40709` `2.19.5` unattributed; `~is_wide` `balls_faced`; `batter_runs in {4, 6}`).
- [`ml/contribution/expectations.py`](file:///c:/Users/admin/Documents/CricImpact_Phase2/ml/contribution/expectations.py): Causal category-stratified walk-forward `Par_20`, `w_hist`, `ExpectedScoreRF`, `ExpectedRunsRF`, `ExpectedSRRF`, cold-start gate (`N_min`), `OTHER_T20` non-ML guard, and Phase 7U baseline baselines.
- [`ml/contribution/phase7u_scorer.py`](file:///c:/Users/admin/Documents/CricImpact_Phase2/ml/contribution/phase7u_scorer.py) & [`ml/contribution/strategy4_scorer.py`](file:///c:/Users/admin/Documents/CricImpact_Phase2/ml/contribution/strategy4_scorer.py): Modular scorers with sensitivity flags (`rr_gap_entry`, `S_res` personal vs partner wicket).
- [`ml/contribution/aggregation.py`](file:///c:/Users/admin/Documents/CricImpact_Phase2/ml/contribution/aggregation.py): Season/competition View A & View B metrics (`tot_pos_raw / n`, `(entry >= 16) | (exit >= 16)` death gate) + Track B causal pre-match ABC builder.
- [`ml/contribution/evaluation.py`](file:///c:/Users/admin/Documents/CricImpact_Phase2/ml/contribution/evaluation.py), [`ml/contribution/validator.py`](file:///c:/Users/admin/Documents/CricImpact_Phase2/ml/contribution/validator.py), [`ml/contribution/pipeline.py`](file:///c:/Users/admin/Documents/CricImpact_Phase2/ml/contribution/pipeline.py): 10-criterion generalisation comparison, sensitivity audits, leakage/permutation gates, and SHA-256 manifest emission.

---

## 14. Resolved Methodology Decisions & Remaining Open Technical Decisions

### 14.1 Resolved Methodology Decisions (Locked in Spec `v2.0`)
1. **`contribution_per_batting_opportunity`:** Approved `tot_pos_raw / batting_inns` (`season_aggregation.py:290`).
2. **Death Over Split Gate:** Approved `(entry_over >= 16.0) | (exit_over >= 16.0)` (`season_aggregation.py:331`).
3. **`rr_gap_entry` in $C_{\text{chase}}$:** Retain `0.0` in baseline `compute_context_and_leverage()` + report mandatory causal `rr_gap_entry` sensitivity audit.
4. **`S_res` Partner-Wicket Quirk:** Preserve `wicket_resource_change < 0` (`wickets_lost_during_stay > 0`) for compatibility parity + report mandatory sensitivity audit vs personal-dismissal attribution across `IPL`, `T20I`, and `OTHER_T20`.
5. **`is_impact` Impact Substitutes:** Unused or bowling-only Impact Subs (`219` of `535` `is_impact==1` in `798` matches) remain strict `DNB` (`NULL`), excluded from ABC denominators.
6. **`Retired Hurt` Multi-Stint & Single-Stint Handling:** Reconstruct per continuous stint (`hiatus` excluded) and aggregate returning batters into one match contribution (`11/11` events in `STANDARD_T20` are non-resuming and score on actual stint telemetry).
7. **`match_id = 40709` `2.19.5` `Retire Out`:** Keep `resolved_dismissed_player_id = pd.NA`, zero fabrication, zero personal dismissal assignment on either crease batter, while preserving exact `+1` team wicket state.
8. **`37087 / 37092 / 37095` UAE Split IDs:** Score all `6` Stage 5B batting appearances absent from `playing_eleven.csv` (`union` roster) with audit flag `is_roster_missing_uae_split = True`.

### 14.2 Remaining Open Technical Decisions Requiring User Approval Before Coding
Before writing any Python modules under `ml/contribution/`, please sign off on the **5 remaining open decisions** detailed in [`stage_5c_implementation_plan.md`](file:///c:/Users/admin/Documents/CricImpact_Phase2/docs/stage_5c_implementation_plan.md) §4:
1. **Exact Strategy 4 Second-Innings (Chase) Adaptation Formulation** (`1A` Model E + $f_{\text{res}}$ + comp norms vs `1B` Model E + comp norms without $f_{\text{res}}$ vs `1C` both side-by-side).
2. **Walk-Forward Training Window & Cold-Start Threshold** (`2A` `N_min = 30` with deterministic prior fallback & periodic `d' < d` refits vs `2B` `2022` burn-in holdout vs `2C` plus Track A Leave-One-Season-Out OOF check).
3. **`OTHER_T20` Explicit Fallback Baseline (`n = 28`: `15` + `13`)** (`3A` Phase 7U baseline + exploratory non-ML empirical shrinkage diagnostic for `3289` flagged `LOW_SAMPLE_EXPLORATORY` vs `3B` formal Strategy 4 abstention on `OTHER_T20`).
4. **`raw_contribution` Column Consistency** (`4A` harmonized `0.5*(z2*L + z3*L)` everywhere vs `4B` preserving Phase 1 Inn-1 staging split).
5. **Pre-Registered Category Promotion Criteria (`Strategy 4` vs `Phase 7U`)** and **`v1` Regime Scope (`798` `STANDARD_T20` matches only; `31` `REVISED_OVERS_DLS` excluded)**.

---

## Audit Completion & Evidence Classification

**Audit Status:** **`RECOVERY COMPLETE — v2.0 SPEC & IMPLEMENTATION PLAN READY FOR APPROVAL`**

- **Verified Directly from Source Code & Active Phase 1 / Phase 2 Files:**
  - All Phase 1 formulas, constants, clipping bounds, Model T/B/E gates, Strategy 4 Workstream A & B logic, RF feature schemas (`7` & `11` features), `0`-warning `.joblib` deserialization in Phase 2 `.venv` (`sklearn 1.9.1`), active CSV row counts, plus Phase 2 `798`-match distribution breakdowns (`IPL` `351` / `T20I` `419` / `OTHER_T20` `28`), `playing_eleven` DNB/Impact-Sub counts (`18,100` `is_played==1` = `13,027` batted + `5,073` DNB; `535` `is_impact==1` = `316` batted + `219` DNB [`201` bowled-only + `18` neither]), `6` UAE split crease appearances in `comp_id=2670`, `11` non-resuming `Retired Hurt` events, and `40709` `2.19.5` unattributed `Retire Out`.
- **Next Action:** **STOP** here and await user review and approval of [`stage_5c_universal_strategy4_specification.md`](file:///c:/Users/admin/Documents/CricImpact_Phase2/docs/stage_5c_universal_strategy4_specification.md) and [`stage_5c_implementation_plan.md`](file:///c:/Users/admin/Documents/CricImpact_Phase2/docs/stage_5c_implementation_plan.md) before writing or running any Stage 5C scoring code.

