"""CricImpact Phase 2 — Win Probability Prediction Engine package.

Stage 6B.1: Feature and Target Construction.
Stage 6B.2: Pre-Match Models and Out-of-Fold Anchor Generation.
Stage 6B.3: First-Innings Live Win Probability Model.
Stage 6B.4: Second-Innings Chase Win Probability Model.
Stage 6B.5: Probability Calibration.
"""

from __future__ import annotations

from ml.win_probability.calibration import (
    CalibrationMetrics,
    IdentityCalibrator,
    IsotonicCalibrator,
    PlattCalibrator,
    WinProbabilityCalibrator,
    compute_ece,
    compute_reliability_table,
    evaluate_calibrated_predictions,
)

from ml.win_probability.chase_model import (
    ChaseModel,
    ChasePredictionResult,
    evaluate_chase_predictions,
)
from ml.win_probability.first_innings_model import (
    FirstInningsModel,
    FirstInningsPredictionResult,
    evaluate_first_innings_predictions,
)
from ml.win_probability.pre_match_model import (
    DEFAULT_PRE_MATCH_PROB,
    MIN_TRAIN_MATCHES_OOF,
    PreMatchAnchorGenerator,
    PreMatchModel,
    PreMatchPredictionResult,
    evaluate_pre_match_predictions,
)
from ml.win_probability.schema import (
    ALL_CATALOG_FEATURES,
    INNINGS_1_FEATURES,
    INNINGS_2_FEATURES,
    STAGE_A_FEATURES,
    STAGE_B_FEATURES,
    STAGE_VERSION,
    TARGET_BATTING_WIN,
    TARGET_HOME_WIN,
)
from ml.win_probability.team_strength import TeamStrengthAggregator
from ml.win_probability.venue_priors import VenuePriorsCalculator
from ml.win_probability.feature_extractor import WinProbabilityFeatureExtractor
from ml.win_probability.worm_graph import (
    MatchDefiningMoment,
    WormGraphGenerator,
    WormGraphPoint,
    WormGraphTrajectory,
)

__all__ = [
    "STAGE_VERSION",
    "STAGE_A_FEATURES",
    "STAGE_B_FEATURES",
    "INNINGS_1_FEATURES",
    "INNINGS_2_FEATURES",
    "ALL_CATALOG_FEATURES",
    "TARGET_BATTING_WIN",
    "TARGET_HOME_WIN",
    "DEFAULT_PRE_MATCH_PROB",
    "MIN_TRAIN_MATCHES_OOF",
    "PreMatchModel",
    "PreMatchPredictionResult",
    "PreMatchAnchorGenerator",
    "evaluate_pre_match_predictions",
    "FirstInningsModel",
    "FirstInningsPredictionResult",
    "evaluate_first_innings_predictions",
    "ChaseModel",
    "ChasePredictionResult",
    "evaluate_chase_predictions",
    "PlattCalibrator",
    "IsotonicCalibrator",
    "IdentityCalibrator",
    "WinProbabilityCalibrator",
    "CalibrationMetrics",
    "compute_ece",
    "compute_reliability_table",
    "evaluate_calibrated_predictions",
    "TeamStrengthAggregator",
    "VenuePriorsCalculator",
    "WinProbabilityFeatureExtractor",
    "WormGraphGenerator",
    "WormGraphTrajectory",
    "WormGraphPoint",
    "MatchDefiningMoment",
]



