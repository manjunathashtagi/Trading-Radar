import pandas as pd

def sector_strength(shortlist_df):
    sector_map = pd.read_csv("data/sector_map.csv")

    df = shortlist_df.merge(sector_map, on="symbol", how="left")
    df = df.dropna(subset=["sector"])

    strength = (
        df.groupby("sector")
        .agg(
            stocks=("symbol", "count"),
            avg_score=("score", "mean")
        )
        .reset_index()
    )

    strength["rank_score"] = strength["stocks"] * strength["avg_score"]
    strength = strength.sort_values("rank_score", ascending=False)

    return strength
