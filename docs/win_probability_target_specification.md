# CricImpact Phase 2 — Win Probability Target Specification & Leakage Prevention

**Stage:** Foundation Stage 5A (Specification & Design Only — **Revision 1.1**)  
**Companion Specifications:**
- [`match_state_specification.md`](file:///c:/Users/admin/Documents/CricImpact_Phase2/docs/match_state_specification.md)
- [`match_regime_policy.md`](file:///c:/Users/admin/Documents/CricImpact_Phase2/docs/match_regime_policy.md)
- [`match_state_feature_dictionary.md`](file:///c:/Users/admin/Documents/CricImpact_Phase2/docs/match_state_feature_dictionary.md)
- [`stage_5a_revision_report.md`](file:///c:/Users/admin/Documents/CricImpact_Phase2/docs/stage_5a_revision_report.md)

---

## Revision History

| Version | Scope | Key Specification Updates |
|:---|:---|:---|
| **1.0** | Initial Stage 5A Target Policy | Defined `target_batting_team_win`, `target_home_team_win`, leakage-free attachment rules, chronological `GroupSplit` requirements, and 7-regime treatment. |
| **1.1** | Stage 5A Technical Review Revision | **Issue B:** Enforced `is_innings_limit_verified == True` gating for standard 20-over WP predictions and RRR/projected-score computations (`legal_balls_remaining` un-clamped). **Issue C:** Separated `50407` with dedicated `eligibility_exclusion_reason = 'unresolved_match_sequence_50407'`, removed `50407` from any `798 vs 802` standard ablation pool, and added §2.1 literal `UNRESOLVED` audit entry. **Issue D:** Explicitly mandated retaining original competition metadata alongside `competition_category` totals (`5/2/134`; `371/30/482`). |

---

## 1. Supervised Target Design (`1 / 0 / NULL`)

### 1.1 Canonical Target Definitions (Two Complementary Views)
For every eligible completed match, outcome ground truth comes exclusively from `matches.win_team_id` *(verified 100% consistent against `ball_by_ball` totals across `805/805` non-DLS matches via `VAL-EXT-005` and `VAL-MCH-001`)*.

To prevent perspective errors across innings swaps and neutral venues, we define **two explicit binary targets** plus one clear conversion rule:

1. **Primary Live In-Play Target — Batting-Team Win (`target_batting_team_win`, where Team A = Current Batting Team on Delivery $b$):**
   $$y_{\text{bat}}(m, i, b) = \begin{cases} 1 & \text{if } \text{win\_team\_id}(m) \text{ is non-null and } \text{batting\_team\_id}(m, i, b) = \text{win\_team\_id}(m) \\ 0 & \text{if } \text{win\_team\_id}(m) \text{ is non-null and } \text{bowling\_team\_id}(m, i, b) = \text{win\_team\_id}(m) \\ \text{pd.NA} & \text{if } \text{win\_team\_id}(m) \text{ is NULL (Tied / No Result / Abandoned)} \end{cases}$$
   - **Why this is the Primary Live Modeling Target:** All match-state features (`score_after`, `wickets_remaining`, `current_run_rate`, `runs_required_after`, `required_run_rate`) describe the **current batting team's** position. Thus $P(y_{\text{bat}} = 1 \mid \text{state}_b)$ always means *probability the side currently batting wins the match*, cleanly preserving innings symmetry (`Innings 1 = batting team defending`, `Innings 2 = chasing team`).
   - **Deterministic Conversion to Any Named Team A / Team B:** For any match-fixed reference team $A$ (`home_team_id` or `team_1_id`), at delivery $b$:
     $$P(\text{Team } A \text{ wins} \mid \text{state}_b) = \begin{cases} \hat{p}_{\text{bat}}(b) & \text{if } \text{batting\_team\_id}(b) = A \\ 1 - \hat{p}_{\text{bat}}(b) & \text{if } \text{bowling\_team\_id}(b) = A \end{cases}$$

2. **Match-Fixed Reference Target — Home / Listed Team A Win (`target_home_team_win`, where Team A = `matches.home_team_id`):**
   $$y_{\text{home}}(m) = \begin{cases} 1 & \text{if } \text{win\_team\_id}(m) = \text{home\_team\_id}(m) \\ 0 & \text{if } \text{win\_team\_id}(m) = \text{away\_team\_id}(m) \\ \text{pd.NA} & \text{if } \text{win\_team\_id}(m) \text{ is NULL} \end{cases}$$
   - **Caveat on `T20I` / Neutral Matches:** Unlike `IPL`, bilateral or tournament `T20I` / `OTHER_T20` fixtures played at neutral grounds (`United Arab Emirates`, Asia Cup, etc.) sometimes list `home_team_id` arbitrarily rather than reflecting true home advantage. Using `target_batting_team_win` as primary modeling label avoids spurious `home_team_id` asymmetry, while `target_home_team_win` supports UI/match-tracker presentation and team-level calibration checks.

---

## 2. Treatment of Ties, No Results, Abandoned, DLS & Super Overs

**Mandatory Rule:** **Never** force a binary `0`/`1` label onto un-won matches (`win_team_id` NULL) and **never** silently inject noisy tiebreakers into standard 20-over training.

| Outcome / Regime Segment | Matches (`883`) | `win_team_id` State | `target_batting_team_win` | `eligibility_exclusion_reason` & Treatment Policy |
| :--- | ---: | :--- | :---: | :--- |
| **`STANDARD_T20`** | **798** | Non-null (`100%` `VAL-EXT-005` reconciled) | **`1` or `0`** | `eligibility_exclusion_reason = pd.NA` (**`is_primary_wp_train_eligible = True`**, `is_dls_eval_slice_eligible = False`). Core clean training & primary evaluation corpus (`IPL` + `OTHER_T20` + `T20I`, verified `120`-ball regulation, original `comp_id`/`comp_name`/`match_format`/`season` preserved). |
| **`INCOMPLETE_OR_UNRESOLVED`** (`14130`, `14164`, `41509` + unresolved `50407`) | **4** (`3` + `1`) | Non-null | **`1` or `0`** *(excluded; unverified limit)* | **`50407`: `eligibility_exclusion_reason = 'unresolved_match_sequence_50407'`** (`is_primary_wp_train_eligible = False`) — **MUST NEVER be used as a standard completed-match training example** and stays barred from standard sensitivity ablations until externally resolved (§2.1). `14130`, `14164`, `41509` carry `eligibility_exclusion_reason = 'sequence_or_termination_anomaly'` (`is_primary_wp_train_eligible = False`, `is_innings_limit_verified = False`, excluded from clean `798` baseline). |
| **`REVISED_OVERS_DLS`** (`28` explicit + `3` unflagged `15795`, `31278`, `48514`) | **31** | Non-null | **`1` or `0`** *(outcome exists, rain-conditioned)* | `eligibility_exclusion_reason = 'dls_or_revised_overs'` (**`is_primary_wp_train_eligible = False`; `is_dls_eval_slice_eligible = True`**). Excluded from primary training so un-timestamped rain reductions and missing targets/limits (`20182`, `23674`, `24822`, `28334`, `15795`, `31278`, `48514`, `16753`/`19959`) do not leak future weather. Evaluated separately as a regime slice (restricting RRR/balls-remaining metrics strictly to `is_target_known & is_innings_limit_verified`). |
| **`SUPER_OVER`** (`9` matches: `innings 1..2` vs `innings 3..4`) | **9** | Non-null (SO winner) | **Reg `1..2`: tie-decided**; **SO `3..4`: `1` or `0`** | `eligibility_exclusion_reason = 'super_over_innings'` (`innings 3..4`, `38` balls — ALWAYS excluded) or `'tied_after_regulation'` (`innings 1..2`, `2,270` balls — excluded from primary binary training because a regulation tie at ball `120` is resolved by a separate post-regulation tiebreaker; retained in calibration/tie evaluation `target = 0.5` conceptual expectation vs SO sensitivity analysis). |
| **`TIED` without Super Over** (`18532`) | **1** | **NULL** | **`pd.NA`** | `eligibility_exclusion_reason = 'tied_no_winner'` (`is_primary_wp_train_eligible = False`). Excluded from binary supervised training. Never impute `0` or `0.5` into binary log-loss unless an explicit multi-outcome/tie loss is researched separately. |
| **`NO_RESULT`** (`21` matches) | **21** | **NULL** | **`pd.NA`** | `eligibility_exclusion_reason = 'no_result_null_winner'` (`is_primary_wp_train_eligible = False`, `is_dls_eval_slice_eligible = False`). Unfinished deliveries must never be labeled `0` or pseudo-labeled via heuristic par scores. Pre-NR stats may not use outcome labels. |
| **`ABANDONED`** (`19` matches: `16` zero-ball, `3` partial) | **19** | **NULL** | **`pd.NA`** | `eligibility_exclusion_reason = 'abandoned_null_winner'` (`is_primary_wp_train_eligible = False`, `0` ball rows for the `16` zero-delivery matches; partial `3` excluded from binary targets). Weather-abandonment frequency tracked only in corpus coverage diagnostics. |

### 2.1 Match `50407` Exclusion & Audit Entry (Issue C)
In [`matches.csv`](file:///c:/Users/admin/Documents/CricImpact_Phase2/data/raw/matches.csv) and [`ball_by_ball.csv`](file:///c:/Users/admin/Documents/CricImpact_Phase2/data/raw/ball_by_ball.csv), `match_id = 50407` (*West Indies in India T20I Series 2026*, `2026-10-14`, `comp_id = 3450`, `win_team_id = 28`, `'West Indies Won by 24 runs'`) records a clean Innings 1 (`247/3` in `120` legal balls) followed by Innings 2 (`223/9` in `117` legal balls), where overs `1..19` have `6` legal balls each, the 9th wicket falls on `19.6`, and Over `20` stops after `20.5` (`wide-5`, `is_wicket = False`, `0` Retired Hurt, zero DLS/revised metadata) with two batters remaining at the crease.

- **Mandatory Audit Determination:**  
  **`UNRESOLVED — source evidence insufficient to determine match status or missing delivery reason.`**
- **Target & Training Policy:**
  - Raw delivery records remain untouched, and no termination cause (abandonment, injury, missing feed, or over reduction) is inferred or speculated.
  - `innings_ball_limit = pd.NA`, `is_innings_limit_verified = False`, `legal_balls_remaining = pd.NA`, `required_run_rate = pd.NA`, `terminal_innings_status_audit = 'unresolved_50407'`, `eligibility_exclusion_reason = 'unresolved_match_sequence_50407'`, `is_primary_wp_train_eligible = False`, and `is_dls_eval_slice_eligible = False`.
  - **`match_id = 50407` MUST NEVER be used as a standard completed-match training example**, and remains quarantined until verified against an official ICC scorecard / over-by-over scoring provider feed confirming why Over 20 terminated at `20.5`.

---

## 3. Causal Label Assignment & Leakage Prevention Architecture

Assigning final match result labels back onto every earlier delivery row `(match_id, innings, innings_ball_num)` is valid **only under strict separation between target attachment and feature construction**:

### 3.1 How Every Delivery State Receives Its Outcome Label Safely
1. **Target Attachment Key:** Each delivery row `(match_id, innings, innings_ball_num)` inherits `win_team_id_raw` *(exact pass-through of `matches.win_team_id`)* purely via relational key `match_id`, comparing only against causal `batting_team_id` / `bowling_team_id` on that row:
   - `y_bat = 1` iff `batting_team_id == matches.win_team_id`
   - `y_bat = 0` iff `bowling_team_id == matches.win_team_id`
2. **Forbidden Feature-Label Cross-Talk:** No feature vector at delivery $b$ may depend — directly or indirectly — on:
   - Whether `match_id` ends in `clean`, `DLS`, `Super Over`, `Abandoned`, `No Result`, or `Tie`.
   - Any post-delivery outcome of future balls $b' > b$ in the same match (`final score` during Innings 1, `terminal_innings_status_audit` such as `9`-wicket absent-hurt closure or `'unresolved_50407'`, total innings balls played, whether an Impact Sub will appear later in the innings, or whether rain will reduce overs later).
   - Post-match `matches.csv` columns (`result`, `man_of_the_match`, `win_team_id`, `revised_target` / `*_revised_overs` on un-timestamped mid-innings rain matches).
   - Post-hoc `ball_by_ball` reverse-sorted fields (`innings_ball_num` max, match margin).
3. **Verified Innings-Limit Gate (`is_innings_limit_verified == True`):** Standard 20-over live Win Probability training and delivery-level inference **MUST require `is_innings_limit_verified == True`** (`innings_ball_limit` non-null, `legal_balls_remaining` un-clamped). When `is_innings_limit_verified == False`, `legal_balls_remaining`, `required_run_rate`, and any projected final score remain `pd.NA`, and standard WP training excludes/abstains on those rows rather than substituting `0` or `120`.

### 3.2 Mandatory Splitting & Historical Prior Hygiene (Future Modeling Stages)
1. **Match-Grouped Splitting (`GroupSplit` by `match_id`):** All deliveries from a single `match_id` **MUST** reside exclusively in one fold (`train` OR `val` OR `test`). Splitting at delivery level leaks match outcome memorization (`> 99%` artificial accuracy) across identical `match_id`s.
2. **Strict Chronological Ordering by `matches.match_date`:**
   - Verified split boundary rule (`VAL-SRC-001`): $\max(\text{date}_{\text{train}}) < \min(\text{date}_{\text{val}}) \le \max(\text{date}_{\text{val}}) < \min(\text{date}_{\text{test}})$ (never order splits by `match_id`, since `61` `match_id`s are non-chronological).
   - Candidate chronological baseline from [`dataset_readiness_report.md`](file:///c:/Users/admin/Documents/CricImpact_Phase2/data/validation/dataset_readiness_report.md): `2022–2024` train / `2025` validation / `2026` holdout test (`481` / `191` / `133` Stage-4 clean matches, balanced across `T20` and `T20I`), further stratified on `STANDARD_T20` (`798` clean matches) across `competition_category`.
3. **Competition Metadata Preservation (`Issue D`):** All training, split, and evaluation artifacts **MUST retain original `comp_id`, `comp_name`, `match_format`, and `season` verbatim** alongside `competition_category` (`IPL`: `5` comps / `371` matches; `OTHER_T20`: `2` comps / `30` matches; `T20I`: `134` comps (`131` active) / `482` matches; deriving categories strictly from `competitions.csv`, never team names).
4. **Causal Historical Priors (`date_prior < match_date`):** Any future team, venue, competition-category, or player rolling form features built on top of this state table **MUST** compute statistics strictly from matches with `match_date < current_match_date` (excluding same-day unseen outcomes), must resolve split player IDs (`39444`/`8638`, `36153`/`8729`, etc.) cleanly without merging true homonyms (`Abdul Samad`, `Rashid Khan`, `Haider Ali`), and must **never** credit `bowler_id` or an unresolved batter (`40709` `2.19.5`, `is_dismissed_player_unresolved == True`) on `Retired Hurt` or `Retire Out` deliveries.
5. **Separate Innings 1 vs. Innings 2 Schema Guards:** Innings 1 rows always carry `pd.NA` (`NULL`) for all chase-target fields (`innings1_total_score`, `target_runs`, `runs_required_after`, `required_run_rate`, `rrr_minus_crr`) so models cannot confuse `0` runs needed with First-Innings states.
