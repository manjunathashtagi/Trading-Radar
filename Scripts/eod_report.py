import pandas as pd
import yfinance as yf
import datetime as dt
import os
import requests

DATE = dt.date.today().strftime("%Y%m%d")
WATCHLIST = f"radar_watchlist_{DATE}.csv"
OUTPUT = f"eod_report_{DATE}.csv"

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

def send_telegram(msg):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    requests.post(url, json={
        "chat_id": TELEGRAM_CHAT_ID,
        "text": msg
    })

def main():
    if not os.path.exists(WATCHLIST):
        print("Watchlist missing")
        return

    watch = pd.read_csv(WATCHLIST)
    results = []

    for _, row in watch.iterrows():
        symbol = row["symbol"]
        bucket = float(row["target_bucket"].replace("%", ""))
        prev_close = row["prev_close"]

        data = yf.download(symbol + ".NS", period="1d", interval="5m", progress=False)
        if data.empty:
            continue

        day_high = data["High"].max()
        target_price = prev_close * (1 + bucket / 100)

        hit = day_high >= target_price

        results.append({
            "symbol": symbol,
            "bucket": f"{bucket}%",
            "prev_close": round(prev_close, 2),
            "target_price": round(target_price, 2),
            "day_high": round(day_high, 2),
            "target_hit": "YES" if hit else "NO"
        })

    df = pd.DataFrame(results)
    df.to_csv(OUTPUT, index=False)

    summary = df.groupby("bucket")["target_hit"].value_counts().unstack(fill_value=0)

    msg = "📊 EOD Radar Report\n\n"
    for bucket in summary.index:
        hit = summary.loc[bucket].get("YES", 0)
        miss = summary.loc[bucket].get("NO", 0)
        msg += f"{bucket} → Hit: {hit}, Miss: {miss}\n"

    send_telegram(msg)
    print("EOD report generated")

if __name__ == "__main__":
    main()
