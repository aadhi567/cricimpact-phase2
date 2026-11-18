"""Stage 4 reusable validation suite orchestration for CricImpact Phase 2."""

from __future__ import annotations

from pathlib import Path

from ml.ingestion.csv_loader import DatasetLoadBundle, load_raw_datasets
from ml.validation.delivery_validator import validate_deliveries
from ml.validation.extras_validator import validate_extras
from ml.validation.match_validator import validate_matches
from ml.validation.playing_eleven_validator import validate_playing_eleven
from ml.validation.relationship_validator import validate_relationships
from ml.validation.schema_validator import validate_schema
from ml.validation.validation_engine import ValidationEngine, ValidationReport
from ml.validation.wicket_validator import validate_wickets


def build_default_validation_engine() -> ValidationEngine:
    """Construct a ValidationEngine registered with all Stage 4 validators."""
    return ValidationEngine(
        validators=[
            ("schema", validate_schema),
            ("relationships", validate_relationships),
            ("extras", validate_extras),
            ("deliveries", validate_deliveries),
            ("wickets", validate_wickets),
            ("matches", validate_matches),
            ("playing_eleven", validate_playing_eleven),
        ]
    )


def run_ingestion_and_validation(
    raw_dir: Path | None = None,
) -> tuple[DatasetLoadBundle, ValidationReport]:
    """Load raw CSV datasets and execute the complete validation suite."""
    bundle = load_raw_datasets(raw_dir=raw_dir, strict=False)
    engine = build_default_validation_engine()
    report = engine.run(bundle)
    return bundle, report


__all__ = [
    "build_default_validation_engine",
    "run_ingestion_and_validation",
]

