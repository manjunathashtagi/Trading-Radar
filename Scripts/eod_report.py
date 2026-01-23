import pandas as pd
from datetime import datetime
import pytz
import os
import requests

IST = pytz.timezone("Asia/Kolkata")

def send_telegram(msg):
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        return

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    requests.post(url, data={"chat_id": chat_id, "text": msg})

def main():
    today = datetime.now(IST).strftime("%Y-%m-%d")
    file_path = f"data/intraday_signals_{today}.csv"

    if not os.path.exists(file_path):
        send_telegram("📉 EOD: No intraday signals today")
        print("❌ No intraday CSV found")
        return

    df = pd.read_csv(file_path)

    if df.empty:
        send_telegram("📉 EOD: No intraday signals today")
        print("❌ CSV exists but empty")
        return

    total = len(df)
    longs = df[df["DIRECTION"] == "LONG"]
    shorts = df[df["DIRECTION"] == "SHORT"]

    msg = (
        f"📊 EOD INTRADAY SUMMARY ({today})\n\n"
        f"Total signals: {total}\n"
        f"🟢 Long signals: {len(longs)}\n"
        f"🔴 Short signals: {len(shorts)}\n\n"
        f"(Based ONLY on alerts sent during the day)"
    )

    send_telegram(msg)
    print("✅ EOD summary sent")

if __name__ == "__main__":
    main()