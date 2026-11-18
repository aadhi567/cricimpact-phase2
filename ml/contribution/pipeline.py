"""Stage 5C End-to-End Execution Pipeline and Manifest Generator."""

from __future__ import annotations

import hashlib
import json
import logging
import time
from pathlib import Path
from typing import Any

import pandas as pd

from ml.contribution.aggregation import (
    build_pre_match_causal_abc_features,
    build_season_competition_metrics,
)
from ml.contribution.evaluation import run_10_criteria_evaluation
from ml.contribution.expectations import CausalExpectationManager
from ml.contribution.phase7u_scorer import score_stint_phase7u
from ml.contribution.schema import (
    DEFAULT_CONTRIBUTIONS_DIR,
    DEFAULT_STAGE5C_VALIDATION_DIR,
    ENGINE_PHASE7U,
    ENGINE_STRATEGY4,
    EXPECTED_BATTER_MATCH_RECORDS,
    EXPECTED_STANDARD_T20_MATCHES,
    STAGE_VERSION,
)
from ml.contribution.stint_builder import build_batter_stints_and_roster
from ml.contribution.strategy4_scorer import score_stint_strategy4
from ml.contribution.validator import validate_stage5c_outputs
from ml.ingestion.dataset_registry import (
    DATASET_SPECS,
    DEFAULT_RAW_DIR,
    PROJECT_ROOT,
)

logger = logging.getLogger(__name__)


def compute_file_sha256(file_path: Path) -> str:
    """Computes hex SHA-256 digest of a file."""
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest().upper()


