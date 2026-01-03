import pandas as pd
import numpy as np
import yfinance as yf
import datetime as dt
import os
import requests

# ================= CONFIG =================
LOOKBACK_DAYS = 60
TOP_N = 120
DATE = dt.date.today().strftime("%Y%m%d")
OUTPUT_CSV = f"radar_watchlist_{DATE}.csv"

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# ================= TELEGRAM =================
def send_telegram(msg):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": msg})

# ================= NIFTY =================
def get_nifty_change_pct():
    nifty = yf.download("^NSEI", period="2d", interval="1d", progress=False)
    if len(nifty) < 2:
        return 0.0
    prev = nifty.iloc[-2]["Close"]
    last = nifty.iloc[-1]["Close"]
    return ((last - prev) / prev) * 100

# ================= SCORES =================
def compute_scores(df):
    df["EMA20"] = df["Close"].ewm(span=20).mean()
    df["EMA50"] = df["Close"].ewm(span=50).mean()

    df["trend_score"] = (
        (df["Close"] > df["EMA20"]).astype(int) * 40 +
        (df["Close"] > df["EMA50"]).astype(int) * 60
    )

    df["momentum_score"] = (
        df["Close"].pct_change(5).clip(-0.1, 0.1) * 500
    ).fillna(0)

    df["volatility_score"] = (
        (df["High"] - df["Low"]).rolling(14).mean() /
        df["Close"]
    ).fillna(0) * 100

    return df

# ================= SECTOR =================
def compute_sector_strength(df):
    sector_map = {}
    for sector, group in df.groupby("sector"):
        sector_map[sector] = group["relative_strength_pct"].mean()
    return sector_map

# ================= BUCKET =================
def assign_bucket(row):
    if row["volatility_score"] > 3.5 and row["momentum_score"] > 3:
        return "7%"
    if row["volatility_score"] > 2 and row["momentum_score"] > 1.5:
        return "5%"
    return "2%"

# ================= MAIN =================
def main():
    universe = pd.read_csv("data/universe_nse.csv")
    nifty_change = get_nifty_change_pct()
    records = []

    for _, u in universe.iterrows():
        symbol = u["symbol"]
        sector = u["sector"]

        try:
            data = yf.download(symbol + ".NS", period=f"{LOOKBACK_DAYS}d", progress=False)
            if len(data) < 30:
                continue

            data = compute_scores(data)
            last = data.iloc[-1]
            prev = data.iloc[-2]

            prev_day_change = (
                (prev["Close"] - data.iloc[-3]["Close"]) /
                data.iloc[-3]["Close"]
            ) * 100

            records.append({
                "symbol": symbol,
                "sector": sector,
                "prev_close": prev["Close"],
                "prev_day_change_pct": prev_day_change,
                "prev_day_volume_ratio": prev["Volume"] /
                    data["Volume"].rolling(20).mean().iloc[-2],
                "trend_score": last["trend_score"],
                "momentum_score": last["momentum_score"],
                "volatility_score": last["volatility_score"]
            })
        except Exception:
            continue

    df = pd.DataFrame(records)

    # -------- Relative Strength --------
    df["relative_strength_pct"] = (
        df["prev_day_change_pct"] - nifty_change
    )

    df = df[df["relative_strength_pct"] >= 0.5]

    # -------- Sector Strength --------
    sector_map = compute_sector_strength(df)
    df["sector_strength"] = df["sector"].map(sector_map)

    df = df[df["sector_strength"] >= 0]

    # -------- Composite Score --------
    df["composite_score"] = (
        df["trend_score"] * 0.4 +
        df["momentum_score"] * 0.35 +
        df["volatility_score"] * 0.25
    )

    df = df.sort_values("composite_score", ascending=False).head(TOP_N)

    df["target_bucket"] = df.apply(assign_bucket, axis=1)
    df["selection_reason"] = "RS + Sector + Trend + Momentum + Volatility"

    df.to_csv(OUTPUT_CSV, index=False)

    # -------- Telegram --------
    msg = (
        f"📊 Pre-Market Radar Ready (09:10)\n\n"
        f"NIFTY Change: {round(nifty_change,2)}%\n"
        f"Stocks Shortlisted: {len(df)}\n\n"
        f"2%: {(df['target_bucket']=='2%').sum()}\n"
        f"5%: {(df['target_bucket']=='5%').sum()}\n"
        f"7%: {(df['target_bucket']=='7%').sum()}\n\n"
        f"Intraday LONG-only radar active"
    )
    send_telegram(msg)

if __name__ == "__main__":
    main()
