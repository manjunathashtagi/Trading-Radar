import pandas as pd
from datetime import datetime
import pytz
import os
import requests

IST = pytz.timezone("Asia/Kolkata")

TRADES_FILE = "data/trades_today.csv"
BOT = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT = os.getenv("TELEGRAM_CHAT_ID")

def send(msg):
    if not BOT:
        return
    requests.post(
        f"https://api.telegram.org/bot{BOT}/sendMessage",
        data={"chat_id": CHAT, "text": msg}
    )

def main():
    if not os.path.exists(TRADES_FILE):
        send("📉 EOD: No trades today")
        return

    df = pd.read_csv(TRADES_FILE)

    total = len(df)
    avg_conf = round(df["confidence"].mean(), 1)

    report = (
        "📊 End of Day Report\n\n"
        f"Trades: {total}\n"
        f"Avg Confidence: {avg_conf}\n"
        "⚠️ Outcome based on levels, not live prices"
    )

    send(report)

if __name__ == "__main__":
    main()