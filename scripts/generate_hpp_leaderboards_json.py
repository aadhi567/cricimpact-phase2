"""CricImpact Phase 2 — Generate HPP Leaderboards for Historical Explorer.

Generates `docs/worm_graph/hpp_leaderboards.json` containing career and season
aggregates for the interactive HPP Explorer UI.
"""

import gzip
import json
import os
import pickle
import sys
from pathlib import Path
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ml.contribution.hpp_aggregator import aggregate_player_career, aggregate_player_season


def main():
    pkl_path = "data/processed/contributions/hpp_stint_evaluations_v1.pkl.gz"
    out_path = "docs/worm_graph/hpp_leaderboards.json"

    print(f"Reading evaluated stints from {pkl_path}...")
    with gzip.open(pkl_path, "rb") as f:
        df = pickle.load(f)

    print("Computing career aggregates...")
    df_career = aggregate_player_career(df)

    print("Computing season aggregates...")
    df_season = aggregate_player_season(df)

    # Clean floats for json
    def clean_records(df_in, limit=100):
        records = []
        for r in df_in.head(limit).to_dict(orient="records"):
            cleaned = {}
            for k, v in r.items():
                if pd.isna(v):
                    cleaned[k] = None
                elif isinstance(v, (float, np.floating)):
                    cleaned[k] = round(float(v), 2)
                elif isinstance(v, (int, np.integer)):
                    cleaned[k] = int(v)
                else:
                    cleaned[k] = v
            records.append(cleaned)
        return records

    output_data = {
        "metadata": {
            "total_matches": 798,
            "total_stints": len(df),
            "batted_stints": len(df[~df["is_dnb"]]),
            "corpus_mean_pressure": round(float(df[~df["is_dnb"]]["mean_pressure"].mean()), 2),
            "corpus_mean_rae": round(float(df[~df["is_dnb"]]["rae"].mean()), 4),
        },
        "career_top": clean_records(df_career, limit=100),
        "season_top": clean_records(df_season, limit=200),
    }

    print(f"Saving to {out_path}...")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2)

    size_kb = os.path.getsize(out_path) / 1024
    print(f"Saved {out_path} ({size_kb:.1f} KB)")


if __name__ == "__main__":
    main()
