"""Stage B7.5 Sequential Wicket State Machine & Attribution Filter."""

from __future__ import annotations

import numpy as np
import pandas as pd

from ml.contribution.bowling_pressure.schema import (
    BOWLER_CREDITED_DISMISSALS,
    NON_BOWLER_DISMISSALS,
    NON_BOWLER_EXTRAS,
)


class SequentialWicketEngine:
    """Processes sequential delivery state transitions with strict attribution filtering."""

    def __init__(self) -> None:
        self.bowler_dismissals_lower = frozenset({d.lower() for d in BOWLER_CREDITED_DISMISSALS})
        self.non_bowler_dismissals_lower = frozenset({d.lower() for d in NON_BOWLER_DISMISSALS})
        self.non_bowler_extras_lower = frozenset({e.lower() for e in NON_BOWLER_EXTRAS})

    def classify_deliveries(
        self,
        df: pd.DataFrame,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """Classify delivery outcome types and individual bowler attribution factors.
        
        Returns:
            (is_bowler_wkt, is_non_bowler_wkt, is_non_bowler_extra, alpha_attr)
        """
        is_wkt = df["is_wicket_event"].fillna(False).astype(bool).to_numpy()
        d_type = (
            df["dismissal_type_canonical"]
            .fillna("")
            .astype(str)
            .str.strip()
            .str.lower()
            .to_numpy()
        )
        extras = (
            df.get("extras_type", pd.Series("", index=df.index))
            .fillna("")
            .astype(str)
            .str.strip()
            .str.lower()
            .to_numpy()
        )

        is_bowler_wkt = is_wkt & np.isin(d_type, list(self.bowler_dismissals_lower))
        is_non_bowler_wkt = is_wkt & (~is_bowler_wkt)
        is_non_bowler_extra = np.isin(extras, list(self.non_bowler_extras_lower))

        # Attribution factor: 1.0 for bowler credited balls/wickets; 0.0 for pure fielding extras or run-outs
        alpha_attr = np.where(is_non_bowler_wkt | is_non_bowler_extra, 0.0, 1.0)

        return is_bowler_wkt, is_non_bowler_wkt, is_non_bowler_extra, alpha_attr
