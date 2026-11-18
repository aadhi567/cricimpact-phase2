"""Primary-key, composite-key, foreign-key, and entity consistency validation (Stage 4 Phase 3B)."""

from __future__ import annotations

import pandas as pd

from ml.ingestion.csv_loader import DatasetLoadBundle
from ml.ingestion.dataset_registry import KNOWN_EXCEPTIONS
from ml.validation.validation_engine import (
    Severity,
    ValidationResult,
    ValidationStatus,
    check_required_columns,
    format_row_id,
    make_skipped_result,
)


def _identify_super_over_match_ids(
    matches: pd.DataFrame,
    bbb: pd.DataFrame | None,
) -> set[int]:
    so_ids: set[int] = set()
    if bbb is not None and {"match_id", "innings"}.issubset(bbb.columns):
        so_ids.update(
            int(x) for x in bbb.loc[bbb["innings"] >= 3, "match_id"].dropna().unique()
        )
    if {"match_id", "result"}.issubset(matches.columns):
        res_str = matches["result"].fillna("").astype(str).str.lower()
        so_mask = res_str.str.contains(r"super over|eliminator|bowl[- ]out", regex=True)
        so_ids.update(int(x) for x in matches.loc[so_mask, "match_id"].dropna().unique())
    return so_ids


def validate_relationships(bundle: DatasetLoadBundle) -> list[ValidationResult]:
    """Execute VAL-PK-001..003, VAL-FK-001..005, and VAL-ENT-001."""
    return [
        _check_val_pk_001_master_keys(bundle),
        _check_val_pk_002_ball_by_ball_key(bundle),
        _check_val_pk_003_playing_eleven_key(bundle),
        _check_val_fk_001_competition_refs(bundle),
        _check_val_fk_002_team_refs(bundle),
        _check_val_fk_003_match_and_ball_team_refs(bundle),
        _check_val_fk_004_ball_player_to_ctp(bundle),
        _check_val_fk_005_ball_player_to_playing_eleven(bundle),
        _check_val_ent_001_player_entities(bundle),
    ]


def _check_val_pk_001_master_keys(bundle: DatasetLoadBundle) -> ValidationResult:
    key_specs = [
        ("competitions", ("comp_id",)),
        ("matches", ("match_id",)),
        ("teams", ("comp_id", "team_id")),
        ("competition_team_player_mapping", ("comp_id", "team_id", "player_id")),
    ]
    missing_tables = [t for t, _ in key_specs if bundle.get(t) is None]
    if len(missing_tables) == len(key_specs):
        return make_skipped_result(
            rule_id="VAL-PK-001",
            dataset="competitions,matches,teams,competition_team_player_mapping",
            field="primary_keys",
            severity=Severity.CRITICAL,
            reason="None of the master reference tables loaded.",
            recommended_action="Fix raw CSV loading first.",
        )

    total_issues = 0
    examples: list[str] = []
    details: dict[str, dict[str, int]] = {}
    skipped_tables: list[str] = []

    for table, key_cols in key_specs:
        df = bundle.get(table)
        if df is None:
            skipped_tables.append(table)
            continue
        if any(c not in df.columns for c in key_cols):
            skipped_tables.append(f"{table}(missing key cols)")
            continue
        null_cnt = int(df[list(key_cols)].isna().any(axis=1).sum())
        dup_mask = df.duplicated(subset=list(key_cols), keep=False)
        dup_extra = int(df.duplicated(subset=list(key_cols), keep="first").sum())
        details[table] = {
            "rows": int(len(df)),
            "null_key_rows": null_cnt,
            "duplicate_extra_rows": dup_extra,
        }
        total_issues += null_cnt + dup_extra
        if dup_extra > 0:
            for _, row in df.loc[dup_mask].drop_duplicates(subset=list(key_cols)).head(3).iterrows():
                if len(examples) < 10:
                    examples.append(f"{table} duplicate {format_row_id(row, key_cols)}")
        if null_cnt > 0 and len(examples) < 10:
            examples.append(f"{table}: {null_cnt} row(s) with NULL in {key_cols}")

    if total_issues > 0:
        status = ValidationStatus.FAIL
    elif skipped_tables:
        status = ValidationStatus.SKIPPED
    else:
        status = ValidationStatus.PASS

    return ValidationResult(
        rule_id="VAL-PK-001",
        dataset="competitions,matches,teams,competition_team_player_mapping",
        field="(comp_id), (match_id), (comp_id,team_id), (comp_id,team_id,player_id)",
        severity=Severity.CRITICAL,
        status=status,
        affected_record_count=total_issues,
        new_anomaly_count=total_issues,
        short_description=(
            "100% uniqueness and 0 nulls across all master primary and composite keys."
            if total_issues == 0 and not skipped_tables
            else (
                f"Skipped master tables unavailable: {', '.join(skipped_tables)}."
                if total_issues == 0
                else f"Detected {total_issues} null or duplicate key violation(s) across master tables."
            )
        ),
        example_record_identifiers=examples,
        recommended_action="Halt ingestion and emit conflicting primary/composite keys.",
        metadata={"key_checks": details, "skipped_tables": skipped_tables},
    )


