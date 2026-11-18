"""CLI Runner for CricImpact Phase 2 Stage 5C Contribution Engine."""

from __future__ import annotations

import argparse
import logging
import sys
import time
import warnings
from pathlib import Path

# Silence scikit-learn / joblib parallel dispatch UserWarnings
warnings.filterwarnings("ignore", category=UserWarning)

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ml.contribution.pipeline import run_stage5c_pipeline
from ml.contribution.schema import (
    DEFAULT_CONTRIBUTIONS_DIR,
    DEFAULT_STAGE5C_VALIDATION_DIR,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

logger = logging.getLogger("run_stage5c")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run CricImpact Phase 2 Stage 5C Contribution Pipeline."
    )
    parser.add_argument(
        "--processed-dir",
        type=Path,
        default=DEFAULT_CONTRIBUTIONS_DIR,
        help="Directory to write processed contribution datasets.",
    )
    parser.add_argument(
        "--validation-dir",
        type=Path,
        default=DEFAULT_STAGE5C_VALIDATION_DIR,
        help="Directory to write validation and evaluation reports.",
    )
    args = parser.parse_args()

    logger.info("Starting CricImpact Phase 2 Stage 5C Execution...")
    start_time = time.time()

    try:
        manifest = run_stage5c_pipeline(
            processed_dir=args.processed_dir,
            validation_dir=args.validation_dir,
        )
        elapsed = time.time() - start_time
        logger.info(
            "Stage 5C Execution Successful in %.2fs! Manifest written to %s",
            elapsed,
            args.processed_dir / "stage5c_contributions_v1_manifest.json",
        )
        return 0
    except Exception as e:
        logger.exception("Stage 5C Execution Failed: %s", e)
        return 1


if __name__ == "__main__":
    sys.exit(main())

