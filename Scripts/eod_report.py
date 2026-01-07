import pandas as pd
import yfinance as yf
import os
import requests
from datetime import datetime, timezone, timedelta

TRADES_FILE = "data/trades_today.csv"

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

IST = timezone(timedelta(hours=5, minutes=30))


def send_telegram(msg):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return
    requests.post(
        f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
        data={"chat_id": TELEGRAM_CHAT_ID, "text": msg},
        timeout=10
    )


def main():
    if not os.path.exists(TRADES_FILE):
        print("No trades today.")
        return

    trades = pd.read_csv(TRADES_FILE)
    if trades.empty:
        return

    results = []

    for _, t in trades.iterrows():
        try:
            df = yf.Ticker(t["symbol"] + ".NS").history(period="1d", interval="5m")
            hit_target = (df["High"] >= t["target"]).any()
            hit_sl = (df["Low"] <= t["sl"]).any()

            if hit_target:
                status = "TARGET HIT"
            elif hit_sl:
                status = "SL HIT"
            else:
                status = "NO HIT"

            results.append(status)

        except Exception:
            results.append("ERROR")

    trades["status"] = results

    summary = trades["status"].value_counts()

    msg = f"📘 *EOD Trade Report* ({datetime.now(IST).strftime('%d %b')})\n\n"
    for k, v in summary.items():
        msg += f"{k}: {v}\n"

    send_telegram(msg)

    os.remove(TRADES_FILE)


if __name__ == "__main__":
    main()