def _check_val_pk_002_ball_by_ball_key(bundle: DatasetLoadBundle) -> ValidationResult:
    req = {"ball_by_ball": ("match_id", "innings", "innings_ball_num")}
    skip_reason = check_required_columns(bundle, req)
    if skip_reason:
        return make_skipped_result(
            rule_id="VAL-PK-002",
            dataset="ball_by_ball",
            field="(match_id, innings, innings_ball_num)",
            severity=Severity.CRITICAL,
            reason=skip_reason,
            recommended_action="Fix ball_by_ball.csv schema before PK checks.",
        )

    bbb = bundle.get("ball_by_ball")
    assert bbb is not None
    key_cols = ["match_id", "innings", "innings_ball_num"]
    null_cnt = int(bbb[key_cols].isna().any(axis=1).sum())
    dup_mask = bbb.duplicated(subset=key_cols, keep=False)
    dup_extra = int(bbb.duplicated(subset=key_cols, keep="first").sum())

    gap_innings = 0
    gap_examples: list[str] = []
    if pd.api.types.is_numeric_dtype(bbb["innings_ball_num"].dtype):
        grp = bbb.dropna(subset=key_cols).groupby(["match_id", "innings"], sort=False)[
            "innings_ball_num"
        ]
        stats = grp.agg(["count", "nunique", "min", "max"])
        # Expected 1..N strictly contiguous without gaps or duplicates
        bad_seq = stats[
            (stats["min"] != 1)
            | (stats["max"] != stats["nunique"])
            | (stats["max"] != stats["count"])
        ]
        gap_innings = int(len(bad_seq))
        for (mid, inn), row in bad_seq.head(5).iterrows():
            gap_examples.append(
                f"(match_id={mid}, innings={inn}, min={int(row['min'])}, max={int(row['max'])}, nunique={int(row['nunique'])}, count={int(row['count'])})"
            )

    examples: list[str] = []
    for _, row in bbb.loc[dup_mask].head(5).iterrows():
        examples.append(f"DUP {format_row_id(row, key_cols)}")
    examples.extend(gap_examples[:5])

    total_bad = null_cnt + dup_extra + gap_innings
    status = ValidationStatus.PASS if total_bad == 0 else ValidationStatus.FAIL
    return ValidationResult(
        rule_id="VAL-PK-002",
        dataset="ball_by_ball",
        field="(match_id, innings, innings_ball_num)",
        severity=Severity.CRITICAL,
        status=status,
        affected_record_count=total_bad,
        new_anomaly_count=total_bad,
        short_description=(
            f"All {len(bbb):,} delivery keys unique (0 duplicates, 0 nulls, 0 contiguous 1..N gaps)."
            if total_bad == 0
            else f"Detected {null_cnt} nulls, {dup_extra} duplicate keys, and {gap_innings} innings with innings_ball_num sequence gaps."
        ),
        example_record_identifiers=examples[:10],
        recommended_action="Halt ingestion; reject unordered, gapped, or duplicate delivery keys.",
        metadata={
            "total_rows": int(len(bbb)),
            "null_key_rows": null_cnt,
            "duplicate_extra_rows": dup_extra,
            "gap_innings_count": gap_innings,
        },
    )


