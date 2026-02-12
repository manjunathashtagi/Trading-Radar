import sys
import os
import pandas as pd
import requests
import time
from datetime import datetime
import pytz

# Fix import path for GitHub
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from alerts.telegram_alerts import send_alert

SIGNALS_FILE = "data/signals.csv"


# -------------------------------------------------------
# Fetch intraday price data (NSE Chart API)
# -------------------------------------------------------
def fetch_intraday_data(symbol):

    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json"
    }

    session = requests.Session()

    try:
        session.get("https://www.nseindia.com", headers=headers, timeout=10)
        time.sleep(1)

        url = f"https://www.nseindia.com/api/chart-databyindex?index={symbol}"
        response = session.get(url, headers=headers, timeout=10)
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


# -------------------------------------------------------
# MAIN
# -------------------------------------------------------
def main():

    if not os.path.exists(SIGNALS_FILE):
        send_alert("📊 EOD REPORT\nNo signals file found.")
        return

    try:
        signals_df = pd.read_csv(SIGNALS_FILE, engine="python")
    except Exception as e:
        send_alert(f"📊 EOD REPORT\nCSV Read Error: {e}")
        return

    if signals_df.empty:
        send_alert("📊 EOD REPORT\nNo trades generated.")
        return

    # Always evaluate latest trading date in file
    signals_df["date"] = pd.to_datetime(signals_df["date"]).dt.date
    latest_date = signals_df["date"].max()

    today_df = signals_df[signals_df["date"] == latest_date]

    if today_df.empty:
        send_alert("📊 EOD REPORT\nNo trades for latest date.")
        return

    message = f"📊 <b>EOD PERFORMANCE REPORT</b>\n"
    message += f"Date: {latest_date}\n\n"

    target_hits = 0
    sl_hits = 0
    open_trades = 0

    ist = pytz.timezone("Asia/Kolkata")

    for idx, signal in today_df.iterrows():

        symbol = signal["symbol"]
        action = signal["action"]
        entry = float(signal["entry"])
        sl = float(signal["sl"])
        tp = float(signal["tp"])
        trigger_time = signal.get("trigger_time", "09:15:00")

        intraday_df = fetch_intraday_data(symbol)

        if intraday_df.empty:
            print(f"No intraday data for {symbol}")
            open_trades += 1
            continue

        # Filter AFTER trigger time
        trigger_datetime = datetime.combine(
            latest_date,
            datetime.strptime(trigger_time, "%H:%M:%S").time()
        )

        intraday_df = intraday_df[intraday_df["timestamp"] >= trigger_datetime]

        result = "⏳ STILL OPEN"

        for _, row in intraday_df.iterrows():

            price = row["price"]

            if action == "BUY":
                if price >= tp:
                    result = "🎯 TARGET HIT"
                    target_hits += 1
                    break
                if price <= sl:
                    result = "❌ SL HIT"
                    sl_hits += 1
                    break

            elif action == "SELL":
                if price <= tp:
                    result = "🎯 TARGET HIT"
                    target_hits += 1
                    break
                if price >= sl:
                    result = "❌ SL HIT"
                    sl_hits += 1
                    break

        if result == "⏳ STILL OPEN":
            open_trades += 1

        signals_df.loc[idx, "result"] = result

        message += (
            f"{'🟢' if action == 'BUY' else '🔴'} {symbol}\n"
            f"Entry: {entry} | SL: {sl} | Target: {tp}\n"
            f"Triggered: {trigger_time}\n"
            f"Result: {result}\n\n"
        )

    total = target_hits + sl_hits + open_trades
    win_rate = round((target_hits / total) * 100, 2) if total > 0 else 0

    message += "---------------------------\n"
    message += f"Total Signals: {total}\n"
    message += f"🎯 Target Hit: {target_hits}\n"
    message += f"❌ SL Hit: {sl_hits}\n"
    message += f"⏳ Open: {open_trades}\n"
    message += f"Win Rate: {win_rate}%"

    # Save updated results
    signals_df.to_csv(SIGNALS_FILE, index=False)

    send_alert(message)


if __name__ == "__main__":
    main()