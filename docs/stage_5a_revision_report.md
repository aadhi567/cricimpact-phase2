# CricImpact Phase 2 — Stage 5A Specification Revision Report

**Stage:** Foundation Stage 5A (Technical Review Revision 1.1 — Specification & Design Only)  
**Project Root:** [`CricImpact_Phase2`](file:///c:/Users/admin/Documents/CricImpact_Phase2)  
**Revised Specifications:**
1. [`match_state_specification.md`](file:///c:/Users/admin/Documents/CricImpact_Phase2/docs/match_state_specification.md) (Revision `1.1`)
2. [`match_regime_policy.md`](file:///c:/Users/admin/Documents/CricImpact_Phase2/docs/match_regime_policy.md) (Revision `1.1`)
3. [`win_probability_target_specification.md`](file:///c:/Users/admin/Documents/CricImpact_Phase2/docs/win_probability_target_specification.md) (Revision `1.1`)
4. [`match_state_feature_dictionary.md`](file:///c:/Users/admin/Documents/CricImpact_Phase2/docs/match_state_feature_dictionary.md) (Revision `1.1`)

---

## 1. Revision Overview & Scope Compliance

Following technical review of the initial Stage 5A draft specifications (`v1.0`), four substantive issues (**Issues A–D**) were identified requiring stricter anti-fabrication rules, unified schema naming, non-clamping null propagation, explicit audit quarantine for `match_id = 50407`, and independent verification of competition taxonomy totals.

All revisions were executed strictly as **specification and design updates (`v1.1`)** inside [`docs/`](file:///c:/Users/admin/Documents/CricImpact_Phase2/docs):
- Zero raw CSV files under [`data/raw/`](file:///c:/Users/admin/Documents/CricImpact_Phase2/data/raw) were modified.
- Zero Stage 4 ingestion/validation modules under [`ml/`](file:///c:/Users/admin/Documents/CricImpact_Phase2/ml), [`scripts/`](file:///c:/Users/admin/Documents/CricImpact_Phase2/scripts), [`tests/`](file:///c:/Users/admin/Documents/CricImpact_Phase2/tests), or [`data/validation/`](file:///c:/Users/admin/Documents/CricImpact_Phase2/data/validation) were altered.
- Zero Stage 5B code, interim/processed feature datasets, trained model artifacts, or Git repositories were created.
- The frozen Phase 1 project (`contribution`) was neither accessed nor modified.

---

## 2. Read-Only Raw Data Evidence Summary

Prior to editing any specification, all four review issues were independently audited in read-only mode against all six immutable CSVs (`200,999` deliveries across `883` matches and `141` competitions) using `.venv\Scripts\python.exe`. Every numeric threshold, match ID, delivery coordinate, and invariant stated across the `v1.1` documents traces directly to verified Stage 4 reports and read-only raw queries.

---

## 3. Issue A — Retire Out, Retired Hurt & Missing `dismissed_player_id` (`40709` `2.19.5`)

### 3.1 Forensic Findings
- **Retired Hurt (`12` deliveries):** All `12` rows have `is_wicket = False`, `dismissal_type = pd.NA`, `dismissal_type_id = pd.NA`, and a populated `dismissed_player_id` matching either `striker_id` (`9` rows) or `non_striker_id` (`3` rows: `20188`, `20243`, `31709`). None of the `12` batters resumed batting later in that innings (`resumed_later = 0`).
- **Retire Out (`6` deliveries):** All `6` rows (`14113`, `20244`, `21585`, `40709`, `40715`, `41512`) have `is_wicket = True`, `dismissal_type = 'Retire Out'`, and `dismissal_type_id = 9`. Crucially, `20244` (`6466`) and `40715` (`1941`) retired the **`non_striker_id`**, proving `Retire Out` is NOT always the striker.
- **Why v1.0 `40709` Fallback Was Empirically Wrong:** On `match_id = 40709`, Innings `2`, `overid = 19`, `over_ball_num = 5` (`innings_ball_num = 117`), raw `striker_id = 3330` (*Hardik Pandya*), `non_striker_id = 7897` (*Namboori Tilak Varma*), `runs = 1`, `is_wicket = True`, `dismissal_type = 'Retire Out'`, and `dismissed_player_id = pd.NA`. Inspecting subsequent deliveries (`19.6` `ib=118` and Over `20` `ib=119..124`) revealed **`striker_id = 4101` (*Mitchell Santner*) alongside `non_striker_id = 3330` (*Hardik Pandya*)**, while `7897` was absent from the crease. Thus v1.0's fallback rule (`resolved_dismissed_player_id -> striker_id / Hardik Pandya`) both fabricated missing identity and misidentified the continuing striker.

### 3.2 Specification Changes Applied (`v1.1`)
1. **Strict Law Separation:**
   - `Retired Hurt`: `is_wicket_event = False`, **`+0` team wickets** (`wickets_lost_after` and `wickets_remaining` unaffected; tracked in `is_retired_hurt_event` and `retired_hurt_count_after`), **zero bowler dismissal credit**, **zero batter dismissal attribution**.
   - `Retire Out`: `is_wicket_event = True`, **`+1` team wicket** (`wickets_lost_after` increments via `is_wicket`), **zero bowler dismissal credit** (non-bowler wicket alongside `RunOut` and `Obstructing the field`).
2. **No Fabrication Rule:** Preserved `dismissed_player_id_raw` untouched AND restricted **`resolved_dismissed_player_id`** strictly to verified source IDs (`ball_by_ball.dismissed_player_id` unless directly supplied by an approved verified external source). On `40709` `2.19.5`, both remain **`pd.NA`**.
3. **Explicit Attribution Guard:** Added **`is_dismissed_player_unresolved = is_wicket_event & dismissed_player_id_raw.isna()`** (`True` only on `40709` `2.19.5`). Downstream player contribution pipelines must **not** assign a batter-out or bowler-wicket credit when identity or rule support is unavailable, while team state (`wickets_lost_after`) remains exact.
4. **Testable Examples:** Added 5-case verification matrix in [`match_state_specification.md`](file:///c:/Users/admin/Documents/CricImpact_Phase2/docs/match_state_specification.md) §5 covering Retired Hurt (striker & non-striker), Retire Out (known striker & non-striker), and Retire Out with missing ID (`40709` `2.19.5`).

---

## 4. Issue B — Verified `innings_ball_limit`, `legal_balls_remaining` & Downstream Impacts

### 4.1 Forensic Findings & v1.0 Defects Corrected
1. **Unit & Schema Verification:** Verified that `first_inn_revised_overs` and `second_inn_revised_overs` in [`matches.csv`](file:///c:/Users/admin/Documents/CricImpact_Phase2/data/raw/matches.csv) store **legal ball counts** (`30..114`), not overs, and that `matches.csv` has **no raw `scheduled_overs` column**.
2. **Removed Erroneous `120` Assumption on `INCOMPLETE_OR_UNRESOLVED`:** `v1.0` [`match_state_feature_dictionary.md`](file:///c:/Users/admin/Documents/CricImpact_Phase2/docs/match_state_feature_dictionary.md) and [`match_regime_policy.md`](file:///c:/Users/admin/Documents/CricImpact_Phase2/docs/match_regime_policy.md) previously assigned `120` balls to `INCOMPLETE_OR_UNRESOLVED` (`14130`, `14164`, `41509`, `50407`). This conflicted with Issue B and Issue C and was removed; all `INCOMPLETE_OR_UNRESOLVED` innings now have `innings_ball_limit = pd.NA` and `is_innings_limit_verified = False`.
3. **Eliminated Duplicate / Inconsistent Names:** Unified `innings_max_legal_balls` $\to$ **`innings_ball_limit`**, `is_innings_limit_known` $\to$ **`is_innings_limit_verified`**, and `legal_balls_remaining_after` $\to$ **`legal_balls_remaining`** across all four documents, plus added **`innings_limit_source`**, **`innings_limit_unavailable_reason`**, and **`is_legal_balls_remaining_negative`**.
4. **Removed Silent Zero Clamping (`max(..., 0)`):** `legal_balls_remaining = innings_ball_limit - L_b` (and `legal_balls_remaining_before = innings_ball_limit - L_{b-1}`) are computed **without** `max(..., 0)` clamping. Any `< 0` result sets `is_legal_balls_remaining_negative = True` and fails validation for data inspection. Exhaustive check across all `200,999` deliveries verified **`0` negative cases** (`0` against `first_inn_revised_overs`, `0` against `second_inn_revised_overs`, `0` against `120` regulation, and `0` against `6` Super Over).
5. **Comprehensive Null Propagation on Missing Limits:** Whenever `*_revised_overs` is missing under `REVISED_OVERS_DLS` (`16` Inn 1 + `9` Inn 2 incl. `15795`, `31278`, `48514`, `20182`, `23674`, `24822`, `28334`, `16753`/`19959` Inn 2), `TIED` (`18532`), `NO_RESULT` (`12` Inn 1 + `40737` Inn 2), `ABANDONED` (`20226`, `21406`), or `INCOMPLETE_OR_UNRESOLVED`: `innings_ball_limit = pd.NA`, `is_innings_limit_verified = False`, `legal_balls_remaining = pd.NA`, `innings_limit_source = 'unavailable'`, and exact `innings_limit_unavailable_reason` is attached (**never** `0`, **never** `120`, **never** `max(observed)`).

### 4.2 Downstream System Impact Documented
Explicit rules added in [`match_state_specification.md`](file:///c:/Users/admin/Documents/CricImpact_Phase2/docs/match_state_specification.md) §4.3, [`win_probability_target_specification.md`](file:///c:/Users/admin/Documents/CricImpact_Phase2/docs/win_probability_target_specification.md) §3.1, and [`match_state_feature_dictionary.md`](file:///c:/Users/admin/Documents/CricImpact_Phase2/docs/match_state_feature_dictionary.md) §5 & §8 ensure that when `is_innings_limit_verified == False`:
- **First-Innings State:** `legal_balls_remaining = pd.NA`, `innings_progress_pct = pd.NA`, `innings_phase = 'revised_or_unverified'`, `'max_balls_reached'` disabled.
- **Second-Innings Chase State:** `legal_balls_remaining = pd.NA`, `'balls_exhausted_lost'` / `'tied_regulation'` disabled.
- **Required Run Rate (`required_run_rate` & `rrr_minus_crr`):** Strictly `pd.NA` (`is_rrr_undefined = True`).
- **Projected Final Score:** Deferred candidate `projected_final_score` MUST return `pd.NA` / abstain rather than fabricating a `120`-ball projection.
- **Win Probability Predictions:** `is_primary_wp_train_eligible` requires `is_innings_limit_verified == True`; standard 20-over live WP predictions must exclude/abstain on unverified limits.

---

## 5. Issue C — Match `50407` Audit & Unresolved Status

### 5.1 Forensic Verification Summary
- **Metadata (`matches.csv` & `competitions.csv`):** `match_id = 50407`, `comp_id = 3450` (*West Indies in India T20I Series 2026*, `T20I`), `match_date = 2026-10-14`, `home_team_id = 18` (*India*) vs. `away_team_id = 28` (*West Indies*), `win_team_id = 28`, `result = 'West Indies Won by 24 runs'`, `first_inn_revised_overs = pd.NA`, `second_inn_revised_overs = pd.NA`, `revised_target = pd.NA`.
- **`playing_eleven.csv`:** Clean `11` played players per team (`0` Impact Subs, `0` duplicates).
- **Ball-by-Ball Trace (`ball_by_ball.csv`):**
  - **Innings 1 (West Indies):** `247/3` in `120` legal balls (`6` legal balls in every over `1..20`, `13:30:23–15:15:33 UTC`).
  - **Innings 2 (India):** `223/9` in `117` legal balls (`130` raw rows). Overs `1..19` each contain `6` legal balls (`114` legal balls); 9th wicket (`Axar Patel` `2876`) fell at `19.6`, and #11 batter `Mayank Yadav` (`27960`) faced `19.7`. **Over `20` (Shamar Joseph, `17:26:06–17:30:16 UTC`) terminates after 5 rows (`20.1` `4`, `20.2` `wide-1`, `20.3` `0`, `20.4` `0`, `20.5` `wide-5`, `is_wicket = False`, `0` Retired Hurt)**, leaving `Arshdeep Singh` (`6464`) and `Mayank Yadav` (`27960`) at the crease (`3` legal balls short of `120`).
  - *Why Stage 4 did not isolate `overid = 20`:* `VAL-SEQ-001` intentionally inspected mid-innings overs (`overid < max_overid`) to avoid false alarms on legitimate partial final overs (target reached / all out).

### 5.2 Audit Determination & Quarantine Updates
- **Mandatory Literal Finding (included across all Stage 5A docs):**
  **`UNRESOLVED — source evidence insufficient to determine match status or missing delivery reason.`**
- **Updates Implemented:**
  - Kept raw delivery rows unchanged and removed `50407` from `v1.0`'s `798 vs 802` sensitivity ablation pool.
  - Assigned dedicated **`eligibility_exclusion_reason = 'unresolved_match_sequence_50407'`** and **`terminal_innings_status_audit = 'unresolved_50407'`**, plus `innings_ball_limit = pd.NA`, `is_innings_limit_verified = False`, `legal_balls_remaining = pd.NA`.
  - Prohibited speculating abandonment, rain halt, concession, injured batter, omitted deliveries, or over reduction, and prohibited using `50407` as a standard completed-match training example.
  - Added dedicated §4.4 audit entry in [`match_regime_policy.md`](file:///c:/Users/admin/Documents/CricImpact_Phase2/docs/match_regime_policy.md) and §2.1 audit entry in [`win_probability_target_specification.md`](file:///c:/Users/admin/Documents/CricImpact_Phase2/docs/win_probability_target_specification.md), specifying official ICC match scorecard / referee report / upstream ball-feed logs as required external resolution evidence.

---

## 6. Issue D — Competition Taxonomy Verification & Metadata Preservation

Independent read-only cross-tabulation across `competitions.csv`, `matches.csv`, and `ball_by_ball.csv` confirmed `100%` exact reconciliation:

| `competition_category` | Verified Metadata Rule (`competitions.csv`) | `competitions.csv` | `matches.csv` | `ball_by_ball.csv` | Verification & Preservation Notes |
| :--- | :--- | ---: | ---: | ---: | :--- |
| **`IPL`** | `match_format == 'T20'` AND `comp_name.startswith('IPL')` | **5** (`1358, 1715, 2193, 2725, 3298`) | **371** | **87,687** | Exact match (`IPL 2022..2026`; `558` `is_impact=1` rows) |
| **`OTHER_T20`** | `match_format == 'T20'` AND NOT `comp_name.startswith('IPL')` | **2** (`2670`, `3289`) | **30** (`15 + 15`) | **6,985** | *Emerging Teams Asia Cup 2024* & *Asia Cup Rising Stars 2025*; lacks schema tier/domestic column in raw CSV |
| **`T20I`** | `match_format == 'T20I'` | **134** (`131` active; `2940, 3405, 3473` unused) | **482** | **106,327** | `0` `'IPL'` / `'League'` keyword collisions in `comp_name` |
| **Total** | Complete lossless partition | **141** | **883** | **200,999** | Verified identically across all 4 Stage 5A documents |

All Stage 5A schemas retain **`comp_id`**, **`comp_name`**, **`match_format`**, and **`season`** verbatim alongside the additive **`competition_category`** column, never infer competition categories from team names, and transparently mark the missing finer domestic-vs-emerging subtype column in `competitions.csv` as an unresolved raw schema limitation.

---

## 7. Cross-Document Revision Summary Matrix

| Document (`docs/`) | Key `v1.1` Revisions |
|:---|:---|
| [`match_state_specification.md`](file:///c:/Users/admin/Documents/CricImpact_Phase2/docs/match_state_specification.md) | Added Revision History; verified §1.2 Issue D counts & original metadata rules; unified §2.4 & §3 formula contract (`innings_ball_limit`, `is_innings_limit_verified`, `legal_balls_remaining`, `is_legal_balls_remaining_negative`, `innings_limit_source`, `innings_limit_unavailable_reason`) with §3.1 negative-ball audit (`0` occurrences); added §4.3 missing-limit downstream impacts; rewrote §5 item 6 for Issue A (`pd.NA` on `40709` `2.19.5`, `is_dismissed_player_unresolved`, non-bowler credit, 5 testable cases); updated §6 `50407` literal `UNRESOLVED` quarantine & missing-limit rules. |
| [`match_regime_policy.md`](file:///c:/Users/admin/Documents/CricImpact_Phase2/docs/match_regime_policy.md) | Added Revision History; updated §1 item 4 & §2 regime table with verified limit columns & separated `50407` out of any `798 vs 802` ablation pool; clarified §4.1 `*_revised_overs` units (legal balls) & all missing-limit innings; updated §4.2 to `innings_ball_limit = 6`; verified §4.3 competition counts & metadata retention; added dedicated **§4.4 `match_id = 50407` Audit Entry** with literal `UNRESOLVED` sentence and external evidence requirements. |
| [`win_probability_target_specification.md`](file:///c:/Users/admin/Documents/CricImpact_Phase2/docs/win_probability_target_specification.md) | Added Revision History; separated `50407` (`'unresolved_match_sequence_50407'`) from `INCOMPLETE_OR_UNRESOLVED` ablation wording in §2; added dedicated **§2.1 Match `50407` Exclusion & Audit Entry** with literal `UNRESOLVED` status; added §3.1 item 3 (`is_innings_limit_verified == True` WP/RRR/projection gate); updated §3.2 for Issue D metadata preservation & Issue A player-attribution exclusions. |
| [`match_state_feature_dictionary.md`](file:///c:/Users/admin/Documents/CricImpact_Phase2/docs/match_state_feature_dictionary.md) | Added Revision History; updated §2 competition metadata retention & counts (`5/2/134`, `371/30/482`); removed `max(..., 0)` from §3 `legal_balls_remaining_before`; fixed §4 `resolved_dismissed_player_id` (`pd.NA` on `40709` `2.19.5`) & added `is_dismissed_player_unresolved` (`22` fields); renamed & unified §5 `innings_ball_limit`, `is_innings_limit_verified`, `legal_balls_remaining` + added `innings_limit_source`, `innings_limit_unavailable_reason`, `is_legal_balls_remaining_negative` (`27` fields); updated §6 `terminal_innings_status_audit` (`'unresolved_50407'`); updated §7 `eligibility_exclusion_reason` (`'unresolved_match_sequence_50407'`); added §8 `projected_final_score` deferred gating entry (`8` entries). |

---

## 8. Remaining Explicitly Unresolved Items (Zero Fabrication)

The following items remain intentionally `pd.NA` or `UNRESOLVED` in Stage 5A pending verified external sources or raw schema extensions:
1. **`match_id = 40709`, Inn `2`, `19.5` (`ib=117`):** `dismissed_player_id_raw` and `resolved_dismissed_player_id` remain `pd.NA` with `is_dismissed_player_unresolved = True` (subsequent raw rows `19.6` and Over `20` show `3330` & `4101` at the crease, yet official `dismissed_player_id` remains unrecorded and unattributed unless directly supplied by a verified external source).
2. **`match_id = 50407` Over `20` Stoppage (`20.5`, `117` legal balls):** **`UNRESOLVED — source evidence insufficient to determine match status or missing delivery reason.`** Excluded via `'unresolved_match_sequence_50407'`.
3. **Missing `*_revised_overs` / `revised_target` Metadata & Raw `scheduled_overs`:** All unpopulated DLS/reduced/halted/tie/incomplete limits remain `pd.NA` (`is_innings_limit_verified = False`, `legal_balls_remaining = pd.NA`), and missing DLS `revised_target` rows (`20182`, `23674`, `24822`, `28334`, `16753`, `19959`, `18532`) remain `pd.NA`. Raw `matches.csv` lacks a `scheduled_overs` column.
4. **`OTHER_T20` Fine-Grained Subtype:** `competitions.csv` lacks an explicit domestic-vs-emerging-international tier field for `2670` and `3289`.
5. **Secondary `extras_2_runs` Subtype Breakdown (`36` rows) & `is_free_hit`:** Bye-vs-legbye allocation inside `extras_2_runs` stays flagged (`is_extras_2_subtype_unresolved`), and `is_free_hit` remains deferred pending `extras_type == 'other'` (`264` rows) & mid-over anomaly rule verification.

---

## 9. Validation & Cross-Document Consistency Verification

Cross-document search and manual inspection across all `5` Markdown files in [`docs/`](file:///c:/Users/admin/Documents/CricImpact_Phase2/docs) verified:
- **Zero deprecated field names** (`innings_max_legal_balls`, `is_innings_limit_known`, `legal_balls_remaining_after`) remain in any revised Stage 5A document.
- **Zero contradictory fallbacks or clamps** (`striker_id` fallback on `40709` `2.19.5`, `120`-ball cap on `INCOMPLETE_OR_UNRESOLVED`, `max(..., 0)` clamping on `legal_balls_remaining`, or `798 vs 802` inclusion of `50407`) remain anywhere in Stage 5A.
- **Exact numeric consistency** across all documents: `141` competitions (`5` IPL, `2` OTHER_T20, `134` T20I), `883` matches (`371` / `30` / `482`; `798 + 31 + 9 + 19 + 21 + 1 + 4`), and `200,999` deliveries (`87,687` / `6,985` / `106,327`), with zero empirical negative `legal_balls_remaining` cases.

---

## 10. Safety, Immutability & Stage 5B Readiness Confirmation

- [`data/raw/`](file:///c:/Users/admin/Documents/CricImpact_Phase2/data/raw) CSV SHA-256 digests and modification timestamps remain completely unchanged.
- Stage 4 code ([`ml/`](file:///c:/Users/admin/Documents/CricImpact_Phase2/ml), [`scripts/`](file:///c:/Users/admin/Documents/CricImpact_Phase2/scripts), [`tests/`](file:///c:/Users/admin/Documents/CricImpact_Phase2/tests)) and Stage 4 audit reports ([`data/validation/`](file:///c:/Users/admin/Documents/CricImpact_Phase2/data/validation)) remain completely untouched.
- Empty placeholder directories (`data/interim/`, `data/processed/`, `data/features/`, `data/metadata/`, `models/`) remain empty; `.git/` does not exist; Phase 1 (`contribution`) remains untouched.
- **Status:** Stage 5A Revision `1.1` is complete and ready for user review and formal approval prior to Stage 5B implementation.
