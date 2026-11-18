"""Statistical Confidence Utilities for Pressure Reliability Index (PRI).

Computes exact Wilson Score binomial confidence intervals on the [0, 100] percentage scale.
Strictly informational: NEVER modifies, shrinks, or pulls the observed reliability rate.
"""

from __future__ import annotations

import math
from typing import Optional, Tuple

from ml.contribution.pressure_reliability.schema import WILSON_Z_90, WILSON_Z_95


def wilson_confidence_interval(
    successes: int,
    total: int,
    z: float = WILSON_Z_95,
) -> Tuple[Optional[float], Optional[float], Optional[float]]:
    """Calculate Wilson score binomial confidence interval in percentage [0.0, 100.0].

    Parameters
    ----------
    successes : int
        Count of strictly positive pressure outcomes (HPC > 0 or PCS > 50).
    total : int
        Count of qualifying pressure opportunities (N >= 0).
    z : float
        Standard normal critical value (1.96 for 95% CI, 1.645 for 90% CI).

    Returns
    -------
    tuple[float | None, float | None, float | None]
        (lower_pct, upper_pct, width_pct) rounded to 2 decimals, or (None, None, None) if total <= 0.
    """
    if total <= 0:
        return (None, None, None)
    if successes < 0 or successes > total:
        raise ValueError(f"Invalid binomial counts: successes={successes}, total={total}")

    p = float(successes) / float(total)
    n = float(total)
    z2 = z * z
    denom = 1.0 + (z2 / n)
    center = (p + (z2 / (2.0 * n))) / denom
    half_width = (z * math.sqrt((p * (1.0 - p) / n) + (z2 / (4.0 * n * n)))) / denom

    low = max(0.0, (center - half_width) * 100.0)
    high = min(100.0, (center + half_width) * 100.0)
    width = high - low
    return (round(low, 2), round(high, 2), round(width, 2))


def wilson_interval_pair(
    successes: int,
    total: int,
) -> dict[str, Optional[float]]:
    """Compute both 95% and 90% Wilson confidence intervals."""
    l95, h95, w95 = wilson_confidence_interval(successes, total, z=WILSON_Z_95)
    l90, h90, w90 = wilson_confidence_interval(successes, total, z=WILSON_Z_90)
    return {
        "wilson_ci95_low": l95,
        "wilson_ci95_high": h95,
        "wilson_ci95_width": w95,
        "wilson_ci90_low": l90,
        "wilson_ci90_high": h90,
        "wilson_ci90_width": w90,
    }


def classify_sample_confidence(n_opportunities: int) -> str:
    """Classify sample size transparency tier (informational only; never alters metrics)."""
    if n_opportunities <= 0:
        return "Insufficient (No Opportunities)"
    if n_opportunities < 5:
        return "Very Low (Provisional)"
    if n_opportunities < 10:
        return "Low (Provisional)"
    if n_opportunities < 20:
        return "Moderate"
    return "High"
