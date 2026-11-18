"""CricImpact Phase 2 — Stage 7C Batch Evaluation Script.

Executes the production HPP Engine across the full historical corpus (798 matches)
and generates `data/processed/contributions/hpp_stint_evaluations_v1.pkl.gz`.
"""

import gzip
import os
import pickle
import sys
import time
from pathlib import Path
import pandas as pd
import numpy as np

# Ensure project root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from ml.contribution.hpp_engine import evaluate_batter_stints
from ml.contribution.hpp_aggregator import aggregate_player_career, aggregate_player_season


def main():
    print("=" * 80)
    print("STAGE 7C: RUNNING PRODUCTION HPP EVALUATION BATCH")
    print("=" * 80)

    start_time = time.time()

    # 1. Load Match States
    print("Loading match states...")
    with gzip.open("data/processed/match_states/match_states_standard_t20_v1.pkl.gz", "rb") as f:
        df_ms = pickle.load(f)
    print(f"Loaded match states: {len(df_ms)} delivery transitions")

    # 2. Load Frozen Stage 7A.3C Benchmarks
    print("Loading Stage 7A.3C frozen ground benchmarks...")
    with gzip.open("scratch/stage_7a_3c/eval_df.pkl.gz", "rb") as f:
        df_eval = pickle.load(f)
    bench_map = dict(zip(df_eval["match_id"], df_eval["arch3_shrink_m5_total"]))
    print(f"Loaded {len(bench_map)} ground benchmarks")

    # 3. Load Player Names
    print("Loading player names...")
    df_bbb = pd.read_csv("data/raw/ball_by_ball.csv", usecols=["striker_id", "striker_name"]).drop_duplicates()
    name_map = dict(zip(df_bbb["striker_id"], df_bbb["striker_name"]))

    # 4. Load Matches for Outcome
    print("Loading matches...")
    df_matches = pd.read_csv("data/raw/matches.csv")

    # 5. Load Stints Metadata for Dismissal routing and DNB tracking
    print("Loading stint metadata...")
    with gzip.open("data/processed/contributions/batter_stints_v1.pkl.gz", "rb") as f:
        df_stints_meta = pickle.load(f)
    print(f"Loaded stint metadata: {len(df_stints_meta)} records")

    # 6. Execute HPP Engine Evaluation
    print("Evaluating batter stints...")
    df_evaluated = evaluate_batter_stints(
        match_states_df=df_ms,
        ground_benchmark_map=bench_map,
        player_names_map=name_map,
        matches_df=df_matches,
        stints_metadata_df=df_stints_meta,
    )

    # 7. Output directory and save
    out_dir = os.path.join("data", "processed", "contributions")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "hpp_stint_evaluations_v1.pkl.gz")

    print(f"Saving evaluated stints to {out_path}...")
    with gzip.open(out_path, "wb") as f:
        pickle.dump(df_evaluated, f, protocol=pickle.HIGHEST_PROTOCOL)

    file_size_mb = os.path.getsize(out_path) / (1024 * 1024)
    print(f"Saved {out_path} successfully ({file_size_mb:.2f} MB)")

    # 8. Verify and Report Summary Metrics
    print("\n" + "=" * 80)
    print("HPP EVALUATION BATCH SUMMARY:")
    print("=" * 80)
    batted = df_evaluated[~df_evaluated["is_dnb"]]
    dnb = df_evaluated[df_evaluated["is_dnb"]]
    print(f"Total Stints in Output:       {len(df_evaluated)}")
    print(f"Batted Stints:                {len(batted)}")
    print(f"DNB Stints:                   {len(dnb)}")
    print(f"Mean Pressure (Batted):       {batted['mean_pressure'].mean():.2f}")
    print(f"Mean Actual Runs (Batted):    {batted['actual_runs'].mean():.2f}")
    print(f"Mean Expected Runs (Batted):  {batted['expected_runs'].mean():.2f}")
    print(f"Mean RAE (Bias):              {batted['rae'].mean():.4f}")
    print(f"Mean HPC:                     {batted['hpc'].mean():.4f}")
    print(f"DNB NaN HPC Count:            {dnb['hpc'].isna().sum()} (Expected: {len(dnb)})")

    # Career Leaders Check
    df_career = aggregate_player_career(df_evaluated)
    print("\nTOP 10 HIGH PRESSURE PLAYERS (CAREER HPC):")
    print("-" * 80)
    cols_show = ["batter_name", "total_matches", "innings_batted", "actual_runs", "mean_rae", "total_hpc", "mean_hpc", "crisis_total_hpc"]
    print(df_career[cols_show].head(10).to_string(index=False))

    elapsed = time.time() - start_time
    print(f"\nBatch completed in {elapsed:.1f} seconds.")


if __name__ == "__main__":
    main()
