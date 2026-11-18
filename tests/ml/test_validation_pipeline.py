"""Comprehensive synthetic unit and integration tests for Stage 4 validation pipeline."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from ml.ingestion.csv_loader import load_raw_datasets
from ml.ingestion.dataset_registry import DATASET_SPECS
from ml.validation import build_default_validation_engine, run_ingestion_and_validation
from ml.validation.extras_validator import derive_is_legal_delivery, derive_team_runs
from ml.validation.report_generator import write_validation_reports
from ml.validation.validation_engine import Severity, ValidationResult, ValidationStatus
from tests.conftest import (
    _ball_row,
    build_clean_synthetic_tables,
    materialize_tables,
)


def _by_id(report) -> dict[str, ValidationResult]:
    return {r.rule_id: r for r in report.results}


def test_clean_baseline_all_31_rules_pass(synthetic_raw_dir: Path) -> None:
    bundle, report = run_ingestion_and_validation(synthetic_raw_dir)
    results = _by_id(report)

    assert len(results) == 31
    assert report.status_counts["FAIL"] == 0
    assert report.status_counts["WARNING"] == 0
    assert report.status_counts["SKIPPED"] == 0
    assert report.status_counts["PASS"] == 31
    assert report.total_known_exceptions == 0
    assert report.total_new_anomalies == 0
    assert bundle.all_loaded is True


def test_unexpected_column_flags_warning_and_keeps_column(tmp_path: Path) -> None:
    tables = build_clean_synthetic_tables()
    c_cols, c_rows = tables["competitions"]
    tables["competitions"] = (c_cols + ["extra_col"], [r + ["kept"] for r in c_rows])
    raw_dir = materialize_tables(tmp_path / "raw", tables)

    bundle, report = run_ingestion_and_validation(raw_dir)
    results = _by_id(report)

    assert "extra_col" in bundle.datasets["competitions"].columns
    assert results["VAL-SCH-001"].status == ValidationStatus.WARNING
    assert results["VAL-PK-001"].status == ValidationStatus.PASS
    assert results["VAL-EXT-005"].status == ValidationStatus.PASS


def test_independent_checks_continue_and_emit_skipped_when_playing_eleven_missing(
    synthetic_raw_dir: Path,
) -> None:
    (synthetic_raw_dir / "playing_eleven.csv").unlink()
    _, report = run_ingestion_and_validation(synthetic_raw_dir)
    results = _by_id(report)

    assert results["VAL-SCH-001"].status == ValidationStatus.FAIL
    assert results["VAL-PK-003"].status == ValidationStatus.SKIPPED
    assert results["VAL-FK-005"].status == ValidationStatus.SKIPPED
    assert results["VAL-P11-001"].status == ValidationStatus.SKIPPED
    assert results["VAL-EXT-001"].status == ValidationStatus.PASS
    assert results["VAL-EXT-005"].status == ValidationStatus.PASS
    assert results["VAL-WKT-002"].status == ValidationStatus.PASS


def test_primary_keys_duplicates_and_innings_ball_num_gap(tmp_path: Path) -> None:
    tables = build_clean_synthetic_tables()
    # 1) Duplicate match_id in matches
    m_cols, m_rows = tables["matches"]
    m_rows.append(list(m_rows[0]))
    # 2) Duplicate innings_ball_num + create gap in ball_by_ball
    b_cols, b_rows = tables["ball_by_ball"]
    ib_idx = b_cols.index("innings_ball_num")
    b_rows[1][ib_idx] = 1  # duplicates ib=1 and creates gap before ib=3
    raw_dir = materialize_tables(tmp_path / "raw", tables)

    _, report = run_ingestion_and_validation(raw_dir)
    results = _by_id(report)

    assert results["VAL-PK-001"].status == ValidationStatus.FAIL
    assert results["VAL-PK-001"].severity == Severity.CRITICAL
    assert results["VAL-PK-002"].status == ValidationStatus.FAIL
    assert results["VAL-PK-002"].severity == Severity.CRITICAL
    assert results["VAL-PK-002"].metadata["duplicate_extra_rows"] == 1
    assert results["VAL-PK-002"].metadata["gap_innings_count"] == 1


def test_playing_eleven_duplicate_super_over_vs_non_super_over(tmp_path: Path) -> None:
    # Non-Super Over duplicate -> FAIL (halt), severity WARNING preserved
    tables_non_so = build_clean_synthetic_tables()
    p_cols, p_rows = tables_non_so["playing_eleven"]
    dup_row = list(p_rows[0])
    dup_row[p_cols.index("batting_order")] = 2
    p_rows.append(dup_row)
    raw_non_so = materialize_tables(tmp_path / "non_so", tables_non_so)
    _, rep_non_so = run_ingestion_and_validation(raw_non_so)
    pk3_non_so = _by_id(rep_non_so)["VAL-PK-003"]
    assert pk3_non_so.status == ValidationStatus.FAIL
    assert pk3_non_so.severity == Severity.WARNING
    assert pk3_non_so.new_anomaly_count == 1

    # Super Over match (known 13613) duplicate -> WARNING, known_exception_count == 1
    tables_so = build_clean_synthetic_tables()
    for tname in ("matches", "playing_eleven", "ball_by_ball"):
        cols, rows = tables_so[tname]
        mid_idx = cols.index("match_id")
        for r in rows:
            if r[mid_idx] == 1001:
                r[mid_idx] = 13613
    p_cols_so, p_rows_so = tables_so["playing_eleven"]
    dup_so = list(p_rows_so[0])
    dup_so[p_cols_so.index("batting_order")] = 2
    p_rows_so.append(dup_so)
    raw_so = materialize_tables(tmp_path / "so", tables_so)
    _, rep_so = run_ingestion_and_validation(raw_so)
    pk3_so = _by_id(rep_so)["VAL-PK-003"]
    assert pk3_so.status == ValidationStatus.WARNING
    assert pk3_so.known_exception_count == 1
    assert pk3_so.new_anomaly_count == 0


def test_foreign_key_failures_and_player_entity_conflicts(tmp_path: Path) -> None:
    tables = build_clean_synthetic_tables()
    m_cols, m_rows = tables["matches"]
    m_rows[0][m_cols.index("comp_id")] = 999  # orphan comp_id -> VAL-FK-001 FAIL
    m_rows[0][m_cols.index("away_team_id")] = 1  # self-play -> VAL-FK-002 & VAL-FK-003 FAIL

    # Conflicting player_id -> two names across ctp vs ball_by_ball -> VAL-ENT-001
    b_cols, b_rows = tables["ball_by_ball"]
    b_rows[0][b_cols.index("striker_name")] = "Aliased Name"
    # Striker missing from playing_eleven -> VAL-FK-005
    b_rows[0][b_cols.index("striker_id")] = 112  # bench player on 1001 -> also triggers bench leak
    # Orphan player missing from ctp -> VAL-FK-004
    b_rows[1][b_cols.index("striker_id")] = 99999

    raw_dir = materialize_tables(tmp_path / "raw", tables)
    _, report = run_ingestion_and_validation(raw_dir)
    results = _by_id(report)

    assert results["VAL-FK-001"].status == ValidationStatus.FAIL
    assert results["VAL-FK-002"].status == ValidationStatus.FAIL
    assert results["VAL-FK-003"].status == ValidationStatus.FAIL
    assert results["VAL-FK-004"].status == ValidationStatus.FAIL
    assert results["VAL-ENT-001"].status == ValidationStatus.WARNING
    assert results["VAL-ENT-001"].metadata["id_to_multiple_names"] >= 1
    assert results["VAL-ENT-001"].new_anomaly_count >= 1


def test_legal_delivery_and_extras_regression_guards(tmp_path: Path) -> None:
    df_test = pd.DataFrame(
        {
            "extras_type": ["None", "wide", "Overstep", "other", "byes", "legbyes", "Penalty"],
            "runs": [4, 0, 1, 0, 0, 0, 0],
            "extras1_runs": [0, 2, 1, 1, 2, 1, 5],
            "extras_2_runs": [0, 0, 4, 0, 0, 0, 0],
        }
    )
    assert list(derive_is_legal_delivery(df_test)) == [
        True,
        False,
        False,
        False,
        True,
        True,
        True,
    ]
    assert list(derive_team_runs(df_test)) == [4, 2, 6, 1, 2, 1, 5]

    # Legacy code 6 on extras_type='None' -> VAL-EXT-001 FAIL
    tables = build_clean_synthetic_tables()
    b_cols, b_rows = tables["ball_by_ball"]
    b_rows[0][b_cols.index("extras1_runs")] = 6
    b_rows[3][b_cols.index("extras_type")] = "NoBallUnknown"
    raw_dir = materialize_tables(tmp_path / "raw", tables)
    _, report = run_ingestion_and_validation(raw_dir)
    results = _by_id(report)
    assert results["VAL-EXT-001"].status == ValidationStatus.FAIL
    assert results["VAL-EXT-002"].status == ValidationStatus.FAIL

    # Arithmetic invariants: wide with runs > 0 and Overstep with extras1_runs != 1 -> VAL-EXT-003 FAIL
    tables2 = build_clean_synthetic_tables()
    b_cols2, b_rows2 = tables2["ball_by_ball"]
    wide_row = next(r for r in b_rows2 if r[b_cols2.index("extras_type")] == "wide")
    nb_row = next(r for r in b_rows2 if r[b_cols2.index("extras_type")] == "Overstep")
    wide_row[b_cols2.index("runs")] = 1
    nb_row[b_cols2.index("extras1_runs")] = 2
    raw_dir2 = materialize_tables(tmp_path / "raw2", tables2)
    _, rep2 = run_ingestion_and_validation(raw_dir2)
    ext3 = _by_id(rep2)["VAL-EXT-003"]
    assert ext3.status == ValidationStatus.FAIL
    assert ext3.metadata["bad_wide_or_byes_with_bat_runs"] == 1
    assert ext3.metadata["bad_noball_e1_not_1"] == 1


def test_known_vs_excessive_extras_anomalies(tmp_path: Path) -> None:
    # >5 new extras anomalies violates VAL-EXT-004 threshold -> FAIL
    tables = build_clean_synthetic_tables()
    b_cols, b_rows = tables["ball_by_ball"]
    e1_idx = b_cols.index("extras1_runs")
    et_idx = b_cols.index("extras_type")
    cnt = 0
    for r in b_rows:
        if r[et_idx] == "None" and cnt < 6:
            r[e1_idx] = 1
            cnt += 1
    raw_dir = materialize_tables(tmp_path / "raw_gt5", tables)
    _, rep = run_ingestion_and_validation(raw_dir)
    ext4 = _by_id(rep)["VAL-EXT-004"]
    assert ext4.status == ValidationStatus.FAIL
    assert ext4.new_anomaly_count == 6

    # Known coord (36097, 2, 8, 6) cleanly separated as known_exception_count=1, new=0
    tables_known = build_clean_synthetic_tables()
    for tname in ("matches", "playing_eleven", "ball_by_ball"):
        cols, rows = tables_known[tname]
        for r in rows:
            if r[cols.index("match_id")] == 1001:
                r[cols.index("match_id")] = 36097
    bk_cols, bk_rows = tables_known["ball_by_ball"]
    # Adjust one innings=2 row to over 8, ball 6? Ensure mid-match overs >= 6 won't trigger seq error
    # Instead test known anomaly directly by giving row coords (36097, 2, 8, 6) on a 1-over-ish sequence:
    # We test VAL-EXT-004 in isolation via bundle!
    bk_rows[12][bk_cols.index("innings")] = 2
    bk_rows[12][bk_cols.index("overid")] = 8
    bk_rows[12][bk_cols.index("over_ball_num")] = 6
    bk_rows[12][bk_cols.index("extras_type")] = "None"
    bk_rows[12][bk_cols.index("extras1_runs")] = 1
    raw_dir_k = materialize_tables(tmp_path / "raw_known", tables_known)
    _, rep_k = run_ingestion_and_validation(raw_dir_k)
    ext4_k = _by_id(rep_k)["VAL-EXT-004"]
    assert ext4_k.status == ValidationStatus.WARNING
    assert ext4_k.known_exception_count == 1
    assert ext4_k.new_anomaly_count == 0


def test_sequence_known_vs_new_overs_and_bowl_speed(tmp_path: Path) -> None:
    tables = build_clean_synthetic_tables()
    b_cols, b_rows = tables["ball_by_ball"]
    # Add 7th legal ball to inn 1 over 1 without changing innings_ball_num gaps (append after ov1, shift ov2 ib up)
    for r in b_rows:
        if r[b_cols.index("innings")] == 1 and r[b_cols.index("overid")] == 2:
            r[b_cols.index("innings_ball_num")] += 1
    extra_legal = _ball_row(
        match_id=1001,
        innings=1,
        overid=1,
        over_ball_num=7,
        innings_ball_num=7,
        batting_team_id=1,
        bowling_team_id=2,
        striker_id=101,
        striker_name="Player 101",
        non_striker_id=102,
        non_striker_name="Player 102",
        bowler_id=208,
        bowler_name="Player 208",
        runs=0,
        bowl_speed=999.0,  # out of range >170
        ts="2025-05-01 14:00:06 UTC",
    )
    b_rows.insert(6, extra_legal)
    raw_dir = materialize_tables(tmp_path / "raw", tables)
    _, rep = run_ingestion_and_validation(raw_dir)
    results = _by_id(rep)

    seq1 = results["VAL-SEQ-001"]
    assert seq1.status == ValidationStatus.WARNING
    assert seq1.new_anomaly_count == 1  # deduplicated (not double counted!)
    assert seq1.metadata["overs_over_6_legal_balls"] == 1

    tel1 = results["VAL-TEL-001"]
    assert tel1.status == ValidationStatus.WARNING
    assert tel1.new_anomaly_count == 1
    assert tel1.metadata["fast_over_170_count"] == 1


def test_retired_hurt_vs_retire_out_and_illegal_dismissals(tmp_path: Path) -> None:
    tables = build_clean_synthetic_tables()
    b_cols, b_rows = tables["ball_by_ball"]
    # Mark one non-wicket row in Inn 2 as Retired Hurt (is_wicket=false + dismissed_player_id populated)
    b_rows[13][b_cols.index("dismissed_player_id")] = 202
    # Add a Catch dismissal on wide -> must trigger VAL-WKT-002 FAIL (CRITICAL)
    wide_row = next(r for r in b_rows if r[b_cols.index("extras_type")] == "wide")
    wide_row[b_cols.index("is_wicket")] = "true"
    wide_row[b_cols.index("dismissal_type_id")] = 2
    wide_row[b_cols.index("dismissal_type")] = "Caught"
    wide_row[b_cols.index("dismissed_player_id")] = 201

    raw_dir = materialize_tables(tmp_path / "raw", tables)
    _, rep = run_ingestion_and_validation(raw_dir)
    results = _by_id(rep)

    wkt1 = results["VAL-WKT-001"]
    assert wkt1.status == ValidationStatus.WARNING
    assert wkt1.metadata["retired_hurt_count"] == 1
    assert results["VAL-WKT-002"].status == ValidationStatus.FAIL
    assert results["VAL-WKT-002"].severity == Severity.CRITICAL

    # Verify Retired Hurt alone does NOT increment wickets in VAL-EXT-005
    tables_rh = build_clean_synthetic_tables()
    br_cols, br_rows = tables_rh["ball_by_ball"]
    br_rows[13][br_cols.index("dismissed_player_id")] = 202
    raw_rh = materialize_tables(tmp_path / "raw_rh", tables_rh)
    _, rep_rh = run_ingestion_and_validation(raw_rh)
    res_rh = _by_id(rep_rh)
    assert res_rh["VAL-WKT-001"].metadata["retired_hurt_count"] == 1
    assert res_rh["VAL-WKT-002"].status == ValidationStatus.PASS
    assert res_rh["VAL-EXT-005"].status == ValidationStatus.PASS


def test_retire_out_blank_id_known_40709_vs_new(tmp_path: Path) -> None:
    tables = build_clean_synthetic_tables()
    b_cols, b_rows = tables["ball_by_ball"]
    # Replace caught wicket in inn 2 with Retire Out lacking dismissed_player_id
    w_row = next(r for r in b_rows if r[b_cols.index("is_wicket")] == "true" and r[b_cols.index("innings")] == 2)
    w_row[b_cols.index("dismissal_type_id")] = 9
    w_row[b_cols.index("dismissal_type")] = "Retire Out"
    w_row[b_cols.index("dismissed_player_id")] = ""
    raw_new = materialize_tables(tmp_path / "raw_new", tables)
    _, rep_new = run_ingestion_and_validation(raw_new)
    wkt1_new = _by_id(rep_new)["VAL-WKT-001"]
    assert wkt1_new.status == ValidationStatus.FAIL
    assert wkt1_new.metadata["new_missing_dp"] == 1


def test_super_over_dls_and_chase_overshoot_failure(tmp_path: Path) -> None:
    # Test 1: Super Over (innings=3/4) & DLS regime isolation
    tables = build_clean_synthetic_tables()
    m_cols, m_rows = tables["matches"]
    b_cols, b_rows = tables["ball_by_ball"]

    # Add DLS match 1002 (20 overs text DLS, missing target -> WARNING; also valid revised_overs)
    m_dls = list(m_rows[0])
    m_dls[m_cols.index("match_id")] = 1002
    m_dls[m_cols.index("first_inn_revised_overs")] = 60
    m_dls[m_cols.index("second_inn_revised_overs")] = 60
    m_dls[m_cols.index("revised_target")] = ""
    m_dls[m_cols.index("result")] = "Beta Warriors Won by 5 runs (DLS Method)"
    m_rows.append(m_dls)

    # Add Super Over match 1003 with innings 3 & 4 rows
    m_so = list(m_rows[0])
    m_so[m_cols.index("match_id")] = 1003
    m_so[m_cols.index("result")] = "Match Tied (Beta Warriors won Super Over)"
    m_rows.append(m_so)
    so_ball = _ball_row(
        match_id=1003,
        innings=3,
        overid=1,
        over_ball_num=1,
        innings_ball_num=1,
        batting_team_id=1,
        bowling_team_id=2,
        striker_id=101,
        striker_name="Player 101",
        non_striker_id=102,
        non_striker_name="Player 102",
        bowler_id=208,
        bowler_name="Player 208",
        runs=4,
        is_four=True,
    )
    b_rows.append(so_ball)
    # Minimal playing eleven for 1002 & 1003
    p_cols, p_rows = tables["playing_eleven"]
    extra_p = []
    for r in p_rows:
        r2 = list(r)
        r2[p_cols.index("match_id")] = 1002
        r3 = list(r)
        r3[p_cols.index("match_id")] = 1003
        extra_p.extend([r2, r3])
    p_rows.extend(extra_p)

    raw_dir = materialize_tables(tmp_path / "raw_regimes", tables)
    _, rep = run_ingestion_and_validation(raw_dir)
    results = _by_id(rep)

    assert results["VAL-MCH-003"].status == ValidationStatus.PASS
    assert results["VAL-MCH-003"].metadata["super_over_matches"] == [1003]
    assert results["VAL-MCH-002"].status == ValidationStatus.WARNING
    assert results["VAL-MCH-002"].metadata["dls_super_over_overlap_count"] == 0
    # Match 1001 alone is clean_completed
    assert results["VAL-EXT-005"].metadata["clean_completed_matches"] == 1
    assert results["VAL-EXT-005"].status == ValidationStatus.PASS

    # Test 2: Invalid chase overshoot (add +8 run anomaly -> s2_prev=13 <=16, s2=21, overshoot=5; wait make last ball=6 while prev=17 > 16!)
    tables_ch = build_clean_synthetic_tables()
    bc, br = tables_ch["ball_by_ball"]
    br[-2][bc.index("runs")] = 6  # s2_prev becomes 19 > s1=16! Violates chase stopping rule
    raw_ch = materialize_tables(tmp_path / "raw_chase_fail", tables_ch)
    _, rep_ch = run_ingestion_and_validation(raw_ch)
    assert _by_id(rep_ch)["VAL-EXT-005"].status == ValidationStatus.FAIL


def test_playing_eleven_impact_sub_t20i_concussion_and_bench_leak(tmp_path: Path) -> None:
    # 1) Valid 12 played with is_impact=1 in T20 -> VAL-P11-001 PASS
    tables = build_clean_synthetic_tables()
    p_cols, p_rows = tables["playing_eleven"]
    # Promote Team 1 bench player 112 to played Impact Sub (is_played=true, is_impact=1)
    bench_t1 = next(r for r in p_rows if r[p_cols.index("team_id")] == 1 and r[p_cols.index("is_played")] == "false")
    bench_t1[p_cols.index("batting_order")] = 12
    bench_t1[p_cols.index("is_played")] = "true"
    bench_t1[p_cols.index("is_captain")] = "false"
    bench_t1[p_cols.index("is_wk")] = "false"
    bench_t1[p_cols.index("is_impact")] = 1
    raw_imp = materialize_tables(tmp_path / "raw_imp", tables)
    _, rep_imp = run_ingestion_and_validation(raw_imp)
    assert _by_id(rep_imp)["VAL-P11-001"].status == ValidationStatus.PASS
    assert _by_id(rep_imp)["VAL-P11-001"].metadata["team_matches_12_played"] == 1

    # 2) T20I match with 12 played & is_impact=0 -> identified cleanly under t20i_concussion_sub_cases
    tables_conc = build_clean_synthetic_tables()
    m_cols, m_rows = tables_conc["matches"]
    m_rows[0][m_cols.index("comp_id")] = 200  # T20I comp
    m_rows[0][m_cols.index("home_team_id")] = 3
    m_rows[0][m_cols.index("home_team")] = "Gamma XI"
    m_rows[0][m_cols.index("away_team_id")] = 4
    m_rows[0][m_cols.index("away_team")] = "Delta XI"
    m_rows[0][m_cols.index("home_team_captain_id")] = 301
    m_rows[0][m_cols.index("away_team_captain_id")] = 401
    m_rows[0][m_cols.index("toss_win_team_id")] = 3
    m_rows[0][m_cols.index("win_team_id")] = 4
    m_rows[0][m_cols.index("result")] = "Delta XI Won by 9 wickets"
    pc, pr = tables_conc["playing_eleven"]
    for r in pr:
        r[pc.index("team_id")] = 3 if r[pc.index("team_id")] == 1 else 4
        r[pc.index("player_id")] = r[pc.index("player_id")] + 200
    bench_t3 = next(r for r in pr if r[pc.index("team_id")] == 3 and r[pc.index("is_played")] == "false")
    bench_t3[pc.index("batting_order")] = 12
    bench_t3[pc.index("is_played")] = "true"
    bench_t3[pc.index("is_captain")] = "false"
    bench_t3[pc.index("is_wk")] = "false"
    bc, br = tables_conc["ball_by_ball"]
    for r in br:
        r[bc.index("batting_team_id")] = 3 if r[bc.index("batting_team_id")] == 1 else 4
        r[bc.index("bowling_team_id")] = 4 if r[bc.index("batting_team_id")] == 3 else 3
        for c in ("striker_id", "non_striker_id", "bowler_id", "dismissed_player_id"):
            idx = bc.index(c)
            if r[idx] != "":
                r[idx] = int(r[idx]) + 200
                nc = c.replace("_id", "_name")
                if nc in bc:
                    r[bc.index(nc)] = f"Player {r[idx]}"
    raw_conc = materialize_tables(tmp_path / "raw_conc", tables_conc)
    _, rep_conc = run_ingestion_and_validation(raw_conc)
    p11_conc = _by_id(rep_conc)["VAL-P11-001"]
    assert p11_conc.status == ValidationStatus.WARNING
    assert p11_conc.metadata["t20i_concussion_sub_cases"] == 1
    assert p11_conc.metadata["non_t20i_12_without_impact"] == 0

    # 3) Bench player appearing in ball_by_ball -> FAIL
    tables_leak = build_clean_synthetic_tables()
    bcl, brl = tables_leak["ball_by_ball"]
    brl[0][bcl.index("striker_id")] = 112  # 112 is bench on team 1
    raw_leak = materialize_tables(tmp_path / "raw_leak", tables_leak)
    _, rep_leak = run_ingestion_and_validation(raw_leak)
    assert _by_id(rep_leak)["VAL-P11-001"].status == ValidationStatus.FAIL
    assert _by_id(rep_leak)["VAL-P11-001"].metadata["bench_leaks_in_ball_by_ball"] == 1


def test_validation_engine_scope_and_non_overwrite_reports(
    synthetic_raw_dir: Path, tmp_path: Path
) -> None:
    bundle, report = run_ingestion_and_validation(synthetic_raw_dir)
    out_dir = tmp_path / "validation_out"

    # Confirm separate T20 / T20I format counts are preserved in VAL-SRC-001
    src1 = _by_id(report)["VAL-SRC-001"]
    assert src1.metadata["competitions_by_format"] == {"T20": 1, "T20I": 1}

    written1 = write_validation_reports(
        report, output_dir=out_dir, raw_hashes_unchanged=True, phase1_untouched=True
    )
    assert written1["markdown"].name == "stage4_ingestion_validation_report.md"
    assert written1["json"].name == "stage4_ingestion_validation_summary.json"

    md_text = written1["markdown"].read_text(encoding="utf-8")
    for sec_num in range(1, 17):
        assert f"## {sec_num}." in md_text

    json_data = json.loads(written1["json"].read_text(encoding="utf-8"))
    assert json_data["total_rules"] == 31
    assert len(json_data["file_summaries"]) == len(DATASET_SPECS)

    # Writing a second time MUST version cleanly to _v2 rather than overwriting
    written2 = write_validation_reports(
        report, output_dir=out_dir, raw_hashes_unchanged=True, phase1_untouched=True
    )
    assert written2["markdown"].name == "stage4_ingestion_validation_report_v2.md"
    assert written2["json"].name == "stage4_ingestion_validation_summary_v2.json"
    assert written1["markdown"].exists()
    assert bundle.all_loaded


def test_schema_domains_unlabeled_matches_timestamps_and_boundaries(tmp_path: Path) -> None:
    tables = build_clean_synthetic_tables()
    m_cols, m_rows = tables["matches"]
    b_cols, b_rows = tables["ball_by_ball"]

    # Add valid No Result match with empty win_team_id -> VAL-MCH-001 PASS
    m_nr = list(m_rows[0])
    m_nr[m_cols.index("match_id")] = 1004
    m_nr[m_cols.index("win_team_id")] = ""
    m_nr[m_cols.index("result")] = "No Result"
    m_rows.append(m_nr)

    # Corrupt batting_type enum -> VAL-SCH-004 FAIL; midnight UTC + boundary omission -> VAL-SEQ-002 & VAL-BND-001 WARNING
    b_rows[0][b_cols.index("batting_type")] = "SWITCH"
    b_rows[0][b_cols.index("delivery_ist_time")] = "2025-05-01 00:00:00 UTC"
    b_rows[3][b_cols.index("is_four")] = "false"  # runs=4, is_four=false

    raw_dir = materialize_tables(tmp_path / "raw_misc", tables)
    _, rep = run_ingestion_and_validation(raw_dir)
    results = _by_id(rep)

    assert results["VAL-SCH-004"].status == ValidationStatus.FAIL
    assert results["VAL-MCH-001"].status == ValidationStatus.PASS
    assert results["VAL-MCH-001"].metadata["regime_counts"]["unlabeled"] == 1
    assert results["VAL-SEQ-002"].status == ValidationStatus.WARNING
    assert results["VAL-BND-001"].status == ValidationStatus.WARNING
    assert results["VAL-BND-001"].new_anomaly_count == 1

    # Now blank win_team_id with 'Won by' text & bad date -> VAL-MCH-001 FAIL & VAL-SCH-002 / VAL-SRC-001 FAIL
    tables2 = build_clean_synthetic_tables()
    m2_cols, m2_rows = tables2["matches"]
    m2_rows[0][m2_cols.index("win_team_id")] = ""
    m2_rows[0][m2_cols.index("match_date")] = "2099-01-01"
    raw_dir2 = materialize_tables(tmp_path / "raw_bad_mch", tables2)
    _, rep2 = run_ingestion_and_validation(raw_dir2)
    res2 = _by_id(rep2)
    assert res2["VAL-MCH-001"].status == ValidationStatus.FAIL
    assert res2["VAL-SRC-001"].status == ValidationStatus.FAIL