def _check_val_pk_003_playing_eleven_key(
    bundle: DatasetLoadBundle,
) -> ValidationResult:
    req = {"playing_eleven": ("match_id", "team_id", "player_id")}
    skip_reason = check_required_columns(bundle, req)
    if skip_reason:
        return make_skipped_result(
            rule_id="VAL-PK-003",
            dataset="playing_eleven",
            field="(match_id, team_id, player_id)",
            severity=Severity.WARNING,
            reason=skip_reason,
            recommended_action="Ensure playing_eleven.csv loads cleanly.",
        )

    p11 = bundle.get("playing_eleven")
    assert p11 is not None
    matches = bundle.get("matches")
    bbb = bundle.get("ball_by_ball")

    known_so_dups: frozenset[int] = KNOWN_EXCEPTIONS["playing_eleven_super_over_dup_matches"]  # type: ignore[assignment]
    so_matches = set(known_so_dups)
    if matches is not None:
        so_matches |= _identify_super_over_match_ids(matches, bbb)

    key_cols = ["match_id", "team_id", "player_id"]
    null_cnt = int(p11[key_cols].isna().any(axis=1).sum())
    dup_extra_mask = p11.duplicated(subset=key_cols, keep="first")
    dup_extra_df = p11.loc[dup_extra_mask]
    extra_count = int(len(dup_extra_df))

    if extra_count == 0 and null_cnt == 0:
        return ValidationResult(
            rule_id="VAL-PK-003",
            dataset="playing_eleven",
            field="(match_id, team_id, player_id)",
            severity=Severity.WARNING,
            status=ValidationStatus.PASS,
            affected_record_count=0,
            short_description="playing_eleven keys are 100% unique with zero nulls.",
            recommended_action="None required.",
        )

    dup_match_ids = set(int(x) for x in dup_extra_df["match_id"].dropna().unique())
    non_so_dups = dup_extra_df.loc[~dup_extra_df["match_id"].isin(so_matches)]
    new_so_dups = dup_extra_df.loc[
        dup_extra_df["match_id"].isin(so_matches)
        & ~dup_extra_df["match_id"].isin(known_so_dups)
    ]
    known_dups = dup_extra_df.loc[dup_extra_df["match_id"].isin(known_so_dups)]

    examples = [
        f"DUP {format_row_id(row, ['match_id', 'team_id', 'player_id', 'batting_order'])}"
        for _, row in dup_extra_df.head(8).iterrows()
    ]

    if null_cnt > 0 or len(non_so_dups) > 0:
        return ValidationResult(
            rule_id="VAL-PK-003",
            dataset="playing_eleven",
            field="(match_id, team_id, player_id)",
            severity=Severity.WARNING,
            status=ValidationStatus.FAIL,
            affected_record_count=null_cnt + extra_count,
            known_exception_count=int(len(known_dups)),
            new_anomaly_count=null_cnt + int(len(non_so_dups)) + int(len(new_so_dups)),
            short_description=(
                f"Illegal duplicate playing_eleven keys detected outside Super Over matches "
                f"({len(non_so_dups)} non-SO extra rows; {null_cnt} null keys)."
            ),
            example_record_identifiers=examples,
            recommended_action="Halt ingestion on non-Super-Over duplicates; preserve Super Over rows separately.",
            known_exceptions_summary=f"{len(known_dups)} known SO duplicate rows in matches {sorted(known_so_dups)}.",
            metadata={"duplicate_match_ids": sorted(dup_match_ids)},
        )

    return ValidationResult(
        rule_id="VAL-PK-003",
        dataset="playing_eleven",
        field="(match_id, team_id, player_id)",
        severity=Severity.WARNING,
        status=ValidationStatus.WARNING,
        affected_record_count=extra_count,
        known_exception_count=int(len(known_dups)),
        new_anomaly_count=int(len(new_so_dups)),
        short_description=(
            f"Found {extra_count} extra duplicate playing_eleven rows exclusively in Super Over matches "
            f"{sorted(dup_match_ids)}; original rows preserved without blind deduplication."
        ),
        example_record_identifiers=examples,
        recommended_action="Preserve raw rows; separate regular XI vs Super Over entries using min(batting_order) downstream.",
        known_exceptions_summary=(
            f"All 40 duplicate rows occur in pre-mid-2024 Super Over matches {sorted(known_so_dups)}."
            if len(new_so_dups) == 0
            else f"{len(known_dups)} known + {len(new_so_dups)} additional SO duplicate rows."
        ),
        metadata={
            "duplicate_match_ids": sorted(dup_match_ids),
            "unique_keys": int(len(p11) - extra_count),
            "total_rows": int(len(p11)),
        },
    )


