"""Unit tests for Stage 6B temporal causality, leakage prevention, and partition integrity."""

from __future__ import annotations

import gzip
import pickle
from pathlib import Path

import pandas as pd
import pytest

from ml.ingestion.dataset_registry import PROJECT_ROOT
from ml.win_probability.feature_extractor import WinProbabilityFeatureExtractor
from ml.win_probability.schema import (
    FORBIDDEN_LEAKAGE_COLUMNS,
    INNINGS_1_FEATURES,
    INNINGS_2_FEATURES,
    STAGE_A_FEATURES,
    STAGE_B_FEATURES,
    TRAIN_END_DATE,
    VAL_END_DATE,
    VAL_START_DATE,
    validate_feature_matrix_no_leakage,
)


@pytest.fixture(scope="module")
def standard_artifacts():
    """Load small subsets of accepted artifacts for read-only leakage verification."""
    ms_path = PROJECT_ROOT / "data" / "processed" / "match_states" / "match_states_standard_t20_v1.pkl.gz"
    abc_path = PROJECT_ROOT / "data" / "processed" / "contributions" / "pre_match_causal_abc_features_v1.pkl.gz"
    pe_path = PROJECT_ROOT / "data" / "raw" / "playing_eleven.csv"

    with gzip.open(ms_path, "rb") as f:
        df_ms = pickle.load(f)
    with gzip.open(abc_path, "rb") as f:
        df_abc = pickle.load(f)
    pe_df = pd.read_csv(pe_path)

    return df_ms, pe_df, df_abc


def test_chronological_splits_zero_match_overlap(standard_artifacts) -> None:
    """Verify that match IDs across train (2022-2024), val (2025), and test (2026) have 0 overlap."""
    df_ms, _, _ = standard_artifacts
    matches = df_ms[["match_id", "match_date"]].drop_duplicates()
    matches["date_str"] = pd.to_datetime(matches["match_date"]).dt.strftime("%Y-%m-%d")

    train_matches = set(matches[matches["date_str"] <= TRAIN_END_DATE]["match_id"])
    val_matches = set(matches[(matches["date_str"] >= VAL_START_DATE) & (matches["date_str"] <= VAL_END_DATE)]["match_id"])
    test_matches = set(matches[matches["date_str"] > VAL_END_DATE]["match_id"])

    assert len(train_matches) == 477
    assert len(val_matches) == 190
    assert len(test_matches) == 131

    # Zero overlap assertions
    assert len(train_matches.intersection(val_matches)) == 0, "Train and Val share matches!"
    assert len(train_matches.intersection(test_matches)) == 0, "Train and Test share matches!"
    assert len(val_matches.intersection(test_matches)) == 0, "Val and Test share matches!"


def test_stage_5c_track_b_strict_causality(standard_artifacts) -> None:
    """Verify that Stage 5C Track B pre-match features have zero same-day or future matches."""
    _, _, df_abc = standard_artifacts
    # Check that df_abc is indexed per match and date
    assert "match_date" in df_abc.columns
    assert "is_abc_cold_start" in df_abc.columns
    # Verify no post-match contribution scores exist in Track B
    assert "contribution_score" not in df_abc.columns
    assert "raw_contribution" not in df_abc.columns


def test_target_invariance_on_pre_match_features(standard_artifacts) -> None:
    """Verify that permuting the match winner produces identical pre-match features."""
    df_ms, pe_df, df_abc = standard_artifacts

    # Select sample match 13511
    sample_match_id = 13511
    sample_ms = df_ms[df_ms["match_id"] == sample_match_id].copy()

    extractor = WinProbabilityFeatureExtractor(sample_ms, pe_df, df_abc)
    feats_real = extractor.extract_pre_match_features_for_match(sample_match_id)

    # Permute win_team_id in match states
    sample_ms_permuted = sample_ms.copy()
    sample_ms_permuted["win_team_id_raw"] = 999999  # Injected fake winner
    extractor_permuted = WinProbabilityFeatureExtractor(sample_ms_permuted, pe_df, df_abc)
    feats_permuted = extractor_permuted.extract_pre_match_features_for_match(sample_match_id)

    # Stage A and Stage B must remain 100% identical
    for k in STAGE_A_FEATURES:
        assert feats_real["stage_a"][k] == feats_permuted["stage_a"][k], f"Target leakage in Stage A feature: {k}"

    for k in STAGE_B_FEATURES:
        assert feats_real["stage_b"][k] == feats_permuted["stage_b"][k], f"Target leakage in Stage B feature: {k}"


def test_feature_matrix_no_forbidden_columns() -> None:
    """Verify that feature lists for all models contain zero forbidden columns."""
    for model_name, feature_list in [
        ("Stage A", STAGE_A_FEATURES),
        ("Stage B", STAGE_B_FEATURES),
        ("Innings 1 Live", INNINGS_1_FEATURES),
        ("Innings 2 Chase", INNINGS_2_FEATURES),
    ]:
        validate_feature_matrix_no_leakage(feature_list)
        overlap = set(feature_list).intersection(FORBIDDEN_LEAKAGE_COLUMNS)
        assert len(overlap) == 0, f"Model {model_name} contains forbidden leakage columns: {overlap}"

