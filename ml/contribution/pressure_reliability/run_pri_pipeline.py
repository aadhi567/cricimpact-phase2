"""Stage PRI-2: Independent Pressure Reliability Index (PRI) Pipeline Runner.

Generates all 10 independent PRI production artifacts under:
    data/processed/contributions/pressure_reliability/

Strict governance:
- Read-only consumption of existing HPP/HPC and PCS production artifacts.
- Zero modification of protected Phase 2 assets or Phase 1 files.
- NO SHRINKAGE (`shrinkage_applied: false`) and NO COMPOSITE SCORE (`composite_score_applied: false`).
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from ml.contribution.pressure_reliability.batting_pri_engine import BattingPRIEngine
from ml.contribution.pressure_reliability.bowling_pri_engine import BowlingPRIEngine
from ml.contribution.pressure_reliability.pri_validation import run_full_validation
from ml.contribution.pressure_reliability.schema import (
    BATTING_SENSITIVITY_ENTRY_P_THRESHOLD,
    BATTING_T10_MEAN_P_THRESHOLD,
    BATTING_T10_PEAK_P_THRESHOLD,
    BOWLING_EXO2_MAX_ENTRY_PTI_THRESHOLD,
    BOWLING_EXO2_MIN_LEGAL_BALLS,
    BOWLING_EXO5_MEAN_ENTRY_PTI_THRESHOLD,
    BOWLING_EXO5_MIN_LEGAL_BALLS,
    COMPETITIONS_CSV_PATH,
    COMPOSITE_SCORE_APPLIED,
    DEFAULT_PRI_OUTPUT_DIR,
    HPC_NEUTRAL_ANCHOR,
    HPP_MATCH_DATA_PATH,
    MATCH_INDEX_PATH,
    MATCH_STATES_PATH,
    MATCHES_CSV_PATH,
    PCS_DELIVERIES_PATH,
    PCS_NEUTRAL_ANCHOR,
    PCS_SPELLS_PATH,
    PLAYER_MAPPING_CSV_PATH,
    PRI_METHODOLOGY_ID,
    PRI_STAGE_VERSION,
    SHRINKAGE_APPLIED,
)


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def run_pri_pipeline(output_dir: Path = DEFAULT_PRI_OUTPUT_DIR) -> Dict[str, Any]:
    """Execute full independent PRI-2 pipeline and write all 10 production outputs."""
    output_dir.mkdir(parents=True, exist_ok=True)
    started_at = datetime.now(timezone.utc).isoformat()

    # 1. Record read-only source artifact SHA-256 hashes before processing
    source_files = {
        "hpp_match_data": HPP_MATCH_DATA_PATH,
        "match_index": MATCH_INDEX_PATH,
        "match_states": MATCH_STATES_PATH,
        "pcs_deliveries": PCS_DELIVERIES_PATH,
        "pcs_spells": PCS_SPELLS_PATH,
        "matches_csv": MATCHES_CSV_PATH,
        "competitions_csv": COMPETITIONS_CSV_PATH,
        "player_mapping_csv": PLAYER_MAPPING_CSV_PATH,
    }
    source_hashes = {
        key: {
            "path": str(path),
            "sha256": _sha256_file(path),
            "size_bytes": path.stat().st_size,
        }
        for key, path in source_files.items()
    }

    # 2. Run Independent Batting & Bowling PRI Engines
    print("[PRI-2] Running independent Batting PRI Engine (T10: mean_p >= 40 OR peak_p >= 60, unshrunk)...")
    batting_engine = BattingPRIEngine()
    batting_out = batting_engine.run()

    print("[PRI-2] Running independent Bowling PRI Engine (EXO_2: max_over_entry_pti >= 35 AND legal_balls >= 12, unshrunk)...")
    bowling_engine = BowlingPRIEngine()
    bowling_out = bowling_engine.run()

    # 3. Run Chronological Validation, Sensitivity Comparisons & 10-Scenario Stress Suite
    print("[PRI-2] Running chronological validation, sensitivity analyses & 10-scenario stress tests...")
    validation_metrics = run_full_validation(batting_out, bowling_out)

    # 4. Write all 8 independent PRI DataFrame artifacts
    df_outputs = {
        "batting_pri_pressure_innings_v1.pkl.gz": batting_out["pressure_innings"],
        "batting_pri_career_v1.pkl.gz": batting_out["career"],
        "batting_pri_season_v1.pkl.gz": batting_out["season"],
        "batting_pri_tournament_v1.pkl.gz": batting_out["tournament"],
        "bowling_pri_pressure_spells_v1.pkl.gz": bowling_out["pressure_spells"],
        "bowling_pri_career_v1.pkl.gz": bowling_out["career"],
        "bowling_pri_season_v1.pkl.gz": bowling_out["season"],
        "bowling_pri_tournament_v1.pkl.gz": bowling_out["tournament"],
    }

    output_inventory: Dict[str, Any] = {}
    for fname, df in df_outputs.items():
        out_path = output_dir / fname
        df.to_pickle(out_path, compression="gzip")
        output_inventory[fname] = {
            "path": str(out_path),
            "rows": int(len(df)),
            "columns": list(df.columns),
            "sha256": _sha256_file(out_path),
            "size_bytes": out_path.stat().st_size,
        }

    # 5. Write validation metrics JSON
    val_path = output_dir / "pri_validation_metrics_v1.json"
    with open(val_path, "w", encoding="utf-8") as f:
        json.dump(validation_metrics, f, indent=2)
    output_inventory["pri_validation_metrics_v1.json"] = {
        "path": str(val_path),
        "sha256": _sha256_file(val_path),
        "size_bytes": val_path.stat().st_size,
    }

    # 6. Build and write pipeline manifest JSON
    completed_at = datetime.now(timezone.utc).isoformat()
    manifest: Dict[str, Any] = {
        "stage": PRI_STAGE_VERSION,
        "methodology_id": PRI_METHODOLOGY_ID,
        "started_at_utc": started_at,
        "completed_at_utc": completed_at,
        "governance": {
            "shrinkage_applied": SHRINKAGE_APPLIED,
            "composite_score_applied": COMPOSITE_SCORE_APPLIED,
            "dnb_excluded_strictly": True,
            "neutral_never_counted_positive": True,
            "pakistan_overall_leaderboard_hidden_by_default": True,
            "pakistan_underlying_data_mutated": False,
        },
        "approved_definitions": {
            "batting_opportunity": {
                "name": "T10",
                "formula": f"mean_p >= {BATTING_T10_MEAN_P_THRESHOLD} OR peak_p >= {BATTING_T10_PEAK_P_THRESHOLD}",
                "positive_condition": f"hpc > {HPC_NEUTRAL_ANCHOR}",
                "neutral_condition": f"hpc == {HPC_NEUTRAL_ANCHOR}",
                "sensitivity_alternative": f"entry_p >= {BATTING_SENSITIVITY_ENTRY_P_THRESHOLD}",
            },
            "bowling_opportunity": {
                "name": "EXO_2",
                "formula": f"max_over_entry_pti >= {BOWLING_EXO2_MAX_ENTRY_PTI_THRESHOLD} AND legal_balls >= {BOWLING_EXO2_MIN_LEGAL_BALLS}",
                "positive_condition": f"pcs_spell > {PCS_NEUTRAL_ANCHOR}",
                "neutral_condition": f"pcs_spell == {PCS_NEUTRAL_ANCHOR}",
                "sensitivity_alternative": f"EXO_5: mean_over_entry_pti >= {BOWLING_EXO5_MEAN_ENTRY_PTI_THRESHOLD} AND legal_balls >= {BOWLING_EXO5_MIN_LEGAL_BALLS}",
            },
        },
        "source_artifacts": source_hashes,
        "batting_audit_summary": batting_out["audit_meta"],
        "bowling_audit_summary": bowling_out["audit_meta"],
        "reconciliation_summary": {
            "batting": validation_metrics["batting_validation"]["reconciliation"],
            "bowling": validation_metrics["bowling_validation"]["reconciliation"],
            "all_10_scenarios_passed": validation_metrics["scenario_stress_tests"]["all_10_scenarios_passed"],
        },
        "generated_outputs": output_inventory,
    }

    manifest_path = output_dir / "pri_pipeline_manifest_v1.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    print(f"[PRI-2] Successfully generated 10 artifacts in: {output_dir}")
    print(
        f"[PRI-2] Batting: {batting_out['audit_meta']['t10_qualifying_innings']} T10 pressure innings "
        f"across {len(batting_out['career'])} career batters "
        f"(unresolved batted IDs: {batting_out['audit_meta']['unresolved_batted_player_ids']})"
    )
    print(
        f"[PRI-2] Bowling: {bowling_out['audit_meta']['exo2_qualifying_spells']} EXO_2 pressure spells "
        f"across {len(bowling_out['career'])} career bowlers"
    )
    print(
        f"[PRI-2] Reconciliation: Batting={manifest['reconciliation_summary']['batting']['exact_count_reconciliation_pass']}, "
        f"Bowling={manifest['reconciliation_summary']['bowling']['exact_count_reconciliation_pass']}, "
        f"NoShrinkage=(Bat:{manifest['reconciliation_summary']['batting']['no_shrinkage_verified']}, "
        f"Bowl:{manifest['reconciliation_summary']['bowling']['no_shrinkage_verified']}), "
        f"All10Scenarios={manifest['reconciliation_summary']['all_10_scenarios_passed']}"
    )
    return manifest


if __name__ == "__main__":
    run_pri_pipeline()
