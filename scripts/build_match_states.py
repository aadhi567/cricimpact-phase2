"""CLI entry point to execute CricImpact Phase 2 Stage 5B match-state generation and validation."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ml.ingestion.dataset_registry import DEFAULT_RAW_DIR  # noqa: E402
from ml.match_state.pipeline import run_match_state_pipeline  # noqa: E402
from ml.match_state.schema import (  # noqa: E402
    DEFAULT_PROCESSED_MATCH_STATES_DIR,
    DEFAULT_STAGE5B_VALIDATION_DIR,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build and validate the Stage 5B delivery-level match-state dataset."
    )
    parser.add_argument(
        "--raw-dir",
        type=Path,
        default=DEFAULT_RAW_DIR,
        help="Path to immutable raw CSV directory (defaults to <project_root>/data/raw).",
    )
    parser.add_argument(
        "--processed-dir",
        type=Path,
        default=DEFAULT_PROCESSED_MATCH_STATES_DIR,
        help="Output directory for versioned Stage 5B dataset and manifest.",
    )
    parser.add_argument(
        "--validation-dir",
        type=Path,
        default=DEFAULT_STAGE5B_VALIDATION_DIR,
        help="Output directory for Stage 5B eligibility, continuity, validation, and schema reports.",
    )
    parser.add_argument(
        "--expected-eligible-matches",
        type=int,
        default=798,
        help="Expected primary eligible match count from Stage 5A Revision 1.1 (set -1 to disable check).",
    )
    parser.add_argument(
        "--no-write",
        action="store_true",
        help="Execute validation and construction in memory without writing output artifacts.",
    )
    args = parser.parse_args(argv)

    expected_eligible = (
        None if args.expected_eligible_matches < 0 else args.expected_eligible_matches
    )
    outcome = run_match_state_pipeline(
        raw_dir=args.raw_dir,
        processed_dir=args.processed_dir,
        validation_dir=args.validation_dir,
        expected_eligible_matches=expected_eligible,
        write_outputs=not args.no_write,
    )

    print(
        f"Stage 5B Status: {outcome.status} | TotalMatches={outcome.total_match_count} "
        f"EligibleMatches={outcome.eligible_match_count} ExcludedMatches={outcome.excluded_match_count} "
        f"PrimaryRows={outcome.primary_row_count:,} AllRows={outcome.all_row_count:,} "
        f"Columns={outcome.column_count} RawHashesUnchanged={outcome.raw_hashes_unchanged} "
        f"Stage4HashesUnchanged={outcome.stage4_hashes_unchanged}"
    )

    if outcome.reconciliation_halted:
        print(f"RECONCILIATION HALT: {outcome.blocker_message}")
        return 2

    if outcome.validation_outcome is not None:
        sc = outcome.validation_outcome["status_counts"]
        cnt = outcome.validation_outcome["continuity"]
        print(
            f"Validation: PASS={sc.get('PASS', 0)} WARNING={sc.get('WARNING', 0)} "
            f"FAIL={sc.get('FAIL', 0)} | ContinuityUnexpectedBreaks={cnt.unexpected_break_count} "
            f"DocumentedDiscontinuities={cnt.documented_discontinuity_count}"
        )
        for r in outcome.validation_outcome["results"]:
            if r.status.value in {"FAIL", "WARNING"}:
                print(
                    f"  [{r.status.value}] {r.rule_id} ({r.severity.value}): "
                    f"affected={r.affected_record_count} -> {r.short_description}"
                )

    written_paths = outcome.written.get("paths", {})
    if written_paths:
        print("Artifacts written:")
        for key, path in sorted(written_paths.items()):
            print(f"  {key}: {path}")
        if outcome.written.get("dataset_sha256"):
            print(
                f"  dataset_sha256={outcome.written['dataset_sha256']} "
                f"size_bytes={outcome.written['dataset_size_bytes']} "
                f"roundtrip_verified={outcome.written['roundtrip_verified']}"
            )

    return 1 if outcome.has_critical_failure else 0


if __name__ == "__main__":
    raise SystemExit(main())