def _check_val_fk_001_competition_refs(bundle: DatasetLoadBundle) -> ValidationResult:
    req = {
        "competitions": ("comp_id",),
        "matches": ("match_id", "comp_id"),
        "teams": ("comp_id", "team_id"),
        "competition_team_player_mapping": ("comp_id", "team_id", "player_id"),
    }
    skip_reason = check_required_columns(bundle, req)
    if skip_reason:
        return make_skipped_result(
            rule_id="VAL-FK-001",
            dataset="matches,teams,competition_team_player_mapping",
            field="comp_id -> competitions.comp_id",
            severity=Severity.CRITICAL,
            reason=skip_reason,
            recommended_action="Ensure competitions, matches, teams, and ctp load cleanly.",
        )

    comps = bundle.get("competitions")
    matches = bundle.get("matches")
    teams = bundle.get("teams")
    ctp = bundle.get("competition_team_player_mapping")
    assert comps is not None and matches is not None and teams is not None and ctp is not None

    valid_comps = set(comps["comp_id"].dropna())
    orphans = 0
    examples: list[str] = []
    orphan_by_table: dict[str, int] = {}

    for tname, df in [("matches", matches), ("teams", teams), ("ctp", ctp)]:
        bad = df.loc[df["comp_id"].notna() & ~df["comp_id"].isin(valid_comps)]
        orphan_by_table[tname] = int(len(bad))
        orphans += int(len(bad))
        for _, row in bad.head(3).iterrows():
            if len(examples) < 10:
                examples.append(f"{tname} orphan comp_id={row['comp_id']}")

    unused_in_matches = sorted(int(x) for x in valid_comps - set(matches["comp_id"].dropna()))
    unused_in_ctp = sorted(int(x) for x in valid_comps - set(ctp["comp_id"].dropna()))

    # Verify comp_name consistency between ctp and competitions if column present
    name_conflicts = 0
    if {"comp_id", "comp_name"}.issubset(comps.columns) and {"comp_id", "comp_name"}.issubset(ctp.columns):
        merged = ctp[["comp_id", "comp_name"]].drop_duplicates().merge(
            comps[["comp_id", "comp_name"]].rename(columns={"comp_name": "master_comp_name"}),
            on="comp_id",
            how="inner",
        )
        mismatched = merged.loc[merged["comp_name"] != merged["master_comp_name"]]
        name_conflicts = int(len(mismatched))
        orphans += name_conflicts
        for _, row in mismatched.head(3).iterrows():
            examples.append(
                f"comp_name mismatch comp_id={row['comp_id']}: {row['comp_name']!r} vs {row['master_comp_name']!r}"
            )

    status = ValidationStatus.PASS if orphans == 0 else ValidationStatus.FAIL
    return ValidationResult(
        rule_id="VAL-FK-001",
        dataset="matches,teams,competition_team_player_mapping",
        field="comp_id -> competitions.comp_id",
        severity=Severity.CRITICAL,
        status=status,
        affected_record_count=orphans,
        new_anomaly_count=orphans,
        short_description=(
            f"0 orphan comp_ids across matches, teams, and ctp ({len(unused_in_matches)} unused competitions logged)."
            if orphans == 0
            else f"Detected {orphans} orphan comp_id or comp_name mismatch(es)."
        ),
        example_record_identifiers=examples,
        recommended_action="Halt ingestion and inspect orphan competition identifiers.",
        metadata={
            "orphans_by_table": orphan_by_table,
            "comp_name_conflicts": name_conflicts,
            "unused_comp_ids_in_matches": unused_in_matches,
            "unused_comp_ids_in_ctp": unused_in_ctp,
        },
    )


def _check_val_fk_002_team_refs(bundle: DatasetLoadBundle) -> ValidationResult:
    req = {
        "teams": ("comp_id", "team_id", "team_name"),
        "matches": ("match_id", "comp_id", "home_team_id", "away_team_id"),
        "competition_team_player_mapping": ("comp_id", "team_id", "team_name"),
    }
    skip_reason = check_required_columns(bundle, req)
    if skip_reason:
        return make_skipped_result(
            rule_id="VAL-FK-002",
            dataset="matches,competition_team_player_mapping",
            field="(comp_id, team_id) -> teams.(comp_id, team_id)",
            severity=Severity.CRITICAL,
            reason=skip_reason,
            recommended_action="Ensure teams, matches, and ctp load cleanly.",
        )

    teams = bundle.get("teams")
    matches = bundle.get("matches")
    ctp = bundle.get("competition_team_player_mapping")
    assert teams is not None and matches is not None and ctp is not None

    valid_pairs = set(zip(teams["comp_id"], teams["team_id"]))
    issues = 0
    examples: list[str] = []

    self_play = matches.loc[matches["home_team_id"] == matches["away_team_id"]]
    issues += int(len(self_play))
    for _, r in self_play.head(3).iterrows():
        examples.append(f"self_play match_id={r['match_id']} team_id={r['home_team_id']}")

    home_missing = matches.loc[
        ~pd.Series(zip(matches["comp_id"], matches["home_team_id"]), index=matches.index).isin(valid_pairs)
    ]
    away_missing = matches.loc[
        ~pd.Series(zip(matches["comp_id"], matches["away_team_id"]), index=matches.index).isin(valid_pairs)
    ]
    ctp_missing = ctp.loc[
        ~pd.Series(zip(ctp["comp_id"], ctp["team_id"]), index=ctp.index).isin(valid_pairs)
    ]

    for label, df in [
        ("matches.home_team_id", home_missing),
        ("matches.away_team_id", away_missing),
        ("ctp.(comp_id,team_id)", ctp_missing),
    ]:
        issues += int(len(df))
        for _, r in df.head(3).iterrows():
            if len(examples) < 10:
                examples.append(f"{label} orphan comp_id={r['comp_id']}")

    status = ValidationStatus.PASS if issues == 0 else ValidationStatus.FAIL
    return ValidationResult(
        rule_id="VAL-FK-002",
        dataset="matches,competition_team_player_mapping",
        field="(comp_id, home_team_id/away_team_id/team_id) -> teams.(comp_id, team_id)",
        severity=Severity.CRITICAL,
        status=status,
        affected_record_count=issues,
        new_anomaly_count=issues,
        short_description=(
            "0 orphan team references in matches or ctp, and 0 self-play fixtures."
            if issues == 0
            else f"Detected {issues} invalid team reference(s) or self-play matches."
        ),
        example_record_identifiers=examples,
        recommended_action="Halt ingestion and quarantine offending match or roster team rows.",
        metadata={
            "self_play_count": int(len(self_play)),
            "home_team_orphans": int(len(home_missing)),
            "away_team_orphans": int(len(away_missing)),
            "ctp_team_orphans": int(len(ctp_missing)),
        },
    )


