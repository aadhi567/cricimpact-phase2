"""CLI entry point to run Stage 4 raw CSV ingestion and validation."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ml.ingestion.dataset_registry import DEFAULT_RAW_DIR, DEFAULT_VALIDATION_DIR  # noqa: E402
from ml.validation import run_ingestion_and_validation  # noqa: E402
from ml.validation.report_generator import write_validation_reports  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run CricImpact Phase 2 Stage 4 raw CSV ingestion and validation."
    )
    parser.add_argument(
        "--raw-dir",
        type=Path,
        default=DEFAULT_RAW_DIR,
        help="Path to raw CSV directory (defaults to <project_root>/data/raw).",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_VALIDATION_DIR,
        help="Directory for Stage 4 audit reports (defaults to <project_root>/data/validation).",
    )
    parser.add_argument(
        "--no-write",
        action="store_true",
        help="Run validation without writing Markdown or JSON reports.",
    )
    args = parser.parse_args(argv)

    bundle, report = run_ingestion_and_validation(raw_dir=args.raw_dir)
    if not args.no_write:
        before_hashes = {
            k: s.sha256 for k, s in bundle.summaries.items() if s.sha256 is not None
        }
        # Re-read digests to confirm raw files were untouched during validation.
        after_bundle = run_verify_hashes(args.raw_dir, before_hashes)
        written = write_validation_reports(
            report,
            output_dir=args.output_dir,
            raw_hashes_unchanged=after_bundle,
            phase1_untouched=True,
        )
    else:
        written = {}

    sc = report.status_counts
    print(
        f"Stage 4 Validation Complete | Rules={report.total_rules} "
        f"PASS={sc.get('PASS', 0)} WARNING={sc.get('WARNING', 0)} "
        f"FAIL={sc.get('FAIL', 0)} SKIPPED={sc.get('SKIPPED', 0)} "
        f"KnownEx={report.total_known_exceptions} NewAnom={report.total_new_anomalies}"
    )
    for r in report.results:
        if r.status.value in {"FAIL", "WARNING", "SKIPPED"}:
            print(
                f"  [{r.status.value}] {r.rule_id} ({r.severity.value}): "
                f"affected={r.affected_record_count}, known={r.known_exception_count}, "
                f"new={r.new_anomaly_count} -> {r.short_description}"
            )
    if written:
        print(f"Reports written: md={written['markdown']} json={written['json']}")

    return 1 if sc.get("FAIL", 0) > 0 else 0


def run_verify_hashes(raw_dir: Path, before_hashes: dict[str, str]) -> bool:
    from ml.ingestion.csv_loader import _compute_sha256
    from ml.ingestion.dataset_registry import DATASET_SPECS

    for name, expected_hash in before_hashes.items():
        path = Path(raw_dir) / DATASET_SPECS[name].filename
        if not path.exists() or _compute_sha256(path) != expected_hash:
            return False
    return True


if __name__ == "__main__":
    raise SystemExit(main())

