import pandas as pd
import requests
from datetime import datetime

CACHE = "data/stage1_cache.csv"

def stage1_shortlist(universe=None, limit=120):
    today = datetime.now().date()

    url = "https://www.nseindia.com/api/equity-stockIndices?index=NIFTY%20TOTAL%20MARKET"

    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json"
    }

    try:
        session = requests.Session()
        session.get("https://www.nseindia.com", headers=headers, timeout=5)
        response = session.get(url, headers=headers, timeout=10)
        data = response.json()

        df = pd.DataFrame(data["data"])

    except Exception as e:
        print("Bulk quote fetch failed:", e)
        return pd.DataFrame(columns=["symbol", "score"])

    total_scanned = len(df)

    # Clean data
    df = df[df["symbol"].notna()]
    df = df[df["lastPrice"].notna()]
    df = df[df["pChange"].notna()]

    # 🔥 NEW STRICT FILTER
    df_filtered = df[
        (abs(df["pChange"]) >= 1.2) &
        (df["lastPrice"] > 50)
    ]

    df_filtered = df_filtered.sort_values(
        by="pChange",
        key=abs,
        ascending=False
    ).head(limit)

    result = pd.DataFrame({
        "symbol": df_filtered["symbol"],
        "score": abs(df_filtered["pChange"]),
        "date": today
    })

    result.to_csv(CACHE, index=False)

    print(
        f"[STAGE-1 STRICT GAP] "
        f"Scanned: {total_scanned} | "
        f"Qualified: {len(result)} | "
        f"Date: {today}"
    )

    return result