import os
import sys
import pandas as pd
import yfinance as yf
from datetime import datetime
import pytz

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from alerts.telegram_alerts import send_alert

SIGNALS_FILE = "data/signals.csv"


def evaluate_trade(symbol, action, entry, sl, tp, trigger_dt):

    try:
        df = yf.download(
            symbol + ".NS",
            period="1d",
            interval="15m",
            progress=False
        )

        if df.empty:
            return "⏳ OPEN"

        df = df[df.index >= trigger_dt]

        for _, row in df.iterrows():

            high = row["High"]
            low = row["Low"]

            if action == "BUY":
                if high >= tp:
                    return "🎯 TARGET HIT"
                if low <= sl:
                    return "❌ SL HIT"

            if action == "SELL":
                if low <= tp:
                    return "🎯 TARGET HIT"
                if high >= sl:
                    return "❌ SL HIT"

        return "⏳ OPEN"

    except:
        return "⏳ OPEN"


def main():

    if not os.path.exists(SIGNALS_FILE):
        send_alert("📊 EOD REPORT\nNo signals file found.")
        return

    df = pd.read_csv(SIGNALS_FILE)

    if df.empty:
        send_alert("📊 EOD REPORT\nNo trades generated today.")
        return

    ist = pytz.timezone("Asia/Kolkata")
    today = datetime.now(ist).date()

    df["date"] = pd.to_datetime(df["date"]).dt.date

    today_df = df[df["date"] == today]

    if today_df.empty:
        send_alert("📊 EOD REPORT\nNo trades generated today.")
        return

    message = f"📊 <b>EOD PERFORMANCE REPORT</b>\n"
    message += f"Date: {today}\n\n"

    wins = 0
    losses = 0
    open_trades = 0

    for idx, row in today_df.iterrows():

        symbol = row["symbol"]
        action = row["action"]
        entry = float(row["entry"])
        sl = float(row["sl"])
        tp = float(row["tp"])
        trigger_time = row["trigger_time"]

        trigger_dt = datetime.combine(
            today,
            datetime.strptime(trigger_time, "%H:%M:%S").time()
        )
        trigger_dt = ist.localize(trigger_dt)

        result = evaluate_trade(symbol, action, entry, sl, tp, trigger_dt)

        df.loc[idx, "result"] = result

        if result == "🎯 TARGET HIT":
            wins += 1
        elif result == "❌ SL HIT":
            losses += 1
        else:
            open_trades += 1

        message += (
            f"{'🟢' if action=='BUY' else '🔴'} {symbol}\n"
            f"Entry: {entry} | SL: {sl} | Target: {tp}\n"
            f"Triggered: {trigger_time}\n"
            f"Result: {result}\n\n"
        )

    total = len(today_df)
    win_rate = round((wins / total) * 100, 2) if total > 0 else 0

    message += "-----------------------------\n"
    message += f"Total: {total}\n"
    message += f"🎯 Wins: {wins}\n"
    message += f"❌ Loss: {losses}\n"
    message += f"⏳ Open: {open_trades}\n"
    message += f"Win Rate: {win_rate}%"

    df.to_csv(SIGNALS_FILE, index=False)

    send_alert(message)


if __name__ == "__main__":
    main()