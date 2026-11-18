"""Comprehensive Stage 5B unit & integration tests (independent of full raw CSV corpus).

Covers all 28 mandatory test cases specified in Stage 5B §16 plus round-trip storage,
non-overwriting versioning, reconciliation halt gating, and spelling normalization.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from ml.ingestion.dataset_registry import DATASET_SPECS
from ml.match_state.eligibility import (
    classify_match_eligibility,
    derive_competition_category,
)
from ml.match_state.feature_deriver import derive_match_state_features
from ml.match_state.pipeline import (
    run_match_state_pipeline,
    run_match_state_pipeline_from_frames,
)
from ml.match_state.schema import (
    COLUMN_SPECS,
    EXPECTED_COLUMN_ORDER,
    MODEL_FEATURE_COLUMNS,
    REGIME_AUDIT_COLUMNS,
    TARGET_COLUMNS,
    UNRESOLVED_50407_AUDIT_STATUS,
    UNRESOLVED_50407_EXCLUSION_REASON,
    UNRESOLVED_50407_MATCH_ID,
)
from ml.match_state.state_builder import (
    DuplicateTransitionKeyError,
    InvalidTransitionKeyError,
    build_delivery_states,
)
from ml.match_state.validator import run_continuity_audit, validate_match_state_dataset
from ml.match_state.writer import (
    resolve_versioned_file_path,
    write_stage5b_outputs,
)


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def _make_delivery(
    *,
    match_id: int = 1001,
    innings: int = 1,
    overid: int = 1,
    over_ball_num: int = 1,
    innings_ball_num: int = 1,
    batting_team_id: int = 1,
    bowling_team_id: int = 2,
    striker_id: int = 101,
    non_striker_id: int = 102,
    bowler_id: int = 208,
    batting_order: int = 1,
    runs: int = 0,
    is_four: bool = False,
    is_six: bool = False,
    is_wicket: bool = False,
    dismissal_type_id: Any = pd.NA,
    dismissal_type: Any = pd.NA,
    dismissed_player_id: Any = pd.NA,
    extras_type: str = "None",
    extras1_runs: int = 0,
    extras_2_runs: int = 0,
    delivery_ist_time: str = "2025-05-01 14:00:00 UTC",
) -> dict[str, Any]:
    return {
        "match_id": match_id,
        "innings": innings,
        "overid": overid,
        "over_ball_num": over_ball_num,
        "innings_ball_num": innings_ball_num,
        "batting_team_id": batting_team_id,
        "bowling_team_id": bowling_team_id,
        "striker_id": striker_id,
        "striker_name": f"Player {striker_id}",
        "non_striker_id": non_striker_id,
        "non_striker_name": f"Player {non_striker_id}",
        "bowler_id": bowler_id,
        "bowler_name": f"Player {bowler_id}",
        "batting_type": "RHB",
        "bowling_type": "Right-arm Fast",
        "batting_order": batting_order,
        "runs": runs,
        "is_four": is_four,
        "is_six": is_six,
        "is_wicket": is_wicket,
        "dismissal_type_id": dismissal_type_id,
        "dismissal_type": dismissal_type,
        "dismissed_player_id": dismissed_player_id,
        "extras_type": extras_type,
        "extras1_runs": extras1_runs,
        "extras_2_runs": extras_2_runs,
        "pace_or_spin": "Pace",
        "bowl_speed": 135.0,
        "stroke": "Drive",
        "delivery_style": "Good",
        "over_or_around": "Over",
        "on_or_off": "Off-side",
        "delivery_ist_time": delivery_ist_time,
    }


def _to_bbb_df(rows: list[dict[str, Any]]) -> pd.DataFrame:
    df = pd.DataFrame(rows)
    for col in (
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
        "dismissal_type_id",
        "dismissed_player_id",
        "extras1_runs",
        "extras_2_runs",
    ):
        df[col] = pd.array(df[col], dtype="Int64")
    for col in ("is_four", "is_six", "is_wicket"):
        df[col] = pd.array(df[col], dtype="boolean")
    for col in (
        "striker_name",
        "non_striker_name",
        "bowler_name",
        "batting_type",
        "bowling_type",
        "dismissal_type",
        "extras_type",
        "pace_or_spin",
        "stroke",
        "delivery_style",
        "over_or_around",
        "on_or_off",
        "delivery_ist_time",
    ):
        df[col] = pd.Series(df[col], dtype="string")
    df["bowl_speed"] = pd.array(df["bowl_speed"], dtype="Float64")
    return df


def _make_competitions_df(rows: list[dict[str, Any]]) -> pd.DataFrame:
    df = pd.DataFrame(rows)
    df["comp_id"] = pd.array(df["comp_id"], dtype="Int64")
    for col in ("comp_name", "match_format", "season"):
        df[col] = pd.Series(df[col], dtype="string")
    return df


def _make_matches_df(rows: list[dict[str, Any]]) -> pd.DataFrame:
    defaults = {
        "comp_id": 100,
        "match_number": 1,
        "match_date": "2025-05-01",
        "stage": "League",
        "venue_id": 10,
        "venue_country": "India",
        "home_team_id": 1,
        "home_team": "Team 1",
        "away_team_id": 2,
        "away_team": "Team 2",
        "home_team_captain_id": 101,
        "away_team_captain_id": 201,
        "toss_win_team_id": 1,
        "toss_opted": "Batting",
        "man_of_the_match": "0",
        "first_inn_revised_overs": pd.NA,
        "second_inn_revised_overs": pd.NA,
        "revised_target": pd.NA,
        "knock_out": 0,
        "win_team_id": 2,
        "result": "Team 2 Won by 10 wickets",
    }
    full_rows = [{**defaults, **r} for r in rows]
    df = pd.DataFrame(full_rows)
    for col in (
        "match_id",
        "comp_id",
        "match_number",
        "venue_id",
        "home_team_id",
        "away_team_id",
        "home_team_captain_id",
        "away_team_captain_id",
        "toss_win_team_id",
        "first_inn_revised_overs",
        "second_inn_revised_overs",
        "revised_target",
        "knock_out",
        "win_team_id",
    ):
        df[col] = pd.array(df[col], dtype="Int64")
    for col in (
        "match_date",
        "stage",
        "venue_country",
        "home_team",
        "away_team",
        "toss_opted",
        "man_of_the_match",
        "result",
    ):
        df[col] = pd.Series(df[col], dtype="string")
    return df


def _make_standard_20over_innings_rows(
    *,
    match_id: int,
    innings: int,
    batting_team_id: int,
    bowling_team_id: int,
    runs_per_ball: int = 1,
    num_overs: int = 20,
    wickets_on_balls: dict[int, tuple[int, str, int | None]] | None = None,
    extras_override: dict[int, tuple[str, int, int, int]] | None = None,
    batting_order_override: dict[int, int] | None = None,
    reversed_timestamps: bool = False,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    ib = 0
    wickets_on_balls = wickets_on_balls or {}
    extras_override = extras_override or {}
    batting_order_override = batting_order_override or {}
    for ov in range(1, num_overs + 1):
        for ob in range(1, 7):
            ib += 1
            bat_r = runs_per_ball
            et, e1, e2 = "None", 0, 0
            if ib in extras_override:
                et, bat_r, e1, e2 = extras_override[ib]
            is_wkt = False
            did: Any = pd.NA
            dt: Any = pd.NA
            dp: Any = pd.NA
            if ib in wickets_on_balls:
                wid, wtype, wdp = wickets_on_balls[ib]
                is_wkt = wtype != "Retired Hurt"
                if is_wkt:
                    did = wid
                    dt = wtype
                dp = pd.NA if wdp is None else wdp
            ts_sec = (1000 - ib) if reversed_timestamps else ib
            mm, ss = divmod(ts_sec, 60)
            hh, mm2 = divmod(mm, 60)
            rows.append(
                _make_delivery(
                    match_id=match_id,
                    innings=innings,
                    overid=ov,
                    over_ball_num=ob,
                    innings_ball_num=ib,
                    batting_team_id=batting_team_id,
                    bowling_team_id=bowling_team_id,
                    striker_id=batting_team_id * 100 + 1,
                    non_striker_id=batting_team_id * 100 + 2,
                    bowler_id=bowling_team_id * 100 + 8,
                    batting_order=batting_order_override.get(ib, 1),
                    runs=bat_r,
                    is_four=(bat_r == 4 and et == "None"),
                    is_six=(bat_r == 6 and et == "None"),
                    is_wicket=is_wkt,
                    dismissal_type_id=did,
                    dismissal_type=dt,
                    dismissed_player_id=dp,
                    extras_type=et,
                    extras1_runs=e1,
                    extras_2_runs=e2,
                    delivery_ist_time=f"2025-05-01 {14 + hh:02d}:{mm2:02d}:{ss:02d} UTC",
                )
            )
    return rows


def _make_full_clean_match_bundle(
    *,
    match_id: int = 1001,
    comp_id: int = 100,
    comp_name: str = "IPL 2025",
    match_format: str = "T20",
    match_date: str = "2025-05-01",
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    comps = _make_competitions_df(
        [{"comp_id": comp_id, "comp_name": comp_name, "match_format": match_format, "season": "2025"}]
    )
    inn1 = _make_standard_20over_innings_rows(
        match_id=match_id, innings=1, batting_team_id=1, bowling_team_id=2, runs_per_ball=1
    )  # 120 runs in 120 balls
    inn2 = _make_standard_20over_innings_rows(
        match_id=match_id, innings=2, batting_team_id=2, bowling_team_id=1, runs_per_ball=1
    )
    # Bump final ball of inn2 from 1 to 2 runs -> 121 runs chasing 121 -> won by 10 wickets
    inn2[-1]["runs"] = 2
    matches = _make_matches_df(
        [
            {
                "match_id": match_id,
                "comp_id": comp_id,
                "match_date": match_date,
                "win_team_id": 2,
                "result": "Team 2 Won by 10 wickets",
            }
        ]
    )
    return _to_bbb_df(inn1 + inn2), matches, comps


# ---------------------------------------------------------------------------
# Tests 1–9: Delivery scoring, legal balls, boundary flags, wickets & retirements
# ---------------------------------------------------------------------------


def test_01_to_06_scoring_legal_deliveries_extras_and_boundary_flags() -> None:
    """Covers tests 1–6: ordinary legal, wide, Overstep, other, runs+extras, unused boundary flags."""
    rows = [
        # 1) Ordinary legal delivery: 1 run
        _make_delivery(innings_ball_num=1, overid=1, over_ball_num=1, runs=1, extras_type="None"),
        # 2) Wide delivery: +2 wides, non-legal
        _make_delivery(innings_ball_num=2, overid=1, over_ball_num=2, runs=0, extras_type="wide", extras1_runs=2),
        # 3) Overstep delivery: 1 nb + 4 bat = 5 team runs, non-legal
        _make_delivery(innings_ball_num=3, overid=1, over_ball_num=3, runs=4, is_four=True, extras_type="Overstep", extras1_runs=1),
        # 4) 'other' extras category: 1 nb + 1 bye (extras_2_runs=1) = 2 team runs, non-legal, uncertainty flagged
        _make_delivery(innings_ball_num=4, overid=1, over_ball_num=4, runs=0, extras_type="other", extras1_runs=1, extras_2_runs=1),
        # 5) Batter runs + extras anomaly pattern or legal boundary without is_four flag: runs=4, is_four=False -> team_runs=4
        _make_delivery(innings_ball_num=5, overid=1, over_ball_num=5, runs=4, is_four=False, extras_type="None"),
        # 6) Spurious is_six=True with runs=0 -> team_runs must stay 0 (boundary flags NEVER drive runs)
        _make_delivery(innings_ball_num=6, overid=1, over_ball_num=6, runs=0, is_six=True, extras_type="None"),
        # 7) Penalty legal delivery (+5 extras, counts as legal)
        _make_delivery(innings_ball_num=7, overid=1, over_ball_num=7, runs=0, extras_type="Penalty", extras1_runs=5),
    ]
    st = build_delivery_states(_to_bbb_df(rows))

    # Row 0: ordinary legal
    assert st.at[0, "score_before"] == 0 and st.at[0, "score_after"] == 1
    assert st.at[0, "legal_balls_completed_before"] == 0 and st.at[0, "legal_balls_completed_after"] == 1
    assert bool(st.at[0, "is_legal_delivery"]) is True
    assert st.at[0, "extras_type"] == "None"  # literal 'None' preserved

    # Row 1: wide
    assert st.at[1, "team_runs"] == 2
    assert bool(st.at[1, "is_wide"]) is True and bool(st.at[1, "is_legal_delivery"]) is False
    assert st.at[1, "legal_balls_completed_before"] == 1 and st.at[1, "legal_balls_completed_after"] == 1

    # Row 2: Overstep + batter runs
    assert st.at[2, "batter_runs"] == 4 and st.at[2, "extras1_runs"] == 1 and st.at[2, "team_runs"] == 5
    assert bool(st.at[2, "is_no_ball"]) is True and bool(st.at[2, "is_legal_delivery"]) is False
    assert st.at[2, "score_after"] == 8 and st.at[2, "legal_balls_completed_after"] == 1

    # Row 3: 'other' provisional non-legal + extras_2_runs
    assert st.at[3, "team_runs"] == 2
    assert bool(st.at[3, "is_no_ball"]) is True and bool(st.at[3, "is_legal_delivery"]) is False
    assert bool(st.at[3, "is_extras_2_subtype_unresolved"]) is True
    assert bool(st.at[3, "scoring_uncertainty_flag"]) is True
    assert st.at[3, "score_after"] == 10 and st.at[3, "legal_balls_completed_after"] == 1

    # Row 4: boundary flag False with runs=4 -> team_runs=4, flagged uncertain
    assert st.at[4, "team_runs"] == 4 and st.at[4, "score_after"] == 14
    assert bool(st.at[4, "is_legal_delivery"]) is True
    assert bool(st.at[4, "scoring_uncertainty_flag"]) is True

    # Row 5: spurious is_six=True with runs=0 -> team_runs=0
    assert st.at[5, "team_runs"] == 0 and st.at[5, "score_after"] == 14
    assert st.at[5, "legal_balls_completed_after"] == 3

    # Row 6: Penalty counts as +1 legal ball and +5 team runs
    assert st.at[6, "team_runs"] == 5 and st.at[6, "score_after"] == 19
    assert bool(st.at[6, "is_legal_delivery"]) is True
    assert st.at[6, "legal_balls_completed_after"] == 4


def test_07_to_09_wickets_retired_hurt_retire_out_and_missing_dismissed_id() -> None:
    """Covers tests 7–9: official wicket, spelling normalization, Retired Hurt (+0), Retire Out (+1, missing ID)."""
    rows = [
        # Official wicket 1: Obstracting spelling typo -> normalized canonical
        _make_delivery(
            innings_ball_num=1,
            overid=1,
            over_ball_num=1,
            is_wicket=True,
            dismissal_type_id=10,
            dismissal_type="Obstracting the field",
            dismissed_player_id=101,
        ),
        # Retired Hurt: is_wicket=False with dismissed_player_id=102 -> +0 official wickets, +1 retired_hurt_count
        _make_delivery(
            innings_ball_num=2,
            overid=1,
            over_ball_num=2,
            striker_id=103,
            non_striker_id=102,
            batting_order=3,
            is_wicket=False,
            dismissal_type_id=pd.NA,
            dismissal_type=pd.NA,
            dismissed_player_id=102,
        ),
        # Retire Out WITH missing dismissed_player_id (like 40709 2.19.5): +1 official wicket, NO fabrication!
        _make_delivery(
            match_id=40709,
            innings=2,
            innings_ball_num=1,
            overid=19,
            over_ball_num=5,
            striker_id=3330,
            non_striker_id=2970,
            is_wicket=True,
            dismissal_type_id=9,
            dismissal_type="Retire Out",
            dismissed_player_id=pd.NA,
        ),
    ]
    st = build_delivery_states(_to_bbb_df(rows))

    # Row 0 (match 1001, ib=1): official wicket + spelling normalization
    r0 = st.loc[(st["match_id"] == 1001) & (st["innings_ball_num"] == 1)].iloc[0]
    assert r0["wickets_lost_before"] == 0 and r0["wickets_lost_after"] == 1
    assert r0["dismissal_type_raw"] == "Obstracting the field"
    assert r0["dismissal_type_canonical"] == "Obstructing the field"
    assert bool(r0["is_dismissed_player_unresolved"]) is False

    # Row 1 (match 1001, ib=2): Retired Hurt
    r1 = st.loc[(st["match_id"] == 1001) & (st["innings_ball_num"] == 2)].iloc[0]
    assert bool(r1["is_wicket_event"]) is False
    assert bool(r1["is_retired_hurt_event"]) is True
    assert r1["wickets_lost_before"] == 1 and r1["wickets_lost_after"] == 1  # +0 official wickets!
    assert r1["retired_hurt_count_before"] == 0 and r1["retired_hurt_count_after"] == 1
    assert pd.isna(r1["dismissal_type_canonical"]) and pd.isna(r1["dismissal_type_id"])

    # Row 2 (match 40709, ib=1): Retire Out missing ID
    r2 = st.loc[st["match_id"] == 40709].iloc[0]
    assert bool(r2["is_wicket_event"]) is True
    assert bool(r2["is_retire_out_event"]) is True
    assert r2["wickets_lost_before"] == 0 and r2["wickets_lost_after"] == 1
    assert pd.isna(r2["dismissed_player_id_raw"])
    assert pd.isna(r2["resolved_dismissed_player_id"])  # NEVER fabricated as striker_id 3330!
    assert bool(r2["is_dismissed_player_unresolved"]) is True


# ---------------------------------------------------------------------------
# Tests 10–19: Innings 1 vs 2, Zero-ball, Limits, Negative Rem, RRR guards, Resets
# ---------------------------------------------------------------------------


def test_10_to_12_and_18_19_innings1_innings2_zero_ball_and_resets() -> None:
    """Covers tests 10, 11, 12, 18, 19: Inn1 null chase, Inn2 chase math, L_b=0 CRR=0, match/innings resets."""
    bbb1, m1, comps = _make_full_clean_match_bundle(match_id=1001)
    # Match 1002: opens Innings 2 with a wide (zero legal balls completed on first delivery)
    inn1_2 = _make_standard_20over_innings_rows(
        match_id=1002, innings=1, batting_team_id=1, bowling_team_id=2, runs_per_ball=1
    )
    inn2_2 = _make_standard_20over_innings_rows(
        match_id=1002, innings=2, batting_team_id=2, bowling_team_id=1, runs_per_ball=1
    )
    # Prepend opening wide in match 1002 inn 2 and adjust innings_ball_num
    wide_open = _make_delivery(
        match_id=1002,
        innings=2,
        overid=1,
        over_ball_num=1,
        innings_ball_num=1,
        batting_team_id=2,
        bowling_team_id=1,
        extras_type="wide",
        extras1_runs=1,
    )
    for idx_r, r in enumerate(inn2_2):
        r["innings_ball_num"] = idx_r + 2
        if r["overid"] == 1:
            r["over_ball_num"] += 1
    inn2_2 = [wide_open] + inn2_2

    matches = pd.concat(
        [
            m1,
            _make_matches_df(
                [
                    {
                        "match_id": 1002,
                        "comp_id": 100,
                        "match_date": "2025-05-02",
                        "toss_win_team_id": 1,
                        "win_team_id": 2,
                        "result": "Team 2 Won by 10 wickets",
                    }
                ]
            ),
        ],
        ignore_index=True,
    )
    bbb = pd.concat([bbb1, _to_bbb_df(inn1_2 + inn2_2)], ignore_index=True)

    elg = classify_match_eligibility(matches, comps, bbb)
    out = derive_match_state_features(build_delivery_states(bbb), elg)

    # 10) First innings chase fields strictly pd.NA
    inn1_rows = out.loc[out["innings"] == 1]
    for c in (
        "innings1_total_score",
        "target_runs",
        "runs_required_before",
        "runs_required_after",
        "required_run_rate",
        "rrr_minus_crr",
    ):
        assert int(inn1_rows[c].notna().sum()) == 0, f"Innings 1 leaked {c}"
    assert bool((inn1_rows["chase_completion_status"] == "not_chase").all())
    assert bool((inn1_rows["target_source"] == "not_applicable_inn1").all())
    assert bool((inn1_rows["is_batting_team_toss_winner"]).all())  # Team 1 won toss & bats Inn 1

    # 11 & 12) Match 1002 Inn 2 first delivery (wide at L_b == 0)
    m2_i2_b1 = out.loc[
        (out["match_id"] == 1002) & (out["innings"] == 2) & (out["innings_ball_num"] == 1)
    ].iloc[0]
    assert m2_i2_b1["score_before"] == 0 and m2_i2_b1["score_after"] == 1
    assert m2_i2_b1["legal_balls_completed_after"] == 0
    assert bool(m2_i2_b1["has_legal_balls_completed"]) is False
    assert m2_i2_b1["current_run_rate"] == pytest.approx(0.0)
    assert pd.isna(m2_i2_b1["rrr_minus_crr"])  # undefined until L_b > 0
    assert m2_i2_b1["innings1_total_score"] == 120
    assert m2_i2_b1["target_runs"] == 121
    assert m2_i2_b1["runs_required_before"] == 121 and m2_i2_b1["runs_required_after"] == 120
    assert m2_i2_b1["legal_balls_remaining_before"] == 120 and m2_i2_b1["legal_balls_remaining"] == 120
    assert m2_i2_b1["required_run_rate"] == pytest.approx(6.0 * 120 / 120)
    assert bool(m2_i2_b1["is_batting_team_toss_winner"]) is False  # swapped in Inn 2

    # 18 & 19) Match boundary & innings boundary resets
    m1_i2_b1 = out.loc[
        (out["match_id"] == 1001) & (out["innings"] == 2) & (out["innings_ball_num"] == 1)
    ].iloc[0]
    assert m1_i2_b1["score_before"] == 0
    assert m1_i2_b1["wickets_lost_before"] == 0
    assert m1_i2_b1["legal_balls_completed_before"] == 0
    assert m1_i2_b1["retired_hurt_count_before"] == 0

    m2_i1_b1 = out.loc[
        (out["match_id"] == 1002) & (out["innings"] == 1) & (out["innings_ball_num"] == 1)
    ].iloc[0]
    assert m2_i1_b1["score_before"] == 0
    assert m2_i1_b1["legal_balls_completed_before"] == 0


def test_13_to_17_innings_limits_negative_rem_zero_rrr_and_undefined_rrr() -> None:
    """Covers tests 13–17: verified revised limit (72b), missing limit, negative remaining balls, RRR=0, RRR=pd.NA."""
    comps = _make_competitions_df(
        [{"comp_id": 100, "comp_name": "Test T20", "match_format": "T20", "season": "2025"}]
    )

    # Match 2001: DLS match with verified limits rev1=72, rev2=72, revised_target=75 (legal-ball unit!)
    dls_inn1 = _make_standard_20over_innings_rows(
        match_id=2001, innings=1, batting_team_id=1, bowling_team_id=2, runs_per_ball=1, num_overs=12
    )  # 72b
    dls_inn2 = _make_standard_20over_innings_rows(
        match_id=2001, innings=2, batting_team_id=2, bowling_team_id=1, runs_per_ball=1, num_overs=12
    )  # reaches 75 by bumping final ball to 4 runs -> RRR=0.0 at winning ball!
    dls_inn2[-1]["runs"] = 4

    # Match 2002: DLS match MISSING revised_overs and revised_target
    miss_inn1 = _make_standard_20over_innings_rows(
        match_id=2002, innings=1, batting_team_id=1, bowling_team_id=2, runs_per_ball=1, num_overs=10
    )
    miss_inn2 = _make_standard_20over_innings_rows(
        match_id=2002, innings=2, batting_team_id=2, bowling_team_id=1, runs_per_ball=1, num_overs=8
    )

    # Match 2003: STANDARD_T20 chase loses with req > 0 at legal_balls_remaining == 0 -> undefined RRR
    lost_inn1 = _make_standard_20over_innings_rows(
        match_id=2003, innings=1, batting_team_id=1, bowling_team_id=2, runs_per_ball=2, num_overs=20
    )  # 240
    lost_inn2 = _make_standard_20over_innings_rows(
        match_id=2003, innings=2, batting_team_id=2, bowling_team_id=1, runs_per_ball=1, num_overs=20
    )  # 120 -> lost by 120 runs

    # Match 2004: Artificial negative legal_balls_remaining (over-count 21 overs = 126b in STANDARD_T20)
    neg_inn1 = _make_standard_20over_innings_rows(
        match_id=2004, innings=1, batting_team_id=1, bowling_team_id=2, runs_per_ball=1, num_overs=21
    )  # 126 runs in 126b (> 120 regulation cap)
    neg_inn2 = _make_standard_20over_innings_rows(
        match_id=2004, innings=2, batting_team_id=2, bowling_team_id=1, runs_per_ball=1, num_overs=20
    )  # 120 runs in 120b -> Team 1 wins by 6 runs

    matches = _make_matches_df(
        [
            {
                "match_id": 2001,
                "first_inn_revised_overs": 72,
                "second_inn_revised_overs": 72,
                "revised_target": 75,
                "win_team_id": 2,
                "result": "Team 2 Won by 10 wickets (DLS)",
            },
            {
                "match_id": 2002,
                "first_inn_revised_overs": pd.NA,
                "second_inn_revised_overs": pd.NA,
                "revised_target": pd.NA,
                "win_team_id": 2,
                "result": "Team 2 Won by 10 wickets (D/L)",
            },
            {
                "match_id": 2003,
                "win_team_id": 1,
                "result": "Team 1 Won by 120 runs",
            },
            {
                "match_id": 2004,
                "win_team_id": 1,
                "result": "Team 1 Won by 6 runs",
            },
        ]
    )
    bbb = _to_bbb_df(dls_inn1 + dls_inn2 + miss_inn1 + miss_inn2 + lost_inn1 + lost_inn2 + neg_inn1 + neg_inn2)
    elg = classify_match_eligibility(matches, comps, bbb)
    out = derive_match_state_features(build_delivery_states(bbb), elg)

    # 13 & 16) Match 2001: verified 72-ball cap + RRR==0.0 on target_achieved
    m2001_end = out.loc[(out["match_id"] == 2001) & (out["innings"] == 2)].iloc[-1]
    assert m2001_end["innings_ball_limit"] == 72
    assert bool(m2001_end["is_innings_limit_verified"]) is True
    assert m2001_end["innings_limit_source"] == "second_inn_revised_overs"
    assert pd.isna(m2001_end["innings_limit_unavailable_reason"])
    assert m2001_end["legal_balls_remaining"] == 0
    assert m2001_end["runs_required_after"] == 0
    assert m2001_end["required_run_rate"] == pytest.approx(0.0)
    assert bool(m2001_end["is_rrr_undefined"]) is False
    assert m2001_end["chase_completion_status"] == "target_achieved"
    assert m2001_end["innings_phase"] == "revised_or_unverified"

    # 14) Match 2002: missing limit -> pd.NA (never 0 or 120)
    m2002_i2 = out.loc[(out["match_id"] == 2002) & (out["innings"] == 2)].iloc[-1]
    assert bool(m2002_i2["is_innings_limit_verified"]) is False
    assert pd.isna(m2002_i2["innings_ball_limit"])
    assert pd.isna(m2002_i2["legal_balls_remaining"])
    assert pd.isna(m2002_i2["legal_balls_remaining_before"])
    assert pd.isna(m2002_i2["innings_progress_pct"])
    assert pd.isna(m2002_i2["required_run_rate"])
    assert m2002_i2["innings_limit_source"] == "unavailable"
    assert pd.notna(m2002_i2["innings_limit_unavailable_reason"])

    # 17) Match 2003: balls exhausted with runs required > 0 -> RRR pd.NA
    m2003_end = out.loc[(out["match_id"] == 2003) & (out["innings"] == 2)].iloc[-1]
    assert m2003_end["legal_balls_remaining"] == 0
    assert m2003_end["runs_required_after"] == 121
    assert pd.isna(m2003_end["required_run_rate"])
    assert bool(m2003_end["is_rrr_undefined"]) is True
    assert pd.isna(m2003_end["rrr_minus_crr"])
    assert m2003_end["chase_completion_status"] == "balls_exhausted_lost"

    # 15) Match 2004: negative remaining balls retained un-clamped, flagged, excluded from primary, and caught by validator
    m2004_neg = out.loc[(out["match_id"] == 2004) & (out["innings"] == 1)].iloc[-1]
    assert m2004_neg["legal_balls_remaining"] == -6  # un-clamped 120 - 126
    assert bool(m2004_neg["is_legal_balls_remaining_negative"]) is True
    assert bool(m2004_neg["is_primary_wp_train_eligible"]) is False

    pri = out.loc[out["is_primary_wp_train_eligible"].fillna(False)].reset_index(drop=True)
    val = validate_match_state_dataset(
        all_states_df=out,
        primary_states_df=pri,
        eligibility_df=elg,
        raw_ball_by_ball=bbb,
        raw_matches=matches,
        raw_competitions=comps,
    )
    by_rule = {r.rule_id: r for r in val["results"]}
    assert val["has_critical_failure"] is True
    assert by_rule["VAL-5B-LIM-001"].status.value == "FAIL"
    assert by_rule["VAL-5B-LIM-001"].metadata["negative_legal_balls_remaining_all"] == 6


# ---------------------------------------------------------------------------
# Tests 20–25: Continuity, Exclusions (50407, DLS, SO, Tied), Duplicate Keys
# ---------------------------------------------------------------------------


def test_20_consecutive_continuity_pass_and_injected_break_detection() -> None:
    """Covers test 20: clean continuity passes (0 breaks), tampered state is immediately caught."""
    bbb, matches, comps = _make_full_clean_match_bundle(match_id=3001)
    elg = classify_match_eligibility(matches, comps, bbb)
    out = derive_match_state_features(build_delivery_states(bbb), elg)

    clean_audit = run_continuity_audit(out, elg)
    assert clean_audit.unexpected_break_count == 0
    assert clean_audit.documented_discontinuity_count == 0
    assert len(clean_audit.audit_df) == 0

    # Inject continuity break on row 5 (state_before != prev state_after) + step mismatch
    tampered = out.copy()
    tampered.loc[5, "score_before"] = tampered.loc[5, "score_before"] + 9
    bad_audit = run_continuity_audit(tampered, elg)
    assert bad_audit.unexpected_break_count >= 2  # consecutive score break + score_step break
    assert "UNEXPECTED_CONTINUITY_BREAK" in set(bad_audit.audit_df["classification"])
    assert "STEP_EQUATION_VIOLATION" in set(bad_audit.audit_df["classification"])


def test_21_to_24_regimes_and_quarantine_exclusions() -> None:
    """Covers tests 21–24: 50407 UNRESOLVED, DLS exclusion, Super Over exclusion, Tied match target pd.NA."""
    comps = _make_competitions_df(
        [{"comp_id": 100, "comp_name": "Series T20I", "match_format": "T20I", "season": "2026"}]
    )

    # Match 50407-like unresolved premature stoppage at 20.5 without wicket (9 wickets fell by 19.6)
    inn1_50407 = _make_standard_20over_innings_rows(
        match_id=UNRESOLVED_50407_MATCH_ID,
        innings=1,
        batting_team_id=28,
        bowling_team_id=18,
        runs_per_ball=2,
        num_overs=20,
    )
    inn2_50407_rows = _make_standard_20over_innings_rows(
        match_id=UNRESOLVED_50407_MATCH_ID,
        innings=2,
        batting_team_id=18,
        bowling_team_id=28,
        runs_per_ball=1,
        num_overs=19,
        wickets_on_balls={i * 12: (2, "Caught", 1801) for i in range(1, 10)},
    )  # 9 wickets in 19 overs (114 balls)
    # Over 20 stops after 5 deliveries (3 legal balls + 2 wides = 117 legal balls, 0 wickets in ov20)
    inn2_50407_rows.extend(
        [
            _make_delivery(match_id=50407, innings=2, overid=20, over_ball_num=1, innings_ball_num=115, batting_team_id=18, bowling_team_id=28, runs=4),
            _make_delivery(match_id=50407, innings=2, overid=20, over_ball_num=2, innings_ball_num=116, batting_team_id=18, bowling_team_id=28, extras_type="wide", extras1_runs=1),
            _make_delivery(match_id=50407, innings=2, overid=20, over_ball_num=3, innings_ball_num=117, batting_team_id=18, bowling_team_id=28, runs=0),
            _make_delivery(match_id=50407, innings=2, overid=20, over_ball_num=4, innings_ball_num=118, batting_team_id=18, bowling_team_id=28, runs=0),
            _make_delivery(match_id=50407, innings=2, overid=20, over_ball_num=5, innings_ball_num=119, batting_team_id=18, bowling_team_id=28, extras_type="wide", extras1_runs=5),
        ]
    )

    # DLS match 4001
    inn1_dls = _make_standard_20over_innings_rows(match_id=4001, innings=1, batting_team_id=18, bowling_team_id=28, runs_per_ball=1, num_overs=10)
    inn2_dls = _make_standard_20over_innings_rows(match_id=4001, innings=2, batting_team_id=28, bowling_team_id=18, runs_per_ball=2, num_overs=10)

    # Super Over match 4002 (equal reg scores + inn 3/4)
    inn1_so = _make_standard_20over_innings_rows(match_id=4002, innings=1, batting_team_id=18, bowling_team_id=28, runs_per_ball=1, num_overs=20)
    inn2_so = _make_standard_20over_innings_rows(match_id=4002, innings=2, batting_team_id=28, bowling_team_id=18, runs_per_ball=1, num_overs=20)
    inn3_so = [_make_delivery(match_id=4002, innings=3, overid=1, over_ball_num=i, innings_ball_num=i, batting_team_id=28, bowling_team_id=18, runs=2) for i in range(1, 7)]
    inn4_so = [_make_delivery(match_id=4002, innings=4, overid=1, over_ball_num=i, innings_ball_num=i, batting_team_id=18, bowling_team_id=28, runs=1) for i in range(1, 7)]

    # Tied match without Super Over 4003
    inn1_tied = _make_standard_20over_innings_rows(match_id=4003, innings=1, batting_team_id=18, bowling_team_id=28, runs_per_ball=1, num_overs=20)
    inn2_tied = _make_standard_20over_innings_rows(match_id=4003, innings=2, batting_team_id=28, bowling_team_id=18, runs_per_ball=1, num_overs=20)

    matches = _make_matches_df(
        [
            {
                "match_id": 50407,
                "home_team_id": 18,
                "away_team_id": 28,
                "win_team_id": 28,
                "result": "Team 28 Won by runs",
            },
            {
                "match_id": 4001,
                "home_team_id": 18,
                "away_team_id": 28,
                "first_inn_revised_overs": 60,
                "second_inn_revised_overs": 60,
                "revised_target": 61,
                "win_team_id": 28,
                "result": "Team 28 Won by 10 wickets (DLS)",
            },
            {
                "match_id": 4002,
                "home_team_id": 18,
                "away_team_id": 28,
                "win_team_id": 28,
                "result": "Match Tied (Team 28 Won via Super Over)",
            },
            {
                "match_id": 4003,
                "home_team_id": 18,
                "away_team_id": 28,
                "win_team_id": pd.NA,
                "result": "Match Tied",
            },
        ]
    )

    bbb = _to_bbb_df(inn1_50407 + inn2_50407_rows + inn1_dls + inn2_dls + inn3_so + inn4_so + inn1_so + inn2_so + inn1_tied + inn2_tied)
    elg = classify_match_eligibility(matches, comps, bbb)
    out = derive_match_state_features(build_delivery_states(bbb), elg)

    elg_idx = elg.set_index("match_id")
    # 21) Match 50407 quarantine
    assert elg_idx.at[50407, "match_regime"] == "INCOMPLETE_OR_UNRESOLVED"
    assert bool(elg_idx.at[50407, "is_primary_wp_train_eligible"]) is False
    assert elg_idx.at[50407, "eligibility_exclusion_reason"] == UNRESOLVED_50407_EXCLUSION_REASON
    assert elg_idx.at[50407, "audit_status_note"] == UNRESOLVED_50407_AUDIT_STATUS
    rows_50407 = out.loc[out["match_id"] == 50407]
    assert bool((~rows_50407["is_innings_limit_verified"]).all())
    assert int(rows_50407["legal_balls_remaining"].notna().sum()) == 0
    assert bool((rows_50407["terminal_innings_status_audit"] == "unresolved_50407").all())

    # Check continuity audit logs 50407 termination discontinuity cleanly
    cnt = run_continuity_audit(out, elg)
    assert cnt.unexpected_break_count == 0
    assert cnt.unresolved_termination_count == 1
    assert cnt.audit_df.iloc[0]["resolution_status"] == UNRESOLVED_50407_AUDIT_STATUS

    # 22) DLS exclusion
    assert elg_idx.at[4001, "match_regime"] == "REVISED_OVERS_DLS"
    assert bool(elg_idx.at[4001, "is_primary_wp_train_eligible"]) is False
    assert bool(elg_idx.at[4001, "is_dls_eval_slice_eligible"]) is True
    assert elg_idx.at[4001, "eligibility_exclusion_reason"] == "dls_or_revised_overs"

    # 23) Super Over exclusion + 6-ball regulation
    assert elg_idx.at[4002, "match_regime"] == "SUPER_OVER"
    assert bool(elg_idx.at[4002, "is_primary_wp_train_eligible"]) is False
    rows_so_34 = out.loc[(out["match_id"] == 4002) & (out["innings"] >= 3)]
    assert bool((rows_so_34["innings_ball_limit"] == 6).all())
    assert bool((rows_so_34["is_super_over_delivery"]).all())
    assert bool((rows_so_34["eligibility_exclusion_reason"] == "super_over_innings").all())
    rows_so_12 = out.loc[(out["match_id"] == 4002) & (out["innings"].isin([1, 2]))]
    assert bool((rows_so_12["eligibility_exclusion_reason"] == "tied_after_regulation").all())

    # 24) Tied match target pd.NA
    assert elg_idx.at[4003, "match_regime"] == "TIED"
    assert bool(elg_idx.at[4003, "is_primary_wp_train_eligible"]) is False
    rows_tied = out.loc[out["match_id"] == 4003]
    assert int(rows_tied["target_batting_team_win"].notna().sum()) == 0
    assert int(rows_tied["target_home_team_win"].notna().sum()) == 0
    assert bool((rows_tied["eligibility_exclusion_reason"] == "tied_no_winner").all())

    # Primary slice strictly empty (0 of 4 matches eligible)
    assert int(out["is_primary_wp_train_eligible"].sum()) == 0


def test_25_duplicate_and_null_transition_key_detection() -> None:
    """Covers test 25: duplicate or null (match_id, innings, innings_ball_num) raises explicit error."""
    dup_df = _to_bbb_df(
        [
            _make_delivery(innings_ball_num=1),
            _make_delivery(innings_ball_num=1),
        ]
    )
    with pytest.raises(DuplicateTransitionKeyError):
        build_delivery_states(dup_df)

    null_df = _to_bbb_df([_make_delivery(innings_ball_num=1)])
    null_df["innings_ball_num"] = pd.array([pd.NA], dtype="Int64")
    with pytest.raises(InvalidTransitionKeyError):
        build_delivery_states(null_df)


# ---------------------------------------------------------------------------
# Tests 26–28 + Storage Round-Trip & Versioning: Metadata, Ordering, Immutability
# ---------------------------------------------------------------------------


def test_26_competition_metadata_preservation_never_uses_team_names() -> None:
    """Covers test 26: original comp metadata intact; category NEVER inferred from team names."""
    comps = _make_competitions_df(
        [
            {"comp_id": 1, "comp_name": "IPL 2025", "match_format": "T20", "season": "2025"},
            {"comp_id": 2, "comp_name": "IL T20 2025", "match_format": "T20", "season": "2024-25"},
            {"comp_id": 3, "comp_name": "Bilateral India T20I", "match_format": "T20I", "season": "2025/26"},
        ]
    )
    cats = derive_competition_category(comps)
    assert list(cats) == ["IPL", "OTHER_T20", "T20I"]

    # Even if team names contain "IPL", a T20I competition stays strictly T20I
    bbb, m, _ = _make_full_clean_match_bundle(
        match_id=5001, comp_id=3, comp_name="Bilateral India T20I", match_format="T20I"
    )
    m["home_team"] = "Mumbai IPL Select"
    m["away_team"] = "Chennai IPL Stars"
    comps_t20i = comps.loc[comps["comp_id"] == 3].copy()
    elg = classify_match_eligibility(m, comps_t20i, bbb)
    out = derive_match_state_features(build_delivery_states(bbb), elg)

    assert out["comp_id"].iloc[0] == 3
    assert out["comp_name"].iloc[0] == "Bilateral India T20I"
    assert out["match_format"].iloc[0] == "T20I"
    assert out["season"].iloc[0] == "2025/26"
    assert out["competition_category"].iloc[0] == "T20I"


def test_27_chronological_and_causal_safety() -> None:
    """Covers test 27: shuffles input & reverses timestamps -> sorts strictly by key; no target/audit leak in features."""
    bbb_ordered, matches, comps = _make_full_clean_match_bundle(match_id=6001)
    # Reverse timestamps and reverse row order
    bbb_shuffled = bbb_ordered.iloc[::-1].copy().reset_index(drop=True)
    bbb_shuffled["delivery_ist_time"] = [
        f"2025-05-01 23:00:{59 - (i % 60):02d} UTC" for i in range(len(bbb_shuffled))
    ]
    elg = classify_match_eligibility(matches, comps, bbb_shuffled)
    out = derive_match_state_features(build_delivery_states(bbb_shuffled), elg)

    # Strictly sorted by (match_id, innings, innings_ball_num)
    assert out["innings"].is_monotonic_increasing
    inn1 = out.loc[out["innings"] == 1]
    assert list(inn1["innings_ball_num"]) == list(range(1, len(inn1) + 1))

    # Role separation: targets & regime/audit columns never inside MODEL_FEATURE_COLUMNS
    assert not (set(MODEL_FEATURE_COLUMNS) & set(TARGET_COLUMNS))
    assert not (set(MODEL_FEATURE_COLUMNS) & set(REGIME_AUDIT_COLUMNS))
    assert tuple(out.columns) == EXPECTED_COLUMN_ORDER
    assert len(COLUMN_SPECS) == 101


def test_28_raw_immutability_roundtrip_and_versioning(tmp_path: Path) -> None:
    """Covers test 28: raw CSVs unmodified, bit-exact .pkl.gz round-trip, non-overwriting _v2 versioning, reconciliation halt."""
    # Build clean 2-match raw directory in tmp_path
    bbb1, m1, comps = _make_full_clean_match_bundle(match_id=7001)
    bbb2, m2, _ = _make_full_clean_match_bundle(match_id=7002, match_date="2025-05-03")
    matches_df = pd.concat([m1, m2], ignore_index=True)
    bbb_df = pd.concat([bbb1, bbb2], ignore_index=True)

    # Snapshot copies for strict equality check after pipeline
    bbb_orig = bbb_df.copy(deep=True)
    matches_orig = matches_df.copy(deep=True)
    comps_orig = comps.copy(deep=True)

    outcome = run_match_state_pipeline_from_frames(
        ball_by_ball=bbb_df,
        matches=matches_df,
        competitions=comps,
        expected_eligible_matches=2,
        processed_dir=tmp_path / "processed",
        validation_dir=tmp_path / "val",
        write_outputs=True,
    )
    assert outcome.status == "COMPLETE"
    assert outcome.eligible_match_count == 2
    assert outcome.has_critical_failure is False

    # Input DataFrames strictly unchanged
    pd.testing.assert_frame_equal(bbb_df, bbb_orig, check_dtype=True, check_exact=True)
    pd.testing.assert_frame_equal(matches_df, matches_orig, check_dtype=True, check_exact=True)
    pd.testing.assert_frame_equal(comps, comps_orig, check_dtype=True, check_exact=True)

    # Bit-exact .pkl.gz round-trip verified
    ds_v1 = outcome.written["paths"]["primary_dataset"]
    assert ds_v1.name == "match_states_standard_t20_v1.pkl.gz"
    reloaded = pd.read_pickle(ds_v1, compression="gzip")
    pd.testing.assert_frame_equal(
        outcome.primary_states_df, reloaded, check_dtype=True, check_exact=True
    )

    # Second write creates _v2 and leaves _v1 byte-identical
    v1_hash = _sha256_file(ds_v1)
    outcome_v2 = run_match_state_pipeline_from_frames(
        ball_by_ball=bbb_df,
        matches=matches_df,
        competitions=comps,
        expected_eligible_matches=2,
        processed_dir=tmp_path / "processed",
        validation_dir=tmp_path / "val",
        write_outputs=True,
    )
    ds_v2 = outcome_v2.written["paths"]["primary_dataset"]
    assert ds_v2.name == "match_states_standard_t20_v2.pkl.gz"
    assert _sha256_file(ds_v1) == v1_hash

    # Eligibility reconciliation gate halts cleanly when expected count disagrees
    halted = run_match_state_pipeline_from_frames(
        ball_by_ball=bbb_df,
        matches=matches_df,
        competitions=comps,
        expected_eligible_matches=999,
        processed_dir=tmp_path / "proc_halt",
        validation_dir=tmp_path / "val_halt",
        write_outputs=True,
    )
    assert halted.status == "BLOCKED"
    assert halted.reconciliation_halted is True
    assert not (tmp_path / "proc_halt" / "match_states_standard_t20_v1.pkl.gz").exists()
    assert halted.written["paths"]["eligibility_csv"].exists()

    # Check resolve_versioned_file_path preserves extension on .pkl.gz
    p1 = resolve_versioned_file_path(tmp_path / "ver_test", "sample_ds", ".pkl.gz")
    p1.write_bytes(b"x")
    p2 = resolve_versioned_file_path(tmp_path / "ver_test", "sample_ds", ".pkl.gz")
    assert p1.name == "sample_ds_v1.pkl.gz" and p2.name == "sample_ds_v2.pkl.gz"


def test_29_documented_incomplete_injury_and_unflagged_reduction_branches() -> None:
    """Verify injury 9-wicket closure stays STANDARD_T20 while unflagged curtailment and mid-over anomaly isolate cleanly."""
    comps = _make_competitions_df(
        [{"comp_id": 100, "comp_name": "IPL 2025", "match_format": "T20", "season": "2025"}]
    )

    # A) Valid injured 9-wicket Innings 2 chase closure (ends on wicket #9 before over 20) -> STANDARD_T20
    inj_inn1 = _make_standard_20over_innings_rows(
        match_id=8001, innings=1, batting_team_id=1, bowling_team_id=2, runs_per_ball=2, num_overs=20
    )  # 240 runs
    inj_inn2 = _make_standard_20over_innings_rows(
        match_id=8001,
        innings=2,
        batting_team_id=2,
        bowling_team_id=1,
        runs_per_ball=1,
        num_overs=15,
        wickets_on_balls={i * 10: (2, "Caught", 201) for i in range(1, 10)},  # 9th wkt falls on ball 90 (last ball!)
    )  # 90/9 in 90b, injured 11th batter -> completed all-out injury closure

    # B) Unflagged equal-over curtailment (12 overs/side, NO DLS columns/text) -> REVISED_OVERS_DLS + unverified limit
    unfl_inn1 = _make_standard_20over_innings_rows(
        match_id=8002, innings=1, batting_team_id=1, bowling_team_id=2, runs_per_ball=1, num_overs=12
    )  # 72 runs, 0 wkts
    unfl_inn2 = _make_standard_20over_innings_rows(
        match_id=8002, innings=2, batting_team_id=2, bowling_team_id=1, runs_per_ball=1, num_overs=12
    )
    unfl_inn2[-1]["runs"] = 2  # 73 chasing 73

    # C) Mid-over sequence anomaly (over 14 has only 5 legal balls while max_overid=20) -> INCOMPLETE_OR_UNRESOLVED
    seq_inn1 = _make_standard_20over_innings_rows(
        match_id=8003, innings=1, batting_team_id=1, bowling_team_id=2, runs_per_ball=1, num_overs=20
    )
    # Remove 14.6 (index 13*6 + 5 = 83) and renumber innings_ball_num cleanly
    seq_inn1 = [r for i, r in enumerate(seq_inn1) if i != 83]
    for idx_r, r in enumerate(seq_inn1, start=1):
        r["innings_ball_num"] = idx_r
    seq_inn2 = _make_standard_20over_innings_rows(
        match_id=8003, innings=2, batting_team_id=2, bowling_team_id=1, runs_per_ball=1, num_overs=20
    )  # 120 > 119

    matches = _make_matches_df(
        [
            {"match_id": 8001, "win_team_id": 1, "result": "Team 1 Won by 150 runs"},
            {"match_id": 8002, "win_team_id": 2, "result": "Team 2 Won by 10 wickets"},
            {"match_id": 8003, "win_team_id": 2, "result": "Team 2 Won by 10 wickets"},
            {"match_id": 8004, "win_team_id": pd.NA, "result": "Match Abandoned"},  # zero-ball match
        ]
    )
    bbb = _to_bbb_df(inj_inn1 + inj_inn2 + unfl_inn1 + unfl_inn2 + seq_inn1 + seq_inn2)
    elg = classify_match_eligibility(matches, comps, bbb).set_index("match_id")
    out = derive_match_state_features(build_delivery_states(bbb), elg.reset_index())

    assert elg.at[8004, "match_regime"] == "ABANDONED"
    assert bool(elg.at[8004, "has_deliveries"]) is False
    assert elg.at[8004, "eligibility_exclusion_reason"] == "abandoned_null_winner"

    assert elg.at[8001, "match_regime"] == "STANDARD_T20"
    assert bool(elg.at[8001, "is_primary_wp_train_eligible"]) is True
    assert bool(out.loc[out["match_id"] == 8001, "terminal_innings_status_audit"].eq("completed_all_out_injury").any())

    assert elg.at[8002, "match_regime"] == "REVISED_OVERS_DLS"
    assert bool(elg.at[8002, "has_unrecorded_over_reduction"]) is True
    assert bool(elg.at[8002, "is_primary_wp_train_eligible"]) is False
    assert bool((~out.loc[out["match_id"] == 8002, "is_innings_limit_verified"]).all())

    assert elg.at[8003, "match_regime"] == "INCOMPLETE_OR_UNRESOLVED"
    assert bool(elg.at[8003, "is_primary_wp_train_eligible"]) is False
    assert elg.at[8003, "eligibility_exclusion_reason"] == "sequence_or_termination_anomaly"
    cnt = run_continuity_audit(out, elg.reset_index())
    assert cnt.unexpected_break_count == 0
    assert cnt.mid_over_anomaly_count == 1
    assert "DOCUMENTED_SOURCE_SEQUENCE_ANOMALY" in set(cnt.audit_df["classification"])


def test_30_end_to_end_csv_pipeline_immutability_and_manifest(tmp_path: Path) -> None:
    """Run full CSV ingestion -> Stage 4 check -> Stage 5B pipeline -> manifest check on isolated tmp CSVs."""
    import json
    from tests.conftest import materialize_tables

    comps_rows = [[100, "IPL 2025", "T20", "2025"]]
    teams_rows = [[100, 1, "Alpha"], [100, 2, "Beta"]]
    ctp_rows = [
        [100, "IPL 2025", tid, "Alpha" if tid == 1 else "Beta", tid * 100 + k, f"Player {tid * 100 + k}"]
        for tid in (1, 2)
        for k in range(1, 12)
    ]
    matches_rows = [
        [
            9001, 100, 1, "2025-05-01", "League", 10, "India",
            1, "Alpha", 2, "Beta", 101, 201, 1, "Batting", "0",
            "", "", "", 0, 2, "Beta Won by 10 wickets",
        ]
    ]
    p11_rows = [
        [9001, tid, tid * 100 + k, k, "true", "true" if k == 1 else "false", "true" if k == 2 else "false", 0, 0]
        for tid in (1, 2)
        for k in range(1, 12)
    ]

    bbb_df, _, _ = _make_full_clean_match_bundle(match_id=9001)
    # Match raw CSV string formatting for booleans ('true'/'false') and empty strings for NA
    bbb_cols = list(DATASET_SPECS["ball_by_ball"].columns)
    bbb_rows_raw: list[list[Any]] = []
    for _, r in bbb_df[bbb_cols].iterrows():
        row_list = []
        for col in bbb_cols:
            val = r[col]
            if pd.isna(val):
                row_list.append("")
            elif col in ("is_four", "is_six", "is_wicket"):
                row_list.append("true" if bool(val) else "false")
            else:
                row_list.append(val)
        bbb_rows_raw.append(row_list)

    raw_dir = materialize_tables(
        tmp_path / "raw",
        {
            "competitions": (list(DATASET_SPECS["competitions"].columns), comps_rows),
            "teams": (list(DATASET_SPECS["teams"].columns), teams_rows),
            "competition_team_player_mapping": (
                list(DATASET_SPECS["competition_team_player_mapping"].columns), ctp_rows
            ),
            "matches": (list(DATASET_SPECS["matches"].columns), matches_rows),
            "playing_eleven": (list(DATASET_SPECS["playing_eleven"].columns), p11_rows),
            "ball_by_ball": (bbb_cols, bbb_rows_raw),
        },
    )

    before_hashes = {
        spec.filename: _sha256_file(raw_dir / spec.filename)
        for spec in DATASET_SPECS.values()
    }

    outcome = run_match_state_pipeline(
        raw_dir=raw_dir,
        processed_dir=tmp_path / "processed",
        validation_dir=tmp_path / "validation",
        expected_eligible_matches=1,
        write_outputs=True,
    )
    assert outcome.status == "COMPLETE"
    assert outcome.raw_hashes_unchanged is True
    assert outcome.stage4_hashes_unchanged is True
    assert outcome.stage4_status_counts["FAIL"] == 0
    assert outcome.primary_row_count == 240
    assert outcome.column_count == 101

    for fname, h in before_hashes.items():
        assert _sha256_file(raw_dir / fname) == h

    manifest = json.loads(outcome.written["paths"]["manifest_json"].read_text(encoding="utf-8"))
    assert manifest["specification_version"] == "Stage 5A Revision 1.1"
    assert manifest["roundtrip_verified"] is True
    assert manifest["raw_hashes_unchanged"] is True
    assert manifest["output_dataset"]["row_count"] == 240
    assert manifest["output_dataset"]["column_count"] == 101
    assert manifest["included_matches"]["match_ids"] == [9001]