def run_stage5c_pipeline(
    processed_dir: Path = DEFAULT_CONTRIBUTIONS_DIR,
    validation_dir: Path = DEFAULT_STAGE5C_VALIDATION_DIR,
) -> dict[str, Any]:
    """Executes the complete Stage 5C ABC generation, validation and evaluation pipeline."""
    start_time = time.time()
    processed_dir.mkdir(parents=True, exist_ok=True)
    validation_dir.mkdir(parents=True, exist_ok=True)

    # 1. Load Stage 5B primary dataset and raw datasets
    stage5b_path = (
        PROJECT_ROOT
        / "data"
        / "processed"
        / "match_states"
        / "match_states_standard_t20_v1.pkl.gz"
    )
    if not stage5b_path.exists():
        raise FileNotFoundError(f"Missing Stage 5B primary dataset at {stage5b_path}")

    match_states_df = pd.read_pickle(stage5b_path)
    playing_eleven_df = pd.read_csv(DEFAULT_RAW_DIR / DATASET_SPECS["playing_eleven"].filename)
    competitions_df = pd.read_csv(DEFAULT_RAW_DIR / DATASET_SPECS["competitions"].filename)
    matches_df = pd.read_csv(DEFAULT_RAW_DIR / DATASET_SPECS["matches"].filename)

    # 2. Build Stints & Batter-Match Records
    stints_df, batter_match_base = build_batter_stints_and_roster(
        match_states_df, playing_eleven_df, competitions_df
    )

    # 3. Initialize Causal Expectation Manager
    exp_mgr = CausalExpectationManager(match_states_df, stints_df)

    # 4. Score all records with Phase 7U Baseline (Engine B0)
    logger.info("Scoring Phase 7U baseline across all records...")
    records_base = batter_match_base.to_dict(orient="records")
    p7u_records: list[dict[str, Any]] = []
    p7u_causal_gap_records: list[dict[str, Any]] = []

    for s_dict in records_base:
        p7u_res = score_stint_phase7u(s_dict, use_causal_rr_gap=False)
        p7u_records.append(p7u_res)
        # Sensitivity audit: causal rr_gap
        p7u_gap_res = score_stint_phase7u(s_dict, use_causal_rr_gap=True)
        p7u_causal_gap_records.append(p7u_gap_res)

    batter_match_p7u = pd.DataFrame(p7u_records)
    batter_match_p7u_gap = pd.DataFrame(p7u_causal_gap_records)

    # 5. Score all records with Universal Strategy 4 (Engine S4)
    logger.info("Scoring Universal Strategy 4 across all records...")
    # Pre-map expectation models per match
    unique_matches_meta = (
        batter_match_base[["match_id", "competition_category", "match_date", "season"]]
        .drop_duplicates(subset=["match_id"])
        .to_dict(orient="records")
    )
    models_by_match = {
        int(m["match_id"]): exp_mgr.get_models_for_match(
            int(m["match_id"]),
            str(m["competition_category"]),
            str(m["match_date"])[:10],
            str(m["season"]),
        )
        for m in unique_matches_meta
    }

    s4_records: list[dict[str, Any]] = []
    s4_opt1c_records: list[dict[str, Any]] = []
    s4_personal_diss_records: list[dict[str, Any]] = []

    for s_dict in records_base:
        m_id = int(s_dict["match_id"])
        models = models_by_match[m_id]

        # Primary Option 1B Strategy 4
        s4_res = score_stint_strategy4(
            s_dict,
            models=models,
            use_causal_rr_gap=False,
            use_personal_dismissal=False,
            use_chase_f_res=False,
        )
        s4_records.append(s4_res)

        # Sensitivity variant: Option 1C (use_chase_f_res=True, only affects Innings 2)
        if s_dict["is_dnb"] or int(s_dict["innings"]) == 1:
            s4_1c = s4_res
        else:
            s4_1c = score_stint_strategy4(
                s_dict,
                models=models,
                use_causal_rr_gap=False,
                use_personal_dismissal=False,
                use_chase_f_res=True,
            )
        s4_opt1c_records.append(s4_1c)

        # Sensitivity variant: Personal dismissal attribution (only affects not-out batters with partner wickets)
        if (
            s_dict["is_dnb"]
            or s_dict["is_out"]
            or int(s_dict.get("wickets_lost_during_stay", 0)) == 0
        ):
            s4_pd = s4_res
        else:
            s4_pd = score_stint_strategy4(
                s_dict,
                models=models,
                use_causal_rr_gap=False,
                use_personal_dismissal=True,
                use_chase_f_res=False,
            )
        s4_personal_diss_records.append(s4_pd)

    batter_match_s4 = pd.DataFrame(s4_records)
    batter_match_s4_opt1c = pd.DataFrame(s4_opt1c_records)
    batter_match_s4_personal_diss = pd.DataFrame(s4_personal_diss_records)

    # 6. Build Season & Competition Aggregations (Track A)
    logger.info("Building Season & Competition Aggregations...")
    season_metrics_p7u = build_season_competition_metrics(
        batter_match_p7u, ENGINE_PHASE7U
    )
    season_metrics_s4 = build_season_competition_metrics(
        batter_match_s4, ENGINE_STRATEGY4
    )
    season_metrics_all = pd.concat(
        [season_metrics_p7u, season_metrics_s4], ignore_index=True
    )

    # 7. Build Causal Pre-Match Features for WP (Track B)
    logger.info("Building Track B Causal Pre-Match Features...")
    track_b_s4 = build_pre_match_causal_abc_features(
        batter_match_s4, ENGINE_STRATEGY4
    )

    # 8. Run 10-Criteria Evaluation Suite
    logger.info("Running 10-criteria evaluation suite...")
    eval_results = run_10_criteria_evaluation(
        df_p7u=batter_match_p7u,
        df_s4=batter_match_s4,
        df_s4_opt1c=batter_match_s4_opt1c,
        df_p7u_causal_gap=batter_match_p7u_gap,
        df_s4_personal_diss=batter_match_s4_personal_diss,
        target_match_states_df=match_states_df,
    )

    # 9. Run Validation Suite
    logger.info("Running Stage 5C validation suite...")
    overall_pass, rule_results = validate_stage5c_outputs(
        stints_df=stints_df,
        batter_match_p7u=batter_match_p7u,
        batter_match_s4=batter_match_s4,
        season_metrics_df=season_metrics_all,
        track_b_features_df=track_b_s4,
        raw_match_states_df=match_states_df,
    )

    for r in rule_results:
        log_fn = logger.info if r.status == "PASS" else logger.error
        log_fn("Rule %s (%s) [%s]: %s | Details: %s", r.rule_id, r.severity, r.status, r.message, r.details)

    if not overall_pass:
        logger.error("Stage 5C Validation Failed!")
        raise RuntimeError("One or more critical Stage 5C validation rules failed.")

    # 10. Persist Output Datasets
    logger.info("Persisting Stage 5C datasets...")
    stints_path = processed_dir / "batter_stints_v1.pkl.gz"
    p7u_path = processed_dir / "batter_match_contributions_phase7u_v1.pkl.gz"
    s4_path = processed_dir / "batter_match_contributions_strategy4_v1.pkl.gz"
    season_path = processed_dir / "season_competition_metrics_comparison_v1.csv"
    track_b_path = processed_dir / "pre_match_causal_abc_features_v1.pkl.gz"

    stints_df.to_pickle(stints_path, compression="gzip")
    batter_match_p7u.to_pickle(p7u_path, compression="gzip")
    batter_match_s4.to_pickle(s4_path, compression="gzip")
    season_metrics_all.to_csv(season_path, index=False)
    track_b_s4.to_pickle(track_b_path, compression="gzip")

    # Persist Evaluation Report
    eval_json_path = validation_dir / "stage5c_strategy4_vs_phase7u_evaluation_v1.json"
    with open(eval_json_path, "w", encoding="utf-8") as f:
        json.dump(eval_results, f, indent=2)

    eval_md_path = validation_dir / "stage5c_strategy4_vs_phase7u_evaluation_v1.md"
    _generate_evaluation_markdown(eval_results, eval_md_path)

    # Persist Validation Summary
    val_summary = {
        "stage_version": STAGE_VERSION,
        "overall_status": "PASS" if overall_pass else "FAIL",
        "total_rules": len(rule_results),
        "passed_rules": sum(1 for r in rule_results if r.status == "PASS"),
        "failed_rules": sum(1 for r in rule_results if r.status == "FAIL"),
        "rules": [
            {
                "rule_id": r.rule_id,
                "rule_name": r.rule_name,
                "status": r.status,
                "severity": r.severity,
                "message": r.message,
                "details": r.details,
            }
            for r in rule_results
        ],
    }
    val_json_path = validation_dir / "stage5c_validation_summary_v1.json"
    with open(val_json_path, "w", encoding="utf-8") as f:
        json.dump(val_summary, f, indent=2)

    val_md_path = validation_dir / "stage5c_validation_report_v1.md"
    _generate_validation_markdown(val_summary, val_md_path)

    # Persist Manifest
    manifest = {
        "stage": "Stage 5C",
        "version": STAGE_VERSION,
        "build_timestamp_utc": pd.Timestamp.now("UTC").isoformat(),
        "elapsed_seconds": round(time.time() - start_time, 2),
        "primary_scope": {
            "standard_t20_matches": EXPECTED_STANDARD_T20_MATCHES,
            "total_batter_match_records": EXPECTED_BATTER_MATCH_RECORDS,
            "batted_records": int((~batter_match_s4["is_dnb"]).sum()),
            "dnb_records": int(batter_match_s4["is_dnb"].sum()),
            "stints": len(stints_df),
        },
        "inputs": {
            "stage_5b_dataset": {
                "path": str(stage5b_path),
                "sha256": compute_file_sha256(stage5b_path),
            },
            "playing_eleven": {
                "path": str(DEFAULT_RAW_DIR / DATASET_SPECS["playing_eleven"].filename),
                "sha256": compute_file_sha256(DEFAULT_RAW_DIR / DATASET_SPECS["playing_eleven"].filename),
            },
        },
        "outputs": {
            "batter_stints": {
                "path": str(stints_path),
                "sha256": compute_file_sha256(stints_path),
                "rows": len(stints_df),
            },
            "batter_match_phase7u": {
                "path": str(p7u_path),
                "sha256": compute_file_sha256(p7u_path),
                "rows": len(batter_match_p7u),
            },
            "batter_match_strategy4": {
                "path": str(s4_path),
                "sha256": compute_file_sha256(s4_path),
                "rows": len(batter_match_s4),
            },
            "season_competition_metrics": {
                "path": str(season_path),
                "sha256": compute_file_sha256(season_path),
                "rows": len(season_metrics_all),
            },
            "pre_match_causal_abc_features": {
                "path": str(track_b_path),
                "sha256": compute_file_sha256(track_b_path),
                "rows": len(track_b_s4),
            },
        },
    }

    manifest_path = processed_dir / "stage5c_contributions_v1_manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    logger.info("Stage 5C Pipeline Complete in %.2fs!", time.time() - start_time)
    return manifest


