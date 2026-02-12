import sys
import os
import pandas as pd
import requests
import time
from datetime import datetime
import pytz
from alerts.telegram_alerts import send_alert

SIGNALS_FILE = "data/signals.csv"


# --------------------------------------------
# Fetch 5-min intraday data from NSE
# --------------------------------------------
def fetch_intraday_data(symbol):

    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json"
    }

    session = requests.Session()
    session.get("https://www.nseindia.com", headers=headers, timeout=20)
    time.sleep(1)

    # NSE chart API
    url = f"https://www.nseindia.com/api/chart-databyindex?index={symbol}"

    try:
        response = session.get(url, headers=headers, timeout=20)
        response.raise_for_status()
        data = response.json()

        if "grapthData" not in data:
            return pd.DataFrame()

        df = pd.DataFrame(data["grapthData"], columns=["timestamp", "price"])

        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
        df["price"] = df["price"].astype(float)

        return df

    except Exception as e:
        print(f"Intraday fetch failed for {symbol}: {e}")
        return pd.DataFrame()


# --------------------------------------------
# MAIN
# --------------------------------------------
def main():

    if not os.path.exists(SIGNALS_FILE):
        send_alert("📊 EOD REPORT\nNo trades generated today.")
        return

    signals_df = pd.read_csv(SIGNALS_FILE)

    if signals_df.empty:
        send_alert("📊 EOD REPORT\nNo trades generated today.")
        return

    ist = pytz.timezone("Asia/Kolkata")
    today = datetime.now(ist).date()

    signals_df["date"] = pd.to_datetime(signals_df["date"]).dt.date
    today_df = signals_df[signals_df["date"] == today]

    if today_df.empty:
        send_alert("📊 EOD REPORT\nNo trades generated today.")
        return

    message = f"📊 <b>EOD PERFORMANCE REPORT</b>\n\n"

    for idx, signal in today_df.iterrows():

        symbol = signal["symbol"]
        action = signal["action"]
        entry = float(signal["entry"])
        sl = float(signal["sl"])
        tp = float(signal["tp"])
        trigger_time = signal["trigger_time"]

        intraday_df = fetch_intraday_data(symbol)

        if intraday_df.empty:
            continue

        # Filter candles AFTER trigger time
        trigger_datetime = datetime.combine(
            today,
            datetime.strptime(trigger_time, "%H:%M:%S").time()
        )

        intraday_df = intraday_df[intraday_df["timestamp"] >= trigger_datetime]

        result = "⏳ STILL OPEN"

        for _, row in intraday_df.iterrows():

            price = row["price"]

            if action == "BUY":
                if price >= tp:
                    result = "🎯 TARGET HIT"
                    break
                if price <= sl:
                    result = "❌ SL HIT"
                    break

            elif action == "SELL":
                if price <= tp:
                    result = "🎯 TARGET HIT"
                    break
                if price >= sl:
                    result = "❌ SL HIT"
                    break

        signals_df.loc[idx, "result"] = result

        message += (
            f"{'🟢' if action == 'BUY' else '🔴'} {symbol}\n"
            f"Entry: {entry} | SL: {sl} | Target: {tp}\n"
            f"Triggered: {trigger_time}\n"
            f"Result: {result}\n\n"
        )

    signals_df.to_csv(SIGNALS_FILE, index=False)

    send_alert(message)


if __name__ == "__main__":
    main()