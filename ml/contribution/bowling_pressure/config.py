"""Stage B7.5 Bowling Pressure Contribution Score (PCS) Configuration."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ml.ingestion.dataset_registry import PROJECT_ROOT
from ml.contribution.bowling_pressure.schema import (
    DEFAULT_PCS_OUTPUT_DIR,
    K_SIGMOID_SLOPE,
    M0_SHRINKAGE_BALLS,
    PRIMARY_ACCELERATION_WINDOW,
    SENSITIVITY_ACCELERATION_WINDOW,
    SIGMA_REF_1ST,
    SIGMA_REF_2ND,
)

DEFAULT_PCS_CONFIG: dict[str, Any] = {
    "parameters": {
        "k_sigmoid_slope": K_SIGMOID_SLOPE,
        "sigma_ref_1st": SIGMA_REF_1ST,
        "sigma_ref_2nd": SIGMA_REF_2ND,
        "m0_shrinkage_balls": M0_SHRINKAGE_BALLS,
        "primary_acc_window": PRIMARY_ACCELERATION_WINDOW,
        "sensitivity_acc_window": SENSITIVITY_ACCELERATION_WINDOW,
        "w_striker_threat": 0.60,
        "w_non_striker_threat": 0.40,
        "dci_cluster_weight": 0.35,
        "dci_starve_weight": 0.25,
        "alpha_resource_elasticity": 0.55,
    },
    "paths": {
        "match_states_path": str(PROJECT_ROOT / "data" / "processed" / "match_states" / "match_states_standard_t20_v1.pkl.gz"),
        "bcm_deliveries_path": str(PROJECT_ROOT / "data" / "processed" / "contributions" / "bowling" / "bowling_delivery_contributions_v1.pkl.gz"),
        "bcm_spells_path": str(PROJECT_ROOT / "data" / "processed" / "contributions" / "bowling" / "bowling_match_spells_v1.pkl.gz"),
        "output_dir": str(DEFAULT_PCS_OUTPUT_DIR),
    },
}


def load_pcs_config(custom_overrides: dict[str, Any] | None = None) -> dict[str, Any]:
    """Return immutable base config updated with optional runtime overrides."""
    cfg = DEFAULT_PCS_CONFIG.copy()
    if custom_overrides:
        if "parameters" in custom_overrides:
            cfg["parameters"] = {**cfg["parameters"], **custom_overrides["parameters"]}
        if "paths" in custom_overrides:
            cfg["paths"] = {**cfg["paths"], **custom_overrides["paths"]}
    return cfg