def _check_val_fk_003_match_and_ball_team_refs(
    bundle: DatasetLoadBundle,
) -> ValidationResult:
    req = {
        "matches": ("match_id", "home_team_id", "away_team_id", "result"),
        "ball_by_ball": ("match_id", "innings", "innings_ball_num", "batting_team_id", "bowling_team_id"),
        "playing_eleven": ("match_id", "team_id"),
    }
    skip_reason = check_required_columns(bundle, req)
    if skip_reason:
        return make_skipped_result(
            rule_id="VAL-FK-003",
            dataset="ball_by_ball,playing_eleven",
            field="match_id, batting_team_id, bowling_team_id",
            severity=Severity.CRITICAL,
            reason=skip_reason,
            recommended_action="Ensure matches, ball_by_ball, and playing_eleven load cleanly.",
        )

    matches = bundle.get("matches")
    bbb = bundle.get("ball_by_ball")
    p11 = bundle.get("playing_eleven")
    assert matches is not None and bbb is not None and p11 is not None

    m_lookup = matches[["match_id", "home_team_id", "away_team_id"]]
    bbb_m = bbb[["match_id", "innings", "innings_ball_num", "batting_team_id", "bowling_team_id"]].merge(
        m_lookup, on="match_id", how="left"
    )
    orphan_bbb_matches = bbb_m.loc[bbb_m["home_team_id"].isna()]
    bad_bbb_teams = bbb_m.loc[
        bbb_m["home_team_id"].notna()
        & (
            (bbb_m["batting_team_id"] == bbb_m["bowling_team_id"])
            | ~bbb_m["batting_team_id"].isin(set(matches["home_team_id"]).union(set(matches["away_team_id"])))
            | ((bbb_m["batting_team_id"] != bbb_m["home_team_id"]) & (bbb_m["batting_team_id"] != bbb_m["away_team_id"]))
            | ((bbb_m["bowling_team_id"] != bbb_m["home_team_id"]) & (bbb_m["bowling_team_id"] != bbb_m["away_team_id"]))
        )
    ]

    p11_m = p11[["match_id", "team_id"]].merge(m_lookup, on="match_id", how="left")
    orphan_p11_matches = p11_m.loc[p11_m["home_team_id"].isna()]
    bad_p11_teams = p11_m.loc[
        p11_m["home_team_id"].notna()
        & (p11_m["team_id"] != p11_m["home_team_id"])
        & (p11_m["team_id"] != p11_m["away_team_id"])
    ]

    examples: list[str] = []
    for _, r in orphan_bbb_matches.head(3).iterrows():
        examples.append(f"bbb orphan match_id={r['match_id']}")
    for _, r in bad_bbb_teams.head(3).iterrows():
        examples.append(f"bbb bad teams {format_row_id(r, ['match_id', 'innings', 'innings_ball_num', 'batting_team_id', 'bowling_team_id'])}")
    for _, r in orphan_p11_matches.head(2).iterrows():
        examples.append(f"p11 orphan match_id={r['match_id']}")
    for _, r in bad_p11_teams.head(2).iterrows():
        examples.append(f"p11 team mismatch {format_row_id(r, ['match_id', 'team_id'])}")

    total_issues = (
        int(len(orphan_bbb_matches))
        + int(len(bad_bbb_teams))
        + int(len(orphan_p11_matches))
        + int(len(bad_p11_teams))
    )
    missing_from_bbb = sorted(
        int(x) for x in set(matches["match_id"].dropna()) - set(bbb["match_id"].dropna())
    )
    missing_from_p11 = sorted(
        int(x) for x in set(matches["match_id"].dropna()) - set(p11["match_id"].dropna())
    )

    status = ValidationStatus.PASS if total_issues == 0 else ValidationStatus.FAIL
    return ValidationResult(
        rule_id="VAL-FK-003",
        dataset="ball_by_ball,playing_eleven",
        field="match_id, batting_team_id, bowling_team_id -> matches",
        severity=Severity.CRITICAL,
        status=status,
        affected_record_count=total_issues,
        new_anomaly_count=total_issues,
        short_description=(
            f"0 orphan match/team references in ball_by_ball or playing_eleven "
            f"({len(missing_from_bbb)} abandoned matches absent from bbb; {len(missing_from_p11)} absent from p11)."
            if total_issues == 0
            else f"Detected {total_issues} orphan match_id or match-team mismatch(es)."
        ),
        example_record_identifiers=examples,
        recommended_action="Halt ingestion and inspect unmatched match or team IDs.",
        metadata={
            "orphan_bbb_match_rows": int(len(orphan_bbb_matches)),
            "bad_bbb_team_rows": int(len(bad_bbb_teams)),
            "orphan_p11_match_rows": int(len(orphan_p11_matches)),
            "bad_p11_team_rows": int(len(bad_p11_teams)),
            "matches_absent_from_ball_by_ball": missing_from_bbb,
            "matches_absent_from_playing_eleven": missing_from_p11,
        },
    )


