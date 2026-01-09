import pandas as pd
import yfinance as yf
import os
import requests
from datetime import datetime, timezone, timedelta

TRADES_FILE = "data/trades_today.csv"
IST = timezone(timedelta(hours=5, minutes=30))

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")


def send(msg):
    if not TELEGRAM_BOT_TOKEN:
        return
    requests.post(
        f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
        data={"chat_id": TELEGRAM_CHAT_ID, "text": msg},
        timeout=10
    )


def main():
    if not os.path.exists(TRADES_FILE):
        print("No trades today")
        return

    df = pd.read_csv(TRADES_FILE)

    results = {"TARGET HIT": 0, "SL HIT": 0, "NO HIT": 0}

    for _, t in df.iterrows():
        hist = yf.Ticker(t["symbol"] + ".NS").history(period="1d", interval="5m")
        if hist.empty:
            continue

        if (hist["High"] >= t["target"]).any():
            results["TARGET HIT"] += 1
        elif (hist["Low"] <= t["sl"]).any():
            results["SL HIT"] += 1
        else:
            results["NO HIT"] += 1

    msg = f"📘 EOD Report ({datetime.now(IST).strftime('%d %b')})\n\n"
    for k, v in results.items():
        msg += f"{k}: {v}\n"

    send(msg)
    os.remove(TRADES_FILE)


if __name__ == "__main__":
    main()