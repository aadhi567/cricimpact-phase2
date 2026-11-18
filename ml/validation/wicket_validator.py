"""Wicket, dismissal type, Retired Hurt, Retire Out, and Cricket Law validation (Stage 4 Phase 3E)."""

from __future__ import annotations

import pandas as pd

from ml.ingestion.csv_loader import DatasetLoadBundle
from ml.ingestion.dataset_registry import (
    KNOWN_EXCEPTIONS,
    NOBALL_OR_BYE_ALLOWED_DISMISSALS,
    VALID_DISMISSAL_TYPES,
    WIDE_ALLOWED_DISMISSALS,
)
from ml.validation.validation_engine import (
    Severity,
    ValidationResult,
    ValidationStatus,
    check_required_columns,
    format_row_id,
    make_skipped_result,
)


_DISMISSAL_ID_TO_TYPES: dict[int, frozenset[str]] = {
    1: frozenset({"Bowled"}),
    2: frozenset({"Caught"}),
    3: frozenset({"LBW"}),
    4: frozenset({"RunOut"}),
    5: frozenset({"Stump"}),
    6: frozenset({"Hit Wicket"}),
    9: frozenset({"Retire Out"}),
    10: frozenset({"Obstracting the field", "Obstructing the field"}),
}


def validate_wickets(bundle: DatasetLoadBundle) -> list[ValidationResult]:
    """Execute VAL-WKT-001 and VAL-WKT-002 on ball_by_ball.csv."""
    return [
        _check_val_wkt_001_wicket_and_retirement_integrity(bundle),
        _check_val_wkt_002_dismissal_law_by_extras(bundle),
    ]


