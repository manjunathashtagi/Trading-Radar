import pandas as pd

def sector_strength(stage1_df):
    sm = pd.read_csv("data/sector_map.csv")
    df = stage1_df.merge(sm, on="symbol", how="left").dropna()

    sec = (
        df.groupby("sector")
        .agg(stocks=("symbol", "count"), score=("score", "mean"))
        .reset_index()
    )
    sec["rank"] = sec["stocks"] * sec["score"]
    return sec.sort_values("rank", ascending=False)
