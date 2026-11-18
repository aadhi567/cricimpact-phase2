"""Reusable read-only CSV ingestion loader for CricImpact Phase 2.

Guarantees:
- Resolves paths relative to project root using pathlib.Path.
- Never modifies raw CSV files.
- Preserves original column names (including unexpected columns) and IDs.
- Preserves literal 'None' strings distinct from blank null values.
- Never coerces missing nullable IDs to zero or drops duplicate rows.
"""

from __future__ import annotations

import csv
import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from ml.ingestion.dataset_registry import (
    DATASET_ORDER,
    DATASET_SPECS,
    DEFAULT_RAW_DIR,
    DatasetSpec,
)


class DatasetLoadError(Exception):
    """Base error for strict dataset loading failures."""


class MissingDatasetFileError(DatasetLoadError):
    """Raised when a required raw CSV file is missing or unreadable."""


class DatasetSchemaError(DatasetLoadError):
    """Raised when a CSV file fails structural header or ragged-row checks."""


@dataclass
class FileLoadSummary:
    """Structural and loading metadata for one CSV file."""

    dataset_name: str
    filename: str
    file_path: Path
    exists: bool
    readable: bool
    loaded: bool
    size_bytes: int | None = None
    sha256: str | None = None
    row_count: int = 0
    column_count: int = 0
    actual_columns: tuple[str, ...] = ()
    missing_columns: tuple[str, ...] = ()
    unexpected_columns: tuple[str, ...] = ()
    order_mismatch: bool = False
    bad_col_rows: int = 0
    bad_col_row_examples: tuple[str, ...] = ()
    parse_error_columns: dict[str, int] = field(default_factory=dict)
    parse_error_examples: dict[str, tuple[str, ...]] = field(default_factory=dict)
    error_message: str | None = None


