# CricImpact Phase 2 — Stage 6A Revision 1: Feature Dictionary & Lifecycle Availability Matrix

**Document:** Stage 6A Feature Dictionary (Revision 1.0)  
**Status:** Approved Feature Dictionary (Planning & Design Only — Stage 6A)  
**Author:** AI Architecture & Data Science Agent  
**Date:** November 2026  
**Project Root:** [`C:\Users\admin\Documents\CricImpact_Phase2`](file:///c:/Users/admin/Documents/CricImpact_Phase2)  
**Companion Documents:**
- [`stage_6a_win_probability_specification.md`](file:///c:/Users/admin/Documents/CricImpact_Phase2/docs/stage_6a_win_probability_specification.md)
- [`stage_6a_target_and_state_construction.md`](file:///c:/Users/admin/Documents/CricImpact_Phase2/docs/stage_6a_target_and_state_construction.md)
- [`stage_6a_training_and_evaluation_plan.md`](file:///c:/Users/admin/Documents/CricImpact_Phase2/docs/stage_6a_training_and_evaluation_plan.md)
- [`stage_6a_data_readiness_report.md`](file:///c:/Users/admin/Documents/CricImpact_Phase2/docs/stage_6a_data_readiness_report.md)
- [`stage_6a_risk_and_leakage_register.md`](file:///c:/Users/admin/Documents/CricImpact_Phase2/docs/stage_6a_risk_and_leakage_register.md)
- [`stage_6a_implementation_plan.md`](file:///c:/Users/admin/Documents/CricImpact_Phase2/docs/stage_6a_implementation_plan.md)
- [`stage_6a_revision_1_report.md`](file:///c:/Users/admin/Documents/CricImpact_Phase2/docs/stage_6a_revision_1_report.md)

---

## 1. Feature Count Reconciliation & Inventory Summary

In the initial draft of the Stage 6A feature specification, an administrative discrepancy occurred where the summary prose cited 36 candidate features while the detailed table rows totaled 42 features. 

This Revision 1 document formally reconciles the catalog into an **authoritative inventory of exactly 42 candidate features** across five functional groups:

```
Authoritative Feature Catalog: Exactly 42 Candidate Features
├── Group 1: Core Delivery & Match-State Features (14 features)
├── Group 2: Team Strength & Lineup Aggregations (11 features)
├── Group 3: Venue, Competition & Historical Priors (5 features)
├── Group 4: Pre-Match Anchor & Toss Features (5 features)
└── Group 5: Trajectory & Momentum Dynamics (7 features)
```

### Feature Counts by Modeling Lifecycle
Information is not uniformly available across all match stages. The 42 features are partitioned into four operational lifecycle stages:
- **Stage A Pre-Match Model:** **7 features** (Franchise/team historical win rates, venue priors, competition category, unweighted squad ABC).
- **Stage B Pre-Match Model:** **20 features** (Stage A features + confirmed 11-player lineup ABC metrics + toss winner/decision).
- **First-Innings Defense Live Model:** **35 features** (20 pre-match/team/venue features + 9 general match state features + 5 general trajectory features + 1 Innings 1 specific feature `expected_final_score_gap`). (5 Innings 2 chase features excluded).
- **Second-Innings Chase Live Model:** **39 features** (20 pre-match/team/venue features + 9 general match state features + 5 chase-specific match state features + 5 general trajectory features + 1 chase pressure feature `target_pressure_index`). (`expected_final_score_gap` excluded).

---

## 2. Authoritative Feature Inventory (All 42 Features)

### Group 1: Core Delivery & Match-State Features (14 Features)

| # | Feature Name | Data Type | Source Dataset | Definition & Calculation Method | Missing / Imputation Policy | Temporal & Lifecycle Scope | Leakage Risk & Safeguard | Model Usage |
| :-: | :--- | :---: | :--- | :--- | :--- | :--- | :--- | :--- |
| 1 | `innings` | `Int64` | Stage 5B `match_states` | Innings sequence (`1` or `2`). | Non-nullable. | All in-play deliveries. | Zero leakage; known at delivery. | Branching flag for 2-head engine. |
| 2 | `score_before` | `Int64` | Stage 5B `match_states` | Cumulative batting team score prior to ball $b$. | Non-nullable; starts at `0`. | All in-play deliveries. | Pre-delivery state avoids in-ball runs. | Both Live Heads. |
| 3 | `wickets_lost_before` | `Int64` | Stage 5B `match_states` | Cumulative batting team dismissals prior to ball $b$. | Non-nullable; starts at `0`. | All in-play deliveries. | Pre-delivery state avoids in-ball wicket. | Both Live Heads. |
| 4 | `wickets_remaining_before` | `Int64` | Stage 5B `match_states` | Batting resources remaining: $10 - \text{wickets\_lost\_before}$. | Non-nullable; starts at `10`. | All in-play deliveries. | Evaluated before delivery. | Both Live Heads. |
| 5 | `legal_balls_completed_before` | `Int64` | Stage 5B `match_states` | Count of legal deliveries bowled prior to ball $b$. | Non-nullable; starts at `0`. | All in-play deliveries. | Evaluated before delivery. | Both Live Heads. |
| 6 | `legal_balls_remaining_before` | `Int64` | Stage 5B `match_states` | Regulation balls remaining: $120 - \text{legal\_balls\_completed\_before}$. | Non-nullable; starts at `120`. | All in-play deliveries. | Clamped in $[0, 120]$ via Stage 5B. | Both Live Heads. |
| 7 | `current_run_rate_before` | `Float64` | Stage 5B `match_states` | $\frac{\text{score\_before}}{\text{legal\_balls\_completed\_before} / 6.0}$. | At ball 0.1, impute with `venue_avg_first_inn_score / 20.0`. | All in-play deliveries. | Evaluated before delivery. | Both Live Heads. |
| 8 | `innings_phase` | `string` | Stage 5B `match_states` | Categorical: `POWERPLAY` ($\le 36$), `MIDDLE` ($37–90$), `DEATH` ($\ge 91$). | Non-nullable. | All in-play deliveries. | Deterministic function of balls completed. | Both Live Heads. |
| 9 | `innings_progress_pct` | `Float64` | Stage 5B `match_states` | $\frac{\text{legal\_balls\_completed\_before}}{120.0}$. Range $[0.0, 1.0]$. | Non-nullable. | All in-play deliveries. | Deterministic temporal index. | Both Live Heads. |
| 10 | `resource_percentage_remaining` | `Float64` | Engineered from Stage 5B | Empirical T20 resource lookup as $f(W_{\text{rem}}, B_{\text{rem}})$. | Non-nullable; range $[0.0, 100.0]$. | All in-play deliveries. | Lookup based strictly on prior state. | Both Live Heads. |
| 11 | `target_runs` | `Int64` | Stage 5B `match_states` | Innings 1 total score $+ 1$. | Innings 1: `pd.NA`. Innings 2: non-nullable. | Innings 2 Live only. | Target is known at innings break. | Chase Head only. |
| 12 | `runs_required_before` | `Int64` | Stage 5B `match_states` | $\text{target\_runs} - \text{score\_before}$. | Innings 1: `pd.NA`. Innings 2: non-nullable. | Innings 2 Live only. | Pre-delivery state avoids in-ball score. | Chase Head only. |
| 13 | `required_run_rate_before` | `Float64` | Stage 5B `match_states` | $\frac{\text{runs\_required\_before}}{\text{legal\_balls\_remaining\_before} / 6.0}$. | Innings 1: `pd.NA`. If $B_{\text{rem}} == 0$: $99.0$. | Innings 2 Live only. | Clamped in $[0.0, 99.0]$. | Chase Head only. |
| 14 | `rrr_minus_crr_before` | `Float64` | Stage 5B `match_states` | $\text{required\_run\_rate\_before} - \text{current\_run\_rate\_before}$. | Innings 1: `pd.NA`. Impute $0.0$ at ball 0.1. | Innings 2 Live only. | Captures run-rate pressure deficit. | Chase Head only. |

---

### Group 2: Team Strength & Lineup Aggregations (11 Features)

| # | Feature Name | Data Type | Source Dataset | Definition & Calculation Method | Missing / Imputation Policy | Temporal & Lifecycle Scope | Leakage Risk & Safeguard | Model Usage |
| :-: | :--- | :---: | :--- | :--- | :--- | :--- | :--- | :--- |
| 15 | `batting_lineup_top3_abc` | `Float64` | Stage 5C Track B + `playing_eleven` | Mean prior ABC of Batters 1–3 in confirmed XI. | If cold start, shrink to $\mu_{\text{comp}}$. | Stage B & Live Play. | Causal prior: $\text{source.date} < \text{target.date}$. | Stage B & Live Heads. |
| 16 | `batting_lineup_mid4_abc` | `Float64` | Stage 5C Track B + `playing_eleven` | Mean prior ABC of Batters 4–7 in confirmed XI. | If cold start, shrink to $\mu_{\text{comp}}$. | Stage B & Live Play. | Causal prior: $\text{source.date} < \text{target.date}$. | Stage B & Live Heads. |
| 17 | `batting_lineup_tail_abc` | `Float64` | Stage 5C Track B + `playing_eleven` | Mean prior ABC of Batters 8–11 in confirmed XI. | Impute category tail prior ($35.0$). | Stage B & Live Play. | Causal prior: $\text{source.date} < \text{target.date}$. | Stage B & Live Heads. |
| 18 | `batting_lineup_mean_abc` | `Float64` | Stage 5C Track B + `playing_eleven` | Mean prior ABC across all 11 players in XI. | Shrink cold starts to $\mu_{\text{comp}}$. | Stage B & Live Play. | Causal prior: $\text{source.date} < \text{target.date}$. | Stage B & Live Heads. |
| 19 | `batting_lineup_std_abc` | `Float64` | Stage 5C Track B + `playing_eleven` | Standard deviation of prior ABC across XI. | Impute category median variance. | Stage B & Live Play. | Causal prior: $\text{source.date} < \text{target.date}$. | Stage B & Live Heads. |
| 20 | `batting_cold_start_count` | `Int64` | Stage 5C Track B + `playing_eleven` | Count of players in XI with `is_abc_cold_start == True`. | Non-nullable; range $[0, 11]$. | Stage B & Live Play. | Derived strictly from prior data. | Stage B & Live Heads. |
| 21 | `bowling_unit_powerplay_econ` | `Float64` | Historical Match States + XI | Causal economy rate conceded in overs 1–6 by attack. | Impute competition Powerplay avg. | Stage B & Live Play. | Historical matches only; prior dates. | Stage B & Live Heads. |
| 22 | `bowling_unit_middle_econ` | `Float64` | Historical Match States + XI | Causal economy rate conceded in overs 7–15 by attack. | Impute competition Middle avg. | Stage B & Live Play. | Historical matches only; prior dates. | Stage B & Live Heads. |
| 23 | `bowling_unit_death_econ` | `Float64` | Historical Match States + XI | Causal economy rate conceded in overs 16–20 by attack. | Impute competition Death avg. | Stage B & Live Play. | Historical matches only; prior dates. | Stage B & Live Heads. |
| 24 | `bowling_unit_strike_rate` | `Float64` | Historical Match States + XI | Historical legal balls per wicket taken by attack. | Impute competition bowling SR avg. | Stage B & Live Play. | Historical matches only; prior dates. | Stage B & Live Heads. |
| 25 | `relative_batting_edge` | `Float64` | Engineered from Lineup ABC | `batting_lineup_mean_abc - opponent_lineup_mean_abc`. | Non-nullable. | Stage B & Live Play. | Evaluated before match start. | Stage B & Live Heads. |

---

### Group 3: Venue, Competition & Historical Priors (5 Features)

| # | Feature Name | Data Type | Source Dataset | Definition & Calculation Method | Missing / Imputation Policy | Temporal & Lifecycle Scope | Leakage Risk & Safeguard | Model Usage |
| :-: | :--- | :---: | :--- | :--- | :--- | :--- | :--- | :--- |
| 26 | `competition_category` | `string` | Stage 5B `match_states` | Tournament category: `IPL`, `T20I`, `OTHER_T20`. | Non-nullable. | All Stages. | Known prior to tournament. | All Model Heads. |
| 27 | `venue_avg_first_inn_score` | `Float64` | Historical Match States | Causal historical average 1st-innings total at ground. | If $< 5$ matches, shrink to category par. | All Stages. | Computed strictly on prior dates. | All Model Heads. |
| 28 | `venue_chase_win_pct` | `Float64` | Historical Match States | Historical win rate for teams batting second at ground. | If $< 5$ matches, shrink to $0.50$. | All Stages. | Computed strictly on prior dates. | All Model Heads. |
| 29 | `venue_avg_death_rr` | `Float64` | Historical Match States | Historical causal scoring rate in overs 16–20 at ground. | Impute category death average ($9.5$). | All Stages. | Computed strictly on prior dates. | Both Live Heads. |
| 30 | `venue_pace_spin_wicket_ratio`| `Float64` | Historical Match States | Historical ratio of pace wickets to spin wickets at ground. | Impute category median ($1.50$). | All Stages. | Computed strictly on prior dates. | All Model Heads. |

---

### Group 4: Pre-Match Anchor & Toss Features (5 Features)

| # | Feature Name | Data Type | Source Dataset | Definition & Calculation Method | Missing / Imputation Policy | Temporal & Lifecycle Scope | Leakage Risk & Safeguard | Model Usage |
| :-: | :--- | :---: | :--- | :--- | :--- | :--- | :--- | :--- |
| 31 | `pre_match_prob_stage_a` | `Float64` | Stage A Model Output | Preliminary win probability before XI and toss. | Non-nullable; default $0.50$. | Stage A & Stage B. | Uses only pre-match historical priors. | Pre-Match & UI. |
| 32 | `pre_match_prob_stage_b` | `Float64` | Stage B Model Output | Updated win probability after BOTH XI and toss. | If Stage B pending, equals Stage A. | Stage B & Live Play. | In training, fit via out-of-fold splits. | Anchor for Live Heads. |
| 33 | `stage_b_prob_delta` | `Float64` | Stage B Model Output | Probability movement: $P_{\text{Stage B}} - P_{\text{Stage A}}$. | If Stage B pending, equals $0.0$. | Stage B & Live Play. | In training, fit via out-of-fold splits. | Both Live Heads. |
| 34 | `is_batting_team_toss_winner`| `boolean` | `matches.csv` / Stage 5B | `True` if current batting team won the toss. | Non-nullable after toss. | Stage B & Live Play. | Known 15 mins before match. | Stage B & Live Heads. |
| 35 | `toss_decision_bat` | `boolean` | `matches.csv` / Stage 5B | `True` if toss winner elected to bat first. | Non-nullable after toss. | Stage B & Live Play. | Known 15 mins before match. | Stage B & Live Heads. |

---

### Group 5: Trajectory & Momentum Dynamics (7 Features)

| # | Feature Name | Data Type | Source Dataset | Definition & Calculation Method | Missing / Imputation Policy | Temporal & Lifecycle Scope | Leakage Risk & Safeguard | Model Usage |
| :-: | :--- | :---: | :--- | :--- | :--- | :--- | :--- | :--- |
| 36 | `runs_last_12_balls` | `Int64` | Engineered from Stage 5B | Runs scored in preceding 12 legal deliveries. | If $B < 12$: impute $\text{CRR} \times 2.0$. | All in-play deliveries. | Evaluated before delivery $b$. | Both Live Heads. |
| 37 | `wickets_last_12_balls` | `Int64` | Engineered from Stage 5B | Wickets lost in preceding 12 legal deliveries. | If $B < 12$: impute $0$. | All in-play deliveries. | Evaluated before delivery $b$. | Both Live Heads. |
| 38 | `runs_last_24_balls` | `Int64` | Engineered from Stage 5B | Runs scored in preceding 24 legal deliveries. | If $B < 24$: impute $\text{CRR} \times 4.0$. | All in-play deliveries. | Evaluated before delivery $b$. | Both Live Heads. |
| 39 | `partnership_runs_current` | `Int64` | Engineered from Stage 5B | Cumulative runs scored since most recent wicket. | Starts at $0$ for opening wicket. | All in-play deliveries. | Evaluated before delivery $b$. | Both Live Heads. |
| 40 | `partnership_balls_current`| `Int64` | Engineered from Stage 5B | Legal balls faced since most recent wicket. | Starts at $0$ for opening wicket. | All in-play deliveries. | Evaluated before delivery $b$. | Both Live Heads. |
| 41 | `expected_final_score_gap` | `Float64` | Engineered from Stage 5B | Projected Final Score minus `venue_avg_first_inn_score`. | Innings 2: `pd.NA`. | Innings 1 Live only. | Evaluated before delivery $b$. | Innings 1 Head only. |
| 42 | `target_pressure_index` | `Float64` | Engineered from Stage 5B | $\left(\frac{\text{RRR}}{\text{venue\_avg\_crr}}\right) \times \left(1 + \frac{\text{wickets\_lost\_before}}{5}\right)$. | Innings 1: `pd.NA`. | Innings 2 Live only. | Evaluated before delivery $b$. | Chase Head only. |

---

## 3. Lifecycle-Specific Feature Availability Matrix

The following authoritative matrix explicitly specifies the availability, presence, and handling of each feature across the four modeling lifecycle stages. Missing or unavailable features **never silently become zero**; they are handled via explicit domain imputations, structural omissions, or pending indicators.

| Feature Name | Stage A (Pre-Match Base) | Stage B (Post-Toss + Confirmed XI) | First-Innings Live Model | Second-Innings Chase Model | Imputation / Missingness Policy |
| :--- | :---: | :---: | :---: | :---: | :--- |
| `competition_category` | **Yes** | **Yes** | **Yes** | **Yes** | Non-nullable. Categorical string. |
| `venue_avg_first_inn_score` | **Yes** | **Yes** | **Yes** | **Yes** | Bayesian shrinkage to category par if $< 5$ matches. |
| `venue_chase_win_pct` | **Yes** | **Yes** | **Yes** | **Yes** | Bayesian shrinkage to $0.50$ if $< 5$ matches. |
| `venue_avg_death_rr` | **Yes** | **Yes** | **Yes** | **Yes** | Impute category death average ($9.5$ rpo). |
| `venue_pace_spin_wicket_ratio`| **Yes** | **Yes** | **Yes** | **Yes** | Impute category median ($1.50$). |
| `pre_match_prob_stage_a` | **Output** | **Yes** | **Yes** | **Yes** | Baseline opening prior. |
| `pre_match_prob_stage_b` | No | **Output** | **Yes** | **Yes** | If Stage B pending, retain Stage A. Out-of-fold in train. |
| `stage_b_prob_delta` | No | **Output** | **Yes** | **Yes** | If Stage B pending, impute $0.0$. |
| `is_batting_team_toss_winner`| No | **Yes** | **Yes** | **Yes** | Available only after toss. |
| `toss_decision_bat` | No | **Yes** | **Yes** | **Yes** | Available only after toss. |
| `batting_lineup_top3_abc` | No | **Yes** | **Yes** | **Yes** | If cold-start player, shrink to category prior $\mu_{\text{comp}}$. |
| `batting_lineup_mid4_abc` | No | **Yes** | **Yes** | **Yes** | If cold-start player, shrink to category prior $\mu_{\text{comp}}$. |
| `batting_lineup_tail_abc` | No | **Yes** | **Yes** | **Yes** | Impute category tail baseline ($35.0$). |
| `batting_lineup_mean_abc` | No | **Yes** | **Yes** | **Yes** | Shrink cold-start players to $\mu_{\text{comp}}$. |
| `batting_lineup_std_abc` | No | **Yes** | **Yes** | **Yes** | Impute category median variance. |
| `batting_cold_start_count` | No | **Yes** | **Yes** | **Yes** | Non-nullable integer $[0, 11]$. |
| `bowling_unit_powerplay_econ` | No | **Yes** | **Yes** | **Yes** | Impute category Powerplay average. |
| `bowling_unit_middle_econ` | No | **Yes** | **Yes** | **Yes** | Impute category Middle average. |
| `bowling_unit_death_econ` | No | **Yes** | **Yes** | **Yes** | Impute category Death average. |
| `bowling_unit_strike_rate` | No | **Yes** | **Yes** | **Yes** | Impute category bowling strike rate. |
| `relative_batting_edge` | No | **Yes** | **Yes** | **Yes** | Difference between team lineup means. |
| `innings` | No | No | **Yes** | **Yes** | Structural flag ($1$ or $2$). |
| `score_before` | No | No | **Yes** | **Yes** | Evaluated before ball $b$; starts at $0$. |
| `wickets_lost_before` | No | No | **Yes** | **Yes** | Evaluated before ball $b$; starts at $0$. |
| `wickets_remaining_before` | No | No | **Yes** | **Yes** | Evaluated before ball $b$; starts at $10$. |
| `legal_balls_completed_before`| No | No | **Yes** | **Yes** | Evaluated before ball $b$; starts at $0$. |
| `legal_balls_remaining_before`| No | No | **Yes** | **Yes** | Evaluated before ball $b$; starts at $120$. |
| `current_run_rate_before` | No | No | **Yes** | **Yes** | Impute with historical venue average CRR at ball 0.1. |
| `innings_phase` | No | No | **Yes** | **Yes** | Non-nullable categorical (`POWERPLAY`, `MIDDLE`, `DEATH`). |
| `innings_progress_pct` | No | No | **Yes** | **Yes** | Continuous index $[0.0, 1.0]$. |
| `resource_percentage_remaining`| No | No | **Yes** | **Yes** | Continuous lookup $[0.0, 100.0]$. |
| `runs_last_12_balls` | No | No | **Yes** | **Yes** | Impute $\text{CRR} \times 2.0$ if $B < 12$. |
| `wickets_last_12_balls` | No | No | **Yes** | **Yes** | Impute $0$ if $B < 12$. |
| `runs_last_24_balls` | No | No | **Yes** | **Yes** | Impute $\text{CRR} \times 4.0$ if $B < 24$. |
| `partnership_runs_current` | No | No | **Yes** | **Yes** | Starts at $0$ for opening wicket. |
| `partnership_balls_current`| No | No | **Yes** | **Yes** | Starts at $0$ for opening wicket. |
| `expected_final_score_gap` | No | No | **Yes** | No | Innings 1 only. Missing (`pd.NA`) in Innings 2. |
| `target_runs` | No | No | No | **Yes** | Innings 2 only. Missing (`pd.NA`) in Innings 1. |
| `runs_required_before` | No | No | No | **Yes** | Innings 2 only. Missing (`pd.NA`) in Innings 1. |
| `required_run_rate_before` | No | No | No | **Yes** | Innings 2 only. If $B_{\text{rem}} == 0$, clamp to $99.0$. |
| `rrr_minus_crr_before` | No | No | No | **Yes** | Innings 2 only. Impute $0.0$ at ball 0.1. |
| `target_pressure_index` | No | No | No | **Yes** | Innings 2 only. Non-linear chase pressure index. |
| **Active Feature Count per Model**| **7 features** | **20 features** | **35 features** | **39 features** | **Authoritative Total Catalog: 42 Features** |
