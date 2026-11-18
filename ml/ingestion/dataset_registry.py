"""Declarative dataset specifications and documented baseline exceptions.

Derived strictly from:
- data/validation/dataset_dictionary.md
- data/validation/data_quality_assessment.md
- data/validation/validation_contract.md
- data/validation/extras_field_investigation.md
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping


PROJECT_ROOT: Path = Path(__file__).resolve().parents[2]
DEFAULT_RAW_DIR: Path = PROJECT_ROOT / "data" / "raw"
DEFAULT_VALIDATION_DIR: Path = PROJECT_ROOT / "data" / "validation"


def resolve_project_path(*parts: str | Path) -> Path:
    """Resolve a path relative to the CricImpact_Phase2 project root."""
    path = PROJECT_ROOT
    for part in parts:
        path = path / part
    return path.resolve()


@dataclass(frozen=True)
class DatasetSpec:
    """Expected raw schema specification for one CSV table."""

    name: str
    filename: str
    columns: tuple[str, ...]
    primary_key: tuple[str, ...]
    primary_key_unique: bool = True
    int_columns: tuple[str, ...] = ()
    float_columns: tuple[str, ...] = ()
    bool_columns: tuple[str, ...] = ()
    date_columns: tuple[str, ...] = ()
    timestamp_columns: tuple[str, ...] = ()
    non_null_columns: tuple[str, ...] = ()
    categorical_domains: Mapping[str, frozenset[str]] = field(default_factory=dict)
    numeric_ranges: Mapping[str, tuple[float | None, float | None]] = field(
        default_factory=dict
    )

    @property
    def column_count(self) -> int:
        return len(self.columns)


DATASET_ORDER: tuple[str, ...] = (
    "competitions",
    "matches",
    "teams",
    "competition_team_player_mapping",
    "playing_eleven",
    "ball_by_ball",
)


VALID_EXTRAS_TYPES: frozenset[str] = frozenset(
    {"None", "wide", "legbyes", "Overstep", "byes", "other", "Penalty"}
)
NON_LEGAL_EXTRAS_TYPES: frozenset[str] = frozenset({"wide", "Overstep", "other"})
LEGAL_EXTRAS_TYPES: frozenset[str] = VALID_EXTRAS_TYPES - NON_LEGAL_EXTRAS_TYPES

VALID_DISMISSAL_TYPES: frozenset[str] = frozenset(
    {
        "Caught",
        "Bowled",
        "LBW",
        "RunOut",
        "Stump",
        "Hit Wicket",
        "Retire Out",
        "Obstracting the field",
        "Obstructing the field",
    }
)
WIDE_ALLOWED_DISMISSALS: frozenset[str] = frozenset(
    {"Stump", "RunOut", "Obstructing the field", "Obstracting the field"}
)
NOBALL_OR_BYE_ALLOWED_DISMISSALS: frozenset[str] = frozenset(
    {"RunOut", "Obstructing the field", "Obstracting the field"}
)


DATASET_SPECS: dict[str, DatasetSpec] = {
    "competitions": DatasetSpec(
        name="competitions",
        filename="competitions.csv",
        columns=("comp_id", "comp_name", "match_format", "season"),
        primary_key=("comp_id",),
        primary_key_unique=True,
        int_columns=("comp_id",),
        non_null_columns=("comp_id", "comp_name", "match_format", "season"),
        categorical_domains={
            "match_format": frozenset({"T20", "T20I"}),
        },
        numeric_ranges={"comp_id": (1, None)},
    ),
    "matches": DatasetSpec(
        name="matches",
        filename="matches.csv",
        columns=(
            "match_id",
            "comp_id",
            "match_number",
            "match_date",
            "stage",
            "venue_id",
            "venue_country",
            "home_team_id",
            "home_team",
            "away_team_id",
            "away_team",
            "home_team_captain_id",
            "away_team_captain_id",
            "toss_win_team_id",
            "toss_opted",
            "man_of_the_match",
            "first_inn_revised_overs",
            "second_inn_revised_overs",
            "revised_target",
            "knock_out",
            "win_team_id",
            "result",
        ),
        primary_key=("match_id",),
        primary_key_unique=True,
        int_columns=(
            "match_id",
            "comp_id",
            "match_number",
            "venue_id",
            "home_team_id",
            "away_team_id",
            "home_team_captain_id",
            "away_team_captain_id",
            "toss_win_team_id",
            "man_of_the_match",
            "first_inn_revised_overs",
            "second_inn_revised_overs",
            "revised_target",
            "knock_out",
            "win_team_id",
        ),
        date_columns=("match_date",),
        non_null_columns=(
            "match_id",
            "comp_id",
            "match_number",
            "match_date",
            "stage",
            "venue_id",
            "venue_country",
            "home_team_id",
            "home_team",
            "away_team_id",
            "away_team",
            "man_of_the_match",
            "knock_out",
            "result",
        ),
        categorical_domains={
            "toss_opted": frozenset({"Fielding", "Batting"}),
        },
        numeric_ranges={
            "match_id": (1, None),
            "comp_id": (1, None),
            "match_number": (1, None),
            "venue_id": (1, None),
            "home_team_id": (1, None),
            "away_team_id": (1, None),
            "man_of_the_match": (0, None),
            "first_inn_revised_overs": (6, 120),
            "second_inn_revised_overs": (6, 120),
            "revised_target": (1, None),
            "knock_out": (0, 1),
        },
    ),
    "teams": DatasetSpec(
        name="teams",
        filename="teams.csv",
        columns=("comp_id", "team_id", "team_name"),
        primary_key=("comp_id", "team_id"),
        primary_key_unique=True,
        int_columns=("comp_id", "team_id"),
        non_null_columns=("comp_id", "team_id", "team_name"),
        numeric_ranges={"comp_id": (1, None), "team_id": (1, None)},
    ),
    "competition_team_player_mapping": DatasetSpec(
        name="competition_team_player_mapping",
        filename="competition_team_player_mapping.csv",
        columns=(
            "comp_id",
            "comp_name",
            "team_id",
            "team_name",
            "player_id",
            "player_name",
        ),
        primary_key=("comp_id", "team_id", "player_id"),
        primary_key_unique=True,
        int_columns=("comp_id", "team_id", "player_id"),
        non_null_columns=(
            "comp_id",
            "comp_name",
            "team_id",
            "team_name",
            "player_id",
            "player_name",
        ),
        numeric_ranges={
            "comp_id": (1, None),
            "team_id": (1, None),
            "player_id": (1, None),
        },
    ),
    "playing_eleven": DatasetSpec(
        name="playing_eleven",
        filename="playing_eleven.csv",
        columns=(
            "match_id",
            "team_id",
            "player_id",
            "batting_order",
            "is_played",
            "is_captain",
            "is_wk",
            "is_impact",
            "is_impact_off",
        ),
        primary_key=("match_id", "team_id", "player_id"),
        primary_key_unique=False,
        int_columns=(
            "match_id",
            "team_id",
            "player_id",
            "batting_order",
            "is_impact",
            "is_impact_off",
        ),
        bool_columns=("is_played", "is_captain", "is_wk"),
        non_null_columns=(
            "match_id",
            "team_id",
            "player_id",
            "is_played",
            "is_impact",
            "is_impact_off",
        ),
        numeric_ranges={
            "match_id": (1, None),
            "team_id": (1, None),
            "player_id": (1, None),
            "batting_order": (1, 13),
            "is_impact": (0, 1),
            "is_impact_off": (0, 1),
        },
    ),
    "ball_by_ball": DatasetSpec(
        name="ball_by_ball",
        filename="ball_by_ball.csv",
        columns=(
            "match_id",
            "innings",
            "overid",
            "over_ball_num",
            "innings_ball_num",
            "batting_team_id",
            "bowling_team_id",
            "striker_id",
            "striker_name",
            "non_striker_id",
            "non_striker_name",
            "bowler_id",
            "bowler_name",
            "batting_type",
            "bowling_type",
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
            "pace_or_spin",
            "bowl_speed",
            "stroke",
            "delivery_style",
            "over_or_around",
            "on_or_off",
            "delivery_ist_time",
        ),
        primary_key=("match_id", "innings", "innings_ball_num"),
        primary_key_unique=True,
        int_columns=(
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
        ),
        float_columns=("bowl_speed",),
        bool_columns=("is_four", "is_six", "is_wicket"),
        timestamp_columns=("delivery_ist_time",),
        non_null_columns=(
            "match_id",
            "innings",
            "overid",
            "over_ball_num",
            "innings_ball_num",
            "batting_team_id",
            "bowling_team_id",
            "striker_id",
            "striker_name",
            "non_striker_id",
            "non_striker_name",
            "bowler_id",
            "bowler_name",
            "batting_type",
            "bowling_type",
            "batting_order",
            "runs",
            "is_four",
            "is_six",
            "is_wicket",
            "extras_type",
            "extras1_runs",
            "extras_2_runs",
            "pace_or_spin",
            "bowl_speed",
            "on_or_off",
            "delivery_ist_time",
        ),
        categorical_domains={
            "batting_type": frozenset({"RHB", "LHB"}),
            "pace_or_spin": frozenset({"Pace", "Spin"}),
            "over_or_around": frozenset({"Over", "Around"}),
            "on_or_off": frozenset({"Off-side", "On-side"}),
        },
        numeric_ranges={
            "match_id": (1, None),
            "innings": (1, 4),
            "overid": (1, 20),
            "over_ball_num": (1, None),
            "innings_ball_num": (1, None),
            "batting_order": (1, 13),
            "runs": (0, 6),
            "extras1_runs": (0, None),
            "extras_2_runs": (0, None),
        },
    ),
}


# Known documented baseline exceptions from Stages 1-2 audit reports.
# Validators reference these strictly to separate known exceptions from newly
# discovered anomalies without mutating raw records or concealing issues.
KNOWN_EXCEPTIONS: dict[str, object] = {
    "playing_eleven_super_over_dup_matches": frozenset({13613, 21176, 28962}),
    "uae_split_player_matches": frozenset({37087, 37092, 37095}),
    "uae_split_player_bbb_ids": frozenset({39444, 36153}),
    "extras_none_with_e1_coords": frozenset({(36097, 2, 8, 6)}),
    "extras_none_with_e2_coords": frozenset({(17555, 1, 5, 4)}),
    "extras_legbyes_with_run_coords": frozenset({(37099, 1, 14, 1)}),
    "incomplete_mid_match_overs": frozenset({(14130, 2, 14)}),
    "retire_out_missing_dismissed_id_coords": frozenset({(40709, 2, 19, 5)}),
    "scorecard_result_text_typo_matches": frozenset({20190}),
    "played_xi_missing_batting_order_team_matches": frozenset({(48512, 25)}),
    "underpopulated_played_xi_team_matches": frozenset({(28333, 17)}),
    "played_xi_over_12_team_matches": frozenset(
        {
            (21585, 2),
            (31272, 3509),
            (40749, 2),
            (50354, 2),
            (50356, 7),
            (50386, 8),
        }
    ),
    "dls_text_missing_target_matches": frozenset({20182, 23674, 24822, 28334}),
    "midnight_utc_placeholder_matches": frozenset({13511, 17737, 24354, 25158}),
    "non_monotonic_timestamp_coords": frozenset(
        {
            (14104, 1, 8),
            (17737, 2, 7),
            (24354, 1, 102),
            (55078, 2, 69),
        }
    ),
    "boundary_omission_coords": frozenset(
        {
            (14113, 1, 1, 3),
            (14123, 1, 3, 6),
            (14149, 1, 12, 2),
            (15609, 2, 17, 8),
            (16425, 2, 13, 1),
            (16754, 1, 6, 1),
            (17396, 1, 19, 3),
            (20236, 2, 2, 7),
            (24350, 2, 6, 6),
            (28958, 1, 3, 2),
            (28959, 1, 5, 1),
            (29816, 2, 20, 6),
            (29817, 1, 6, 1),
            (30062, 1, 9, 2),
            (31277, 1, 7, 5),
            (34427, 2, 19, 4),
            (35429, 2, 5, 5),
            (40722, 1, 20, 6),
            (40730, 2, 3, 6),
            (40739, 1, 19, 1),
            (40766, 1, 16, 6),
            (50342, 2, 13, 5),
            (51384, 2, 13, 3),
        }
    ),
    "bowl_speed_outlier_coords": frozenset(
        {
            (13513, 2, 13, 6),
            (13524, 1, 4, 5),
            (13524, 1, 14, 2),
            (13614, 1, 5, 4),
            (14108, 2, 9, 5),
            (14111, 2, 9, 6),
            (14114, 1, 3, 5),
            (14116, 2, 19, 4),
            (14122, 2, 19, 6),
            (14143, 1, 11, 4),
            (14144, 2, 4, 1),
            (14160, 1, 16, 5),
            (14160, 2, 5, 4),
            (15795, 1, 1, 1),
            (16259, 2, 2, 6),
            (16316, 1, 18, 4),
            (16317, 1, 16, 5),
            (16317, 2, 7, 4),
            (17557, 1, 2, 6),
            (17627, 1, 3, 2),
            (17740, 1, 8, 1),
            (17764, 1, 19, 6),
            (17765, 1, 8, 6),
            (18532, 1, 4, 3),
            (18532, 1, 9, 1),
            (19960, 1, 20, 6),
            (20194, 1, 7, 6),
            (20201, 1, 6, 6),
            (20202, 1, 17, 6),
            (20214, 1, 7, 4),
            (20235, 1, 6, 3),
            (20236, 2, 7, 5),
            (21176, 2, 16, 3),
            (21176, 2, 16, 4),
            (21178, 1, 6, 4),
            (24822, 1, 12, 3),
            (28334, 1, 17, 2),
            (28334, 2, 11, 3),
            (28334, 2, 13, 1),
            (28963, 1, 18, 4),
            (29926, 1, 12, 3),
            (30065, 2, 6, 2),
            (32134, 1, 14, 2),
        }
    ),
    "same_name_distinct_ids": {
        "Abdul Samad": frozenset({6922, 7446}),
        "Rashid Khan": frozenset({4722, 20172}),
        "Haider Ali": frozenset({7338, 28756}),
        "Basil Hameed": frozenset({8638, 39444}),
        "Muhammad Farooq": frozenset({27373, 28978}),
        "Mohammad Ali": frozenset({3083, 20229}),
        "Bashir Ahmad": frozenset({29833, 39479}),
    },
    "confirmed_true_homonym_names": frozenset({"Abdul Samad", "Rashid Khan", "Haider Ali"}),
}
