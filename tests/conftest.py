"""Shared synthetic CSV fixtures for CricImpact Phase 2 Stage 4 tests.

All tests operate strictly on temporary synthetic CSV directories created inside
pytest's tmp_path and NEVER access or modify files in data/raw/ or Phase 1.
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path
from typing import Any

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ml.ingestion.dataset_registry import DATASET_SPECS  # noqa: E402


def write_csv(path: Path, columns: list[str] | tuple[str, ...], rows: list[list[Any]]) -> None:
    """Write a UTF-8 CSV file with exact column headers and raw string formatting."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(list(columns))
        writer.writerows(rows)


def _ball_row(
    *,
    match_id: int,
    innings: int,
    overid: int,
    over_ball_num: int,
    innings_ball_num: int,
    batting_team_id: int,
    bowling_team_id: int,
    striker_id: int,
    striker_name: str,
    non_striker_id: int,
    non_striker_name: str,
    bowler_id: int,
    bowler_name: str,
    batting_order: int = 1,
    runs: int = 1,
    is_four: bool = False,
    is_six: bool = False,
    is_wicket: bool = False,
    dismissal_type_id: Any = "",
    dismissal_type: Any = "",
    dismissed_player_id: Any = "",
    extras_type: str = "None",
    extras1_runs: int = 0,
    extras_2_runs: int = 0,
    bowl_speed: float = 135.0,
    stroke: str = "Drive",
    delivery_style: str = "Outswinger",
    over_or_around: str = "Over",
    ts: str = "2025-05-01 14:00:00 UTC",
) -> list[Any]:
    return [
        match_id,
        innings,
        overid,
        over_ball_num,
        innings_ball_num,
        batting_team_id,
        bowling_team_id,
        striker_id,
        striker_name,
        non_striker_id,
        non_striker_name,
        bowler_id,
        bowler_name,
        "RHB",
        "Right-arm Fast",
        batting_order,
        runs,
        "true" if is_four else "false",
        "true" if is_six else "false",
        "true" if is_wicket else "false",
        dismissal_type_id,
        dismissal_type,
        dismissed_player_id,
        extras_type,
        extras1_runs,
        extras_2_runs,
        "Pace",
        bowl_speed,
        stroke,
        delivery_style,
        over_or_around,
        "Off-side",
        ts,
    ]


