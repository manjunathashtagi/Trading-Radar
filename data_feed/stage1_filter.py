import pandas as pd
from nsepython import equity_history
from datetime import datetime, timedelta

CACHE = "data/stage1_cache.csv"

def stage1_shortlist(universe, limit=120):
    today = datetime.now().date()

    # ---- Try cache first ----
    try:
        cache = pd.read_csv(CACHE, parse_dates=["date"])
        if not cache.empty and cache["date"].iloc[0].date() == today:
            return cache
    except Exception:
        pass

    rows = []
    to_d = datetime.now()
    from_d = to_d - timedelta(days=5)

    for sym in universe["symbol"]:
        try:
            df = equity_history(
                sym, "EQ",
                from_d.strftime("%d-%m-%Y"),
                to_d.strftime("%d-%m-%Y")
            )

            if df is None or len(df) < 2:
                continue

            df = df.tail(2)
            close_now = df.iloc[-1]["CLOSE"]
            close_prev = df.iloc[-2]["CLOSE"]
            vol_now = df.iloc[-1]["VOLUME"]
            vol_prev = df.iloc[-2]["VOLUME"]

            pct = ((close_now - close_prev) / close_prev) * 100
            vol_ratio = vol_now / max(vol_prev, 1)

            if abs(pct) > 2 and vol_ratio > 1.5:
                rows.append({
                    "symbol": sym,
                    "score": abs(pct) * vol_ratio
                })

        except Exception:
            continue

    # ---- SAFE HANDLING OF EMPTY RESULT ----
    if not rows:
        df_empty = pd.DataFrame(columns=["symbol", "score"])
        df_empty["date"] = today
        df_empty.to_csv(CACHE, index=False)
        return df_empty

    df = pd.DataFrame(rows)
    df = df.sort_values("score", ascending=False).head(limit)
    df["date"] = today
    df.to_csv(CACHE, index=False)

    return df