def _check_val_wkt_001_wicket_and_retirement_integrity(
    bundle: DatasetLoadBundle,
) -> ValidationResult:
    req = {
        "ball_by_ball": (
            "match_id",
            "innings",
            "overid",
            "over_ball_num",
            "striker_id",
            "non_striker_id",
            "is_wicket",
            "dismissal_type_id",
            "dismissal_type",
            "dismissed_player_id",
        )
    }
    skip_reason = check_required_columns(bundle, req)
    if skip_reason:
        return make_skipped_result(
            rule_id="VAL-WKT-001",
            dataset="ball_by_ball",
            field="is_wicket, dismissal_type, dismissal_type_id, dismissed_player_id",
            severity=Severity.WARNING,
            reason=skip_reason,
            recommended_action="Ensure wicket columns are loaded cleanly.",
        )

    bbb = bundle.get("ball_by_ball")
    assert bbb is not None
    if not pd.api.types.is_bool_dtype(bbb["is_wicket"].dtype) or not pd.api.types.is_numeric_dtype(
        bbb["dismissal_type_id"].dtype
    ):
        return make_skipped_result(
            rule_id="VAL-WKT-001",
            dataset="ball_by_ball",
            field="is_wicket, dismissal_type_id",
            severity=Severity.WARNING,
            reason="Wicket typed columns failed parsing.",
            recommended_action="Fix VAL-SCH-002 parse errors first.",
        )
    w_df = bbb.loc[bbb["is_wicket"].fillna(False)]
    nw_df = bbb.loc[~bbb["is_wicket"].fillna(False)]

    # 1) Official wickets missing dismissal_type / dismissal_type_id or invalid enum/id match
    missing_dt = w_df.loc[w_df["dismissal_type"].isna() | w_df["dismissal_type_id"].isna()]
    bad_dt_enum = w_df.loc[
        w_df["dismissal_type"].notna()
        & ~w_df["dismissal_type"].astype(str).isin(VALID_DISMISSAL_TYPES)
    ]

    id_type_mismatch_idx: list[int] = []
    for idx, r in w_df.dropna(subset=["dismissal_type_id", "dismissal_type"]).iterrows():
        did = int(r["dismissal_type_id"])
        dtype = str(r["dismissal_type"])
        if dtype not in _DISMISSAL_ID_TO_TYPES.get(did, frozenset()):
            id_type_mismatch_idx.append(idx)

    # 2) Official wickets missing dismissed_player_id (preserve known 40709 Retire Out!)
    known_retire_out_coords: frozenset[tuple[int, int, int, int]] = KNOWN_EXCEPTIONS["retire_out_missing_dismissed_id_coords"]  # type: ignore[assignment]
    missing_dp = w_df.loc[w_df["dismissed_player_id"].isna()]
    known_missing_dp = 0
    new_missing_dp_rows: list[pd.Series] = []
    for _, r in missing_dp.iterrows():
        coord = (int(r["match_id"]), int(r["innings"]), int(r["overid"]), int(r["over_ball_num"]))
        if coord in known_retire_out_coords and str(r["dismissal_type"]) == "Retire Out":
            known_missing_dp += 1
        else:
            new_missing_dp_rows.append(r)

    # 3) Official dismissed_player_id must be one of the two batters on strike
    bad_batter_ref = bbb.loc[
        bbb["dismissed_player_id"].notna()
        & (bbb["dismissed_player_id"] != bbb["striker_id"])
        & (bbb["dismissed_player_id"] != bbb["non_striker_id"])
    ]

    # 4) Retired Hurt detection: is_wicket == False AND dismissed_player_id present
    retired_hurt_df = nw_df.loc[nw_df["dismissed_player_id"].notna()]
    invalid_nw_with_dt = nw_df.loc[
        nw_df["dismissal_type"].notna() | nw_df["dismissal_type_id"].notna()
    ]

    # 5) Spelling variant check ('Obstracting the field')
    obstracting_df = w_df.loc[w_df["dismissal_type"].astype(str) == "Obstracting the field"]

    retire_out_total = int((w_df["dismissal_type"].astype(str) == "Retire Out").sum())

    hard_errors = (
        int(len(missing_dt))
        + int(len(bad_dt_enum))
        + len(id_type_mismatch_idx)
        + len(new_missing_dp_rows)
        + int(len(bad_batter_ref))
        + int(len(invalid_nw_with_dt))
    )

    known_count = int(len(retired_hurt_df)) + known_missing_dp + int(len(obstracting_df))
    examples: list[str] = []

    for _, r in missing_dt.head(3).iterrows():
        examples.append(f"MISSING_DISMISSAL_TYPE {format_row_id(r, ['match_id', 'innings', 'overid', 'over_ball_num'])}")
    for _, r in bad_dt_enum.head(2).iterrows():
        examples.append(f"INVALID_DISMISSAL_TYPE {format_row_id(r, ['match_id', 'innings', 'overid', 'over_ball_num', 'dismissal_type'])}")
    for r in new_missing_dp_rows[:3]:
        examples.append(f"NEW_MISSING_DISMISSED_ID {format_row_id(r, ['match_id', 'innings', 'overid', 'over_ball_num', 'dismissal_type'])}")
    for _, r in bad_batter_ref.head(2).iterrows():
        examples.append(f"DISMISSED_NOT_BATTER {format_row_id(r, ['match_id', 'innings', 'overid', 'over_ball_num', 'dismissed_player_id'])}")
    for _, r in invalid_nw_with_dt.head(2).iterrows():
        examples.append(f"NON_WICKET_HAS_TYPE {format_row_id(r, ['match_id', 'innings', 'overid', 'over_ball_num', 'dismissal_type'])}")
    for _, r in missing_dp.head(2).iterrows():
        if len(examples) < 10:
            examples.append(f"[KNOWN] RETIRE_OUT_BLANK_ID {format_row_id(r, ['match_id', 'innings', 'overid', 'over_ball_num', 'striker_id'])}")
    for _, r in retired_hurt_df.head(3).iterrows():
        if len(examples) < 10:
            examples.append(f"[KNOWN] RETIRED_HURT {format_row_id(r, ['match_id', 'innings', 'overid', 'over_ball_num', 'dismissed_player_id'])}")

    if hard_errors > 0:
        status = ValidationStatus.FAIL
    elif known_count > 0:
        status = ValidationStatus.WARNING
    else:
        status = ValidationStatus.PASS

    return ValidationResult(
        rule_id="VAL-WKT-001",
        dataset="ball_by_ball",
        field="is_wicket, dismissal_type, dismissal_type_id, dismissed_player_id",
        severity=Severity.WARNING,
        status=status,
        affected_record_count=hard_errors + known_count,
        known_exception_count=known_count,
        new_anomaly_count=hard_errors,
        short_description=(
            f"Official wickets: {len(w_df):,}; Retired Hurt (is_wicket=false, dismissed_player_id present): {len(retired_hurt_df)}; "
            f"Retire Out: {retire_out_total} ({known_missing_dp} known blank ID at 40709 inn 2 19.5); "
            f"'Obstracting' spelling rows: {len(obstracting_df)}; unexpected errors: {hard_errors}."
        ),
        example_record_identifiers=examples[:10],
        recommended_action=(
            "Never count non-empty dismissed_player_id with is_wicket=false as a wicket (12 Retired Hurt cases); "
            "resolve 40709 19.5 blank Retire Out ID to striker downstream and normalize 'Obstracting' spelling."
        ),
        known_exceptions_summary=(
            "Preserved 12 Retired Hurt rows (is_wicket=false + populated dismissed_player_id), "
            "match 40709 inn 2 19.5 Retire Out blank dismissed_player_id, and 2 'Obstracting the field' rows."
        ),
        metadata={
            "official_wickets": int(len(w_df)),
            "retired_hurt_count": int(len(retired_hurt_df)),
            "retire_out_count": retire_out_total,
            "known_missing_dp_retire_out": known_missing_dp,
            "new_missing_dp": len(new_missing_dp_rows),
            "obstracting_spelling_count": int(len(obstracting_df)),
            "missing_dismissal_type_on_wicket": int(len(missing_dt)),
            "invalid_dismissal_enum": int(len(bad_dt_enum)),
            "id_type_mismatches": len(id_type_mismatch_idx),
            "dismissed_not_on_pitch": int(len(bad_batter_ref)),
            "non_wicket_with_dismissal_type": int(len(invalid_nw_with_dt)),
            "dismissal_type_counts": {
                str(k): int(v) for k, v in w_df["dismissal_type"].value_counts().to_dict().items()
            },
        },
    )