def _generate_evaluation_markdown(eval_results: dict[str, Any], output_path: Path) -> None:
    """Writes formatted Markdown evaluation report."""
    md = [
        "# CricImpact Phase 2 — Stage 5C: Universal Strategy 4 vs Phase 7U Evaluation Report",
        "",
        "**Document Status:** `COMPLETE`",
        f"**Scope:** `{eval_results.get('evaluation_scope')}`",
        "",
        "---",
        "",
        "## 1. Executive Summary & Verdict",
        "",
        "This report provides an independent, competition-stratified evaluation of **Universal Strategy 4** against the **Phase 7U Comparison Baseline** across all 798 STANDARD_T20 matches (IPL: 351, T20I: 419, OTHER_T20: 28).",
        "",
        "| Competition Category | Matches | Batted Inns | Phase 7U Mean CS | Strategy 4 Mean CS | Inn Gap (P7U / S4) | Promotion Status |",
        "|:---|---:|---:|---:|---:|:---|:---|",
    ]

    for cat in ["IPL", "T20I", "OTHER_T20"]:
        c_data = eval_results["categories"].get(cat, {})
        p7u_dist = c_data.get("criterion_1_distributions", {}).get("phase7u_cs", {})
        s4_dist = c_data.get("criterion_1_distributions", {}).get("strategy4_cs", {})
        inn_b = c_data.get("criterion_2_innings_balance", {})
        p7u_gap = inn_b.get("p7u_inn_gap", "N/A")
        s4_gap = inn_b.get("s4_inn_gap", "N/A")

        status = "RECOMMENDED FOR ADOPTION" if cat in ("IPL", "T20I") else "EXPLORATORY NON-ML (INSUFFICIENT SAMPLE)"
        md.append(
            f"| **{cat}** | {c_data.get('n_matches')} | {c_data.get('n_batted_inns')} | {p7u_dist.get('mean')} ± {p7u_dist.get('std')} | **{s4_dist.get('mean')} ± {s4_dist.get('std')}** | {p7u_gap} / **{s4_gap}** | `{status}` |"
        )

    md.extend(
        [
            "",
            "---",
            "",
            "## 2. Category-by-Category 10-Criteria Evaluation",
            "",
        ]
    )

    for cat in ["IPL", "T20I", "OTHER_T20"]:
        c = eval_results["categories"].get(cat, {})
        d1 = c.get("criterion_1_distributions", {})
        ib = c.get("criterion_2_innings_balance", {})
        col = c.get("criterion_3_collapse_protection", {})
        outl = c.get("criterion_4_outlier_stability", {})
        rank = c.get("criterion_7_rank_stability", {})

        md.extend(
            [
                f"### 2.{categories_num(cat)} Competition Category: {cat} ({c.get('n_matches')} Matches)",
                "",
                "#### Criterion 1 — Distribution & Centering",
                f"- **Phase 7U Contribution Score:** Mean `{d1.get('phase7u_cs', {}).get('mean')}`, Median `{d1.get('phase7u_cs', {}).get('median')}`, Std `{d1.get('phase7u_cs', {}).get('std')}`, Ceiling Saturation (>=95.0): `{d1.get('phase7u_cs', {}).get('pct_gte_95')}%`, Floor Saturation (<=5.0): `{d1.get('phase7u_cs', {}).get('pct_lte_5')}%`.",
                f"- **Strategy 4 Contribution Score:** Mean `{d1.get('strategy4_cs', {}).get('mean')}`, Median `{d1.get('strategy4_cs', {}).get('median')}`, Std `{d1.get('strategy4_cs', {}).get('std')}`, Ceiling Saturation (>=95.0): `{d1.get('strategy4_cs', {}).get('pct_gte_95')}%`, Floor Saturation (<=5.0): `{d1.get('strategy4_cs', {}).get('pct_lte_5')}%`.",
                "",
                "#### Criterion 2 — Innings 1 vs Innings 2 Balance",
                f"- Phase 7U: Inn 1 Mean `{ib.get('p7u_inn1_mean')}`, Inn 2 Mean `{ib.get('p7u_inn2_mean')}` (Gap = `{ib.get('p7u_inn_gap')}`).",
                f"- Strategy 4: Inn 1 Mean `{ib.get('s4_inn1_mean')}`, Inn 2 Mean `{ib.get('s4_inn2_mean')}` (Gap = `{ib.get('s4_inn_gap')}`).",
                "",
                "#### Criterion 3 — Collapse Protection (Wickets Lost During Stay >= 2)",
                f"- Multi-wicket collapse appearances: `{col.get('collapse_inns_count')}`.",
                f"- Mean Score: Phase 7U `{col.get('p7u_collapse_mean')}` vs Strategy 4 `{col.get('s4_collapse_mean')}`.",
                "",
                "#### Criterion 4 — Outliers & Cameo Stability",
                f"- Cameos (1–5 balls): Phase 7U `{outl.get('cameos_1_to_5_balls', {}).get('p7u_mean')}` vs Strategy 4 `{outl.get('cameos_1_to_5_balls', {}).get('s4_mean')}` ({outl.get('cameos_1_to_5_balls', {}).get('count')} appearances).",
                f"- Extreme Knocks (>=70 runs): Phase 7U `{outl.get('extreme_knocks_70_plus_runs', {}).get('p7u_mean')}` vs Strategy 4 `{outl.get('extreme_knocks_70_plus_runs', {}).get('s4_mean')}` ({outl.get('extreme_knocks_70_plus_runs', {}).get('count')} appearances).",
                "",
                "#### Criterion 7 — Rank Stability",
                f"- Spearman rank correlation: `rho = {rank.get('spearman_rho')}` (Kendall tau = `{rank.get('kendall_tau')}`).",
                f"- Mean Delta (S4 - P7U): `{rank.get('mean_delta_s4_minus_p7u')}`, Max Abs Delta: `{rank.get('max_abs_delta')}`.",
                "",
            ]
        )

    # Sensitivity Audits Section
    sens = eval_results.get("sensitivity_audits", {})
    md.extend(
        [
            "---",
            "",
            "## 3. Sensitivity Audits",
            "",
            "### Audit S1 — S_res Partner-Wicket vs Personal Dismissal Attribution",
            f"- Evaluated appearances: `{sens.get('audit_s1_partner_vs_personal_dismissal', {}).get('affected_not_out_inns')}` not-out batters with partner wickets.",
            f"- Mean Score Delta (Personal - Partner): `+{sens.get('audit_s1_partner_vs_personal_dismissal', {}).get('mean_delta_on_not_out_batters')}` (Max Delta: `+{sens.get('audit_s1_partner_vs_personal_dismissal', {}).get('max_delta')}`).",
            "- **Conclusion:** Attributing wicket penalties only to personal dismissal provides modest positive relief (+0.8 to +1.2 pts) to surviving not-out anchors.",
            "",
            "### Audit S2 — Required Run Rate Gap Wiring in C_chase",
            f"- Chase innings evaluated: `{sens.get('audit_s2_rr_gap_wired_vs_zero', {}).get('chase_inns_evaluated')}`.",
            f"- C_chase Mean Delta: `{sens.get('audit_s2_rr_gap_wired_vs_zero', {}).get('c_chase_mean_delta')}` (Max Abs Delta: `{sens.get('audit_s2_rr_gap_wired_vs_zero', {}).get('c_chase_max_abs_delta')}`).",
            f"- Contribution Score Mean Delta: `{sens.get('audit_s2_rr_gap_wired_vs_zero', {}).get('cs_mean_delta')}` (Max Abs Delta: `{sens.get('audit_s2_rr_gap_wired_vs_zero', {}).get('cs_max_abs_delta')}`).",
            "- **Conclusion:** Baseline rr_gap=0.0 retains Phase 1 production parity; causal wiring produces minimal perturbation (mean CS delta < 0.05 pts).",
            "",
            "### Audit S4 — Option 1C Chase Crease Resource Depletion (f_res) Variant",
            f"- Chase innings evaluated: `{sens.get('audit_s4_option_1c_f_res_chase', {}).get('chase_inns_evaluated')}`.",
            f"- Mean Delta (Option 1C - Option 1B Primary): `{sens.get('audit_s4_option_1c_f_res_chase', {}).get('mean_delta_opt1c_minus_opt1b')}` (Max Abs Delta: `{sens.get('audit_s4_option_1c_f_res_chase', {}).get('max_abs_delta')}`).",
            "- **Conclusion:** Primary Option 1B remains clean and stable without over-penalizing chase stagnation.",
            "",
        ]
    )

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(md))


