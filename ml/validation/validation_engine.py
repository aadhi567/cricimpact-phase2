"""Reusable Pydantic-backed validation engine and result contracts."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Sequence

import pandas as pd
from pydantic import BaseModel, Field

from ml.ingestion.csv_loader import DatasetLoadBundle


class Severity(str, Enum):
    """Severity levels defined in data/validation/validation_contract.md."""

    CRITICAL = "CRITICAL"
    WARNING = "WARNING"
    INFO = "INFO"


class ValidationStatus(str, Enum):
    """Validation outcome statuses supported by Stage 4."""

    PASS = "PASS"
    WARNING = "WARNING"
    FAIL = "FAIL"
    SKIPPED = "SKIPPED"


class ValidationResult(BaseModel):
    """Structured result emitted by every validation rule."""

    rule_id: str
    dataset: str
    field: str
    severity: Severity
    status: ValidationStatus
    affected_record_count: int = Field(ge=0)
    short_description: str
    example_record_identifiers: list[str] = Field(default_factory=list)
    recommended_action: str
    known_exception_count: int = Field(default=0, ge=0)
    new_anomaly_count: int = Field(default=0, ge=0)
    known_exceptions_summary: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ValidationReport(BaseModel):
    """Aggregated validation execution report across all rules and datasets."""

    generated_at_utc: str
    raw_dir: str
    file_summaries: list[dict[str, Any]]
    results: list[ValidationResult]
    status_counts: dict[str, int]
    severity_counts: dict[str, int]
    total_rules: int
    total_known_exceptions: int
    total_new_anomalies: int
    section_summaries: dict[str, Any] = Field(default_factory=dict)


ValidatorFn = Callable[[DatasetLoadBundle], list[ValidationResult]]


def check_required_columns(
    bundle: DatasetLoadBundle,
    requirements: dict[str, tuple[str, ...]],
) -> str | None:
    """Return a skip reason if any required table or column is missing."""
    for table, cols in requirements.items():
        df = bundle.get(table)
        if df is None:
            summary = bundle.summaries.get(table)
            err = summary.error_message if summary else "not loaded"
            return f"Required table '{table}' is unavailable ({err})."
        missing = [c for c in cols if c not in df.columns]
        if missing:
            return (
                f"Required columns missing from '{table}': {', '.join(missing)}."
            )
    return None


def make_skipped_result(
    *,
    rule_id: str,
    dataset: str,
    field: str,
    severity: Severity,
    reason: str,
    recommended_action: str,
) -> ValidationResult:
    """Construct a standardized SKIPPED result when prerequisites are unavailable."""
    return ValidationResult(
        rule_id=rule_id,
        dataset=dataset,
        field=field,
        severity=severity,
        status=ValidationStatus.SKIPPED,
        affected_record_count=0,
        short_description=f"Check skipped: {reason}",
        example_record_identifiers=[],
        recommended_action=recommended_action,
    )


def format_row_id(row: pd.Series, cols: Sequence[str]) -> str:
    """Format a compact identifier string for example_record_identifiers."""
    parts = [f"{col}={row.get(col, '<NA>')}" for col in cols]
    return "(" + ", ".join(parts) + ")"


class ValidationEngine:
    """Executes registered validators independently and aggregates results."""

    def __init__(self, validators: Sequence[tuple[str, ValidatorFn]] | None = None):
        self._validators: list[tuple[str, ValidatorFn]] = list(validators or [])

    def register(self, name: str, fn: ValidatorFn) -> None:
        self._validators.append((name, fn))

    def run(
        self,
        bundle: DatasetLoadBundle,
        *,
        section_summaries: dict[str, Any] | None = None,
    ) -> ValidationReport:
        all_results: list[ValidationResult] = []
        diagnostics: dict[str, Any] = dict(section_summaries or {})

        for name, validator in self._validators:
            try:
                results = validator(bundle)
                all_results.extend(results)
            except Exception as exc:  # pragma: no cover - defensive isolation
                all_results.append(
                    ValidationResult(
                        rule_id=f"VAL-ENGINE-{name.upper()}",
                        dataset="pipeline",
                        field="*",
                        severity=Severity.CRITICAL,
                        status=ValidationStatus.FAIL,
                        affected_record_count=0,
                        short_description=f"Validator '{name}' raised unexpected error: {exc}",
                        example_record_identifiers=[],
                        recommended_action="Inspect traceback and validator dependencies.",
                    )
                )

        status_counts = {s.value: 0 for s in ValidationStatus}
        severity_counts = {sev.value: 0 for sev in Severity}
        total_known = 0
        total_new = 0
        for r in all_results:
            status_counts[r.status.value] = status_counts.get(r.status.value, 0) + 1
            severity_counts[r.severity.value] = severity_counts.get(r.severity.value, 0) + 1
            total_known += r.known_exception_count
            total_new += r.new_anomaly_count

        return ValidationReport(
            generated_at_utc=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
            raw_dir=str(bundle.raw_dir),
            file_summaries=bundle.summary_rows(),
            results=all_results,
            status_counts=status_counts,
            severity_counts=severity_counts,
            total_rules=len(all_results),
            total_known_exceptions=total_known,
            total_new_anomalies=total_new,
            section_summaries=diagnostics,
        )

