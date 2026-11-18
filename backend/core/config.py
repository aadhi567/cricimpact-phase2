"""Application configuration and dataset path settings for CricImpact Phase 2."""

from pathlib import Path
from typing import List
from pydantic import BaseModel, Field


class Settings(BaseModel):
    """Configuration settings for the CricImpact Phase 2 API server."""

    # Project metadata
    PROJECT_NAME: str = "CricImpact Phase 2 - Bowling Analytics API"
    VERSION: str = "1.0.0"
    API_V1_PREFIX: str = "/api"
    BOWLING_PREFIX: str = "/api/bowling"
    DESCRIPTION: str = (
        "Production read-only REST API exposing the Stage B4 Bowling Contribution Model (BCM) "
        "outputs, including Bowling Contribution Score (BCS), Bowler Win Probability Added (bWPA), "
        "Expected Runs Prevented (ERP), Wicket Quality Multipliers (WQM), and delivery-level analysis."
    )

    # Server settings
    HOST: str = "127.0.0.1"
    PORT: int = 8000
    CORS_ORIGINS: List[str] = ["*"]

    # Base Paths
    BASE_DIR: Path = Path(__file__).resolve().parent.parent.parent
    DATA_DIR: Path = BASE_DIR / "data"
    PROCESSED_BOWLING_DIR: Path = DATA_DIR / "processed" / "contributions" / "bowling"
    PROCESSED_PCS_DIR: Path = DATA_DIR / "processed" / "contributions" / "bowling_pressure"
    RAW_DIR: Path = DATA_DIR / "raw"

    # Dataset Files
    MANIFEST_FILE: Path = PROCESSED_BOWLING_DIR / "bowling_pipeline_manifest_v1.json"
    CAREER_FILE: Path = PROCESSED_BOWLING_DIR / "bowling_career_summary_v1.pkl.gz"
    SEASON_FILE: Path = PROCESSED_BOWLING_DIR / "bowling_season_summary_v1.pkl.gz"
    SPELLS_FILE: Path = PROCESSED_BOWLING_DIR / "bowling_match_spells_v1.pkl.gz"
    DELIVERIES_FILE: Path = PROCESSED_BOWLING_DIR / "bowling_delivery_contributions_v1.pkl.gz"
    PLAYER_MAPPING_FILE: Path = RAW_DIR / "competition_team_player_mapping.csv"

    # PCS Production Files
    PCS_MANIFEST_FILE: Path = PROCESSED_PCS_DIR / "pcs_pipeline_manifest_v1.json"
    PCS_VALIDATION_FILE: Path = PROCESSED_PCS_DIR / "pcs_validation_metrics_v1.json"
    PCS_CAREER_FILE: Path = PROCESSED_PCS_DIR / "pcs_career_summary_v1.pkl.gz"
    PCS_SEASON_FILE: Path = PROCESSED_PCS_DIR / "pcs_season_summary_v1.pkl.gz"
    PCS_SPELLS_FILE: Path = PROCESSED_PCS_DIR / "pcs_match_spells_v1.pkl.gz"
    PCS_DELIVERIES_FILE: Path = PROCESSED_PCS_DIR / "pcs_delivery_contributions_v1.pkl.gz"
    PCS_PREFIX: str = "/api/pcs"

    # Batting HPP Validated Production Artifacts (Read-Only)
    WORM_GRAPH_DIR: Path = BASE_DIR / "docs" / "worm_graph"
    BATTING_LEADERBOARDS_FILE: Path = WORM_GRAPH_DIR / "hpp_leaderboards.json"
    BATTING_MATCH_DATA_FILE: Path = WORM_GRAPH_DIR / "hpp_match_data.json"
    BATTING_MATCH_INDEX_FILE: Path = WORM_GRAPH_DIR / "match_index.json"
    BATTING_TRAJECTORIES_DIR: Path = WORM_GRAPH_DIR / "trajectories"
    BATTING_PREFIX: str = "/api/batting"

    # PRI-2 Pressure Reliability Index Production Artifacts (Read-Only)
    PROCESSED_PRI_DIR: Path = DATA_DIR / "processed" / "contributions" / "pressure_reliability"
    PRI_MANIFEST_FILE: Path = PROCESSED_PRI_DIR / "pri_pipeline_manifest_v1.json"
    PRI_VALIDATION_FILE: Path = PROCESSED_PRI_DIR / "pri_validation_metrics_v1.json"
    PRI_BATTING_INNINGS_FILE: Path = PROCESSED_PRI_DIR / "batting_pri_pressure_innings_v1.pkl.gz"
    PRI_BATTING_CAREER_FILE: Path = PROCESSED_PRI_DIR / "batting_pri_career_v1.pkl.gz"
    PRI_BATTING_SEASON_FILE: Path = PROCESSED_PRI_DIR / "batting_pri_season_v1.pkl.gz"
    PRI_BATTING_TOURNAMENT_FILE: Path = PROCESSED_PRI_DIR / "batting_pri_tournament_v1.pkl.gz"
    PRI_BOWLING_SPELLS_FILE: Path = PROCESSED_PRI_DIR / "bowling_pri_pressure_spells_v1.pkl.gz"
    PRI_BOWLING_CAREER_FILE: Path = PROCESSED_PRI_DIR / "bowling_pri_career_v1.pkl.gz"
    PRI_BOWLING_SEASON_FILE: Path = PROCESSED_PRI_DIR / "bowling_pri_season_v1.pkl.gz"
    PRI_BOWLING_TOURNAMENT_FILE: Path = PROCESSED_PRI_DIR / "bowling_pri_tournament_v1.pkl.gz"
    PRI_PREFIX: str = "/api/pri"

    # Expected Production Counts
    EXPECTED_MATCHES: int = 798
    EXPECTED_DELIVERIES: int = 190575
    EXPECTED_SPELLS: int = 9482
    EXPECTED_CAREER_BOWLERS: int = 638
    EXPECTED_SEASON_RECORDS: int = 1587

    # Query Defaults
    DEFAULT_MIN_BALLS: int = 60
    DEFAULT_PAGE_SIZE: int = 20
    MAX_PAGE_SIZE: int = 100
    MAX_COMPARISON_PLAYERS: int = 5
    MIN_COMPARISON_PLAYERS: int = 2


settings = Settings()