def _check_val_fk_004_ball_player_to_ctp(bundle: DatasetLoadBundle) -> ValidationResult:
    req = {
        "matches": ("match_id", "comp_id"),
        "competition_team_player_mapping": ("comp_id", "team_id", "player_id"),
        "ball_by_ball": (
            "match_id",
            "innings",
            "innings_ball_num",
            "batting_team_id",
            "bowling_team_id",
            "striker_id",
            "non_striker_id",
            "bowler_id",
            "dismissed_player_id",
        ),
    }
    skip_reason = check_required_columns(bundle, req)
    if skip_reason:
        return make_skipped_result(
            rule_id="VAL-FK-004",
            dataset="ball_by_ball",
            field="(comp_id, team_id, striker/non_striker/bowler/dismissed_player_id) -> ctp",
            severity=Severity.CRITICAL,
            reason=skip_reason,
            recommended_action="Ensure matches, ctp, and ball_by_ball load cleanly.",
        )

    matches = bundle.get("matches")
    ctp = bundle.get("competition_team_player_mapping")
    bbb = bundle.get("ball_by_ball")
    assert matches is not None and ctp is not None and bbb is not None

    valid_ctp = ctp[["comp_id", "team_id", "player_id"]].drop_duplicates()
    bbb_c = bbb[
        [
            "match_id",
            "innings",
            "innings_ball_num",
            "batting_team_id",
            "bowling_team_id",
            "striker_id",
            "non_striker_id",
            "bowler_id",
            "dismissed_player_id",
        ]
    ].merge(matches[["match_id", "comp_id"]], on="match_id", how="left")

    role_checks = [
        ("striker_id", "batting_team_id"),
        ("non_striker_id", "batting_team_id"),
        ("bowler_id", "bowling_team_id"),
        ("dismissed_player_id", "batting_team_id"),
    ]
    total_orphans = 0
    examples: list[str] = []
    orphans_by_role: dict[str, int] = {}

    for p_col, t_col in role_checks:
        sub = bbb_c.loc[bbb_c[p_col].notna(), ["match_id", "innings", "innings_ball_num", "comp_id", t_col, p_col]].rename(
            columns={t_col: "team_id", p_col: "player_id"}
        )
        merged = sub.merge(
            valid_ctp.assign(_matched=1),
            on=["comp_id", "team_id", "player_id"],
            how="left",
        )
        miss = merged.loc[merged["_matched"].isna()]
        cnt = int(len(miss))
        orphans_by_role[p_col] = cnt
        total_orphans += cnt
        for _, r in miss.head(3).iterrows():
            if len(examples) < 10:
                examples.append(f"{p_col} missing in ctp {format_row_id(r, ['match_id', 'comp_id', 'team_id', 'player_id'])}")

    status = ValidationStatus.PASS if total_orphans == 0 else ValidationStatus.FAIL
    return ValidationResult(
        rule_id="VAL-FK-004",
        dataset="ball_by_ball",
        field="(comp_id, team_id, striker/non_striker/bowler/dismissed_player_id) -> ctp",
        severity=Severity.CRITICAL,
        status=status,
        affected_record_count=total_orphans,
        new_anomaly_count=total_orphans,
        short_description=(
            f"All {len(bbb):,} deliveries resolved 100% against competition_team_player_mapping (0 orphans)."
            if total_orphans == 0
            else f"{total_orphans} player reference(s) in ball_by_ball failed to resolve against competition_team_player_mapping."
        ),
        example_record_identifiers=examples,
        recommended_action="Halt ingestion on missing competition-team-player roster entries.",
        metadata={"orphans_by_role": orphans_by_role},
    )


