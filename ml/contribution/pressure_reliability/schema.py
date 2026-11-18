"""Stage PRI-2: Pressure Reliability Index (PRI) Schema & Frozen Governance Constants.

Strict invariants:
- NO SHRINKAGE applied anywhere in PRI.
- NO COMPOSITE SCORE combining Reliability Rate and Contribution Quality.
- Read-only consumption of existing HPP/HPC and PCS production artifacts.
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

from ml.ingestion.dataset_registry import PROJECT_ROOT

PRI_STAGE_VERSION: Final[str] = "Stage PRI-2 v1.0"
PRI_METHODOLOGY_ID: Final[str] = "PRI_DUAL_AXIS_UNSHRUNK_T10_EXO2_V1"

# Mandatory Anti-Shrinkage Invariant
SHRINKAGE_APPLIED: Final[bool] = False
COMPOSITE_SCORE_APPLIED: Final[bool] = False

# Approved Batting Pressure Opportunity Definition (T10)
BATTING_T10_MEAN_P_THRESHOLD: Final[float] = 40.0
BATTING_T10_PEAK_P_THRESHOLD: Final[float] = 60.0
BATTING_SENSITIVITY_ENTRY_P_THRESHOLD: Final[float] = 40.0

# Approved Bowling Pressure Opportunity Definition (EXO_2) & Sensitivity (EXO_5)
BOWLING_EXO2_MAX_ENTRY_PTI_THRESHOLD: Final[float] = 35.0
BOWLING_EXO2_MIN_LEGAL_BALLS: Final[int] = 12
BOWLING_EXO5_MEAN_ENTRY_PTI_THRESHOLD: Final[float] = 25.0
BOWLING_EXO5_MIN_LEGAL_BALLS: Final[int] = 12

# Diagnostic Dangerous Partnership Threshold (from PCS PTI)
BOWLING_STAND_BREAK_PTI_THRESHOLD: Final[float] = 25.0

# Exact Polarity Anchors (Neutral is NEVER counted as positive)
HPC_NEUTRAL_ANCHOR: Final[float] = 0.0
PCS_NEUTRAL_ANCHOR: Final[float] = 50.0

# Statistical Confidence Interval Z-scores (Wilson Binomial Interval — Informational Only)
WILSON_Z_95: Final[float] = 1.959963984540054
WILSON_Z_90: Final[float] = 1.6448536269514722

# Chronological Validation Partition Years (Strict Temporal Separation)
TRAIN_MAX_YEAR: Final[int] = 2024
VAL_YEAR: Final[int] = 2025
HOLDOUT_TEST_MIN_YEAR: Final[int] = 2026

# Authoritative B8 Pakistan Visibility Policy Team Identifiers
PAKISTAN_TEAM_NAMES: Final[frozenset[str]] = frozenset({"Pakistan", "Pakistan A"})

# Read-Only Source Artifact Paths
WORM_GRAPH_DIR: Final[Path] = PROJECT_ROOT / "docs" / "worm_graph"
HPP_MATCH_DATA_PATH: Final[Path] = WORM_GRAPH_DIR / "hpp_match_data.json"
HPP_LEADERBOARDS_PATH: Final[Path] = WORM_GRAPH_DIR / "hpp_leaderboards.json"
MATCH_INDEX_PATH: Final[Path] = WORM_GRAPH_DIR / "match_index.json"
TRAJECTORIES_DIR: Final[Path] = WORM_GRAPH_DIR / "trajectories"

MATCH_STATES_PATH: Final[Path] = (
    PROJECT_ROOT / "data" / "processed" / "match_states" / "match_states_standard_t20_v1.pkl.gz"
)
PCS_DIR: Final[Path] = PROJECT_ROOT / "data" / "processed" / "contributions" / "bowling_pressure"
PCS_DELIVERIES_PATH: Final[Path] = PCS_DIR / "pcs_delivery_contributions_v1.pkl.gz"
PCS_SPELLS_PATH: Final[Path] = PCS_DIR / "pcs_match_spells_v1.pkl.gz"
PCS_SEASON_PATH: Final[Path] = PCS_DIR / "pcs_season_summary_v1.pkl.gz"
PCS_CAREER_PATH: Final[Path] = PCS_DIR / "pcs_career_summary_v1.pkl.gz"
PCS_MANIFEST_PATH: Final[Path] = PCS_DIR / "pcs_pipeline_manifest_v1.json"

RAW_DIR: Final[Path] = PROJECT_ROOT / "data" / "raw"
MATCHES_CSV_PATH: Final[Path] = RAW_DIR / "matches.csv"
COMPETITIONS_CSV_PATH: Final[Path] = RAW_DIR / "competitions.csv"
PLAYER_MAPPING_CSV_PATH: Final[Path] = RAW_DIR / "competition_team_player_mapping.csv"

# Separate Independent PRI Output Directory
DEFAULT_PRI_OUTPUT_DIR: Final[Path] = (
    PROJECT_ROOT / "data" / "processed" / "contributions" / "pressure_reliability"
)
