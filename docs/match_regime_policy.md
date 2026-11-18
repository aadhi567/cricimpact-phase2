# CricImpact Phase 2 — Match Regime Classification & Eligibility Policy

**Stage:** Foundation Stage 5A (Specification & Design Only — **Revision 1.1**)  
**Companion Specifications:**
- [`match_state_specification.md`](file:///c:/Users/admin/Documents/CricImpact_Phase2/docs/match_state_specification.md)
- [`win_probability_target_specification.md`](file:///c:/Users/admin/Documents/CricImpact_Phase2/docs/win_probability_target_specification.md)
- [`match_state_feature_dictionary.md`](file:///c:/Users/admin/Documents/CricImpact_Phase2/docs/match_state_feature_dictionary.md)
- [`stage_5a_revision_report.md`](file:///c:/Users/admin/Documents/CricImpact_Phase2/docs/stage_5a_revision_report.md)

---

## Revision History

| Version | Scope | Key Policy Updates |
|:---|:---|:---|
| **1.0** | Initial Stage 5A Policy | Defined mutually exclusive 7-regime classification across all `883` matches, deterministic precedence tree, orthogonal audit flags, and DLS/SO isolation. |
| **1.1** | Stage 5A Technical Review Revision | **Issue B:** Unified verified limit status (`innings_ball_limit`, `is_innings_limit_verified`, `legal_balls_remaining`), removed `120`-ball assumption from `INCOMPLETE_OR_UNRESOLVED` and missing-metadata innings, clarified `*_revised_overs` are stored as legal balls, and prohibited inferring limits from observed deliveries. **Issue C:** Separated `match_id = 50407` (`unresolved_match_sequence_50407`) out of any standard ablation pool and added a dedicated §4.4 `UNRESOLVED` audit entry specifying required external evidence. **Issue D:** Explicitly verified competition taxonomy totals (`5/2/134`; `371/30/482`) and original metadata retention. |

---

## 1. Design Principles & Non-Leakage Rules

1. **Full Coverage Across All `883` Matches:** No match is silently dropped during Stage 5 state construction. Every match receives a deterministic primary `match_regime` enum plus causal orthogonal regime flags.
2. **Metadata-Only, Non-Destructive Classification:** Classification relies exclusively on verified raw tables ([`matches.csv`](file:///c:/Users/admin/Documents/CricImpact_Phase2/data/raw/matches.csv), [`competitions.csv`](file:///c:/Users/admin/Documents/CricImpact_Phase2/data/raw/competitions.csv), [`ball_by_ball.csv`](file:///c:/Users/admin/Documents/CricImpact_Phase2/data/raw/ball_by_ball.csv)). Neither `matches.csv` nor `ball_by_ball.csv` is edited, repaired, or coerced.
3. **Strict Anti-Leakage Boundary:** `match_regime` and outcome-dependent sub-flags (`has_dls_or_revised_meta`, `has_unrecorded_over_reduction`, `is_tied_after_regulation`, `has_sequence_anomaly`, etc.) depend on post-match outcomes and **MUST NEVER be used as live model input features** during ball-by-ball training or inference. They exist solely for dataset partitioning, training eligibility gating, regime-specific evaluation slicing, and diagnostic auditing.
4. **Detection of Unflagged Equal-Reduced Matches (`15795`, `31278`, `48514`) & Rain Tie (`18532`):** Forensic Stage 5A audit identified `3` completed equal-over shortened matches lacking any DLS metadata or `(D/L)` text in `matches.csv` (`15795`: 12 overs/side; `31278`: 16 overs/side; `48514`: 12 overs/side), plus `1` rain-curtailed tie (`18532`: `160/10` vs `75/4` in `54b`). Classifying these cleanly prevents blindly applying a `120`-legal-ball cap to shortened or unverified innings (`is_innings_limit_verified = False`, `innings_ball_limit = pd.NA`).

---

## 2. Canonical Seven-Regime Taxonomy (`match_regime`)

All `883` matches map deterministically to one mutually exclusive primary `match_regime` label across the **7 required regime classes**, supplemented by orthogonal overlap flags (`§3`):

| # | `match_regime` Label | Exact Deterministic Definition | Matches (`883`) | Deliveries (`200,999`) | Innings Ball Limit Status (`innings_ball_limit` / `is_innings_limit_verified`) | Primary Win-Prob Training Eligible? |
|---:|:---|:---|---:|---:|:---|:---|
| 1 | **`STANDARD_T20`** | `win_team_id.notna()` AND NOT `is_super_over` AND NOT `has_dls_or_revised_meta` AND NOT `has_unrecorded_over_reduction` AND NOT `has_sequence_anomaly`. Both innings governed strictly by standard `120`-legal-ball regulation (`798` completely clean matches; the `4` isolated sequence/termination anomalies `14130`, `14164`, `41509`, `50407` are quarantined in `INCOMPLETE_OR_UNRESOLVED` below). | **798** | **190,631** | **`120` (`is_innings_limit_verified = True` via `standard_t20_format_rule`)** | **Yes — Primary Corpus** |
| 2 | **`REVISED_OVERS_DLS`** | `win_team_id.notna()` AND NOT `is_super_over` AND (`has_dls_or_revised_meta` OR `has_unrecorded_over_reduction`). Spans all `28` explicitly flagged DLS/revised matches **plus** the `3` unflagged equal-reduced matches (`15795`, `31278`, `48514`). | **31** (`28` explicit + `3` unflagged) | **5,161** (`4,726` + `435`) | **Verified (`*_revised_overs` in balls) ONLY when non-null** (`37` innings); **`pd.NA` (`is_innings_limit_verified = False`)** across all `25` missing innings (`16` Inn 1 + `9` Inn 2 incl. `15795`, `31278`, `48514`, `20182`, `23674`, `24822`, `28334`, `16753`/`19959` Inn 2). **Never substitute `120`.** | **No** *(excluded from primary training to avoid mid-innings hindsight leakage and missing-limit distortion; retained for isolated DLS evaluation)* |
| 3 | **`SUPER_OVER`** | `win_team_id.notna()` AND (`has_super_over_innings` OR `result` matches Super Over / Eliminator OR regulation `inn1_runs == inn2_runs` without DLS). Encompasses `6` post-July-2024 SO matches with `innings 3/4` (`38` SO deliveries) + `3` pre-July-2024 SO matches (`13613`, `21176`, `28962`) missing `innings 3/4`. | **9** | **2,308** (`2,270` reg + `38` SO) | **Regulation `120` (`inn 1..2`); `6` (`inn 3..4`)** (`is_innings_limit_verified = True`) | **`innings 3..4`: NEVER.** `innings 1..2`: **No** in primary binary training (isolated as tie-at-40-overs calibration slice — `§3` of target spec). |
| 4 | **`ABANDONED`** | `result == 'Match Abandoned'` (`win_team_id` is NULL). Includes `16` zero-delivery matches (absent from `ball_by_ball.csv`, `3` also absent from `playing_eleven.csv`: `36210`, `41503`, `48513`) and `3` partial Inn 1 matches (`15410`, `20226`, `21406`). | **19** (`16` zero-ball + `3` partial) | **258** (`3` partial matches) | **`114` (`15410` Inn 1 `rev1=114`)**; **`pd.NA` (`is_innings_limit_verified = False`)** on `20226` & `21406`. | **No** (`win_team_id` is NULL; zero outcome label). |
| 5 | **`NO_RESULT`** | `result == 'No Result'` (`win_team_id` is NULL). Includes `19` Inn 1-only matches and `2` partial Inn 2 matches (`17765` with `rev1/rev2=72, revised_target=130`; `40737`). `9` of `21` carry revised-over metadata (`15546`, `17765`, `31707`, `39983`, `39985`, `41975`, `46311`, `46749`, `50408`). | **21** | **1,495** | **Verified (`*_revised_overs`) on `10` innings (`9` Inn 1 + `17765` Inn 2); `pd.NA` (`is_innings_limit_verified = False`) on `13` missing innings (`12` Inn 1 + `40737` Inn 2).** | **No** (`win_team_id` is NULL; zero outcome label). |
| 6 | **`TIED`** | Regulation tie with **no team winner** (`win_team_id` is NULL AND `result == 'Match Tied'`). Covers `18532` (NZ vs IND `160/10` vs `75/4` in `54b`, rain-halted tie on DLS par without DLS columns populated). *Orthogonal `is_tied_after_regulation = True` additionally tags all `9` `SUPER_OVER` matches.* | **1** *(+ `9` orthogonal SO ties)* | **179** | **`pd.NA` (`is_innings_limit_verified = False`)** in both innings (`18532` curtailed at `54b` without `revised_overs`). | **No** (`win_team_id` is NULL; cannot assign `1`/`0`). |
| 7 | **`INCOMPLETE_OR_UNRESOLVED`** | Matches exhibiting unresolved sequence, termination, or reconciliation failure (`has_sequence_anomaly = True`):<br>• `14130` (inn 1 & 2 ov 14 = `5` legal balls each, `119b`, `37` vs `'36'` text mismatch)<br>• `14164` (inn 1 ov 14 = `5` legal balls, `119b`)<br>• `41509` (inn 1 ov 12 = `7` legal balls, `119b` bowled out)<br>• **`50407` (`UNRESOLVED` — inn 2 stopped `20.5` at `117b`, `9` wkts, `win_team_id = 28`; see §4.4)**<br>Plus any future ingested match failing `VAL-MCH-001`, `VAL-EXT-005`, or exhibiting partial completed innings without DLS metadata. | **4** *(Quarantined; `50407` UNRESOLVED)* | **967** | **`pd.NA` (`is_innings_limit_verified = False`)** across anomaly/unresolved innings — **never assume `120` legal balls or compute `legal_balls_remaining` without verified metadata.** | **Excluded:** **`50407` MUST NEVER be used as a standard completed-match training example** (`eligibility_exclusion_reason = 'unresolved_match_sequence_50407'`). `14130`, `14164`, `41509` stay excluded from baseline `798` corpus (`sequence_or_termination_anomaly`). |

> **Total Reconciliation:** `798 (STANDARD_T20) + 31 (REVISED_OVERS_DLS) + 9 (SUPER_OVER) + 19 (ABANDONED) + 21 (NO_RESULT) + 1 (TIED) + 4 (INCOMPLETE_OR_UNRESOLVED) = 883 matches`, and `190,631 + 5,161 + 2,308 + 258 + 1,495 + 179 + 967 = 200,999 deliveries` — **100.0% lossless coverage.**

*(Note on `20190`: `inn1 = 121/8 (120b)`, `inn2 = 127/5 (96b)`, valid `win_team_id = 3509`, `100%` exact `ball_by_ball` arithmetic; only the human text summary `matches.result` says `"6 wickets"` instead of `5`. Because `matches.result` text is never a model input or target, `20190` remains cleanly inside `STANDARD_T20` with `has_margin_text_mismatch = True`.)*

---

## 3. Precedence & Deterministic Decision Tree

To ensure mutually exclusive primary assignment while retaining every overlapping condition in orthogonal boolean flags, apply precedence top-to-bottom on `(matches LEFT JOIN comps LEFT JOIN bbb_agg)`:

```text
1. If result == 'Match Abandoned':                      -> ABANDONED
2. Else if result == 'No Result':                       -> NO_RESULT
3. Else if win_team_id IS NULL (or result == 'Match Tied'): -> TIED
4. Else if has_super_over_flag:                         -> SUPER_OVER
   (has_so_innings OR SO regex in result OR (inn1_runs == inn2_runs AND NOT has_dls_or_revised_meta))
5. Else if has_dls_or_revised_meta OR has_unrecorded_over_reduction: -> REVISED_OVERS_DLS
   (has_dls_or_revised_meta = (D/L|DLS in result) OR rev1.notna() OR rev2.notna() OR revised_target.notna();
    has_unrecorded_over_reduction = completed non-DLS where inn1 ended with max_overid < 20 AND inn1_wickets < 10
    [identifies 15795, 31278, 48514 cleanly, distinct from 14130/14164 where max_overid == 20])
6. Else if has_sequence_anomaly OR fails_target_reconciliation: -> INCOMPLETE_OR_UNRESOLVED
   (identifies 14130, 14164, 41509, 50407; plus any future match failing VAL-EXT-005/VAL-MCH-001)
7. Else:                                                -> STANDARD_T20
```

### 3.1 Orthogonal Audit & Overlap Flags (Attached to Every Match / Delivery)
Because cricket conditions overlap, primary classification is always paired with these non-mutating boolean flags:
- `has_dls_or_revised_meta`: `True` for `38` matches (`28` completed `REVISED_OVERS_DLS` + `9` `NO_RESULT` + `1` `ABANDONED` `15410`).
- `has_unrecorded_over_reduction`: `True` for `15795`, `31278`, `48514` (`3` equal-reduced matches) and `18532` (`TIED` on DLS par at `54b`).
- `is_tied_after_regulation`: `True` for `10` matches (`9` `SUPER_OVER` + `1` `TIED` `18532`).
- `has_super_over_innings`: `True` for `6` matches with `innings >= 3` (`34429`, `40725`, `45512`, `48027`, `48029`, `50359`).
- `has_missing_super_over_feed`: `True` for `3` pre-July-2024 SO matches (`13613`, `21176`, `28962`) lacking `innings 3/4` and carrying `40` duplicate `playing_eleven` rows.
- `has_sequence_anomaly`: `True` for `14130`, `14164`, `41509`, `50407` (abnormal legal balls per over/match termination).
- `has_extras_anomaly`: `True` for `17555`, `36097`, `37099`, `14130` (`4` documented extras/sequence quirks).
- `has_margin_text_mismatch`: `True` for `14130` and `20190`.
- `has_uae_split_player_id`: `True` for `37087`, `37092`, `37095` (`Basil Hameed` `39444`/`8638`, `Syed Haider` `36153`/`8729` split across `ball_by_ball` and `playing_eleven`).
- `has_deliveries`: `False` for the `16` zero-ball abandoned matches (`31281..50189`), `True` for `867` matches.

---

## 4. Handling Specific Regime Details

### 4.1 Explicit DLS Matches, Unit Rules & Missing Revised Overs (Issue B)
- **Unit Rule for `first_inn_revised_overs` and `second_inn_revised_overs`:** Despite the column name containing `"overs"`, raw CSV values store **legal ball counts** (`30..114`), never overs (`30` = `5` overs, `72` = `12` overs, `114` = `19` overs). Furthermore, `matches.csv` has **no** explicit `scheduled_overs` column. Therefore, `innings_ball_limit` is resolved strictly from verified format rules (`STANDARD_T20` & reg `SUPER_OVER`: `120`; SO `inn 3..4`: `6`) or populated `*_revised_overs` values — **never inferred from observed maximum delivery counts** (`max(legal_balls_completed)`), and **never defaulted to `0` or `120` when a limit is unavailable**.
- **`4` Completed `(D/L)` / `(DLS)` Matches Without `revised_target` (`20182`, `23674`, `24822`, `28334`):** All `4` have `first_inn_revised_overs = NA` and `second_inn_revised_overs = NA`, confirming mid-innings rain curtailment halted play after 2nd innings began without stored revised caps. Both `innings_ball_limit` and `target_runs` remain `pd.NA` (`is_innings_limit_verified = False`, `legal_balls_remaining = pd.NA`).
- **All Other DLS / NR / Abandoned / Tie Innings Missing `*_revised_overs`:** Includes `12` additional Innings 1 rows in explicit DLS matches (`13612`, `16754`, `21070`, `21586`, `28046`, `29984`, `34428`, `40749`, `48611`, plus `20182`, `23674`, `24822`, `28334`), Innings 2 of `16753` and `19959` (where only `first_inn_revised_overs = 66` is populated and `second_inn_revised_overs` / `revised_target` are `pd.NA`), `12` Inn 1 + `40737` Inn 2 in `NO_RESULT`, `20226` & `21406` in `ABANDONED`, `18532` (`TIED`), and the `3` unflagged equal-reduced matches (`15795`, `31278`, `48514`). In every case where `*_revised_overs` is null under a non-standard/curtailed/halted regime, `innings_ball_limit = pd.NA`, `is_innings_limit_verified = False`, `legal_balls_remaining = pd.NA`, `innings_limit_source = 'unavailable'`, and `innings_limit_unavailable_reason` records the exact gap (`matches_revised_overs_null_in_dls_or_halted_regime`, etc.). Note for instance `16754` Inn 1 (`90` balls, `lim_meta = NA`) and `29984` Inn 1 (`64` balls, `lim_meta = NA`): substituting `120` would severely distort `legal_balls_remaining`, RRR, Projected Final Score, and Win Probability predictions.
- **DLS Leakage Rule:** In `23` matches with populated `revised_target` (plus `first/second_inn_revised_overs`), raw CSVs do **not** record which delivery experienced rain stoppage. Applying final reduced over caps or `revised_target` backward to ball `1.1` leaks future weather interruptions; therefore, `REVISED_OVERS_DLS` is **strictly isolated** from primary standard Win Probability training.

### 4.2 Super Over Isolation Rules
- `innings >= 3` (`38` rows across `6` matches) uses `innings_ball_limit = 6` (`is_innings_limit_verified = True`, `innings_limit_source = 'super_over_regulation_6_balls'`), `overid = 1`, and is **always excluded** from regulation 20-over Win Probability modeling (`is_super_over_delivery = True`).
- Older `3` matches (`13613`, `21176`, `28962`) emit regulation `innings 1..2` states only (`has_missing_super_over_feed = True`); zero synthetic Super Over rows are invented.
- Within `playing_eleven.csv`, raw `40` duplicate rows in those `3` matches remain preserved (`VAL-PK-003`); downstream lineup utilities extract regular XI via earliest/minimal `batting_order` without blind deduplication.

### 4.3 Temporal Stratification & Verified Competition Metadata Retention (Issue D)
As verified in [`stage4_ingestion_validation_report_v2.md`](file:///c:/Users/admin/Documents/CricImpact_Phase2/data/validation/stage4_ingestion_validation_report_v2.md) (`VAL-SRC-001`), chronological splits (`max(train_date) < min(val_date) < min(test_date)`) must group strictly by `match_id` ordered by `match_date` and preserve all original metadata fields (`comp_id`, `comp_name`, `match_format`, `season`) verbatim alongside additive `competition_category` (`IPL`: `5` comps / `371` matches / `87,687` deliveries; `OTHER_T20`: `2` comps `2670` & `3289` / `30` matches / `6,985` deliveries; `T20I`: `134` comps (`131` active, `3` unused: `2940`, `3405`, `3473`) / `482` matches / `106,327` deliveries) so neither franchise/international proportions nor DLS/SO frequencies silently skew splits. Note that `competitions.csv` provides no explicit domestic-vs-emerging-international subtype column for `OTHER_T20`; any further sub-classification stays unresolved unless schema metadata supplies it (never parse team names).

### 4.4 Dedicated Audit Entry: Match `50407` (`INCOMPLETE_OR_UNRESOLVED`) (Issue C)
- **Verified Raw Record (`matches.csv`, `competitions.csv`, `playing_eleven.csv`, `ball_by_ball.csv`):**
  - `match_id = 50407`, `comp_id = 3450` (*West Indies in India T20I Series 2026*, `match_format = 'T20I'`, `season = '2026'`), `match_number = 4`, `match_date = 2026-10-14`, India (`18`) vs. West Indies (`28`), India won toss (`Fielding`), `win_team_id = 28`, `result = 'West Indies Won by 24 runs'`.
  - All DLS columns (`first_inn_revised_overs`, `second_inn_revised_overs`, `revised_target`) are `pd.NA`. `playing_eleven.csv` records `11` clean played players per side (`0` Impact Subs).
  - **Innings 1 (West Indies):** Complete `247/3` in `120` legal balls (`130` raw rows, `6` legal balls in every over `1..20`, `13:30:23–15:15:33 UTC`).
  - **Innings 2 (India):** `223/9` in `117` legal balls (`130` raw rows, `15:33:49–17:30:16 UTC`). Overs `1..19` each contain exactly `6` legal balls (`114` legal balls), with the 9th wicket falling at `19.6` (`Axar Patel` `2876` caught) and #11 batter `Mayank Yadav` (`27960`) facing `19.7`. Over `20` (bowled by `Shamar Joseph` `47050`, `17:26:06–17:30:16 UTC`) contains only `5` rows (`20.1` `4` runs, `20.2` `wide-1`, `20.3` `0`, `20.4` `0`, `20.5` `wide-5`; `is_wicket = False` on `20.5`, `0` Retired Hurt), leaving `Arshdeep Singh` (`6464`) and `Mayank Yadav` (`27960`) un-dismissed at the crease (`3` legal balls bowled in Over `20`, `3` short of `120` legal balls).
- **Mandatory Audit Status:**
  **`UNRESOLVED — source evidence insufficient to determine match status or missing delivery reason.`**
- **Non-Speculation & Treatment Policy:**
  1. Never speculate whether Innings 2 ended via abandonment, rain interruption, injured batter, retired-hurt omission, concession, early close, shortened over allocation, or truncated delivery feed.
  2. Never alter, drop, or pad raw `ball_by_ball.csv` deliveries.
  3. Set `match_regime = 'INCOMPLETE_OR_UNRESOLVED'`, `has_sequence_anomaly = True`, `innings_ball_limit = pd.NA`, `is_innings_limit_verified = False`, `legal_balls_remaining = pd.NA`, `terminal_innings_status_audit = 'unresolved_50407'`, `eligibility_exclusion_reason = 'unresolved_match_sequence_50407'`, and `is_primary_wp_train_eligible = False`. **`match_id = 50407` MUST NEVER be used as a standard completed-match training example.**
- **External Evidence Required to Resolve:** Official ICC/match scorecard, Duckworth-Lewis/match-referee playing-conditions record, or upstream scoring-provider ball-by-ball log confirming whether deliveries after `20.5` occurred and were omitted or why the match terminated at `117` legal balls.
