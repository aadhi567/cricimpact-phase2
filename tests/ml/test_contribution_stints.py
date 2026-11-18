"""Unit tests for Stage 5C stint and roster reconstruction."""

import pandas as pd
import numpy as np
import pytest

from ml.contribution.stint_builder import build_batter_stints_and_roster
from ml.contribution.schema import (
    EXPECTED_BATTER_MATCH_RECORDS,
    EXPECTED_STANDARD_T20_MATCHES,
)
from ml.ingestion.dataset_registry import (
    DATASET_SPECS,
    DEFAULT_RAW_DIR,
    PROJECT_ROOT,
)


@pytest.fixture(scope="module")
def staged_data():
    stage5b_path = (
        PROJECT_ROOT
        / "data"
        / "processed"
        / "match_states"
        / "match_states_standard_t20_v1.pkl.gz"
    )
    df = pd.read_pickle(stage5b_path)
    p11 = pd.read_csv(DEFAULT_RAW_DIR / DATASET_SPECS["playing_eleven"].filename)
    stints_df, batter_match_df = build_batter_stints_and_roster(df, p11)
    return stints_df, batter_match_df, df


def test_stint_and_roster_reconciliation(staged_data):
    stints_df, batter_match_df, _ = staged_data
    assert len(batter_match_df) == EXPECTED_BATTER_MATCH_RECORDS
    assert batter_match_df["match_id"].nunique() == EXPECTED_STANDARD_T20_MATCHES
    assert batter_match_df.duplicated(subset=["match_id", "innings", "player_id"]).sum() == 0


def test_dnb_preservation_and_impact_subs(staged_data):
    _, batter_match_df, _ = staged_data
    dnb_rows = batter_match_df[batter_match_df["is_dnb"]]
    assert len(dnb_rows) >= 5073
    assert (dnb_rows["actual_runs"] == 0).all()
    assert (dnb_rows["balls_faced"] == 0).all()

    # Check Impact Subs DNB
    impact_dnb = batter_match_df[batter_match_df["is_impact"] & batter_match_df["is_dnb"]]
    assert len(impact_dnb) >= 219


def test_zero_ball_dismissals_vs_non_striker_dnb(staged_data):
    stints_df, batter_match_df, _ = staged_data
    # 0 balls faced and dismissed must have is_out=True and is_dnb=False
    zero_ball_out = batter_match_df[(batter_match_df["balls_faced"] == 0) & (batter_match_df["is_out"])]
    assert len(zero_ball_out) > 0
    assert (~zero_ball_out["is_dnb"]).all()

    # 0 balls faced and not out must have is_dnb=True
    zero_ball_not_out = batter_match_df[(batter_match_df["balls_faced"] == 0) & (~batter_match_df["is_out"])]
    assert (zero_ball_not_out["is_dnb"]).all()


def test_special_cricket_edge_cases(staged_data):
    stints_df, batter_match_df, _ = staged_data
    # Match 40709 2.19.5 Retire Out
    m40709 = batter_match_df[batter_match_df["match_id"] == 40709]
    assert len(m40709) == 24
    assert (m40709["has_unresolved_dismissal_in_match"]).sum() == 1
    # Both crease batters remain not out
    tilak = m40709[m40709["player_id"] == 7897]
    assert len(tilak) == 1
    assert tilak["dismissal_status"].iloc[0] == "not out"

    # Retired hurt stints count
    rh_stints = stints_df[stints_df["is_retired_hurt"]]
    assert len(rh_stints) == 11
    assert (rh_stints["dismissal_status"] == "not out").all()

    # UAE split players in 37087, 37092, 37095
    uae_rows = batter_match_df[batter_match_df["is_roster_missing_uae_split"]]
    assert len(uae_rows) == 6
    assert set(uae_rows["match_id"].unique()) == {37087, 37092, 37095}
    assert set(uae_rows["player_id"].unique()) == {36153, 39444}


def test_balls_faced_and_boundary_counts(staged_data):
    stints_df, batter_match_df, df_states = staged_data
    # Compare balls_faced against ~is_wide across all scored appearances
    total_stint_bf = stints_df["balls_faced"].sum()
    # Total ~is_wide deliveries in primary dataset
    total_non_wide_deliveries = (~df_states["is_wide"]).sum()
    assert total_stint_bf == total_non_wide_deliveries

    # Boundary counts
    total_stint_fours = stints_df["fours"].sum()
    total_raw_fours = (df_states["batter_runs"] == 4).sum()
    assert total_stint_fours == total_raw_fours

    total_stint_sixes = stints_df["sixes"].sum()
    total_raw_sixes = (df_states["batter_runs"] == 6).sum()
    assert total_stint_sixes == total_raw_sixes
