import sys
import os
import pandas as pd
from datetime import datetime
import pytz

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from alerts.telegram_alerts import send_alert

SIGNALS_FILE = "data/signals.csv"
PRICE_LOG_FILE = "data/price_log.csv"


def main():

    if not os.path.exists(SIGNALS_FILE):
        send_alert("📊 EOD REPORT\nNo signals file found.")
        return

    if not os.path.exists(PRICE_LOG_FILE):
        send_alert("📊 EOD REPORT\nNo price log file found.")
        return

    signals_df = pd.read_csv(SIGNALS_FILE, engine="python")
    price_df = pd.read_csv(PRICE_LOG_FILE, engine="python")

    if signals_df.empty:
        send_alert("📊 EOD REPORT\nNo trades generated.")
        return

    signals_df["date"] = pd.to_datetime(signals_df["date"]).dt.date
    price_df["date"] = pd.to_datetime(price_df["date"]).dt.date

    latest_date = signals_df["date"].max()

    today_signals = signals_df[signals_df["date"] == latest_date]
    today_prices = price_df[price_df["date"] == latest_date]

    message = f"📊 <b>EOD PERFORMANCE REPORT</b>\n"
    message += f"Date: {latest_date}\n\n"

    target_hits = 0
    sl_hits = 0
    open_trades = 0

    for idx, signal in today_signals.iterrows():

        symbol = signal["symbol"]
        action = signal["action"]
        entry = float(signal["entry"])
        sl = float(signal["sl"])
        tp = float(signal["tp"])
        trigger_time = signal["trigger_time"]

        symbol_prices = today_prices[today_prices["symbol"] == symbol]

        symbol_prices = symbol_prices[
            symbol_prices["time"] >= trigger_time
        ]

        result = "⏳ STILL OPEN"

        for _, row in symbol_prices.iterrows():

            price = float(row["price"])

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
            f"{'🟢' if action=='BUY' else '🔴'} {symbol}\n"
            f"Entry: {entry} | SL: {sl} | Target: {tp}\n"
            f"Triggered: {trigger_time}\n"
            f"Result: {result}\n\n"
        )

    total = target_hits + sl_hits + open_trades
    win_rate = round((target_hits / total) * 100, 2) if total else 0

    message += "-------------------------\n"
    message += f"Total: {total}\n"
    message += f"🎯 Target: {target_hits}\n"
    message += f"❌ SL: {sl_hits}\n"
    message += f"⏳ Open: {open_trades}\n"
    message += f"Win Rate: {win_rate}%"

    signals_df.to_csv(SIGNALS_FILE, index=False)

    send_alert(message)


if __name__ == "__main__":
    main()