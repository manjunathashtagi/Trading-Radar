import os
import pandas as pd
import yfinance as yf
from datetime import datetime
import pytz

from alerts.telegram_alerts import send_alert

SIGNALS_FILE = "data/signals.csv"


def safe_fetch(symbol):
    import time
    for _ in range(3):
        try:
            df = yf.download(symbol, period="5d", interval="15m", progress=False)
            if not df.empty:
                return df
        except:
            time.sleep(1)
    return None


def evaluate_trade(symbol, action, entry, sl, tp, trigger_dt):

    df = safe_fetch(symbol + ".NS")

    if df is None or df.empty:
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

    return "⏳ OPEN"


def main():

    if not os.path.exists(SIGNALS_FILE):
        send_alert("📊 EOD REPORT\nNo signals file.")
        return

    df = pd.read_csv(SIGNALS_FILE)

    if df.empty:
        send_alert("📊 EOD REPORT\nNo trades today.")
        return

    ist = pytz.timezone("Asia/Kolkata")
    today = datetime.now(ist).date()

    df["date"] = pd.to_datetime(df["date"]).dt.date
    today_df = df[df["date"] == today]

    if today_df.empty:
        send_alert("📊 EOD REPORT\nNo trades today.")
        return

    wins, losses = 0, 0

    message = f"📊 EOD REPORT\nDate: {today}\n\n"

    for _, row in today_df.iterrows():

        symbol = row["symbol"]

        trigger_dt = datetime.combine(
            today,
            datetime.strptime(row["trigger_time"], "%H:%M:%S").time()
        )

        trigger_dt = ist.localize(trigger_dt)

        result = evaluate_trade(
            symbol,
            row["action"],
            row["entry"],
            row["sl"],
            row["tp"],
            trigger_dt
        )

        if result == "🎯 TARGET HIT":
            wins += 1
        elif result == "❌ SL HIT":
            losses += 1

        message += f"{symbol} → {result}\n"

    total = len(today_df)
    winrate = round((wins / total) * 100, 2) if total else 0

    message += f"\nTotal: {total}\nWins: {wins}\nLoss: {losses}\nWinRate: {winrate}%"

    send_alert(message)


if __name__ == "__main__":
    main()