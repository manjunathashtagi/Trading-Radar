import pandas as pd
from nsepython import equity_history
from datetime import datetime, timedelta

CACHE_FILE = "data/stage1_cache.csv"

def stage1_shortlist(symbols_df, limit=120, force=False):
    today = datetime.now().date()

    # ---- LOAD CACHE IF EXISTS ----
    if not force:
        try:
            cache = pd.read_csv(CACHE_FILE, parse_dates=["date"])
            cache_date = cache["date"].iloc[0].date()

            if cache_date == today:
                return cache["symbol"].tolist()
        except Exception:
            pass

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

            c1, c0 = df.iloc[-1]["CLOSE"], df.iloc[-2]["CLOSE"]
            v1, v0 = df.iloc[-1]["VOLUME"], df.iloc[-2]["VOLUME"]

            pct = ((c1 - c0) / c0) * 100
            vol_ratio = v1 / max(v0, 1)

            if abs(pct) > 2 and vol_ratio > 1.5:
                shortlisted.append({
                    "symbol
