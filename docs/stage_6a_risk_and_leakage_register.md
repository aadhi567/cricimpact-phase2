# CricImpact Phase 2 — Stage 6A Revision 1: Risk & Data Leakage Register

**Document:** Stage 6A Risk & Data Leakage Register (Revision 1.0)  
**Status:** Approved Risk Register (Planning & Design Only — Stage 6A)  
**Author:** AI Architecture & Data Science Agent  
**Date:** November 2026  
**Project Root:** [`C:\Users\admin\Documents\CricImpact_Phase2`](file:///c:/Users/admin/Documents/CricImpact_Phase2)  
**Companion Documents:**
- [`stage_6a_win_probability_specification.md`](file:///c:/Users/admin/Documents/CricImpact_Phase2/docs/stage_6a_win_probability_specification.md)
- [`stage_6a_feature_dictionary.md`](file:///c:/Users/admin/Documents/CricImpact_Phase2/docs/stage_6a_feature_dictionary.md)
- [`stage_6a_target_and_state_construction.md`](file:///c:/Users/admin/Documents/CricImpact_Phase2/docs/stage_6a_target_and_state_construction.md)
- [`stage_6a_training_and_evaluation_plan.md`](file:///c:/Users/admin/Documents/CricImpact_Phase2/docs/stage_6a_training_and_evaluation_plan.md)
- [`stage_6a_data_readiness_report.md`](file:///c:/Users/admin/Documents/CricImpact_Phase2/docs/stage_6a_data_readiness_report.md)
- [`stage_6a_implementation_plan.md`](file:///c:/Users/admin/Documents/CricImpact_Phase2/docs/stage_6a_implementation_plan.md)
- [`stage_6a_revision_1_report.md`](file:///c:/Users/admin/Documents/CricImpact_Phase2/docs/stage_6a_revision_1_report.md)

---

## 1. Risk Governance & Leakage Prevention Protocol

Predictive modeling for live sports faces acute risks of data leakage, target contamination, and temporal snooping. If future match information, in-sample anchor predictions, or post-match outcomes leak into feature sets or training pipelines, the resulting models will exhibit artificially inflated offline validation metrics while collapsing completely in live operational deployment.

This register identifies **19 distinct risk categories**, assesses their failure modes, and establishes non-negotiable architectural mitigations alongside explicit programmatic unit test assertions.

---

## 2. Exhaustive Risk Matrix & Mitigation Catalog

### Risk 01: Intra-Match Delivery Leakage in Dataset Splitting
- **Failure Mode:** Deliveries from the same match appear across both training and test sets. Adjacent deliveries ($b-1$ in train, $b$ in test) allow the model to memorize the target outcome directly from delivery context.
- **Impact:** Critical (Catastrophic offline overfit, live model failure).
- **Detection Method:** Assert that the set intersection of `match_id` across train, val, and test splits is empty.
- **Prevention Mechanism:** Match-level grouping is strictly enforced. No match is ever split across partitions. All 190,575 standard deliveries inherit their split assignment from `match_id`.
- **Automated Test Requirement:**
  ```python
  assert len(set(train_df['match_id']).intersection(set(test_df['match_id']))) == 0
  assert len(set(train_df['match_id']).intersection(set(val_df['match_id']))) == 0
  ```

### Risk 02: Same-Day Doubleheader Contamination
- **Failure Mode:** Two matches occur on the same calendar date $d$ (e.g. afternoon and evening IPL matches). If Match 2 incorporates player statistics or expectation updates generated from Match 1 without timestamps, temporal causality is violated.
- **Impact:** High (Subtle lookahead bias).
- **Detection Method:** Check that all historical source records satisfy $\text{source.match\_date} < \text{target.match\_date}$.
- **Prevention Mechanism:** Strict calendar date inequality: $\text{source.match\_date} < \text{target.match\_date}$. Same-day matches are categorically excluded from historical expectation windows.
- **Automated Test Requirement:**
  ```python
  assert (df_abc['source_match_date'] >= df_abc['target_match_date']).sum() == 0
  ```

### Risk 03: Future Player Statistics / In-Match Form Leakage
- **Failure Mode:** Computing a player's recent batting average, strike rate, or form by including runs scored in the match currently being predicted.
- **Impact:** Critical.
- **Detection Method:** Permute the match outcome and verify that player pre-match features remain identical.
- **Prevention Mechanism:** Stage 5C Track B features (`pre_match_causal_abc_features_v1.pkl.gz`) pre-compute all player metrics prior to the start of the match. Feature extraction in Stage 6 binds solely to Track B records; no dynamic in-match recalculation of prior form is permitted.
- **Automated Test Requirement:**
  ```python
  assert check_feature_target_invariance(feature_extractor, match_id) == True
  ```

### Risk 04: Current-Match and Post-Match ABC Feature Contamination
- **Failure Mode:** Using Strategy 4 final match contributions (`batter_match_contributions_strategy4_v1.pkl.gz`) as input features during live in-play predictions.
- **Impact:** Critical (Direct target leakage).
- **Detection Method:** Assert that no column from the Strategy 4 final contribution dataset exists in the live feature store.
- **Prevention Mechanism:** Strategy 4 match contributions are classified as *evaluation/target artifacts* and are strictly prohibited from entering the feature store. Only Track B (`pre_match_causal_abc_features_v1.pkl.gz`) is exposed to the model pipeline.
- **Automated Test Requirement:**
  ```python
  assert 'contribution_score' not in feature_matrix.columns
  assert 'raw_contribution' not in feature_matrix.columns
  ```

### Risk 05: Match-Result Fields in Feature Matrix
- **Failure Mode:** Feature matrix includes columns containing `win_team_id`, `target_batting_team_win`, `target_home_team_win`, winning margin, or `chase_completion_status`.
- **Impact:** Critical.
- **Detection Method:** Schema validation scan checking for forbidden column substrings (`win`, `result`, `margin`, `chase_completion`).
- **Prevention Mechanism:** Explicit feature whitelist schema (`WinProbabilityFeatureSchema`). Any column not explicitly declared in the schema is dropped prior to model input.
- **Automated Test Requirement:**
  ```python
  forbidden_cols = {'win_team_id', 'win_team_id_raw', 'target_batting_team_win', 'target_home_team_win', 'result', 'winning_margin'}
  assert len(forbidden_cols.intersection(set(feature_matrix.columns))) == 0
  ```

### Risk 06: Target Leakage into State Construction
- **Failure Mode:** Generating live delivery states using `score_after`, `wickets_lost_after`, or in-delivery boundary indicators (`is_boundary_six`).
- **Impact:** Critical.
- **Detection Method:** Assert that only `_before` state features are ingested by the model pipeline.
- **Prevention Mechanism:** State generation strictly uses `score_before`, `wickets_lost_before`, and `legal_balls_completed_before`.
- **Automated Test Requirement:**
  ```python
  assert 'score_after' not in model_feature_list
  assert 'wickets_lost_after' not in model_feature_list
  ```

### Risk 07: In-Sample Pre-Match Anchor Predictions in Live Model Training
- **Failure Mode:** Training the live in-play model on historical deliveries using pre-match probability features ($\hat{p}_{\text{Stage B}}$) generated *in-sample* by a pre-match model that was trained on those very same matches. The pre-match model's training errors/overfitting leak into the live model.
- **Impact:** Critical (Anchor distortion).
- **Detection Method:** Verify that training features for $\hat{p}_{\text{Stage B}}$ are generated strictly via out-of-fold predictions.
- **Prevention Mechanism:** Pre-match probabilities in the training set MUST be generated via **Expanding-Window Out-of-Fold Cross-Validation** across the 2022–2024 training set. The pre-match model never predicts on its own training folds when creating features for the live model.
- **Automated Test Requirement:**
  ```python
  assert pre_match_anchor_generator.is_out_of_fold == True
  ```

### Risk 08: Lifecycle Feature Unavailability (Future State Leakage into Earlier Stages)
- **Failure Mode:** Supplying Stage B or Live features (e.g. `toss_winner`, `target_runs`, `current_run_rate`) into Stage A pre-match predictions, or supplying Innings 2 chase features into Innings 1 defense models.
- **Impact:** Critical.
- **Detection Method:** Assert that Stage A and Innings 1 feature matrices contain zero null-imputed chase or toss columns.
- **Prevention Mechanism:** Strict lifecycle feature gating enforcing the Lifecycle Availability Matrix (`docs/stage_6a_feature_dictionary.md`).
- **Automated Test Requirement:**
  ```python
  assert 'target_runs' not in stage_a_features.columns
  assert 'target_runs' not in innings_1_features.columns
  ```

### Risk 09: DLS & Rain-Affected Match Feature Distortion
- **Failure Mode:** Training on matches where overs were reduced mid-innings causes the model to learn distorted relationships between balls remaining and required runs.
- **Impact:** High.
- **Detection Method:** Assert that all training matches have `is_primary_wp_train_eligible == True`.
- **Prevention Mechanism:** Primary training corpus strictly filters on `is_primary_wp_train_eligible == True` (excluding all 31 DLS matches). DLS matches are quarantined in a dedicated secondary evaluation slice (`is_dls_eval_slice_eligible == True`).
- **Automated Test Requirement:**
  ```python
  assert train_df['has_dls_or_revised_meta'].sum() == 0
  assert train_df['is_primary_wp_train_eligible'].all() == True
  ```

### Risk 10: Super Over Artifact Contamination
- **Failure Mode:** Standard regulation delivery models are trained on Super Over deliveries, or regulation tie outcomes are labeled with post-Super Over winners, introducing hindsight bias.
- **Impact:** High.
- **Detection Method:** Check that `innings <= 2` and `has_super_over_innings == False`.
- **Prevention Mechanism:** Super Over innings (innings 3 and 4) are strictly excluded from the standard delivery dataset (`has_super_over_innings == False`). Regulation tied matches are excluded from standard training.
- **Automated Test Requirement:**
  ```python
  assert (train_df['innings'] > 2).sum() == 0
  assert train_df['is_tied_after_regulation'].sum() == 0
  ```

### Risk 11: Legal Balls Remaining / Over-Limit Deliveries
- **Failure Mode:** Over-limit deliveries (e.g. ball 20.1 in an unpenalized 20-over innings) or negative balls remaining produce undefined run rate calculations ($999.0$ rpo).
- **Impact:** High.
- **Detection Method:** Assert that `legal_balls_remaining_before` is bounded in $[0, 120]$.
- **Prevention Mechanism:** Clamping and validation enforced in Stage 5B (`is_innings_limit_verified == True`, `is_legal_balls_remaining_negative == False`).
- **Automated Test Requirement:**
  ```python
  assert (feature_df['legal_balls_remaining_before'] < 0).sum() == 0
  assert (feature_df['legal_balls_remaining_before'] > 120).sum() == 0
  ```

### Risk 12: Impact Substitute Lineup Desynchronization
- **Failure Mode:** In IPL matches featuring an Impact Player (12 players listed per side), batting or bowling aggregations use 12 players instead of the 11 active on-field players, diluting lineup strength.
- **Impact:** Medium.
- **Detection Method:** Assert that every aggregated lineup vector contains exactly 11 active players.
- **Prevention Mechanism:** Lineup aggregator sorts players by `batting_order` and filters to the top 11 active players. Substituted-off players (`is_impact_off == 1`) are excluded once the Impact Player (`is_impact == 1`) enters.
- **Automated Test Requirement:**
  ```python
  assert all(len(lineup) == 11 for lineup in team_lineups.values())
  ```

### Risk 13: Missing or Incomplete Playing XI Roster States
- **Failure Mode:** In preliminary pre-match stages (Stage A) or unrecorded matches, confirmed XI is unavailable, causing feature extraction to crash on null lineup vectors.
- **Impact:** High.
- **Detection Method:** Check that Stage A feature extraction executes successfully with zero nulls when playing XI is empty.
- **Prevention Mechanism:** Stage A fallback protocol: when playing XI is unavailable, impute team strength using the franchise/national team's trailing 2-season rolling average prior ABC.
- **Automated Test Requirement:**
  ```python
  assert pre_match_features['batting_lineup_mean_abc'].isna().sum() == 0
  ```

### Risk 14: Venue Identifier Aliasing & Low-Sample Grounds
- **Failure Mode:** 31 venues have $< 3$ historical matches, leading to noisy par scores (e.g. 1 match with score 230 falsely sets ground par to 230).
- **Impact:** Medium.
- **Detection Method:** Assert that all computed venue par scores fall within reasonable cricketing bounds ($[120.0, 220.0]$).
- **Prevention Mechanism:** Empirical Bayesian shrinkage: ground par is shrunk toward the competition-category mean $\mu_{\text{comp}}$ when historical ground count $N_{\text{venue}} < 5$.
- **Automated Test Requirement:**
  ```python
  assert all(120.0 <= venue_par <= 220.0 for venue_par in venue_priors.values())
  ```

### Risk 15: Team ID Drift & Franchise Rebranding
- **Failure Mode:** Franchise rebrandings (e.g. Delhi Daredevils to Delhi Capitals, Punjab KXIP to PBKS) create disconnected historical records.
- **Impact:** Low.
- **Detection Method:** Check that all team IDs belong to the validated canonical team catalog.
- **Prevention Mechanism:** Rebrandings across 2022–2026 are unified under canonical team IDs in Stage 4/5B `teams.csv` mappings.
- **Automated Test Requirement:**
  ```python
  assert feature_df['batting_team_id'].isin(VALID_CANONICAL_TEAM_IDS).all()
  ```

### Risk 16: Calibration Set Overfitting & Leakage
- **Failure Mode:** Calibrating probability outputs (via Platt scaling or Isotonic Regression) on the test set or training set.
- **Impact:** Critical.
- **Detection Method:** Verify that the calibrator object records `training_split == 'VAL_2025'`.
- **Prevention Mechanism:** The calibrator is strictly fit on the 2025 Validation Set. The 2026 Test Set is never exposed to the calibrator during training or fitting.
- **Automated Test Requirement:**
  ```python
  assert calibrator.is_fitted == True
  assert calibrator.training_split_id == 'VAL_2025'
  ```

### Risk 17: Temporal Test-Set Snooping / Split Contamination
- **Failure Mode:** Engineering features, tuning hyperparameters, or selecting features based on performance observed on the 2026 Test Set.
- **Impact:** High.
- **Detection Method:** Audit run logs ensuring the test set pipeline is executed only once for final reporting.
- **Prevention Mechanism:** Strict chronological pipeline isolation: all hyperparameters, feature selection thresholds, and calibrators are frozen prior to running final inference on the 2026 Test Set.
- **Automated Test Requirement:**
  ```python
  assert test_set_evaluation_run_count <= 1
  ```

### Risk 18: Unequal Match Weighting Distortion in Model Evaluation
- **Failure Mode:** Long matches with 240+ deliveries dominate overall test metrics, masking poor performance on shorter, high-leverage matches.
- **Impact:** Medium.
- **Detection Method:** Compare unweighted vs equal-match-weighted metrics in validation reports.
- **Prevention Mechanism:** The evaluation engine reports both delivery-weighted and equal-match-weighted metrics, using equal-match weighting as the primary model gating standard.
- **Automated Test Requirement:**
  ```python
  assert 'brier_score_match_weighted' in evaluation_metrics
  ```

### Risk 19: Duplicate Delivery States
- **Failure Mode:** Re-runs or corrupted data ingestion generate duplicate rows with identical `(match_id, innings, innings_ball_num)`.
- **Impact:** Critical.
- **Detection Method:** Assert uniqueness of the compound delivery key across all rows.
- **Prevention Mechanism:** Enforce uniqueness constraints during dataset loading.
- **Automated Test Requirement:**
  ```python
  assert feature_df.duplicated(subset=['match_id', 'innings', 'innings_ball_num']).sum() == 0
  ```
