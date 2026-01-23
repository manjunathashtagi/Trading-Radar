import pandas as pd
import requests
import os
from datetime import datetime
import pytz

IST = pytz.timezone("Asia/Kolkata")
TRADES_FILE = "data/trades_today.csv"

TG_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TG_CHAT = os.getenv("TELEGRAM_CHAT_ID")

def send_tg(msg):
    if not TG_TOKEN or not TG_CHAT:
        return
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": TG_CHAT, "text": msg})

def get_close(symbol):
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
    if not os.path.exists(TRADES_FILE):
        send_tg("📉 EOD: No intraday signals today")
        return

    df = pd.read_csv(TRADES_FILE)
    results = []

    for _, r in df.iterrows():
        close = get_close(r.SYMBOL)
        if close is None:
            continue

        direction = 1 if r.SIDE == "LONG" else -1
        outcome = "✅ HIT" if (close * direction) > 0 else "❌ FAIL"

        results.append(f"{r.SYMBOL} ({r.SIDE}) → {outcome}")

    if not results:
        send_tg("📉 EOD: No valid outcomes")
        return

    msg = "📊 EOD REPORT\n\n" + "\n".join(results[:30])
    send_tg(msg)

if __name__ == "__main__":
    main()