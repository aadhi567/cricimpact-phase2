"""Stage B7.5 Master Production Pipeline Runner for Bowling Pressure Contribution Score (PCS).

Executes full delivery-level, spell-level, season-level, and career-level PCS generation,
offline testbench validation, reconciliation analytics, and artifact serialization.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import os
from pathlib import Path
import sys
import time
from typing import Any

# Ensure workspace root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import numpy as np
import pandas as pd

from ml.contribution.bowling_pressure.config import load_pcs_config
from ml.contribution.bowling_pressure.pcs_career_aggregator import PCSCareerAggregator
from ml.contribution.bowling_pressure.pcs_delivery_engine import PCSDeliveryEngine
from ml.contribution.bowling_pressure.pcs_season_aggregator import PCSSeasonAggregator
from ml.contribution.bowling_pressure.pcs_spell_aggregator import PCSSpellAggregator
from ml.contribution.bowling_pressure.pcs_validation import PCSValidationSuite


# 14 Protected Assets with SHA-256 baselines
PROTECTED_ASSETS = {
    "data/processed/calibration/calibration_manifest_v1.json": "8b11483723f5bf0f02a5df2bdf346bb4f4d585ba4a249e29a2babc16d5e2bcd1",
    "data/processed/calibration/val_2025_calibrated_predictions_v1.pkl.gz": "2b0700be46316a4b3c14c80167e6af58b1ccdb314fc1786a2bff7f8335d82bb9",
    "data/processed/calibration/test_2026_calibrated_predictions_v1.pkl.gz": "a627c11e4359346e6ae032707730d9fdf63d3f4b99d2d744ac019b3ac86eb46d",
    "data/processed/calibration/test_2026_evaluation_manifest_v1.json": "d0d62de97bd9ae2c184f66e289c86e6909b75c725109e7eb61b62fff7231d029",
    "data/processed/match_states/match_states_standard_t20_v1.pkl.gz": "815a8e1ff4e428e85b942caeaaea9e45af1bf159eeb794c7c425390d476cb871",
    "data/processed/contributions/bowling/bowling_pipeline_manifest_v1.json": "02b1c063ba77453856d732b135159806e5f6707f247d2752ea0a09b88742fd0c",
    "data/processed/contributions/bowling/bowling_career_summary_v1.pkl.gz": "fe02e39c31aa7a49ef333882c550297a5903ebcd619ff7c0b746e689d019233a",
    "data/processed/contributions/bowling/bowling_season_summary_v1.pkl.gz": "46fce3ce10b5690b4d3b2bed4245d5ed088dd9de6f1b2d3a306d053f6bcea96a",
    "data/processed/contributions/bowling/bowling_match_spells_v1.pkl.gz": "09c03ec38fc5d4d03dac8360f1631434a6cdc2d85010dd53e6432f0803b6328d",
    "data/processed/contributions/bowling/bowling_delivery_contributions_v1.pkl.gz": "14e05e69700c9d909887239aecb936b78413707aa95077d619f1388a06924cb3",
    "data/processed/contributions/hpp_stint_evaluations_v1.pkl.gz": "a83e44b9eb8337b32ae99cf7960e5bd8171940137f33b3546e8a1465cfb0fcd5",
    "docs/worm_graph/hpp_dashboard.html": "5b32bca5a591d4a7e75e3420dedde4fb53f7c96ed814ba7907f3c9b777017408",
    "docs/worm_graph/worm_graph.html": "4343bf5171e7ecd6db76e669aa90522f596059f797c93277210ce284caf5f719",
    "docs/worm_graph/hpp_explorer.html": "aef374b9aabedb171810215e5a1582cfc57d7f7ad10b7e5fb476e1a7fd15e8ba",
}


def compute_sha256(filepath: str | Path) -> str:
    """Compute standard SHA-256 hash of a file."""
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def verify_protected_assets() -> bool:
    """Verify all 14 protected assets match their baseline hashes."""
    for rel_path, expected_hash in PROTECTED_ASSETS.items():
        if not os.path.exists(rel_path):
            raise FileNotFoundError(f"Missing protected asset: {rel_path}")
        curr_hash = compute_sha256(rel_path)
        if curr_hash != expected_hash:
            raise ValueError(
                f"INTEGRITY MISMATCH on protected asset {rel_path}!\n"
                f"Expected: {expected_hash}\nActual:   {curr_hash}"
            )
    return True


def run_pipeline() -> dict[str, Any]:
    """Execute master PCS pipeline end-to-end."""
    print("=" * 70)
    print("CRICIMPACT PHASE 2 — STAGE B7.5 PRODUCTION PCS PIPELINE RUNNER")
    print("=" * 70)

    # 1. Pre-execution hash check
    print("\n[Step 1/8] Verifying pre-execution protected asset integrity...")
    verify_protected_assets()
    print(">>> 14/14 Protected assets verified 100% matched baseline.")

    config = load_pcs_config()
    out_dir = Path("data/processed/contributions/bowling_pressure")
    out_dir.mkdir(parents=True, exist_ok=True)

    # 2. Load input datasets (Read-only)
    print("\n[Step 2/8] Loading inputs (read-only)...")
    t0 = time.time()
    bcm_path = "data/processed/contributions/bowling/bowling_delivery_contributions_v1.pkl.gz"
    df_raw = pd.read_pickle(bcm_path)
    print(f">>> Loaded {len(df_raw):,} deliveries from BCM in {time.time() - t0:.2f}s")

    # 3. Delivery-level PCS evaluation
    print("\n[Step 3/8] Evaluating delivery-level pressure features...")
    t1 = time.time()
    delivery_engine = PCSDeliveryEngine(config)
    df_deliveries = delivery_engine.evaluate_deliveries(df_raw)
    deliv_time = time.time() - t1
    print(f">>> Evaluated {len(df_deliveries):,} deliveries in {deliv_time:.2f}s")

    # 4. Spell-level aggregation
    print("\n[Step 4/8] Aggregating match spells...")
    t2 = time.time()
    spell_aggregator = PCSSpellAggregator(config)
    df_spells = spell_aggregator.aggregate_spells(df_deliveries)
    spell_time = time.time() - t2
    print(f">>> Aggregated {len(df_spells):,} match spells in {spell_time:.2f}s")

    # 5. Season-level aggregation
    print("\n[Step 5/8] Aggregating season summaries (with EB shrinkage M0=48)...")
    t3 = time.time()
    season_aggregator = PCSSeasonAggregator(config)
    df_seasons = season_aggregator.aggregate_seasons(df_spells)
    season_time = time.time() - t3
    print(f">>> Aggregated {len(df_seasons):,} season records in {season_time:.2f}s")

    # 6. Career-level aggregation
    print("\n[Step 6/8] Aggregating career summaries (with EB shrinkage M0=48)...")
    t4 = time.time()
    career_aggregator = PCSCareerAggregator(config)
    df_career = career_aggregator.aggregate_career(df_spells)
    career_time = time.time() - t4
    print(f">>> Aggregated {len(df_career):,} career records in {career_time:.2f}s")

    # 7. Run validation testbench (20 scenarios)
    print("\n[Step 7/8] Running comprehensive validation testbench (20 scenarios)...")
    val_suite = PCSValidationSuite(config)
    val_results = val_suite.run_all_tests()
    val_path = out_dir / "pcs_validation_metrics_v1.json"
    val_suite.save_validation_results(val_path)
    print(f">>> Validation passed: {val_results['all_passed']} ({val_results['passed_count']}/{val_results['total_scenarios']})")

    # 8. Serialization & Manifest Generation
    print("\n[Step 8/8] Serializing artifacts and generating pipeline manifest...")
    
    # Save deliveries
    deliv_out_path = out_dir / "pcs_delivery_contributions_v1.pkl.gz"
    df_deliveries.to_pickle(deliv_out_path, compression="gzip")
    deliv_hash = compute_sha256(deliv_out_path)
    print(f"Saved: {deliv_out_path} ({os.path.getsize(deliv_out_path) / (1024*1024):.2f} MB, SHA-256: {deliv_hash[:16]}...)")

    # Save spells
    spells_out_path = out_dir / "pcs_match_spells_v1.pkl.gz"
    df_spells.to_pickle(spells_out_path, compression="gzip")
    spells_hash = compute_sha256(spells_out_path)
    print(f"Saved: {spells_out_path} ({os.path.getsize(spells_out_path) / 1024:.2f} KB, SHA-256: {spells_hash[:16]}...)")

    # Save seasons
    seasons_out_path = out_dir / "pcs_season_summary_v1.pkl.gz"
    df_seasons.to_pickle(seasons_out_path, compression="gzip")
    seasons_hash = compute_sha256(seasons_out_path)
    print(f"Saved: {seasons_out_path} ({os.path.getsize(seasons_out_path) / 1024:.2f} KB, SHA-256: {seasons_hash[:16]}...)")

    # Save career
    career_out_path = out_dir / "pcs_career_summary_v1.pkl.gz"
    df_career.to_pickle(career_out_path, compression="gzip")
    career_hash = compute_sha256(career_out_path)
    print(f"Saved: {career_out_path} ({os.path.getsize(career_out_path) / 1024:.2f} KB, SHA-256: {career_hash[:16]}...)")

    val_hash = compute_sha256(val_path)

    # Compute correlation and VIF metrics with existing BCM outputs
    print("\nComputing statistical reconciliation and correlation matrix...")
    corr_df = df_deliveries[["rpe", "pcs_delivery", "bcs", "bwpa", "erp", "WQM"]].dropna().corr()
    print("Correlation matrix (Delivery Level):")
    print(corr_df.round(4))

    # Spell-level correlations
    # Merge spell BCS/bWPA from existing bowling match spells
    bcm_spells_path = "data/processed/contributions/bowling/bowling_match_spells_v1.pkl.gz"
    bcm_spells = pd.read_pickle(bcm_spells_path)
    merged_spells = pd.merge(
        df_spells,
        bcm_spells[["match_id", "innings", "bowler_id", "total_bcs", "total_bwpa", "total_erp", "mean_wqm"]],
        on=["match_id", "innings", "bowler_id"],
        how="inner",
    )
    spell_corr = merged_spells[["total_rpe", "pcs_spell", "total_bcs", "total_bwpa", "total_erp", "mean_wqm"]].corr()
    print("\nCorrelation matrix (Spell Level):")
    print(spell_corr.round(4))

    # Variance Inflation Factor (VIF)
    # Checking multicollinearity of PCS alongside BCS and bWPA in predicting win/impact
    from sklearn.linear_model import LinearRegression
    clean_merged = merged_spells[["total_bcs", "total_bwpa", "pcs_spell"]].dropna()
    X = clean_merged[["total_bcs", "total_bwpa"]].values
    y = clean_merged["pcs_spell"].values
    reg = LinearRegression().fit(X, y)
    r2 = reg.score(X, y)
    vif_pcs = 1.0 / (1.0 - r2) if r2 < 1.0 else np.inf
    print(f"\nPCS Multicollinearity / VIF vs BCS & bWPA: R2 = {r2:.4f}, VIF = {vif_pcs:.3f} (< 5.0 indicates zero collinearity)")

    # Partition breakdowns
    seasons_str = df_deliveries["season"].astype(str)
    train_mask = seasons_str.isin(["2022", "2023", "2024"])
    val_mask = seasons_str == "2025"
    test_mask = seasons_str == "2026"

    partition_stats = {
        "train_2022_2024": {
            "deliveries": int(train_mask.sum()),
            "pcs_mean": float(df_deliveries.loc[train_mask, "pcs_delivery"].mean()),
            "pcs_std": float(df_deliveries.loc[train_mask, "pcs_delivery"].std()),
            "rpe_mean": float(df_deliveries.loc[train_mask, "rpe"].mean()),
            "rpe_std": float(df_deliveries.loc[train_mask, "rpe"].std()),
        },
        "val_2025": {
            "deliveries": int(val_mask.sum()),
            "pcs_mean": float(df_deliveries.loc[val_mask, "pcs_delivery"].mean()),
            "pcs_std": float(df_deliveries.loc[val_mask, "pcs_delivery"].std()),
            "rpe_mean": float(df_deliveries.loc[val_mask, "rpe"].mean()),
            "rpe_std": float(df_deliveries.loc[val_mask, "rpe"].std()),
        },
        "test_2026_holdout": {
            "deliveries": int(test_mask.sum()),
            "pcs_mean": float(df_deliveries.loc[test_mask, "pcs_delivery"].mean()),
            "pcs_std": float(df_deliveries.loc[test_mask, "pcs_delivery"].std()),
            "rpe_mean": float(df_deliveries.loc[test_mask, "rpe"].mean()),
            "rpe_std": float(df_deliveries.loc[test_mask, "rpe"].std()),
        },
    }

    # Summary distributions
    def _dist_summary(series: pd.Series) -> dict[str, float]:
        clean = series.dropna()
        q25, q50, q75 = np.percentile(clean, [25, 50, 75])
        return {
            "count": int(len(clean)),
            "mean": round(float(clean.mean()), 3),
            "std": round(float(clean.std()), 3),
            "min": round(float(clean.min()), 3),
            "q25": round(float(q25), 3),
            "median": round(float(q50), 3),
            "q75": round(float(q75), 3),
            "max": round(float(clean.max()), 3),
            "iqr": round(float(q75 - q25), 3),
        }

    distributions = {
        "delivery_rpe": _dist_summary(df_deliveries["rpe"]),
        "delivery_pcs": _dist_summary(df_deliveries["pcs_delivery"]),
        "spell_rpe": _dist_summary(df_spells["total_rpe"]),
        "spell_pcs": _dist_summary(df_spells["pcs_spell"]),
        "season_pcs_raw": _dist_summary(df_seasons["pcs_season_raw"]),
        "season_pcs_shrunk": _dist_summary(df_seasons["pcs_season_shrunk"]),
        "career_pcs_raw": _dist_summary(df_career["pcs_career_raw"]),
        "career_pcs_shrunk": _dist_summary(df_career["pcs_career_shrunk"]),
    }

    manifest = {
        "pipeline_name": "CricImpact_Phase2_BPCM_PCS",
        "stage": "B7.5",
        "version": "1.0.0",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "input_records": {
            "total_deliveries": len(df_deliveries),
            "total_spells": len(df_spells),
            "total_seasons": len(df_seasons),
            "total_career_bowlers": len(df_career),
        },
        "partitions": partition_stats,
        "distributions": distributions,
        "correlations": {
            "delivery_level": corr_df.to_dict(),
            "spell_level": spell_corr.to_dict(),
            "vif_pcs_vs_bcs_bwpa": round(float(vif_pcs), 4),
        },
        "artifacts": {
            "pcs_delivery_contributions": {
                "path": str(deliv_out_path).replace("\\", "/"),
                "sha256": deliv_hash,
                "records": len(df_deliveries),
            },
            "pcs_match_spells": {
                "path": str(spells_out_path).replace("\\", "/"),
                "sha256": spells_hash,
                "records": len(df_spells),
            },
            "pcs_season_summary": {
                "path": str(seasons_out_path).replace("\\", "/"),
                "sha256": seasons_hash,
                "records": len(df_seasons),
            },
            "pcs_career_summary": {
                "path": str(career_out_path).replace("\\", "/"),
                "sha256": career_hash,
                "records": len(df_career),
            },
            "pcs_validation_metrics": {
                "path": str(val_path).replace("\\", "/"),
                "sha256": val_hash,
                "scenarios_passed": f"{val_results['passed_count']}/{val_results['total_scenarios']}",
            },
        },
        "validation_testbench_status": "PASS" if val_results["all_passed"] else "FAIL",
    }

    manifest_path = out_dir / "pcs_pipeline_manifest_v1.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
    print(f"Saved: {manifest_path} (SHA-256: {compute_sha256(manifest_path)[:16]}...)")

    # 8. Post-execution protected asset verification
    print("\n[Post-Check] Verifying post-execution protected asset integrity...")
    verify_protected_assets()
    print(">>> 14/14 Protected assets verified 100% matched baseline.")

    print("\n" + "=" * 70)
    print("STAGE B7.5 PCS PIPELINE EXECUTION COMPLETED SUCCESSFULLY!")
    print("=" * 70)

    return manifest


if __name__ == "__main__":
    run_pipeline()
