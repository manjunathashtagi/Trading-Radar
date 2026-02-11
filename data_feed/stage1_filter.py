import pandas as pd
from nsepython import nse_eq
from datetime import datetime

CACHE = "data/stage1_cache.csv"

def stage1_shortlist(universe, limit=120):
    today = datetime.now().date()
    total_scanned = len(universe)

    rows = []

    for sym in universe["symbol"]:
        try:
            quote = nse_eq(sym)

            last_price = quote.get("priceInfo", {}).get("lastPrice")
            prev_close = quote.get("priceInfo", {}).get("previousClose")

            if not last_price or not prev_close:
                continue

            pct_change = ((last_price - prev_close) / prev_close) * 100

            # NSE appropriate gap filter
            if abs(pct_change) >= 0.8:
                rows.append({
                    "symbol": sym,
                    "score": abs(pct_change)
                })

        except Exception:
            continue

    if not rows:
        df_empty = pd.DataFrame(columns=["symbol", "score"])
        df_empty["date"] = today
        df_empty.to_csv(CACHE, index=False)

        print(
            f"[STAGE-1 DONE] "
            f"Scanned: {total_scanned} | "
            f"Qualified: 0 | "
            f"Date: {today}"
        )

        return df_empty

    df = pd.DataFrame(rows)
    df = df.sort_values("score", ascending=False).head(limit)
    df["date"] = today
    df.to_csv(CACHE, index=False)

    print(
        f"[STAGE-1 DONE] "
        f"Scanned: {total_scanned} | "
        f"Qualified: {len(df)} | "
        f"Date: {today}"
    )

    return df