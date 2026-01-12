import pandas as pd
import os
import requests

TRADES_FILE = "data/trades_today.csv"

def send_telegram(msg):
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    requests.post(url, data={"chat_id": chat_id, "text": msg})

def main():
    if not os.path.exists(TRADES_FILE):
        print("No trades today.")
        return

    df = pd.read_csv(TRADES_FILE)
    report = f"📘 EOD Report\nTotal trades: {len(df)}"
    send_telegram(report)

if __name__ == "__main__":
    main()