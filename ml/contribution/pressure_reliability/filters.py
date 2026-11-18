"""Reusable Filtering & Visibility Logic for Pressure Reliability Index (PRI).

Provides:
1. Custom minimum opportunity filter validation & application (accepts any integer >= 0).
2. Authoritative B8 Pakistan overall leaderboard visibility exclusion (never mutates underlying data).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Set
import pandas as pd

from ml.contribution.pressure_reliability.schema import (
    PAKISTAN_TEAM_NAMES,
    PLAYER_MAPPING_CSV_PATH,
)


def validate_min_opportunities(value: Any) -> int:
    """Validate user-supplied minimum pressure opportunity threshold.

    Accepts any non-negative whole integer (0, 1, 2, ...).
    Rejects booleans, negative numbers, decimals/floats, NaN, and non-integer strings.
    """
    if isinstance(value, bool):
        raise ValueError("Minimum opportunities must be a non-negative integer, not a boolean.")

    if isinstance(value, int):
        if value < 0:
            raise ValueError(f"Minimum opportunities cannot be negative (got {value}).")
        return value

    if isinstance(value, float):
        raise ValueError(f"Minimum opportunities must be a whole integer, not a decimal (got {value}).")

    if isinstance(value, str):
        s = value.strip()
        if not s:
            raise ValueError("Minimum opportunities cannot be empty.")
        if s.startswith("-"):
            raise ValueError(f"Minimum opportunities cannot be negative (got '{value}').")
        if not s.isdigit():
            raise ValueError(f"Minimum opportunities must be a valid non-negative integer (got '{value}').")
        return int(s)

    raise ValueError(f"Invalid minimum opportunities value: {value!r}")


def apply_min_opportunity_filter(
    df: pd.DataFrame,
    count_col: str,
    min_opportunities: Any = 0,
    sort_by: str | None = None,
    ascending: bool = False,
) -> pd.DataFrame:
    """Filter PRI summary DataFrame by user-supplied minimum opportunity count.

    Rules:
    - Validates `min_opportunities` strictly (whole integer >= 0).
    - `0` includes all players with at least 1 qualifying opportunity (`count_col >= 1`).
      Players with 0 qualifying opportunities are excluded from active rankings
      (unavailable / insufficient sample, never shown as 0% reliability).
    - Does NOT modify any underlying player calculation.
    - Recomputes contiguous 1..N `rank` column on the returned view.
    """
    min_n = validate_min_opportunities(min_opportunities)
    effective_min = max(1, min_n)

    if count_col not in df.columns:
        raise KeyError(f"Column '{count_col}' not found in PRI DataFrame.")

    filtered = df[df[count_col] >= effective_min].copy()
    if sort_by and sort_by in filtered.columns and len(filtered) > 0:
        filtered = filtered.sort_values(
            by=[sort_by, count_col],
            ascending=[ascending, False],
            na_position="last",
        )
    filtered = filtered.reset_index(drop=True)
    filtered["rank"] = range(1, len(filtered) + 1)
    return filtered


def load_pakistan_player_ids(mapping_path: Path = PLAYER_MAPPING_CSV_PATH) -> Set[int]:
    """Load authoritative Pakistan national player_ids from competition_team_player_mapping.csv.

    Strictly matches normalized team_name in {'Pakistan', 'Pakistan A'}.
    Never guesses from player names; unknown nationality is never classified as Pakistan.
    """
    if not mapping_path.exists():
        raise FileNotFoundError(f"Authoritative player mapping file missing: {mapping_path}")

    df = pd.read_csv(mapping_path)
    if "team_name" not in df.columns or "player_id" not in df.columns:
        raise ValueError("competition_team_player_mapping.csv missing required columns.")

    team_clean = df["team_name"].fillna("").astype(str).str.strip()
    pak_mask = team_clean.isin(PAKISTAN_TEAM_NAMES)
    return set(df.loc[pak_mask, "player_id"].dropna().astype(int).unique().tolist())


def apply_overall_leaderboard_visibility(
    df: pd.DataFrame,
    player_id_col: str = "player_id",
    exclude_pakistan: bool = True,
    pakistan_ids: Set[int] | None = None,
) -> pd.DataFrame:
    """Apply Stage B8 Overall Leaderboard visibility policy without mutating source data.

    - When `exclude_pakistan=True` (default overall leaderboard), hides verified Pakistan players
      identified strictly by authoritative `player_id`.
    - Players with missing/unknown `player_id` or non-Pakistan nationality are retained.
    - Underlying datasets and individual player profiles remain 100% intact.
    """
    if not exclude_pakistan or len(df) == 0:
        out = df.copy().reset_index(drop=True)
        out["rank"] = range(1, len(out) + 1)
        return out

    pak_set = pakistan_ids if pakistan_ids is not None else load_pakistan_player_ids()

    def _is_verified_pak(val: Any) -> bool:
        if pd.isna(val):
            return False
        try:
            return int(val) in pak_set
        except (ValueError, TypeError):
            return False

    is_pak = df[player_id_col].map(_is_verified_pak)
    out = df[~is_pak].copy().reset_index(drop=True)
    out["rank"] = range(1, len(out) + 1)
    return out
