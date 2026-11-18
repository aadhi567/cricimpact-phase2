"""CricImpact Phase 2 — Generate HPP Data for Historical Match Explorer.

Reads `data/processed/contributions/hpp_stint_evaluations_v1.pkl.gz` and exports
a compact match-keyed JSON file for the Historical Match Explorer UI.
"""

import gzip
import json
import os
import pickle
import pandas as pd


def main():
    pkl_path = "data/processed/contributions/hpp_stint_evaluations_v1.pkl.gz"
    out_path = "docs/worm_graph/hpp_match_data.json"

    print(f"Reading evaluated stints from {pkl_path}...")
    with gzip.open(pkl_path, "rb") as f:
        df = pickle.load(f)

    print(f"Loaded {len(df)} total records. Filtering active and DNB records...")

    match_dict = {}
    for mid, grp in df.groupby("match_id"):
        stint_list = []
        for _, row in grp.iterrows():
            stint_list.append({
                "name": str(row["batter_name"]),
                "inn": int(row["innings"]),
                "runs": int(row["actual_runs"]),
                "balls": int(row["balls_faced"]),
                "fours": int(row["fours"]),
                "sixes": int(row["sixes"]),
                "exp_runs": None if pd.isna(row["expected_runs"]) else round(float(row["expected_runs"]), 1),
                "rae": None if pd.isna(row["rae"]) else round(float(row["rae"]), 2),
                "mean_p": None if pd.isna(row["mean_pressure"]) else round(float(row["mean_pressure"]), 1),
                "peak_p": None if pd.isna(row["peak_pressure"]) else round(float(row["peak_pressure"]), 1),
                "hpc": None if pd.isna(row["hpc"]) else round(float(row["hpc"]), 2),
                "tier": str(row["pressure_tier"]),
                "dismissal": str(row["dismissal_status"]),
                "dismissal_type": None if pd.isna(row["dismissal_type_canonical"]) else str(row["dismissal_type_canonical"]),
                "is_out": bool(row["is_out"]),
                "is_dnb": bool(row["is_dnb"]),
            })
        match_dict[int(mid)] = stint_list

    print(f"Exporting {len(match_dict)} matches to {out_path}...")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(match_dict, f, separators=(",", ":"))

    size_mb = os.path.getsize(out_path) / (1024 * 1024)
    print(f"Successfully generated {out_path} ({size_mb:.2f} MB)")


if __name__ == "__main__":
    main()

