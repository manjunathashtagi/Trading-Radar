import pandas as pd
from nsepython import equity_history
from datetime import datetime, timedelta

CACHE = "data/stage1_cache.csv"

def stage1_shortlist(universe, limit=120):
    today = datetime.now().date()

    try:
        cache = pd.read_csv(CACHE, parse_dates=["date"])
        if cache["date"].iloc[0].date() == today:
            return cache
    except Exception:
        pass

    rows = []
    to_d = datetime.now()
    from_d = to_d - timedelta(days=5)

    for sym in universe["symbol"]:
        try:
            df = equity_history(sym, "EQ",
                from_d.strftime("%d-%m-%Y"),
                to_d.strftime("%d-%m-%Y")
            )
            if df is None or len(df) < 2:
                continue

            df = df.tail(2)
            pct = ((df.iloc[-1]["CLOSE"] - df.iloc[-2]["CLOSE"])
                  / df.iloc[-2]["CLOSE"]) * 100
            vol = df.iloc[-1]["VOLUME"] / max(df.iloc[-2]["VOLUME"], 1)

            if abs(pct) > 2 and vol > 1.5:
                rows.append({
                    "symbol": sym,
                    "score": abs(pct) * vol,
                    "date": today
                })
        except Exception:
            continue

    df = pd.DataFrame(rows).sort_values("score", ascending=False).head(limit)
    df.to_csv(CACHE, index=False)
    return df