def _check_val_wkt_002_dismissal_law_by_extras(
    bundle: DatasetLoadBundle,
) -> ValidationResult:
    req = {
        "ball_by_ball": (
            "match_id",
            "innings",
            "overid",
            "over_ball_num",
            "extras_type",
            "is_wicket",
            "dismissal_type",
        )
    }
    skip_reason = check_required_columns(bundle, req)
    if skip_reason:
        return make_skipped_result(
            rule_id="VAL-WKT-002",
            dataset="ball_by_ball",
            field="extras_type, is_wicket, dismissal_type",
            severity=Severity.CRITICAL,
            reason=skip_reason,
            recommended_action="Ensure extras_type and wicket columns load cleanly.",
        )

    bbb = bundle.get("ball_by_ball")
    assert bbb is not None
    if not pd.api.types.is_bool_dtype(bbb["is_wicket"].dtype):
        return make_skipped_result(
            rule_id="VAL-WKT-002",
            dataset="ball_by_ball",
            field="is_wicket",
            severity=Severity.CRITICAL,
            reason="is_wicket failed boolean parsing.",
            recommended_action="Fix VAL-SCH-002 parse errors first.",
        )
    w_df = bbb.loc[bbb["is_wicket"].fillna(False)].copy()
    w_df["_et"] = w_df["extras_type"].astype(str)
    w_df["_dt"] = w_df["dismissal_type"].fillna("<NA>").astype(str)

    bad_wide = w_df.loc[(w_df["_et"] == "wide") & ~w_df["_dt"].isin(WIDE_ALLOWED_DISMISSALS)]
    bad_nb_or_bye = w_df.loc[
        w_df["_et"].isin({"Overstep", "other", "byes", "legbyes"})
        & ~w_df["_dt"].isin(NOBALL_OR_BYE_ALLOWED_DISMISSALS)
    ]

    violations = pd.concat([bad_wide, bad_nb_or_bye])
    examples = [
        f"ILLEGAL_DISMISSAL extras={r['_et']!r} dismissal={r['_dt']!r} at {format_row_id(r, ['match_id', 'innings', 'overid', 'over_ball_num'])}"
        for _, r in violations.head(8).iterrows()
    ]

    status = ValidationStatus.PASS if len(violations) == 0 else ValidationStatus.FAIL
    return ValidationResult(
        rule_id="VAL-WKT-002",
        dataset="ball_by_ball",
        field="extras_type, is_wicket, dismissal_type",
        severity=Severity.CRITICAL,
        status=status,
        affected_record_count=int(len(violations)),
        new_anomaly_count=int(len(violations)),
        short_description=(
            f"All {int((w_df['_et'] != 'None').sum())} wickets on extras balls obey Cricket Laws "
            "(wide: Stump/RunOut/Obstructing only; Overstep/other/byes/legbyes: RunOut/Obstructing only)."
            if len(violations) == 0
            else f"{len(violations)} wicket(s) violated Cricket Laws for dismissal modes on wides/no-balls/byes."
        ),
        example_record_identifiers=examples,
        recommended_action="Halt ingestion if bowler-credited dismissals (Caught/Bowled/LBW/Stump on no-ball) appear on illegal deliveries.",
        metadata={
            "wide_wickets": int((w_df["_et"] == "wide").sum()),
            "overstep_wickets": int((w_df["_et"] == "Overstep").sum()),
            "other_wickets": int((w_df["_et"] == "other").sum()),
            "byes_wickets": int((w_df["_et"] == "byes").sum()),
            "legbyes_wickets": int((w_df["_et"] == "legbyes").sum()),
        },
    )
