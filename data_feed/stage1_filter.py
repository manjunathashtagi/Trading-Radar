import pandas as pd
from nsepython import equity_history
from datetime import datetime, timedelta

CACHE = "data/stage1_cache.csv"

def stage1_shortlist(universe, limit=120):
    today = datetime.now().date()
    total_scanned = len(universe)

    # ---------- TRY CACHE FIRST ----------
    try:
        cache = pd.read_csv(CACHE, parse_dates=["date"])
        if not cache.empty and cache["date"].iloc[0].date() == today:
            print(
                f"[STAGE-1 CACHE] "
                f"Scanned: {total_scanned} | "
                f"Qualified: {len(cache)} | "
                f"Date: {today}"
            )
            return cache
    except Exception:
        pass

    rows = []
    to_d = datetime.now()
    from_d = to_d - timedelta(days=5)

    for sym in universe["symbol"]:
        try:
            df = equity_history(
                sym,
                "EQ",
                from_d.strftime("%d-%m-%Y"),
                to_d.strftime("%d-%m-%Y")
            )

            if df is None or len(df) < 2:
                continue

            df = df.tail(2)

            close_now = df.iloc[-1]["CLOSE"]
            close_prev = df.iloc[-2]["CLOSE"]

            pct_change = ((close_now - close_prev) / close_prev) * 100

            # ✅ NSE-APPROPRIATE PRE-MARKET FILTER
            # No volume filter (NSE pre-open volume is meaningless)
            if abs(pct_change) >= 0.8:
                rows.append({
                    "symbol": sym,
                    "score": abs(pct_change)
                })

        except Exception:
            continue

    # ---------- SAFE EMPTY HANDLING ----------
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