import sys
import os

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import pandas as pd
import requests
import time
from datetime import datetime
import pytz
from alerts.telegram_alerts import send_alert

SIGNALS_FILE = "data/signals.csv"


def fetch_bulk_snapshot():
    url = "https://www.nseindia.com/api/equity-stockIndices?index=NIFTY%20TOTAL%20MARKET"

    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json"
    }

    session = requests.Session()
    session.get("https://www.nseindia.com", headers=headers, timeout=20)
    time.sleep(1)

    response = session.get(url, headers=headers, timeout=20)
    response.raise_for_status()

    data = response.json()
    return pd.DataFrame(data["data"])


def main():

    if not os.path.exists(SIGNALS_FILE):
        send_alert("📊 EOD REPORT\nNo trades generated today.")
        return

    signals_df = pd.read_csv(SIGNALS_FILE)

    ist = pytz.timezone("Asia/Kolkata")
    today = datetime.now(ist).date()

    signals_df["date"] = pd.to_datetime(signals_df["date"]).dt.date
    today_df = signals_df[signals_df["date"] == today]

    if today_df.empty:
        send_alert("📊 EOD REPORT\nNo trades generated today.")
        return

    market_df = fetch_bulk_snapshot()

    message = f"📊 <b>EOD PERFORMANCE REPORT</b>\n\n"

    for idx, signal in today_df.iterrows():

        symbol = signal["symbol"]
        action = signal["action"]
        entry = float(signal["entry"])
        sl = float(signal["sl"])
        tp = float(signal["tp"])

        stock = market_df[market_df["symbol"] == symbol]
        if stock.empty:
            continue

        day_high = float(stock.iloc[0]["dayHigh"])
        day_low = float(stock.iloc[0]["dayLow"])

        result = "⏳ STILL OPEN"

        if action == "BUY":
            if day_high >= tp:
                result = "🎯 TARGET HIT"
            elif day_low <= sl:
                result = "❌ SL HIT"

        elif action == "SELL":
            if day_low <= tp:
                result = "🎯 TARGET HIT"
            elif day_high >= sl:
                result = "❌ SL HIT"

        signals_df.loc[idx, "result"] = result

        message += (
            f"{'🟢' if action == 'BUY' else '🔴'} {symbol}\n"
            f"Entry: {entry} | SL: {sl} | Target: {tp}\n"
            f"High: {day_high} | Low: {day_low}\n"
            f"Result: {result}\n\n"
        )

    signals_df.to_csv(SIGNALS_FILE, index=False)

    send_alert(message)


if __name__ == "__main__":
    main()