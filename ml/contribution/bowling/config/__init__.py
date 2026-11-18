"""Bowling configuration loader and constants."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Final

CONFIG_PATH: Final[Path] = Path(__file__).resolve().parent / "bowling_config.json"


def load_bowling_config(path: Path | str | None = None) -> dict[str, Any]:
    """Load the calibrated bowling configuration dictionary."""
    target_path = Path(path) if path else CONFIG_PATH
    if not target_path.exists():
        raise FileNotFoundError(f"Bowling config not found at: {target_path}")
    with open(target_path, "r", encoding="utf-8") as f:
        return json.load(f)