def build_clean_synthetic_tables() -> dict[str, tuple[list[str], list[list[Any]]]]:
    """Construct a completely valid minimal 6-table cricket dataset where all 31 rules PASS.

    Contains:
    - comp_id=100 ('Synthetic T20 League', format='T20') with teams 1 & 2, match 1001.
    - Team 1 bats first (2 overs -> 12 legal deliveries, 16 runs, 1 wicket).
    - Team 2 chases in 2 overs (over 1: 6 legal + 1 wide; over 2: 2 legal -> 18 runs, 1 wicket -> Won by 9 wickets).
    """
    competitions_rows = [
        [100, "Synthetic T20 League", "T20", "2025"],
        [200, "Synthetic Bilateral T20I", "T20I", "2025"],
    ]
    teams_rows = [
        [100, 1, "Alpha Challengers"],
        [100, 2, "Beta Warriors"],
        [200, 3, "Gamma XI"],
        [200, 4, "Delta XI"],
    ]

    ctp_rows: list[list[Any]] = []
    # Team 1 players: 101..112; Team 2 players: 201..212; Team 3: 301..312; Team 4: 401..412
    for comp_id, comp_name, tid, tname, base in [
        (100, "Synthetic T20 League", 1, "Alpha Challengers", 100),
        (100, "Synthetic T20 League", 2, "Beta Warriors", 200),
        (200, "Synthetic Bilateral T20I", 3, "Gamma XI", 300),
        (200, "Synthetic Bilateral T20I", 4, "Delta XI", 400),
    ]:
        for offset in range(1, 13):
            pid = base + offset
            ctp_rows.append([comp_id, comp_name, tid, tname, pid, f"Player {pid}"])

    matches_rows = [
        [
            1001,
            100,
            1,
            "2025-05-01",
            "League",
            10,
            "India",
            1,
            "Alpha Challengers",
            2,
            "Beta Warriors",
            101,
            201,
            1,
            "Batting",
            0,  # documented sentinel allowed in schema
            "",
            "",
            "",
            0,
            2,
            "Beta Warriors Won by 9 wickets",
        ]
    ]

    p11_rows: list[list[Any]] = []
    for tid, base in [(1, 100), (2, 200)]:
        for pos in range(1, 12):
            p11_rows.append(
                [
                    1001,
                    tid,
                    base + pos,
                    pos,
                    "true",
                    "true" if pos == 1 else "false",
                    "true" if pos == 2 else "false",
                    0,
                    0,
                ]
            )
        # 12th squad player on bench
        p11_rows.append([1001, tid, base + 12, "", "false", "", "", 0, 0])

    bbb_rows: list[list[Any]] = []
    # Innings 1: Team 1 bats vs Team 2 bowls, 2 overs (12 legal balls)
    # Over 1: 6 legal balls scoring 1 each = 6 runs (include 1 legbyes & 1 byes)
    inn1_spec = [
        # (overid, ob, ib, bat_runs, e1, e2, et, wicket, d_id, d_type, dp, speed, stroke, ds, oa)
        (1, 1, 1, 1, 0, 0, "None", False, "", "", "", 138.2, "Drive", "Outswinger", "Over"),
        (1, 2, 2, 0, 1, 0, "legbyes", False, "", "", "", 139.0, "None", "Inswinger", "Over"),
        (1, 3, 3, 0, 1, 0, "byes", False, "", "", "", 137.5, "None", "None", "Around"),
        (1, 4, 4, 4, 0, 0, "None", False, "", "", "", 0.0, "Pull shot", "Short", "Over"),
        (1, 5, 5, 1, 0, 0, "None", False, "", "", "", 136.0, "Worked", "Good", "Over"),
        (1, 6, 6, 1, 0, 0, "None", False, "", "", "", 135.4, "Push", "Good", "Over"),
        # Over 2: 6 legal balls scoring 8 runs (total Inn 1 = 16 runs, 1 wicket)
        (2, 1, 7, 6, 0, 0, "None", False, "", "", "", 140.1, "Loft", "Full", "Over"),
        (2, 2, 8, 0, 0, 0, "None", True, 2, "Caught", 101, 134.0, "Cut", "Short", "Around"),
        (2, 3, 9, 1, 0, 0, "None", False, "", "", "", 135.0, "Single", "Good", "Over"),
        (2, 4, 10, 0, 0, 0, "None", False, "", "", "", 132.5, "Defense", "Good", "Over"),
        (2, 5, 11, 1, 0, 0, "None", False, "", "", "", 136.8, "Glance", "Leg", "Around"),
        (2, 6, 12, 0, 0, 0, "None", False, "", "", "", 134.9, "Leave", "Outside", ""),
    ]
    sec = 0
    for ov, ob, ib, runs, e1, e2, et, wkt, did, dt, dp, spd, stk, ds, oa in inn1_spec:
        sec += 1
        striker = 101 if ib <= 8 else 103
        bbb_rows.append(
            _ball_row(
                match_id=1001,
                innings=1,
                overid=ov,
                over_ball_num=ob,
                innings_ball_num=ib,
                batting_team_id=1,
                bowling_team_id=2,
                striker_id=striker,
                striker_name=f"Player {striker}",
                non_striker_id=102,
                non_striker_name="Player 102",
                bowler_id=208 if ov == 1 else 209,
                bowler_name="Player 208" if ov == 1 else "Player 209",
                batting_order=1 if striker == 101 else 3,
                runs=runs,
                is_four=(runs == 4),
                is_six=(runs == 6),
                is_wicket=wkt,
                dismissal_type_id=did,
                dismissal_type=dt,
                dismissed_player_id=dp,
                extras_type=et,
                extras1_runs=e1,
                extras_2_runs=e2,
                bowl_speed=spd,
                stroke=stk,
                delivery_style=ds,
                over_or_around=oa,
                ts=f"2025-05-01 14:00:{sec:02d} UTC",
            )
        )

    # Innings 2: Team 2 chases 17 (Team 1 made 16):
    # Over 1 has 1 wide (non-legal) + 6 legal = 7 rows (12 runs), 1 wicket.
    # Over 2 has 2 legal balls scoring 1 + 4 = 5 -> total 17/1 -> Won by 9 wickets!
    inn2_spec = [
        (1, 1, 1, 0, 1, 0, "wide", False, "", "", "", 130.0, "None", "Wide", "Over"),
        (1, 2, 2, 4, 0, 0, "None", False, "", "", "", 131.5, "Drive", "Full", "Over"),
        (1, 3, 3, 1, 0, 0, "None", False, "", "", "", 133.2, "Push", "Good", "Over"),
        (1, 4, 4, 0, 1, 1, "Overstep", False, "", "", "", 134.0, "Leave", "Bouncer", "Over"),
        (1, 5, 5, 0, 0, 0, "None", True, 1, "Bowled", 201, 136.0, "Miss", "Yorker", "Over"),
        (1, 6, 6, 4, 0, 0, "None", False, "", "", "", 132.1, "Sweep", "Full", "Around"),
        (1, 7, 7, 1, 0, 0, "None", False, "", "", "", 130.5, "Work", "Good", "Over"),
        (1, 8, 8, 0, 0, 0, "None", False, "", "", "", 129.8, "Defend", "Good", "Over"),
        # Over 2: 2 legal balls -> 1 + 4 = 5 (prev = 13 <= 16; final = 17; overshoot = 1)
        (2, 1, 9, 1, 0, 0, "None", False, "", "", "", 128.0, "Push", "Good", "Over"),
        (2, 2, 10, 4, 0, 0, "None", False, "", "", "", 129.5, "Drive", "Half-volley", "Over"),
    ]
    sec = 0
    for ov, ob, ib, runs, e1, e2, et, wkt, did, dt, dp, spd, stk, ds, oa in inn2_spec:
        sec += 1
        striker = 201 if ib <= 5 else 203
        bbb_rows.append(
            _ball_row(
                match_id=1001,
                innings=2,
                overid=ov,
                over_ball_num=ob,
                innings_ball_num=ib,
                batting_team_id=2,
                bowling_team_id=1,
                striker_id=striker,
                striker_name=f"Player {striker}",
                non_striker_id=202,
                non_striker_name="Player 202",
                bowler_id=108 if ov == 1 else 109,
                bowler_name="Player 108" if ov == 1 else "Player 109",
                batting_order=1 if striker == 201 else 3,
                runs=runs,
                is_four=(runs == 4),
                is_six=(runs == 6),
                is_wicket=wkt,
                dismissal_type_id=did,
                dismissal_type=dt,
                dismissed_player_id=dp,
                extras_type=et,
                extras1_runs=e1,
                extras_2_runs=e2,
                bowl_speed=spd,
                stroke=stk,
                delivery_style=ds,
                over_or_around=oa,
                ts=f"2025-05-01 15:00:{sec:02d} UTC",
            )
        )

    return {
        "competitions": (list(DATASET_SPECS["competitions"].columns), competitions_rows),
        "teams": (list(DATASET_SPECS["teams"].columns), teams_rows),
        "competition_team_player_mapping": (
            list(DATASET_SPECS["competition_team_player_mapping"].columns),
            ctp_rows,
        ),
        "matches": (list(DATASET_SPECS["matches"].columns), matches_rows),
        "playing_eleven": (list(DATASET_SPECS["playing_eleven"].columns), p11_rows),
        "ball_by_ball": (list(DATASET_SPECS["ball_by_ball"].columns), bbb_rows),
    }


def materialize_tables(
    target_dir: Path, tables: dict[str, tuple[list[str], list[list[Any]]]]
) -> Path:
    """Write all table specs from a dictionary into target_dir."""
    for name, (cols, rows) in tables.items():
        write_csv(target_dir / DATASET_SPECS[name].filename, cols, rows)
    return target_dir


@pytest.fixture()
def synthetic_raw_dir(tmp_path: Path) -> Path:
    """Provide a fresh temporary directory containing 6 valid baseline CSV files."""
    tables = build_clean_synthetic_tables()
    return materialize_tables(tmp_path / "raw", tables)

