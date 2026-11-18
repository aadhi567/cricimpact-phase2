"""Stage 5B vectorized delivery transition state builder (Stage 5A Revision 1.1)."""

from __future__ import annotations

import pandas as pd

from ml.ingestion.dataset_registry import VALID_EXTRAS_TYPES
from ml.match_state.schema import TRANSITION_KEY_COLUMNS
from ml.validation.extras_validator import derive_is_legal_delivery, derive_team_runs


class DuplicateTransitionKeyError(ValueError):
    """Raised when duplicate (match_id, innings, innings_ball_num) transition keys occur."""


class InvalidTransitionKeyError(ValueError):
    """Raised when transition key columns contain nulls or missing required fields."""


_REQUIRED_BBB_COLS: tuple[str, ...] = (
    "match_id",
    "innings",
    "overid",
    "over_ball_num",
    "innings_ball_num",
    "batting_team_id",
    "bowling_team_id",
    "striker_id",
    "non_striker_id",
    "bowler_id",
    "batting_order",
    "runs",
    "is_four",
    "is_six",
    "is_wicket",
    "dismissal_type_id",
    "dismissal_type",
    "dismissed_player_id",
    "extras_type",
    "extras1_runs",
    "extras_2_runs",
    "delivery_ist_time",
)


def build_delivery_states(
    ball_by_ball: pd.DataFrame,
    *,
    allow_empty: bool = False,
) -> pd.DataFrame:
    """Build deterministic pre-delivery and post-delivery state accumulators at delivery grain.

    Notes
    -----
    - Strictly sorts by (match_id, innings, innings_ball_num) ascending (never timestamps).
    - Raises InvalidTransitionKeyError on null keys and DuplicateTransitionKeyError on duplicate keys.
    - Uses Stage 4 approved formulas:
      * team_runs = runs + extras1_runs + extras_2_runs
      * is_legal_delivery = extras_type not in {'wide', 'Overstep', 'other'}
      * official wickets = ball_by_ball.is_wicket (Retired Hurt adds +0; Retire Out adds +1)
      * resolved_dismissed_player_id NEVER fabricates missing dismissed_player_id
    """
    missing_cols = [c for c in _REQUIRED_BBB_COLS if c not in ball_by_ball.columns]
    if missing_cols:
        raise InvalidTransitionKeyError(
            f"ball_by_ball missing required columns for state construction: {missing_cols}"
        )

    if len(ball_by_ball) == 0:
        if allow_empty:
            return ball_by_ball.copy()
        raise InvalidTransitionKeyError("ball_by_ball contains 0 rows.")

    df = ball_by_ball.copy()

    # Validate transition key non-null and strict uniqueness
    key_cols = list(TRANSITION_KEY_COLUMNS)
    null_key_mask = df[key_cols].isna().any(axis=1)
    if bool(null_key_mask.any()):
        sample = df.loc[null_key_mask, key_cols].head(5).to_dict(orient="records")
        raise InvalidTransitionKeyError(
            f"Null values detected in transition key {key_cols}: {sample}"
        )

    dup_mask = df.duplicated(subset=key_cols, keep=False)
    if bool(dup_mask.any()):
        dup_cnt = int(df.duplicated(subset=key_cols, keep="first").sum())
        sample = df.loc[dup_mask, key_cols].head(8).to_dict(orient="records")
        raise DuplicateTransitionKeyError(
            f"Detected {dup_cnt} duplicate delivery transition key(s) on {key_cols}: {sample}"
        )

    # Sort strictly by (match_id, innings, innings_ball_num) ascending
    df = df.sort_values(key_cols, kind="mergesort").reset_index(drop=True)

    # Verify extras_type domain strictly (case-sensitive literal 'None' allowed)
    extras_series = df["extras_type"].astype("string")
    bad_extras_mask = extras_series.isna() | ~extras_series.isin(VALID_EXTRAS_TYPES)
    if bool(bad_extras_mask.any()):
        bad_vals = sorted(str(x) for x in extras_series.loc[bad_extras_mask].dropna().unique())
        raise ValueError(f"Invalid or null extras_type value(s) detected: {bad_vals}")

    # Delivery event calculations (reusing Stage 4 extras_validator helpers)
    team_runs = pd.array(derive_team_runs(df), dtype="Int64")
    is_legal = pd.array(derive_is_legal_delivery(df), dtype="boolean")
    batter_runs = pd.array(df["runs"], dtype="Int64")
    extras1_runs = pd.array(df["extras1_runs"], dtype="Int64")
    extras_2_runs = pd.array(df["extras_2_runs"], dtype="Int64")
    is_boundary_four = pd.array(df["is_four"], dtype="boolean")
    is_boundary_six = pd.array(df["is_six"], dtype="boolean")

    is_wide = pd.array((extras_series == "wide"), dtype="boolean")
    is_no_ball = pd.array(extras_series.isin(["Overstep", "other"]), dtype="boolean")

    is_wicket_event = pd.array(df["is_wicket"], dtype="boolean")
    dismissed_raw = pd.array(df["dismissed_player_id"], dtype="Int64")
    dismissal_type_raw = pd.Series(df["dismissal_type"], index=df.index, dtype="string")
    dismissal_type_id = pd.array(df["dismissal_type_id"], dtype="Int64")

    wkt_bool = pd.Series(is_wicket_event, index=df.index).fillna(False).astype(bool)
    has_dis_pid = pd.Series(dismissed_raw, index=df.index).notna()

    is_retired_hurt_event = pd.array((~wkt_bool) & has_dis_pid, dtype="boolean")
    is_retire_out_event = pd.array(
        wkt_bool & (dismissal_type_raw == "Retire Out"), dtype="boolean"
    )

    dismissal_canonical = dismissal_type_raw.where(wkt_bool, pd.NA).astype("string")
    is_obstracting = (dismissal_canonical == "Obstracting the field").fillna(False)
    dismissal_canonical = dismissal_canonical.mask(is_obstracting, "Obstructing the field")
    dismissal_id_clean = pd.Series(dismissal_type_id, index=df.index).where(wkt_bool, pd.NA)
    dismissal_raw_clean = dismissal_type_raw.where(wkt_bool, pd.NA).astype("string")

    # Never fabricate missing dismissed_player_id from striker_id / non_striker_id
    resolved_dismissed_player_id = dismissed_raw.copy()
    is_dismissed_player_unresolved = pd.array(
        wkt_bool & pd.Series(dismissed_raw, index=df.index).isna(), dtype="boolean"
    )

    e2_pos = pd.Series(extras_2_runs, index=df.index) > 0
    is_extras_2_subtype_unresolved = pd.array(e2_pos, dtype="boolean")

    b_runs_s = pd.Series(batter_runs, index=df.index)
    e1_s = pd.Series(extras1_runs, index=df.index)
    four_s = pd.Series(is_boundary_four, index=df.index).fillna(False)
    six_s = pd.Series(is_boundary_six, index=df.index).fillna(False)

    scoring_uncertainty = (
        e2_pos
        | (
            (extras_series == "None")
            & (
                ((b_runs_s == 4) & ~four_s)
                | ((b_runs_s == 6) & ~six_s)
                | (b_runs_s == 5)
                | (e1_s > 0)
            )
        )
        | ((extras_series == "legbyes") & (b_runs_s > 0))
        | ((e1_s == 5) & extras_series.isin(["wide", "byes", "legbyes", "Penalty"]))
        | (extras_series == "other")
    )
    scoring_uncertainty_flag = pd.array(scoring_uncertainty, dtype="boolean")
    is_super_over_delivery = pd.array(df["innings"] >= 3, dtype="boolean")

    # Vectorized per-(match_id, innings) causal state accumulators
    work = pd.DataFrame(
        {
            "match_id": df["match_id"].astype("int64"),
            "innings": df["innings"].astype("int64"),
            "_tr": pd.Series(team_runs, index=df.index).astype("int64"),
            "_wkt": wkt_bool.astype("int64"),
            "_leg": pd.Series(is_legal, index=df.index).astype("int64"),
            "_rh": pd.Series(is_retired_hurt_event, index=df.index).astype("int64"),
        },
        index=df.index,
    )
    grp = work.groupby(["match_id", "innings"], sort=False)

    score_after = grp["_tr"].cumsum()
    score_before = score_after - work["_tr"]

    wickets_lost_after = grp["_wkt"].cumsum()
    wickets_lost_before = wickets_lost_after - work["_wkt"]
    wickets_remaining = (10 - wickets_lost_after).clip(lower=0)

    legal_balls_after = grp["_leg"].cumsum()
    legal_balls_before = legal_balls_after - work["_leg"]

    retired_hurt_after = grp["_rh"].cumsum()
    retired_hurt_before = retired_hurt_after - work["_rh"]

    state_df = pd.DataFrame(
        {
            "match_id": pd.array(df["match_id"], dtype="Int64"),
            "innings": pd.array(df["innings"], dtype="Int64"),
            "batting_team_id": pd.array(df["batting_team_id"], dtype="Int64"),
            "bowling_team_id": pd.array(df["bowling_team_id"], dtype="Int64"),
            "overid": pd.array(df["overid"], dtype="Int64"),
            "over_ball_num": pd.array(df["over_ball_num"], dtype="Int64"),
            "innings_ball_num": pd.array(df["innings_ball_num"], dtype="Int64"),
            "delivery_ist_time": pd.Series(df["delivery_ist_time"], index=df.index, dtype="string"),
            "striker_id": pd.array(df["striker_id"], dtype="Int64"),
            "non_striker_id": pd.array(df["non_striker_id"], dtype="Int64"),
            "bowler_id": pd.array(df["bowler_id"], dtype="Int64"),
            "batting_order": pd.array(df["batting_order"], dtype="Int64"),
            # Pre-delivery accumulators
            "score_before": pd.array(score_before, dtype="Int64"),
            "wickets_lost_before": pd.array(wickets_lost_before, dtype="Int64"),
            "legal_balls_completed_before": pd.array(legal_balls_before, dtype="Int64"),
            "retired_hurt_count_before": pd.array(retired_hurt_before, dtype="Int64"),
            # Delivery events
            "batter_runs": batter_runs,
            "extras_type": extras_series,
            "extras1_runs": extras1_runs,
            "extras_2_runs": extras_2_runs,
            "team_runs": team_runs,
            "is_legal_delivery": is_legal,
            "is_wide": is_wide,
            "is_no_ball": is_no_ball,
            "is_boundary_four": is_boundary_four,
            "is_boundary_six": is_boundary_six,
            "is_wicket_event": is_wicket_event,
            "is_retired_hurt_event": is_retired_hurt_event,
            "is_retire_out_event": is_retire_out_event,
            "dismissal_type_id": pd.array(dismissal_id_clean, dtype="Int64"),
            "dismissal_type_canonical": dismissal_canonical,
            "dismissal_type_raw": dismissal_raw_clean,
            "dismissed_player_id_raw": dismissed_raw,
            "resolved_dismissed_player_id": resolved_dismissed_player_id,
            "is_dismissed_player_unresolved": is_dismissed_player_unresolved,
            "is_extras_2_subtype_unresolved": is_extras_2_subtype_unresolved,
            "scoring_uncertainty_flag": scoring_uncertainty_flag,
            "is_super_over_delivery": is_super_over_delivery,
            # Post-delivery accumulators
            "score_after": pd.array(score_after, dtype="Int64"),
            "wickets_lost_after": pd.array(wickets_lost_after, dtype="Int64"),
            "wickets_remaining": pd.array(wickets_remaining, dtype="Int64"),
            "legal_balls_completed_after": pd.array(legal_balls_after, dtype="Int64"),
            "retired_hurt_count_after": pd.array(retired_hurt_after, dtype="Int64"),
        },
        index=df.index,
    )
    return state_df
