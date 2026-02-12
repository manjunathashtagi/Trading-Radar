import sys
import os
import pandas as pd
import requests
import time
from datetime import datetime
import pytz

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

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
    df = pd.DataFrame(data["data"])

    return df


def main():

    if not os.path.exists(SIGNALS_FILE):
        print("No signals file found.")
        return

    signals_df = pd.read_csv(SIGNALS_FILE)

    if signals_df.empty:
        print("No signals to evaluate.")
        return

    market_df = fetch_bulk_snapshot()

    ist = pytz.timezone("Asia/Kolkata")
    current_time = datetime.now(ist).strftime("%H:%M")

    message = f"📊 <b>EOD PERFORMANCE REPORT</b> | {current_time}\n\n"

    for _, signal in signals_df.iterrows():

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

        message += (
            f"{'🟢' if action == 'BUY' else '🔴'} <b>{action}</b> – {symbol}\n"
            f"Entry: {round(entry,2)} | SL: {round(sl,2)} | Target: {round(tp,2)}\n"
            f"Day High: {round(day_high,2)} | Day Low: {round(day_low,2)}\n"
            f"Result: {result}\n\n"
        )

    send_alert(message)


if __name__ == "__main__":
    main()