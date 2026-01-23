import pandas as pd
import requests
from datetime import datetime
import pytz
import os

IST = pytz.timezone("Asia/Kolkata")

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

def send(msg):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": CHAT_ID, "text": msg})

def fetch_close(symbol):
    try:
        url = f"https://www.nseindia.com/api/quote-equity?symbol={symbol}"
        headers = {
            "User-Agent": "Mozilla/5.0",
            "Referer": "https://www.nseindia.com/"
        }
        r = requests.get(url, headers=headers, timeout=5)
        return r.json()["priceInfo"]["close"]
    except Exception:
        return None

def main():
    today = datetime.now(IST).strftime("%Y-%m-%d")
    path = f"data/intraday_signals_{today}.csv"

    if not os.path.exists(path):
        send("📉 EOD: No intraday signals today")
        return

    df = pd.read_csv(path)
    results = []

    for _, r in df.iterrows():
        close = fetch_close(r.SYMBOL)
        if close is None:
            continue

        pnl = r.MOVE_PCT if r.DIRECTION == "LONG" else -r.MOVE_PCT
        results.append(pnl)

    if not results:
        send("📉 EOD: Signals existed but no data available")
        return

    msg = f"📊 EOD INTRADAY SUMMARY ({today})\n\n"
    msg += f"Total signals: {len(results)}\n"
    msg += f"Winning: {sum(1 for x in results if x > 0)}\n"
    msg += f"Losing: {sum(1 for x in results if x <= 0)}\n"
    msg += f"Avg move: {round(sum(results)/len(results), 2)}%\n"

    send(msg)

if __name__ == "__main__":
    main()