@dataclass
class DatasetLoadBundle:
    """Container holding all loaded DataFrames and structured ingestion metadata."""

    raw_dir: Path
    datasets: dict[str, pd.DataFrame]
    summaries: dict[str, FileLoadSummary]

    @property
    def all_files_present(self) -> bool:
        return all(s.exists and s.readable for s in self.summaries.values())

    @property
    def all_loaded(self) -> bool:
        return all(s.loaded for s in self.summaries.values())

    @property
    def has_structural_errors(self) -> bool:
        return any(
            (not s.loaded)
            or bool(s.missing_columns)
            or bool(s.unexpected_columns)
            or s.bad_col_rows > 0
            or bool(s.parse_error_columns)
            for s in self.summaries.values()
        )

    def get(self, name: str) -> pd.DataFrame | None:
        return self.datasets.get(name)

    def summary_rows(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for name in DATASET_ORDER:
            s = self.summaries[name]
            rows.append(
                {
                    "dataset": s.dataset_name,
                    "filename": s.filename,
                    "loaded": s.loaded,
                    "rows": s.row_count,
                    "columns": s.column_count,
                    "expected_columns": DATASET_SPECS[name].column_count,
                    "size_bytes": s.size_bytes,
                    "sha256": s.sha256,
                    "missing_columns": list(s.missing_columns),
                    "unexpected_columns": list(s.unexpected_columns),
                    "bad_col_rows": s.bad_col_rows,
                    "parse_error_columns": dict(s.parse_error_columns),
                    "error_message": s.error_message,
                }
            )
        return rows


def _compute_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def _inspect_csv_structure(path: Path, spec: DatasetSpec) -> FileLoadSummary:
    summary = FileLoadSummary(
        dataset_name=spec.name,
        filename=spec.filename,
        file_path=path,
        exists=path.exists(),
        readable=False,
        loaded=False,
    )
    if not path.exists() or not path.is_file():
        summary.error_message = f"Missing required CSV file: {path}"
        return summary

    try:
        summary.size_bytes = path.stat().st_size
        summary.sha256 = _compute_sha256(path)
        with path.open("r", encoding="utf-8-sig", newline="") as fh:
            reader = csv.reader(fh)
            try:
                header = next(reader)
            except StopIteration:
                summary.readable = True
                summary.error_message = f"Empty CSV file (missing header): {path}"
                return summary

            summary.readable = True
            summary.actual_columns = tuple(header)
            summary.column_count = len(header)
            expected_set = set(spec.columns)
            actual_set = set(header)
            summary.missing_columns = tuple(c for c in spec.columns if c not in actual_set)
            summary.unexpected_columns = tuple(c for c in header if c not in expected_set)
            summary.order_mismatch = tuple(header) != spec.columns and not (
                summary.missing_columns or summary.unexpected_columns
            )

            expected_len = len(header)
            bad_examples: list[str] = []
            bad_count = 0
            row_count = 0
            for line_num, row in enumerate(reader, start=2):
                row_count += 1
                if len(row) != expected_len:
                    bad_count += 1
                    if len(bad_examples) < 5:
                        bad_examples.append(
                            f"line {line_num}: expected {expected_len} cols, got {len(row)}"
                        )
            summary.row_count = row_count
            summary.bad_col_rows = bad_count
            summary.bad_col_row_examples = tuple(bad_examples)
    except OSError as exc:
        summary.error_message = f"Unreadable file {path}: {exc}"
    except UnicodeDecodeError as exc:
        summary.error_message = f"Encoding error reading {path}: {exc}"
    except csv.Error as exc:
        summary.error_message = f"CSV framing error in {path}: {exc}"

    return summary


def _safe_cast_columns(
    df: pd.DataFrame, spec: DatasetSpec, summary: FileLoadSummary
) -> pd.DataFrame:
    """Cast columns to nullable pandas dtypes without dropping bad values or filling 0."""
    # Convert empty string cells (and padded NaN from short ragged rows) ONLY to pd.NA;
    # literal 'None' strings remain 'None'.
    for col in df.columns:
        raw_series = df[col]
        df[col] = raw_series.where(raw_series.notna() & (raw_series != ""), pd.NA)

    int_set = set(spec.int_columns)
    float_set = set(spec.float_columns)
    bool_set = set(spec.bool_columns)

    for col in spec.columns:
        if col not in df.columns:
            continue
        non_null = df[col].dropna()
        if col in int_set:
            if len(non_null) == 0:
                df[col] = pd.Series(pd.NA, index=df.index, dtype="Int64")
                continue
            cleaned = non_null.astype(str).str.strip()
            valid_mask = cleaned.str.fullmatch(r"-?\d+")
            if bool(valid_mask.all()):
                try:
                    parsed = cleaned.astype("int64")
                    casted = pd.Series(pd.NA, index=df.index, dtype="Int64")
                    casted.loc[non_null.index] = parsed
                    df[col] = casted
                    continue
                except (ValueError, OverflowError):
                    pass
            bad_vals = non_null.loc[~valid_mask] if not bool(valid_mask.all()) else non_null
            summary.parse_error_columns[col] = int(len(bad_vals))
            summary.parse_error_examples[col] = tuple(
                f"row_idx={idx}: {val!r}" for idx, val in bad_vals.head(5).items()
            )
            df[col] = df[col].astype("string")
        elif col in float_set:
            if len(non_null) == 0:
                df[col] = pd.Series(float("nan"), index=df.index, dtype="float64")
                continue
            numeric = pd.to_numeric(non_null, errors="coerce")
            valid_mask = numeric.notna() & np.isfinite(numeric)
            if bool(valid_mask.all()):
                casted = pd.Series(float("nan"), index=df.index, dtype="float64")
                casted.loc[non_null.index] = numeric.astype("float64")
                df[col] = casted
            else:
                bad_vals = non_null.loc[~valid_mask]
                summary.parse_error_columns[col] = int(len(bad_vals))
                summary.parse_error_examples[col] = tuple(
                    f"row_idx={idx}: {val!r}" for idx, val in bad_vals.head(5).items()
                )
                df[col] = df[col].astype("string")
        elif col in bool_set:
            if len(non_null) == 0:
                df[col] = pd.Series(pd.NA, index=df.index, dtype="boolean")
                continue
            lowered = non_null.astype(str).str.strip().str.lower()
            valid_mask = lowered.isin({"true", "false"})
            if bool(valid_mask.all()):
                casted = pd.Series(pd.NA, index=df.index, dtype="boolean")
                casted.loc[non_null.index] = lowered.map({"true": True, "false": False})
                df[col] = casted
            else:
                bad_vals = non_null.loc[~valid_mask]
                summary.parse_error_columns[col] = int(len(bad_vals))
                summary.parse_error_examples[col] = tuple(
                    f"row_idx={idx}: {val!r}" for idx, val in bad_vals.head(5).items()
                )
                df[col] = df[col].astype("string")
        else:
            df[col] = df[col].astype("string")

    # Preserve any unexpected extra columns untouched (with '' -> pd.NA normalization)
    for col in summary.unexpected_columns:
        df[col] = df[col].astype("string")

    return df


def load_single_dataset(
    name: str,
    raw_dir: Path | None = None,
    *,
    strict: bool = False,
) -> tuple[pd.DataFrame | None, FileLoadSummary]:
    """Load one named raw dataset without mutating data or discarding extra columns."""
    if name not in DATASET_SPECS:
        raise ValueError(f"Unknown dataset name {name!r}; expected one of {DATASET_ORDER}.")

    spec = DATASET_SPECS[name]
    resolved_dir = Path(raw_dir).resolve() if raw_dir is not None else DEFAULT_RAW_DIR
    file_path = resolved_dir / spec.filename
    summary = _inspect_csv_structure(file_path, spec)

    if not summary.readable or summary.error_message is not None:
        if strict:
            raise MissingDatasetFileError(summary.error_message or f"Cannot read {file_path}")
        return None, summary

    if summary.bad_col_rows > 0:
        # Still attempt safe pandas read with on_bad_lines="skip" ONLY so other
        # independent validations can see valid rows, OR report failure cleanly.
        try:
            df = pd.read_csv(
                file_path,
                dtype=str,
                keep_default_na=False,
                encoding="utf-8-sig",
                on_bad_lines="skip",
            )
            df = _safe_cast_columns(df, spec, summary)
            summary.loaded = True
        except Exception as exc:
            summary.error_message = f"Failed reading CSV {file_path}: {exc}"
            df = None
        if strict:
            raise DatasetSchemaError(
                f"{spec.filename} has {summary.bad_col_rows} ragged rows: "
                f"{summary.bad_col_row_examples}"
            )
        return df, summary

    try:
        df = pd.read_csv(
            file_path,
            dtype=str,
            keep_default_na=False,
            encoding="utf-8-sig",
        )
        df = _safe_cast_columns(df, spec, summary)
        summary.row_count = int(len(df))
        summary.column_count = int(len(df.columns))
        summary.loaded = True
    except Exception as exc:
        summary.error_message = f"Failed reading CSV {file_path}: {exc}"
        if strict:
            raise DatasetSchemaError(summary.error_message) from exc
        return None, summary

    if strict and (summary.missing_columns or summary.unexpected_columns):
        raise DatasetSchemaError(
            f"{spec.filename} schema mismatch: missing={summary.missing_columns}, "
            f"unexpected={summary.unexpected_columns}"
        )

    return df, summary


def load_raw_datasets(
    raw_dir: Path | None = None,
    *,
    strict: bool = False,
) -> DatasetLoadBundle:
    """Load all six raw CSV datasets and return DataFrames plus a full summary."""
    resolved_dir = Path(raw_dir).resolve() if raw_dir is not None else DEFAULT_RAW_DIR
    datasets: dict[str, pd.DataFrame] = {}
    summaries: dict[str, FileLoadSummary] = {}

    for name in DATASET_ORDER:
        df, summary = load_single_dataset(name, raw_dir=resolved_dir, strict=strict)
        summaries[name] = summary
        if df is not None:
            datasets[name] = df

    return DatasetLoadBundle(
        raw_dir=resolved_dir,
        datasets=datasets,
        summaries=summaries,
    )
