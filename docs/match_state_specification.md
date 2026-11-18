# CricImpact Phase 2 — Match-State Engineering Specification

**Stage:** Foundation Stage 5A (Specification & Design Only — **Revision 1.1**)  
**Project Root:** [`CricImpact_Phase2`](file:///c:/Users/admin/Documents/CricImpact_Phase2)  
**Source-of-Truth References:**
- [`dataset_dictionary.md`](file:///c:/Users/admin/Documents/CricImpact_Phase2/data/validation/dataset_dictionary.md)
- [`extras_field_investigation.md`](file:///c:/Users/admin/Documents/CricImpact_Phase2/data/validation/extras_field_investigation.md)
- [`data_quality_assessment.md`](file:///c:/Users/admin/Documents/CricImpact_Phase2/data/validation/data_quality_assessment.md)
- [`validation_contract.md`](file:///c:/Users/admin/Documents/CricImpact_Phase2/data/validation/validation_contract.md)
- [`dataset_readiness_report.md`](file:///c:/Users/admin/Documents/CricImpact_Phase2/data/validation/dataset_readiness_report.md)
- [`stage4_ingestion_validation_report_v2.md`](file:///c:/Users/admin/Documents/CricImpact_Phase2/data/validation/stage4_ingestion_validation_report_v2.md)
- Stage 4 Ingestion & Validation Modules: [`dataset_registry.py`](file:///c:/Users/admin/Documents/CricImpact_Phase2/ml/ingestion/dataset_registry.py), [`csv_loader.py`](file:///c:/Users/admin/Documents/CricImpact_Phase2/ml/ingestion/csv_loader.py), [`extras_validator.py`](file:///c:/Users/admin/Documents/CricImpact_Phase2/ml/validation/extras_validator.py), [`delivery_validator.py`](file:///c:/Users/admin/Documents/CricImpact_Phase2/ml/validation/delivery_validator.py), [`wicket_validator.py`](file:///c:/Users/admin/Documents/CricImpact_Phase2/ml/validation/wicket_validator.py), [`match_validator.py`](file:///c:/Users/admin/Documents/CricImpact_Phase2/ml/validation/match_validator.py), [`relationship_validator.py`](file:///c:/Users/admin/Documents/CricImpact_Phase2/ml/validation/relationship_validator.py), [`playing_eleven_validator.py`](file:///c:/Users/admin/Documents/CricImpact_Phase2/ml/validation/playing_eleven_validator.py)

**Related Companion Specifications:**
- [`match_regime_policy.md`](file:///c:/Users/admin/Documents/CricImpact_Phase2/docs/match_regime_policy.md)
- [`win_probability_target_specification.md`](file:///c:/Users/admin/Documents/CricImpact_Phase2/docs/win_probability_target_specification.md)
- [`match_state_feature_dictionary.md`](file:///c:/Users/admin/Documents/CricImpact_Phase2/docs/match_state_feature_dictionary.md)
- [`stage_5a_revision_report.md`](file:///c:/Users/admin/Documents/CricImpact_Phase2/docs/stage_5a_revision_report.md)

---

## Revision History

| Version | Scope | Key Specification Updates |
|:---|:---|:---|
| **1.0** | Initial Stage 5A Design | Established delivery transition grain `(match_id, innings, innings_ball_num)`, causal formulas, approved extras rules, regime taxonomy, and feature contract. |
| **1.1** | Stage 5A Technical Review Revision | **Issue A:** Disallowed fabricating `resolved_dismissed_player_id` on `40709` `2.19.5`, added `is_dismissed_player_unresolved`, clarified batter/bowler non-attribution, and added testable Retired Hurt / Retire Out cases. **Issue B:** Unified verified-limit schema (`innings_ball_limit`, `is_innings_limit_verified`, `legal_balls_remaining`, `innings_limit_source`, `innings_limit_unavailable_reason`), prohibited silent `0`/`120` substitution or negative clamping, removed `120` assumption from `INCOMPLETE_OR_UNRESOLVED`/DLS/NR missing-limit innings, and documented RRR/projected-score/WP impacts. **Issue C:** Formalized `50407` as literally `UNRESOLVED` pending external verification. **Issue D:** Explicitly verified competition taxonomy counts (`5/2/134`; `371/30/482`) and raw metadata preservation rules. |

---

## 1. Purpose, Scope & Verified Competition Taxonomy

### 1.1 Objective
Define the exact, deterministic, leakage-free delivery-level match-state transition specification for **CricImpact Phase 2** so downstream engineering (Stage 5B+) can construct match-state tables and train the **Win Probability Prediction Engine**. This specification does **not** alter raw CSV files, Stage 4 validation code, or Phase 1 (`contribution`), and does **not** implement WPA, Pressure Index, HPPS, or model training.

### 1.2 Competition Scope & Metadata-Only Category Policy (Issue D)
All T20 competitions in [`competitions.csv`](file:///c:/Users/admin/Documents/CricImpact_Phase2/data/raw/competitions.csv) (`141` registered competitions; `138` active in [`matches.csv`](file:///c:/Users/admin/Documents/CricImpact_Phase2/data/raw/matches.csv); `883` matches; `200,999` deliveries across `2022-01-22` to `2026-11-01`) remain in scope. Original source columns **`comp_id`**, **`comp_name`**, **`match_format`**, and **`season` MUST NEVER be replaced or overwritten** in any match-state table, feature dataset, or model artifact; `competition_category` is strictly an additive derived column.

To preserve competition heterogeneity (franchise rules such as IPL Impact Substitutes, tournament structures, scoring distributions) without ever inferring categories from team names, every record derives `competition_category` **exclusively from `competitions.match_format` and `competitions.comp_name`**:

| `competition_category` | Verified Metadata Rule (`competitions.csv`) | Comps (`competitions.csv`) | Active Matches (`matches.csv`) | Deliveries (`ball_by_ball.csv`) | Domain & Schema Limitation Notes |
| :--- | :--- | ---: | ---: | ---: | :--- |
| **`IPL`** | `match_format == 'T20'` AND `comp_name.startswith('IPL')` | 5 (`1358`, `1715`, `2193`, `2725`, `3298`) | 371 | 87,687 | Franchise T20 league (`IPL 2022..2026`); sole group permitting Impact Substitutes (`558` `is_impact=1` rows) and containing the `6` `13`-played team-matches. |
| **`OTHER_T20`** | `match_format == 'T20'` AND NOT `comp_name.startswith('IPL')` | 2 (`2670`: *Mens T20 Emerging Teams Asia Cup 2024*; `3289`: *Asia Cup Rising Stars 2025*) | 30 (`15 + 15`) | 6,985 | Non-IPL `T20` competitions (`0` Impact Subs). **Unresolved schema subtype:** `competitions.csv` lacks an explicit `tier` or `domestic_vs_emerging_intl` column, and teams mix Test-nation `A` squads and Associate national sides; classification stays strictly metadata-based without parsing team names. |
| **`T20I`** | `match_format == 'T20I'` | 134 (`131` active; `2940`, `3405`, `3473` unused with `0` matches) | 482 | 106,327 | Full international T20s (`0` `'IPL'` keyword collisions); `0` Impact Subs; permits `12`-played concussion substitutes with `is_impact=0` (`20880`, `29926`, `32132`, `40039`). |
| **Verified Total** | Deterministic partition of `competitions.csv` | **141** | **883** | **200,999** | Directly re-verified against `competitions.csv`, `matches.csv`, and `stage4_ingestion_validation_report_v2.md`. |

---

## 2. Match-State Grain, Chronological Ordering & Dual-State Transition Contract

### 2.1 Primary Record Grain
- **Grain:** Exactly **one match-state record per recorded delivery transition** `(match_id, innings, innings_ball_num)` from [`ball_by_ball.csv`](file:///c:/Users/admin/Documents/CricImpact_Phase2/data/raw/ball_by_ball.csv).
- **Row Volume:** `200,999` raw delivery transitions (`105,727` Innings 1; `95,234` Innings 2; `25` Innings 3; `13` Innings 4).
- **Zero-Delivery Matches:** The `16` zero-ball `"Match Abandoned"` fixtures in `matches.csv` generate **`0` delivery match-state records** and are accounted for strictly at match/regime grain (`docs/match_regime_policy.md`).

### 2.2 Deterministic Delivery Ordering
All state reconstruction **MUST** sort strictly ascending by:
```text
(match_id ASC, innings ASC, innings_ball_num ASC)
```
Stage 4 `VAL-PK-002` proved `(match_id, innings, innings_ball_num)` is `100%` unique (`0` duplicates, `0` nulls) and strictly contiguous `1..N` across all `1,724` innings.

> **Mandatory Ordering Constraint:** **Never** sort deliveries by `delivery_ist_time` or `match_id` alone:
> 1. `delivery_ist_time` uses `UTC` suffixes despite its column name, contains `42` `00:00:00 UTC` placeholder rows across `4` matches (`13511`, `17737`, `24354`, `25158`), and moves backward within an innings on `4` verified rows (`14104` inn 1 `ib=8`, `17737` inn 2 `ib=7`, `24354` inn 1 `ib=102`, `55078` inn 2 `ib=69`).
> 2. `matches.match_id` is non-monotonic with `matches.match_date` on `61` rows (`VAL-SRC-001`). Always use `match_date` for chronological train/val/test ordering.

### 2.3 Preserved Context & Source Identifiers per Record
Every match-state row retains full lossless traceability back to raw CSV tables:
- **Competition Metadata (from `competitions.csv`):** `comp_id`, `comp_name`, `match_format`, `competition_category`, `season`.
- **Match & Venue Metadata (from `matches.csv`):** `match_id`, `match_date`, `match_number`, `stage`, `knock_out`, `venue_id`, `venue_country`, `home_team_id`, `away_team_id`, `toss_win_team_id`, `toss_opted`, `is_batting_team_toss_winner` *(causal pre-match context defined as `batting_team_id == toss_win_team_id`; `100%` non-null across all `867` matches with deliveries, missing only on `15` zero-ball abandoned matches; raw `matches.csv` contains no stadium name string, so `venue_id` and `venue_country` jointly identify the venue)*.
- **Innings & Team Context (from `ball_by_ball.csv`):** `innings`, `batting_team_id`, `bowling_team_id`.
- **Source Delivery Sequence Keys:** `overid`, `over_ball_num`, `innings_ball_num`, `delivery_ist_time` *(audit metadata only)*.
- **Participant Keys (Audit / Context Only):** `striker_id`, `non_striker_id`, `bowler_id`, `batting_order`.

### 2.4 Pre-Delivery (`*_before`) vs. Post-Delivery (`*_after`) State Architecture
Every delivery row $b \in \{1, \dots, N_{m,i}\}$ within `(match_id = m, innings = i)` represents an atomic state transition:

$$\text{State}_{\text{before}}[b] \xrightarrow{\;\text{Delivery } b \text{ Event}\;} \text{State}_{\text{after}}[b]$$

Let $r_b = \text{team\_runs}[b]$, $w_b = \mathbb{I}(\text{is\_wicket}[b] = \text{true})$, and $\ell_b = \mathbb{I}(\text{is\_legal\_delivery}[b] = \text{true})$.

- **Initial Condition ($b = 1$, start of innings $i$):**
  - `score_before[1] = 0`
  - `wickets_lost_before[1] = 0`
  - `legal_balls_completed_before[1] = 0`
  - `retired_hurt_count_before[1] = 0`
  - For Innings 2: `innings1_total_score` and `target_runs` (when known) are initialized at $b = 1$; `runs_required_before[1] = target_runs` (when known).
- **Intra-Innings State Transition Equations ($b \ge 1$):**
  - `score_after[b] = score_before[b] + r_b`
  - `wickets_lost_after[b] = wickets_lost_before[b] + w_b`
  - `legal_balls_completed_after[b] = legal_balls_completed_before[b] + \ell_b`
  - `retired_hurt_count_after[b] = retired_hurt_count_before[b] + is_retired_hurt_event[b]`
  - If `is_innings_limit_verified` (`innings_ball_limit` is defined from verified metadata/format rules, never inferred from observed deliveries):
    $$\text{legal\_balls\_remaining\_before}[b] = \text{innings\_ball\_limit} - \text{legal\_balls\_completed\_before}[b]$$
    $$\text{legal\_balls\_remaining}[b] = \text{innings\_ball\_limit} - \text{legal\_balls\_completed\_after}[b]$$
    **No silent clamping to zero:** if either expression evaluates `< 0`, set `is_legal_balls_remaining_negative = True` and trigger validation investigation rather than coercing to `0`. If `is_innings_limit_verified == False`, both `legal_balls_remaining_before` and `legal_balls_remaining` MUST remain `pd.NA` (never substitute `0` or `120`).
  - In Innings 2 when `target_runs` is known: `runs_required_before[b] = max(target_runs - score_before[b], 0)` and `runs_required_after[b] = max(target_runs - score_after[b], 0)`.

- **Sequential Continuity Invariant (for every consecutive delivery $b \ge 2$ within the same `(match_id, innings)`):**
  $$\begin{aligned}
  \text{score\_before}[b] &= \text{score\_after}[b - 1] \\
  \text{wickets\_lost\_before}[b] &= \text{wickets\_lost\_after}[b - 1] \\
  \text{legal\_balls\_completed\_before}[b] &= \text{legal\_balls\_completed\_after}[b - 1] \\
  \text{retired\_hurt\_count\_before}[b] &= \text{retired\_hurt\_count\_after}[b - 1]
  \end{aligned}$$
  Under a verified fixed over allocation (`is_innings_limit_verified == True` with `innings_ball_limit` constant) and fixed target (`target_runs` constant):
  $$\text{legal\_balls\_remaining\_before}[b] = \text{legal\_balls\_remaining}[b - 1], \qquad \text{runs\_required\_before}[b] = \text{runs\_required\_after}[b - 1]$$

- **Primary Training Observation Rule:**
  - **`post_delivery` (`*_after`) is the primary model training observation** on every delivery row. It captures the exact live scoreboard after delivery $b$ resolves, from which the Win Probability Engine predicts the eventual outcome.
  - **`pre_delivery` (`*_before`) is retained** in the state specification as the transition invariant audit pair (`after[b-1] == before[b]`) and for Stage 5B continuity unit tests (as well as enabling eventual pre- vs. post-ball comparison in later modeling stages without implementing WPA now).

- **Explicitly Documented State-Transition Discontinuities:**
  1. **Match Start ($b = 1$, Innings $1$):** Resets from empty pre-match state to `0/0` (`0` legal balls).
  2. **Innings Break (`innings 1 -> innings 2`):** `score`, `wickets_lost`, `legal_balls_completed`, `retired_hurt_count` reset to `0`; `batting_team_id` and `bowling_team_id` swap; Innings 2 initializes chase target context (`innings1_total_score`, `target_runs`, `runs_required_before[1] = target_runs`).
  3. **Regulation-to-Super-Over Transition (`innings 2 -> 3` and `3 -> 4`):** Regulation innings reset to Super Over mini-match state (`6`-legal-ball max, `0/0`). Strictly excluded from regulation 20-over Win Probability training (`docs/match_regime_policy.md`).
  4. **Mid-Innings DLS Interruption Gap (Unobserved Stoppage Ball):** Raw CSVs store match-level `first_inn_revised_overs`, `second_inn_revised_overs`, and `revised_target` without a per-delivery rain-interruption timestamp. Hence any true mid-innings revision creates a latent target/ball-limit jump not pinpointed in `ball_by_ball.csv`, requiring isolation of DLS matches from standard training.

---

## 3. First-Innings Features & Mathematical Formulas

All formulas below operate strictly on causal cumulative aggregates through delivery $b$ of `(match_id, innings = 1)`:

| Concept | Exact Formula / Rule | Edge-Case & Unit Safeguards |
| :--- | :--- | :--- |
| **`innings`** | Constant `1` for 1st innings (`int`). | Super Overs use `3` or `4` and are isolated. |
| **`total_runs` (`score_after`)** | $\sum_{k=1}^{b} \left(\text{runs}_k + \text{extras1\_runs}_k + \text{extras\_2\_runs}_k\right)$ | Verified `100%` across `805/805` non-DLS matches (`VAL-EXT-005`). |
| **`wickets_lost_after`** | $\sum_{k=1}^{b} \mathbb{I}(\text{is\_wicket}_k = \text{true})$ | Only counts official dismissals (`10,881`). **Never** increment on `12` Retired Hurt events (`is_wicket=false`). |
| **`wickets_remaining`** | $\max(10 - \text{wickets\_lost\_after}, 0)$ | Ranges `0..10`. In rare injured-batter endings (`5` verified Innings 2 chases: `15409`, `17627`, `29983`, `42743`, `48917`), an innings ends officially at `9` wickets down with `wickets_remaining = 1` (observable only terminally, never leaked early). |
| **`is_legal_delivery`** | $\text{extras\_type}_b \notin \{\text{'wide'}, \text{'Overstep'}, \text{'other'}\}$ | `None`, `byes`, `legbyes`, `Penalty` all return `True` (`192,445` legal, `8,554` illegal). |
| **`legal_balls_completed_after`** | $L_b = \sum_{k=1}^{b} \mathbb{I}(\text{is\_legal\_delivery}_k)$ | Uses cumulative legal-ball mask, **never** `innings_ball_num` or `over_ball_num` (which differ in `1,665 / 1,724` innings). |
| **`innings_ball_limit`** *(and **`is_innings_limit_verified`**, **`innings_limit_source`**, **`innings_limit_unavailable_reason`**)* | Determined strictly from verified match/innings metadata — **NEVER from observed deliveries or defaulting missing `*_revised_overs` to `120`**:<br>• **Explicit revised-overs metadata:** In Inn `1`, if `first_inn_revised_overs` is non-null $\to$ `int(first_inn_revised_overs)` (`is_innings_limit_verified = True`, `innings_limit_source = 'first_inn_revised_overs'`); in Inn `2`, same for `second_inn_revised_overs` (`6..120` **legal balls, NOT overs**).<br>• **Super Over (`innings >= 3`):** `6` (`is_innings_limit_verified = True`, `innings_limit_source = 'super_over_regulation_6_balls'`).<br>• **`STANDARD_T20` (`798` clean matches) & regulation `innings 1..2` of `SUPER_OVER` (`9` matches):** `120` under verified `match_format in {'T20', 'T20I'}` regulation rules (`is_innings_limit_verified = True`, `innings_limit_source = 'standard_t20_format_rule'`).<br>• **All missing-limit / curtailed / halted / unresolved innings** *(any `REVISED_OVERS_DLS`, `ABANDONED`, `NO_RESULT`, `TIED` inning where `*_revised_overs` is null; unflagged reduced matches `15795`, `31278`, `48514`; and `INCOMPLETE_OR_UNRESOLVED` `14130`, `14164`, `41509`, `50407`)*: `innings_ball_limit = pd.NA`, `is_innings_limit_verified = False`, `innings_limit_source = 'unavailable'`, exact `innings_limit_unavailable_reason`. | **Raw metadata gap:** `matches.csv` has no explicit `scheduled_overs` column, so even clean standard T20 regulation `120` depends on format regulation plus absence of revision/curtailment signals. Never derive limit from observed max delivery number or substitute `120` when a revised-overs value is null. |
| **`legal_balls_remaining`** | $\begin{cases} \text{innings\_ball\_limit} - L_b & \text{if } \text{is\_innings\_limit\_verified} \\ \text{pd.NA} & \text{otherwise} \end{cases}$ | **Un-clamped arithmetic (Issue B):** If `< 0`, flag `is_legal_balls_remaining_negative = True` and inspect underlying data — **never silently clamp negative values to `0`** (empirical corpus audit confirmed `0` negative occurrences across all verified innings). When `is_innings_limit_verified == False`, must remain `pd.NA` (never substitute `0` or `120`). |
| **`overs_completed_decimal`** | $O_b^{\text{dec}} = L_b / 6.0$ (`Float64`) | Continuous overs in `[0.0, 20.0]` (`18` balls $\to$ `3.0`, `19` $\to$ `3.1667`). Always use decimal overs for rates and regressions. |
| **`overs_completed_notation`** | $\lfloor L_b / 6 \rfloor + (L_b \bmod 6) / 10.0$ *(display/audit `Float64` only)* | Cricket notation (`0.1..19.6`, `20.0`). **Forbidden** in linear arithmetic or run-rate denominators. |
| **`current_run_rate`** | $\begin{cases} 0.0 & \text{if } L_b = 0 \\ \dfrac{6.0 \cdot \text{score\_after}[b]}{L_b} & \text{if } L_b > 0 \end{cases}$ | **Zero-division guard:** When `L_b == 0` (e.g., wide/no-ball on opening delivery `ib=1`), outputs `0.0` paired with `has_legal_balls_completed = (L_b > 0)`. |
| **`innings_phase`** | If `innings >= 3`: `'super_over'`.<br>Else if `is_innings_limit_verified` and `innings_ball_limit == 120`: `'powerplay'` ($0 \le L_b \le 36$), `'middle'` ($37 \le L_b \le 90$), `'death'` ($91 \le L_b \le 120$).<br>Else: `'revised_or_unverified'`. | Using legal balls `0..36 / 37..90 / 91..120` avoids mislabeling shortened or unverified-limit overs (such as over `10` of a `12`-over match) as `'middle'`, while `innings_progress_pct = L_b / innings_ball_limit` remains `pd.NA` unless `is_innings_limit_verified == True`. |
| **Team / Venue / Comp Context** | `batting_team_id`, `bowling_team_id`, `venue_id`, `venue_country`, `comp_id`, `comp_name`, `match_format`, `season`, `competition_category` (`IPL`/`OTHER_T20`/`T20I`) | Preserved losslessly from raw CSVs (`competitions`, `matches`, `ball_by_ball`). |
| **`innings_completion_status_at_ball`** | Causal in-play status after ball $b$:<br>- `'target_achieved'` (Inn 2 only when `is_target_known`)<br>- `'all_out_10'` (`wickets_lost_after == 10`)<br>- `'max_balls_reached'` (`is_innings_limit_verified` and `legal_balls_remaining <= 0`)<br>- `'in_progress'` (otherwise) | **Audit-only `terminal_innings_status_audit`** additionally records post-match closure categories (`completed_all_out_injury`, `completed_unrecorded_curtailment`, `halted_nr_abandoned`, `unresolved_50407`). **Never** leak terminal closure labels backward onto mid-innings deliveries as predictive features. |

### 3.1 Verification Audit: Negative Remaining Balls & Unverified Limit Coverage
Cross-checking every delivery across all `867` played matches (`1,724` innings) against [`matches.csv`](file:///c:/Users/admin/Documents/CricImpact_Phase2/data/raw/matches.csv) confirmed:
- **`legal_balls_completed > first_inn_revised_overs`:** `0` innings (`25/25` non-null matches satisfy `legal_balls <= first_inn_revised_overs`).
- **`legal_balls_completed > second_inn_revised_overs`:** `0` innings (`25/25` non-null matches satisfy `legal_balls <= second_inn_revised_overs`).
- **`legal_balls_completed > 120` (Inn `1..2`) or `> 6` (Inn `3..4`):** `0` innings (`max = 120` in regulation, `5` in SO `inn 3..4`).
- Even with zero historical negative cases, any future feed where `legal_balls_remaining < 0` MUST leave the raw difference negative, set `is_legal_balls_remaining_negative = True`, and fail validation for data inspection rather than silently clamping to zero.

---

## 4. Second-Innings Features, Chase Edge Cases & Missing-Limit Impact (Issue B)

In Innings 2 (`innings == 2`), every first-innings state metric (`score_after`, `wickets_lost_after`, `wickets_remaining`, `legal_balls_completed_after`, `legal_balls_remaining`, `innings_ball_limit`, `is_innings_limit_verified`, `overs_completed_decimal`, `current_run_rate`, `innings_phase`, `innings_progress_pct`, team/venue/competition context, `innings_completion_status_at_ball`) applies symmetrically using Innings 2 cumulative values and `second_inn_revised_overs` *(in legal balls)* as the revised ball limit when applicable (leaving `innings_ball_limit = pd.NA` and `is_innings_limit_verified = False` whenever `second_inn_revised_overs` is absent on DLS/reduced/halted/unresolved matches). In addition, chase state features are computed causally from the completed 1st innings:

### 4.1 Exact Target & Chase Formulas
Let $S_1 = \text{innings1\_total\_score}$ be the exact final team score of Innings 1:

1. **`target_runs` and `is_target_known`:**
   - **Standard non-DLS & equal-reduced without revised target column:**
     If match has `has_dls_or_revised_meta == False` (and not `18532` rain-tie; includes unflagged equal-reduced matches `15795`, `31278`, `48514` where Innings 1 completed at parity overs without DLS target adjustment), $\text{target\_runs} = S_1 + 1$, $\text{is\_target\_known} = \text{True}$.
     *(Empirical verification: across `407/407` clean chases, `target_runs = S_1 + 1` holds with `100.0%` exact boundary reconciliation.)*
   - **Explicit DLS with populated `matches.revised_target` (`23` matches total: `22` completed + `1` No Result `17765`):**
     $\text{target\_runs} = \text{matches.revised\_target}$, $\text{is\_target\_known} = \text{True}$, **`target_source = 'dls_revised_target'`**. *(Strictly regime-isolated because mid-innings revision timing is unrecorded.)*
   - **Equal-reduced `16753` (`132` in `66b`) & `19959` (`131` in `66b`):** Both have `first_inn_revised_overs = 66`, `second_inn_revised_overs = pd.NA`, `revised_target = pd.NA`, and zero `(D/L)`/`(DLS)` text; treat as `target_runs = pd.NA` unless explicitly flagged under equal-reduced `S_1 + 1` rule in DLS slice tests, **never** invent a target for `(D/L)`/`(DLS)` matches.
   - **DLS-text matches missing `revised_target` (`20182`, `23674`, `24822`, `28334`) & Tie case lacking complete DLS target (`18532`):**
     `target_runs = pd.NA`, `is_target_known = False`. **Never reverse-engineer missing targets from final winning margins.**

2. **`runs_required_after`:**
   $$\text{runs\_required\_after}[b] = \begin{cases} \text{pd.NA} & \text{if } \neg \text{is\_target\_known} \\ \max\left(\text{target\_runs} - \text{score\_after}[b],\; 0\right) & \text{if } \text{is\_target\_known} \end{cases}$$

3. **`required_run_rate` (RRR) & `is_rrr_undefined`:**
   Never divide by zero or compute rates from an unverified limit (`is_innings_limit_verified == False`):
   $$\text{required\_run\_rate}[b] = \begin{cases} \text{pd.NA} & \text{if } \neg \text{is\_target\_known} \text{ or } \neg \text{is\_innings\_limit\_verified} \\ 0.0 & \text{if } \text{runs\_required\_after}[b] = 0 \text{ (target achieved)} \\ \text{pd.NA} & \text{if } \text{runs\_required\_after}[b] > 0 \text{ and } \text{legal\_balls\_remaining}[b] \le 0 \\ \dfrac{6.0 \cdot \text{runs\_required\_after}[b]}{\text{legal\_balls\_remaining}[b]} & \text{if } \text{runs\_required\_after}[b] > 0 \text{ and } \text{legal\_balls\_remaining}[b] > 0 \end{cases}$$
   Paired boolean indicator:
   $$\text{is\_rrr\_undefined}[b] = \mathbb{I}\left(\text{required\_run\_rate}[b] \text{ is missing/undefined}\right)$$
   Paired rate pressure differential (`rrr_minus_crr`) is defined identically when both `required_run_rate` and `has_legal_balls_completed` are valid (`pd.NA` when `RRR` is undefined or `L_b == 0`).

### 4.2 Explicit Behavior Across All Six Required Chase Scenarios

| Scenario | `runs_required_after` | `legal_balls_remaining` | `required_run_rate` | `is_rrr_undefined` | `chase_completion_status` | Downstream Modeling Note |
| :--- | :---: | :---: | :---: | :---: | :--- | :--- |
| **1. Target already achieved** (`score_after >= target_runs`) | `0` | `>= 0` when limit verified (`0` on `20.6`; `pd.NA` if `!is_innings_limit_verified`) | **`0.0`** if limit verified else `pd.NA` | `False` if limit verified else `True` | `'target_achieved'` | Even when `legal_balls_remaining == 0`, `runs_required == 0` resolves RRR to `0.0` when `is_innings_limit_verified == True`. |
| **2. No legal balls remaining, runs still needed** (`is_innings_limit_verified` & `legal_balls_remaining == 0` & `runs_required_after >= 2`) | `>= 2` | `0` | **`pd.NA`** *(no div by 0)* | **`True`** | `'balls_exhausted_lost'` | Terminal losing state (`120` legal balls exhausted; target missed by `runs_required - 1` runs). |
| **3. Tie at the end of regulation innings** (`score_after == inn1_total` at `legal_balls_remaining == 0`) | `1` (or `pd.NA` if `18532` non-DLS-target tie) | `0` (`pd.NA` on `18532`) | **`pd.NA`** *(no div by 0)* | **`True`** | `'tied_regulation'` (`SO` matches) / `'target_unknown'` (`18532`) | Covers all `9` Super Over ties after `120` balls (and `18532` DLS-par tie). Regulation tie target semantics governed in `win_probability_target_specification.md`. |
| **4. All-out innings** (`wickets_lost_after == 10` before target) | `>= 1` (if target known) | `>= 0` if verified, else `pd.NA` | Computable if `balls_rem > 0 & is_innings_limit_verified`, else `pd.NA` | `True` if `balls_rem <= 0` or unverified | `'all_out_lost'` | Chasing innings closes immediately because `wickets_remaining == 0`. *(The `5` injured `9`-wicket closures `15409`, `17627`, `29983`, `42743`, `48917` remain `'in_progress'` causally at ball $b$.)* |
| **5. Incomplete / Unresolved innings** (`17765`, `40737` NR partial chases; `50407` ending `20.5` at `117b`; `14130` inn 2 `119b`) | Computed if target known | `pd.NA` unless verified (`17765` has `rev2=72`; **`50407`, `40737`, `14130` are `pd.NA`**) | **`pd.NA`** (`50407`, `40737`, `14130`) / standard formula (`17765`) | **`True`** (`50407`, `40737`, `14130`) | `'in_progress'` causally | **Never** assume `120` balls for `50407` or `INCOMPLETE_OR_UNRESOLVED` (`UNRESOLVED` sequence). |
| **6. DLS revised targets** (`23` populated `revised_target`; `4` missing `(D/L)`/`(DLS)` targets) | `max(revised_target - score, 0)` when known; else `pd.NA` | `second_inn_revised_overs - L_b` when non-null; else `pd.NA` (`20182`, `23674`, `24822`, `28334`, `16753`, `19959`) | Safe formula when both known; else `pd.NA` | `True` when target or `rev2` missing | `'target_achieved'` / `'in_progress'` / etc. | All `22` completed `revised_target` rows (plus NR `17765`) also populate `second_inn_revised_overs`. Missing `rev2` stays `pd.NA`, never `120`. |

### 4.3 System-Wide Downstream Impact When `is_innings_limit_verified == False`
Whenever `is_innings_limit_verified == False` (`innings_ball_limit` is `pd.NA`), downstream pipelines **MUST** enforce strict null propagation and never substitute `0` or `120`:
1. **First-Innings State Features:** `legal_balls_remaining = pd.NA`, `innings_progress_pct = pd.NA`, `innings_phase = 'revised_or_unverified'`, and `innings_completion_status_at_ball` never fires `'max_balls_reached'`.
2. **Second-Innings Chase Features:** `legal_balls_remaining = pd.NA`; `chase_completion_status` never asserts `'balls_exhausted_lost'` or `'tied_regulation'`.
3. **Required Run Rate (`required_run_rate` & `rrr_minus_crr`):** Must output `pd.NA` with `is_rrr_undefined = True`, even if `target_runs` is known (e.g., `20182`, `23674`, `24822`, `28334`, `40737`, `50407`).
4. **Projected Final Score (Future Stage Feature Contract):** Any first-innings projected final score calculation (e.g., par projection or $\text{score} + \text{CRR} \times \text{legal\_balls\_remaining}/6$) **MUST return `pd.NA` / remain disabled** whenever `is_innings_limit_verified == False`; fabricating a `120`-ball projection on reduced or halted matches is prohibited.
5. **Win Probability Predictions:** Primary 20-over live Win Probability training and standard 120-ball inference **MUST exclude / abstain (`is_primary_wp_train_eligible = False`)** whenever `is_innings_limit_verified == False`, preventing distorted probability spikes or false resource-depletion signals from missing limits.

---

## 5. Delivery Event Representation & Approved Extras Semantics

Per [`extras_field_investigation.md`](file:///c:/Users/admin/Documents/CricImpact_Phase2/data/validation/extras_field_investigation.md) and [`extras_validator.py`](file:///c:/Users/admin/Documents/CricImpact_Phase2/ml/validation/extras_validator.py):

1. **Batter Runs (`batter_runs`):** Raw `ball_by_ball.runs` (`0..6`). Represents runs off the bat.
2. **Primary Extras (`extras1_runs`):** Raw numeric count (`0..5`, NOT a legacy category ID!). Holds wide runs (`1..5`), leg-bye runs (`1..5`), bye runs (`1..5`), 1-run no-ball penalty (`1` on `Overstep` & `other`), or `Penalty` (`5`).
3. **Secondary Extras (`extras_2_runs`):** Raw numeric count (`0`, `1`, `4`) storing non-bat extras (byes/leg-byes) on `35` no-balls (`21` `Overstep`, `14` `other`) plus `1` anomalous `None` row (`17555` `1.5.4`). Preserves an explicit `is_extras_2_subtype_unresolved = (extras_2_runs > 0)` audit note because CSV alone cannot split byes vs. leg-byes on those `35` deliveries.
4. **Total Team Runs (`team_runs`):** Unconditionally derived as:
   $$\text{team\_runs} = \text{runs} + \text{extras1\_runs} + \text{extras\_2\_runs}$$
   Verified across `200,999` deliveries (`284,257` total runs). **No silent row edits.**
5. **Preserved Four Approved Documented Anomalies:**
   - `36097` inn 2 `8.6` (`extras_type='None'`, `runs=0`, `extras1_runs=1`, `extras_2_runs=0`)
   - `17555` inn 1 `5.4` (`extras_type='None'`, `runs=0`, `extras1_runs=0`, `extras_2_runs=1`)
   - `37099` inn 1 `14.1` (`extras_type='legbyes'`, `runs=1`, `extras1_runs=0`, `extras_2_runs=0` — preserves `team_runs = 1`; only player-batting analytics separates batter credit)
   - `14130` inn 2 ov `14` (`5` legal balls + `1` wide inside `ob=1..6`)
   All four are preserved identically in raw inputs, correctly summed into `score_after` / `legal_balls_completed`, and flagged via `has_extras_anomaly` / `has_sequence_anomaly`.
6. **Wicket Events, Retired Hurt vs. Retire Out & Dismissal Attribution (Issue A):**
   - **Official Wicket Flag (`is_wicket_event`):** Equals raw `ball_by_ball.is_wicket` (`bool`). **Never** infer team wickets from `dismissed_player_id.notna()`.
   - **Retired Hurt vs. Retire Out Distinction:**
     1. **Retired Hurt (`12` rows):** Injury/illness exit with `is_wicket = False`, `dismissal_type = pd.NA`, `dismissal_type_id = pd.NA`, and populated `dismissed_player_id` (`0` resumed later; `20188`, `20243`, `31709` retired the `non_striker_id`). **Adds `+0` team wickets** (`wickets_lost_after` and `wickets_remaining` unchanged; tracked separately in `is_retired_hurt_event` & `retired_hurt_count_after`), preserves raw dismissal columns, and **must NEVER assign a dismissal contribution to `bowler_id` (nor treat the exit as a batter dismissal)**.
     2. **Retire Out (`6` rows):** Official tactical retirement with `is_wicket = True`, `dismissal_type = 'Retire Out'`, `dismissal_type_id = 9`. **Increments the team innings wicket count (`+1` via verified `is_wicket`)**, tracks `is_retire_out_event = True`, and **must NEVER assign a wicket dismissal credit to `bowler_id`** (just as `RunOut` and `Obstructing the field` are non-bowler dismissals under Cricket Laws).
   - **Missing Dismissed-Player Attribution (`40709` Inn `2` Delivery `19.5`):**
     - Raw `dismissed_player_id_raw` is preserved untouched as `pd.NA` (`190,107` nulls overall = `190,106` non-exits + `1` unresolved `Retire Out`).
     - **`resolved_dismissed_player_id` MUST remain `pd.NA`** whenever raw `dismissed_player_id` is missing unless a verified external source directly provides the identity. *(Never infer from `striker_id` — indeed, `20244` & `40715` retired non-strikers, and on `40709` `2.19.6`, `striker_id=3330` stayed at the crease while `4101` entered alongside him!)*
     - Add explicit attribution flag: **`is_dismissed_player_unresolved = is_wicket_event & dismissed_player_id_raw.isna()`** (`True` only on `40709` `2.19.5`).
     - **Impact on Match State vs. Player Contributions:** Team match-state calculations (`wickets_lost_after`, `wickets_remaining`) remain exact via `is_wicket = True`; however, in downstream batter/bowler contribution calculations, deliveries with `is_dismissed_player_unresolved == True` (and non-bowler dismissals `Retired Hurt` / `Retire Out`) **must NOT assign a batter-out or bowler-wicket credit when the relevant identity/source support is unavailable**.
   - **Dismissal Spellings:** Preserve `dismissal_type_raw` (`'Obstracting the field'` untouched on `2` rows) and expose `dismissal_type_canonical` normalizing `'Obstracting the field'` $\to$ `'Obstructing the field'` (`dismissal_type_id = 10`), enforced against `VAL-WKT-002` Cricket Law checks.
   - **Testable Verification Examples:**

| Scenario | Verified Corpus Row | `is_wicket` | `dismissal_type_canonical` | `dismissed_player_id_raw` | `resolved_dismissed_player_id` | `is_dismissed_player_unresolved` | `wickets_lost` Delta | Bowler Wicket Credit |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Retired Hurt (Striker)** | `14114` Inn `2` `14.1` (`ib=80`) | `False` | `pd.NA` | `1440` | `1440` | `False` | **`+0`** | **None (`0`)** |
| **Retired Hurt (Non-Striker)** | `20188` Inn `1` `11.1` (`ib=64`) | `False` | `pd.NA` | `2003` | `2003` | `False` | **`+0`** | **None (`0`)** |
| **Retire Out (Known Striker)** | `14113` Inn `1` `19.2` (`ib=116`) | `True` | `'Retire Out'` | `305` | `305` | `False` | **`+1`** | **None (`0`)** |
| **Retire Out (Known Non-Striker)** | `20244` Inn `2` `15.6` (`ib=91`) | `True` | `'Retire Out'` | `6466` | `6466` | `False` | **`+1`** | **None (`0`)** |
| **Retire Out (Missing ID)** | `40709` Inn `2` `19.5` (`ib=117`) | `True` | `'Retire Out'` | **`pd.NA`** | **`pd.NA`** | **`True`** | **`+1`** | **None (`0`; batter/bowler unattributed)** |
7. **Legal Delivery & Extra Subtype Flags (`is_legal_delivery`, `is_wide`, `is_no_ball`):**
   - `is_wide = (extras_type == 'wide')` (`7,714` rows).
   - `is_no_ball = extras_type.isin({'Overstep', 'other'})` (`840` rows: `576` `Overstep` + `264` `other`).
   - `is_legal_delivery = ~extras_type.isin({'wide', 'Overstep', 'other'})` (`True` iff `~is_wide & ~is_no_ball`; `192,445` legal vs. `8,554` illegal deliveries).
   - `extras_type == 'Penalty'` (`16753` inn 2 `6.4`, `5` runs) has `is_legal_delivery = True`, `is_wide = False`, `is_no_ball = False`.
8. **Boundary Indicators (`is_boundary_four`, `is_boundary_six`):**
   - Preserve raw `is_four` / `is_six` alongside `runs`. Explicitly note the `23` documented `'None'` rows (`20` with `runs=4, is_four=false`; `3` with `runs=6, is_six=false`) may reflect all-run 4s, overthrows (`2 + 4`), or tagging omissions; team scoring always relies on numeric `runs`.
9. **Overthrow / Unusual Scoring Uncertainty Flag (`scoring_uncertainty_flag`):**
   Boolean flag set `True` whenever a delivery has ambiguity in boundary/law/attribution breakdown even though `team_runs` is exact:
   - `extras_2_runs > 0` (`36` rows: bye vs. leg-bye split unknown)
   - `(extras_type == 'None') & (((runs == 4) & ~is_four) | ((runs == 6) & ~is_six) | (runs == 5))` (all-run / overthrow / untagged boundaries)
   - `extras1_runs == 5` on `wide`, `byes`, `legbyes`, or `Penalty` (`274` rows: overthrow / boundary / penalty ambiguity)
   - `extras_type == 'other'` (`264` rows: non-overstep no-ball cause unspecified for ~20% non-beamer/non-full-toss rows)
   - Any of the isolated documented extras anomalies (`17555` `1.5.4`, `36097` `2.8.6`, `37099` `1.14.1`)
10. **Super Over Deliveries (`is_super_over_delivery`):**
    - `is_super_over_delivery = (innings >= 3)` (`38` rows across `6` matches from July 2024 onward; `overid = 1`, `6`-legal-ball cap). Excluded from primary 20-over Win Probability training.
11. **Free-Hit Derivation Exclusion Policy:**
    - **Do NOT derive or include `is_free_hit` as a Stage 5 match-state feature at this stage.**
    - **Rationale:** `ball_by_ball.csv` has no raw `is_free_hit` field, and safe sequential propagation (`Overstep`/`other` $\to$ free hit carried over subsequent `wide`s until the next legal/valid delivery) depends on resolving: (a) whether all `52` non-beamer/non-full-toss `extras_type == 'other'` deliveries always carried a free hit across varying tournament playing conditions, (b) missing-delivery mid-over feeds (`14130` `1.14`, `14130` `2.14`, `14164` `1.14`, `41509` `1.12`) where an unobserved intervening no-ball or consumption ball could silently flip state across an entire sequence, and (c) innings boundaries vs mid-innings halts. Any future inclusion requires separate formal rule verification.

---

## 6. Match-Level Data Quality & Edge-Case Disposition Summary

*(Full regime taxonomy & target exclusion rules appear in [`match_regime_policy.md`](file:///c:/Users/admin/Documents/CricImpact_Phase2/docs/match_regime_policy.md) and [`win_probability_target_specification.md`](file:///c:/Users/admin/Documents/CricImpact_Phase2/docs/win_probability_target_specification.md); raw values are **never** altered.)*

| Edge Case / Known Issue | Exact Scope in Raw CSVs | State Generation Rule | Model Eligibility Impact |
| :--- | :--- | :--- | :--- |
| **`14130`, `14164`, `41509`, and `50407` Sequence Anomalies (Issue C)** | `14130` inn 1 & 2 ov 14 (`5` legal each $\to$ `119b`, `37` vs `'36'` text margin); `14164` inn 1 ov 14 (`5` legal $\to$ `119b`); `41509` inn 1 ov 12 (`7` legal $\to$ bowled out `20.4`, `119b`); `50407` inn 2 ov `1..19` complete (`114b`), ov `20` stops after `20.5` wide-5 (`117b`, `9` wkts, `223/9` vs `247/3`, `'West Indies Won by 24 runs'`) | Preserve raw rows; compute `legal_balls_completed` strictly via `cumsum(is_legal_delivery)`. Because **`50407`** is `UNRESOLVED — source evidence insufficient to determine match status or missing delivery reason.`, and sequence anomalies lack verified `innings_ball_limit`, set `is_innings_limit_verified = False`, `innings_ball_limit = pd.NA`, `legal_balls_remaining = pd.NA`. | Quarantined in `INCOMPLETE_OR_UNRESOLVED` (`has_sequence_anomaly = True`). **`50407` MUST NEVER be used as a standard completed-match training example** (`eligibility_exclusion_reason = 'unresolved_match_sequence_50407'`). |
| **Four Approved Extras Anomalies** | `36097` `2.8.6`, `17555` `1.5.4`, `37099` `1.14.1`, `14130` `2.14` | Compute `team_runs = runs + e1 + e2`; flag `has_extras_anomaly = True`. Reconciles `100%` of match winners. | Eligible in state generation (`team_runs` exact); `37099` `14.1` separated only in batter-level analytics. |
| **Retired Hurt vs. Retire Out (Issue A)** | `12` Retired Hurt (`is_wicket=false` + ID); `6` Retire Out (`is_wicket=true`; `40709` `2.19.5` missing ID) | Only `is_wicket == true` increments `wickets_lost`; keep `dismissed_player_id_raw` and `resolved_dismissed_player_id` = `pd.NA` on `40709` `2.19.5` with `is_dismissed_player_unresolved = True`; never credit `bowler_id` for Retire Out / Retired Hurt. | Team scoreboard state completely eligible (`0` artificial wicket distortion); player attribution skips unresolved IDs & tactical retirements. |
| **`40` Super Over `playing_eleven` Duplicates** | `13613`, `21176`, `28962` (`40` duplicate rows with distinct `batting_order`) | Preserved raw. Any lineup helper uses `min(batting_order)` regular XI per `(match_id, team_id, player_id)` rather than blind deduplication. | Note `13613`, `21176`, `28962` belong to `SUPER_OVER` regime regardless. |
| **`9` Super Over Matches & `3` Missing SO Feeds** | `9` matches tied after `120` legal balls (`6` from July 2024+ have `38` `innings 3/4` balls; `3` pre-July-2024 `13613`, `21176`, `28962` omit `innings 3/4`) | Emit regulation `innings 1..2` states for all `9` (`2,270` rows, `innings_ball_limit=120`) and tag `innings 3..4` (`38` rows, `innings_ball_limit=6`) `is_super_over_delivery = True`. No synthetic SO balls for older `3`. | `innings 3..4` always excluded from 20-over training. Regulation `innings 1..2` isolated under `SUPER_OVER` (`tied_after_regulation`) per target policy. |
| **`28` Explicit DLS/Revised + `10` Unlabeled Revised + `3` Unflagged Reduced (`15795`, `31278`, `48514`) + `18532`** | `28` completed explicit DLS/revised (`22` completed w/ `revised_target`, `4` `(D/L)` without `revised_target`: `20182`, `23674`, `24822`, `28334`, `2` equal-reduced `16753`, `19959`) + `3` unflagged `12`/`16`-over completed matches + `10` unlabeled revised (incl. NR `17765` w/ `revised_target=130`) + `18532` rain-tie | Generate states using `*_revised_overs` (`first_inn_revised_overs` / `second_inn_revised_overs`, stored as **legal balls**) ONLY when non-null; leave `innings_ball_limit = pd.NA`, `is_innings_limit_verified = False`, `legal_balls_remaining = pd.NA`, and `target_runs = pd.NA` wherever missing — never substitute `120` or infer from max delivery number. | **Excluded from primary Standard T20 model training (`is_primary_wp_train_eligible = False`).** Evaluated strictly in isolated `REVISED_OVERS_DLS` slices where limits/targets are verified. |
| **UAE Split Player IDs & Name Conflicts** | Matches `37087`, `37092`, `37095`: `39444`/`8638` (*Basil Hameed*), `36153`/`8729` (*Syed Haider*/*Haider Shah*); plus `4458` (`AHT Donald`/`Aneurin Donald`), split pairs vs `3` true homonyms | Preserved raw IDs. Core match-state features (`score`, `wickets`, `balls`, `CRR`, `RRR`) do not join on `playing_eleven` player IDs. Curated `player_alias_override` deferred strictly to Stage 5B+ player-feature work (never merge true homonyms). | `has_uae_split_player_id` logged; zero effect on score/ball match-state eligibility. |
| **`16` Abandoned Zero-Ball Matches** | `16` matches absent from `ball_by_ball.csv` (`3` also absent from `playing_eleven.csv`: `36210`, `41503`, `48513`) | Produce **`0` rows** in delivery-grain state table; retained at match grain in `ABANDONED`. | `win_team_id` is NULL $\to$ excluded from supervised Win Probability training (`target = NULL`). |
