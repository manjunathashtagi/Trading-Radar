import pandas as pd
from nsepython import nse_bhavcopy
from datetime import datetime

CACHE = "data/stage1_cache.csv"

def stage1_shortlist(universe, limit=120):
    today = datetime.now().date()

    try:
        # 🔥 Single bulk download (entire NSE)
        df = nse_bhavcopy("equities", today.strftime("%d-%m-%Y"))

    except Exception as e:
        print("Bhavcopy fetch failed:", e)
        return pd.DataFrame(columns=["symbol", "score"])

    if df is None or df.empty:
        print("Empty bhavcopy.")
        return pd.DataFrame(columns=["symbol", "score"])

    total_scanned = len(df)

    # Keep only EQ series
    df = df[df["SERIES"] == "EQ"]

    # Calculate % change
    df["pct_change"] = (
        (df["CLOSE_PRICE"] - df["PREV_CLOSE"]) /
        df["PREV_CLOSE"]
    ) * 100

    # NSE-appropriate filter
    df_filtered = df[abs(df["pct_change"]) >= 0.8]

    # Rank by magnitude
    df_filtered = df_filtered.sort_values(
        by="pct_change",
        key=abs,
        ascending=False
    ).head(limit)

    result = pd.DataFrame({
        "symbol": df_filtered["SYMBOL"],
        "score": abs(df_filtered["pct_change"]),
        "date": today
    })

    result.to_csv(CACHE, index=False)

    print(
        f"[STAGE-1 FAST] "
        f"Scanned: {total_scanned} | "
        f"Qualified: {len(result)} | "
        f"Date: {today}"
    )

    return result