import pandas as pd
import requests
import zipfile
import io
from datetime import datetime

CACHE = "data/stage1_cache.csv"

def stage1_shortlist(universe=None, limit=120):
    today = datetime.now()
    date_str = today.strftime("%d%b%Y").upper()

    # NSE bhavcopy URL format
    url = f"https://archives.nseindia.com/content/historical/EQUITIES/{today.strftime('%Y')}/{today.strftime('%b').upper()}/cm{date_str}bhav.csv.zip"

    headers = {
        "User-Agent": "Mozilla/5.0"
    }

    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()

        with zipfile.ZipFile(io.BytesIO(response.content)) as z:
            filename = z.namelist()[0]
            df = pd.read_csv(z.open(filename))

    except Exception as e:
        print("Bhavcopy download failed:", e)
        return pd.DataFrame(columns=["symbol", "score"])

    total_scanned = len(df)

    # Filter EQ series only
    df = df[df["SERIES"] == "EQ"]

    # Calculate % change
    df["pct_change"] = (
        (df["CLOSE"] - df["PREVCLOSE"]) /
        df["PREVCLOSE"]
    ) * 100

    # Gap filter (NSE realistic)
    df_filtered = df[abs(df["pct_change"]) >= 0.8]

    df_filtered = df_filtered.sort_values(
        by="pct_change",
        key=abs,
        ascending=False
    ).head(limit)

    result = pd.DataFrame({
        "symbol": df_filtered["SYMBOL"],
        "score": abs(df_filtered["pct_change"]),
        "date": today.date()
    })

    result.to_csv(CACHE, index=False)

    print(
        f"[STAGE-1 FAST] "
        f"Scanned: {total_scanned} | "
        f"Qualified: {len(result)} | "
        f"Date: {today.date()}"
    )

    return result