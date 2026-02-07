import pandas as pd
from nsepython import equity_history
from datetime import datetime, timedelta

def stage1_shortlist(symbols_df, limit=120):
    shortlisted = []

    to_date = datetime.now()
    from_date = to_date - timedelta(days=5)

    for sym in symbols_df["symbol"]:
        try:
            df = equity_history(
                symbol=sym,
                series="EQ",
                start_date=from_date.strftime("%d-%m-%Y"),
                end_date=to_date.strftime("%d-%m-%Y")
            )

            if df is None or len(df) < 2:
                continue

            df = df.tail(2)

            close_today = df.iloc[-1]["CLOSE"]
            close_prev = df.iloc[-2]["CLOSE"]

            vol_today = df.iloc[-1]["VOLUME"]
            vol_prev = df.iloc[-2]["VOLUME"]

            pct_change = ((close_today - close_prev) / close_prev) * 100
            vol_ratio = vol_today / max(vol_prev, 1)

            if abs(pct_change) > 2 and vol_ratio > 1.5:
                shortlisted.append({
                    "symbol": sym,
                    "pct_change": pct_change,
                    "vol_ratio": vol_ratio
                })

        except Exception:
            continue

    df_short = pd.DataFrame(shortlisted)

    if df_short.empty:
        return []

    df_short["score"] = abs(df_short["pct_change"]) * df_short["vol_ratio"]
    df_short = df_short.sort_values("score", ascending=False)

    return df_short.head(limit)["symbol"].tolist()
