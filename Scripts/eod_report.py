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
        send_alert("📊 EOD REPORT\nNo price log found.")
        return

    signals_df = pd.read_csv(SIGNALS_FILE)
    price_df = pd.read_csv(PRICE_LOG_FILE)

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

    message = f"📊 <b>EOD PERFORMANCE REPORT</b>\n"
    message += f"Date: {today}\n\n"

    total = 0
    wins = 0
    losses = 0
    open_trades = 0

    for idx, signal in today_df.iterrows():

        symbol = signal["symbol"]
        action = signal["action"]
        entry = float(signal["entry"])
        sl = float(signal["sl"])
        tp = float(signal["tp"])
        trigger_time = signal["trigger_time"]

        trigger_dt = datetime.combine(
            today,
            datetime.strptime(trigger_time, "%H:%M:%S").time()
        )

        symbol_prices = price_df[
            (price_df["symbol"] == symbol)
        ].copy()

        symbol_prices["datetime"] = pd.to_datetime(
            symbol_prices["date"] + " " + symbol_prices["time"]
        )

        symbol_prices = symbol_prices[
            symbol_prices["datetime"] >= trigger_dt
        ]

        result = "⏳ OPEN"

        for _, row in symbol_prices.iterrows():
            price = float(row["price"])

            if action == "BUY":
                if price >= tp:
                    result = "🎯 TARGET HIT"
                    wins += 1
                    break
                if price <= sl:
                    result = "❌ SL HIT"
                    losses += 1
                    break

            if action == "SELL":
                if price <= tp:
                    result = "🎯 TARGET HIT"
                    wins += 1
                    break
                if price >= sl:
                    result = "❌ SL HIT"
                    losses += 1
                    break

        if result == "⏳ OPEN":
            open_trades += 1

        signals_df.loc[idx, "result"] = result

        message += (
            f"{'🟢' if action=='BUY' else '🔴'} {symbol}\n"
            f"Entry: {entry} | SL: {sl} | Target: {tp}\n"
            f"Triggered: {trigger_time}\n"
            f"Result: {result}\n\n"
        )

        total += 1

    signals_df.to_csv(SIGNALS_FILE, index=False)

    win_rate = round((wins / total) * 100, 2) if total > 0 else 0

    message += "-----------------------------\n"
    message += f"Total: {total}\n"
    message += f"🎯 Wins: {wins}\n"
    message += f"❌ Loss: {losses}\n"
    message += f"⏳ Open: {open_trades}\n"
    message += f"Win Rate: {win_rate}%"

    send_alert(message)


if __name__ == "__main__":
    main()