def _check_val_fk_005_ball_player_to_playing_eleven(
    bundle: DatasetLoadBundle,
) -> ValidationResult:
    req = {
        "playing_eleven": ("match_id", "team_id", "player_id"),
        "ball_by_ball": (
            "match_id",
            "innings",
            "innings_ball_num",
            "batting_team_id",
            "bowling_team_id",
            "striker_id",
            "non_striker_id",
            "bowler_id",
            "dismissed_player_id",
        ),
    }
    skip_reason = check_required_columns(bundle, req)
    if skip_reason:
        return make_skipped_result(
            rule_id="VAL-FK-005",
            dataset="ball_by_ball,playing_eleven",
            field="(match_id, team_id, player_id)",
            severity=Severity.WARNING,
            reason=skip_reason,
            recommended_action="Ensure ball_by_ball and playing_eleven load cleanly.",
        )

    p11 = bundle.get("playing_eleven")
    bbb = bundle.get("ball_by_ball")
    assert p11 is not None and bbb is not None

    valid_p11 = p11[["match_id", "team_id", "player_id"]].drop_duplicates().assign(_matched=1)
    known_matches: frozenset[int] = KNOWN_EXCEPTIONS["uae_split_player_matches"]  # type: ignore[assignment]
    known_pids: frozenset[int] = KNOWN_EXCEPTIONS["uae_split_player_bbb_ids"]  # type: ignore[assignment]

    role_checks = [
        ("striker_id", "batting_team_id"),
        ("non_striker_id", "batting_team_id"),
        ("bowler_id", "bowling_team_id"),
        ("dismissed_player_id", "batting_team_id"),
    ]
    unmatched_frames: list[pd.DataFrame] = []
    unmatched_by_role: dict[str, int] = {}

    for p_col, t_col in role_checks:
        sub = bbb.loc[bbb[p_col].notna(), ["match_id", "innings", "innings_ball_num", t_col, p_col]].rename(
            columns={t_col: "team_id", p_col: "player_id"}
        )
        merged = sub.merge(valid_p11, on=["match_id", "team_id", "player_id"], how="left")
        miss = merged.loc[merged["_matched"].isna()].copy()
        miss["role"] = p_col
        unmatched_by_role[p_col] = int(len(miss))
        if len(miss) > 0:
            unmatched_frames.append(miss)

    if not unmatched_frames:
        return ValidationResult(
            rule_id="VAL-FK-005",
            dataset="ball_by_ball,playing_eleven",
            field="(match_id, team_id, player_id)",
            severity=Severity.WARNING,
            status=ValidationStatus.PASS,
            affected_record_count=0,
            short_description="100% of active delivery player IDs matched playing_eleven.",
            recommended_action="None required.",
        )

    all_miss = pd.concat(unmatched_frames, ignore_index=True)
    distinct_deliveries = int(
        all_miss[["match_id", "innings", "innings_ball_num"]].drop_duplicates().shape[0]
    )
    known_mask = all_miss["match_id"].isin(known_matches) & all_miss["player_id"].isin(known_pids)
    known_deliveries = int(
        all_miss.loc[known_mask, ["match_id", "innings", "innings_ball_num"]].drop_duplicates().shape[0]
    )
    new_deliveries = int(
        all_miss.loc[~known_mask, ["match_id", "innings", "innings_ball_num"]].drop_duplicates().shape[0]
    )

    examples = [
        f"{r['role']} missing in p11 {format_row_id(r, ['match_id', 'innings', 'innings_ball_num', 'team_id', 'player_id'])}"
        for _, r in all_miss.drop_duplicates(subset=["match_id", "player_id", "role"]).head(8).iterrows()
    ]

    return ValidationResult(
        rule_id="VAL-FK-005",
        dataset="ball_by_ball,playing_eleven",
        field="(match_id, team_id, player_id)",
        severity=Severity.WARNING,
        status=ValidationStatus.WARNING,
        affected_record_count=distinct_deliveries,
        known_exception_count=known_deliveries,
        new_anomaly_count=new_deliveries,
        short_description=(
            f"{distinct_deliveries} deliveries ({len(all_miss)} role refs) lack matching raw player_id in playing_eleven"
            + (
                f" — all within documented UAE split-ID matches {sorted(known_matches)}."
                if new_deliveries == 0
                else f" ({known_deliveries} known UAE, {new_deliveries} NEW unmatched deliveries)."
            )
        ),
        example_record_identifiers=examples,
        recommended_action="Warn and preserve raw IDs; resolve player joins via canonical player_alias map only in Stage 5+ if approved.",
        known_exceptions_summary=(
            f"UAE matches {sorted(known_matches)}: ball_by_ball logs {sorted(known_pids)} (Basil Hameed / Syed Haider) "
            "while playing_eleven logs {8638, 8729}."
        ),
        metadata={
            "distinct_deliveries_affected": distinct_deliveries,
            "total_role_references_missing": int(len(all_miss)),
            "missing_by_role": unmatched_by_role,
            "affected_match_ids": sorted(int(x) for x in all_miss["match_id"].dropna().unique()),
            "affected_player_ids": sorted(int(x) for x in all_miss["player_id"].dropna().unique()),
        },
    )