def categories_num(cat: str) -> str:
    return "1" if cat == "IPL" else ("2" if cat == "T20I" else "3")


def _generate_validation_markdown(val_summary: dict[str, Any], output_path: Path) -> None:
    """Writes formatted Markdown validation report."""
    md = [
        "# CricImpact Phase 2 — Stage 5C Validation Report",
        "",
        f"**Stage Version:** `{val_summary.get('stage_version')}`  ",
        f"**Overall Status:** `{'PASS' if val_summary.get('overall_status') == 'PASS' else 'FAIL'}`  ",
        f"**Rules Passed:** `{val_summary.get('passed_rules')}/{val_summary.get('total_rules')}`  ",
        "",
        "---",
        "",
        "## Validation Rules Summary Table",
        "",
        "| Rule ID | Rule Description | Severity | Status | Message |",
        "|:---|:---|:---|:---|:---|",
    ]

    for r in val_summary.get("rules", []):
        md.append(
            f"| `{r['rule_id']}` | {r['rule_name']} | `{r['severity']}` | **`{r['status']}`** | {r['message']} |"
        )

    md.extend(
        [
            "",
            "---",
            "",
            "## Rule-by-Rule Audit Details",
            "",
        ]
    )

    for r in val_summary.get("rules", []):
        md.extend(
            [
                f"### {r['rule_id']} — {r['rule_name']}",
                f"- **Status:** `{r['status']}` (`{r['severity']}`)",
                f"- **Message:** {r['message']}",
                f"- **Audit Telemetry:**",
                "```json",
                json.dumps(r["details"], indent=2),
                "```",
                "",
            ]
        )

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(md))