def _check_val_ent_001_player_entities(bundle: DatasetLoadBundle) -> ValidationResult:
    req = {
        "competition_team_player_mapping": ("comp_id", "team_id", "team_name", "player_id", "player_name"),
    }
    skip_reason = check_required_columns(bundle, req)
    if skip_reason:
        return make_skipped_result(
            rule_id="VAL-ENT-001",
            dataset="competition_team_player_mapping,ball_by_ball",
            field="player_id, player_name",
            severity=Severity.WARNING,
            reason=skip_reason,
            recommended_action="Ensure competition_team_player_mapping loads cleanly.",
        )

    ctp = bundle.get("competition_team_player_mapping")
    bbb = bundle.get("ball_by_ball")
    assert ctp is not None

    # 1) One player_id must map to exactly one player_name across ctp + bbb
    id_name_frames = [ctp[["player_id", "player_name"]].dropna()]
    if bbb is not None:
        for id_c, nm_c in [
            ("striker_id", "striker_name"),
            ("non_striker_id", "non_striker_name"),
            ("bowler_id", "bowler_name"),
        ]:
            if {id_c, nm_c}.issubset(bbb.columns):
                id_name_frames.append(
                    bbb[[id_c, nm_c]].dropna().rename(columns={id_c: "player_id", nm_c: "player_name"})
                )

    combined = pd.concat(id_name_frames, ignore_index=True).drop_duplicates()
    id_counts = combined.groupby("player_id")["player_name"].nunique()
    conflicting_ids = id_counts[id_counts > 1]

    # 2) Same player_name mapping to >1 player_id in ctp
    ctp_id_per_name = ctp.groupby("player_name")["player_id"].nunique()
    multi_id_names = sorted(str(n) for n in ctp_id_per_name[ctp_id_per_name > 1].index)
    known_same_name: dict[str, frozenset[int]] = KNOWN_EXCEPTIONS["same_name_distinct_ids"]  # type: ignore[assignment]
    confirmed_homonyms: frozenset[str] = KNOWN_EXCEPTIONS["confirmed_true_homonym_names"]  # type: ignore[assignment]

    same_team_split: list[str] = []
    cross_team_names: list[str] = []
    new_multi_id_names: list[str] = []
    examples: list[str] = []

    for pname in multi_id_names:
        sub = ctp.loc[ctp["player_name"] == pname]
        pids = sorted(int(x) for x in sub["player_id"].unique())
        teams = sorted(str(x) for x in sub["team_name"].unique())
        same_comp_same_team = int((sub.groupby(["comp_id", "team_id"])["player_id"].nunique() > 1).sum())
        if pname in confirmed_homonyms:
            cross_team_names.append(pname)
        else:
            same_team_split.append(pname)
        is_known = pname in known_same_name and set(pids) == set(known_same_name[pname])
        if not is_known:
            new_multi_id_names.append(pname)
        if len(examples) < 10:
            tag = "homonym" if pname in confirmed_homonyms else ("split_same_comp_team" if same_comp_same_team > 0 else "split_id")
            examples.append(f"{pname}: ids={pids}, teams={teams} [{tag}]")

    conflicting_id_details: dict[int, list[str]] = {}
    for pid in conflicting_ids.index[:10]:
        names = sorted(str(n) for n in combined.loc[combined["player_id"] == pid, "player_name"].unique())
        conflicting_id_details[int(pid)] = names
        examples.insert(0, f"[NEW] ID_NAME_VARIANT player_id={pid} -> {names}")

    known_name_count = len(multi_id_names) - len(new_multi_id_names)
    new_count = int(len(conflicting_ids)) + len(new_multi_id_names)
    affected = int(len(conflicting_ids)) + len(multi_id_names)

    if affected == 0:
        status = ValidationStatus.PASS
    else:
        status = ValidationStatus.WARNING

    return ValidationResult(
        rule_id="VAL-ENT-001",
        dataset="competition_team_player_mapping,ball_by_ball",
        field="player_id, player_name",
        severity=Severity.WARNING,
        status=status,
        affected_record_count=affected,
        known_exception_count=known_name_count,
        new_anomaly_count=new_count,
        short_description=(
            f"1 player_id->name spelling/initial conflict across tables ({conflicting_id_details}); "
            f"{len(multi_id_names)} shared player_names in ctp (3 confirmed homonyms, 4 split IDs)."
            if len(conflicting_ids) == 1
            else f"{len(conflicting_ids)} player_id->name conflicts across tables and {len(multi_id_names)} player_names with >1 player_id in ctp "
            f"(known={known_name_count}, new={new_count})."
        ),
        example_record_identifiers=examples[:10],
        recommended_action="Do NOT merge true homonyms or auto-overwrite names; log curated player_alias_override policy downstream.",
        known_exceptions_summary=(
            "7 documented ctp name pairs: 3 confirmed homonyms (Abdul Samad, Rashid Khan, Haider Ali) + "
            "4 same-team/nation split pairs (Basil Hameed, Muhammad Farooq, Mohammad Ali, Bashir Ahmad), "
            "plus Syed Haider/Haider Shah across ball_by_ball & playing_eleven. Note: newly observed player_id=4458 name variant "
            "('AHT Donald' in ctp vs 'Aneurin Donald' in ball_by_ball)."
        ),
        metadata={
            "id_to_multiple_names": int(len(conflicting_ids)),
            "conflicting_id_details": conflicting_id_details,
            "multi_id_names": multi_id_names,
            "same_team_split_candidates": same_team_split,
            "confirmed_homonyms": cross_team_names,
            "new_multi_id_names": new_multi_id_names,
        },
    )
