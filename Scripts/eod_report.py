import pandas as pd
import requests
import os

TRADES_FILE = "data/trades_today.csv"

def send(msg):
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat = os.getenv("TELEGRAM_CHAT_ID")
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    requests.post(url, data={"chat_id": chat, "text": msg})

def fetch_ohlc(symbol):
    url = f"https://www.nseindia.com/api/quote-equity?symbol={symbol}"
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json",
        "Referer": "https://www.nseindia.com/"
    }
    r = requests.get(url, headers=headers, timeout=5)
    price = r.json()["priceInfo"]
    return price["intraDayHighLow"]["max"], price["intraDayHighLow"]["min"]

def main():
    if not os.path.exists(TRADES_FILE):
        send("📉 EOD: No intraday signals today")
        return

    df = pd.read_csv(TRADES_FILE)
    report = []

    for _, r in df.iterrows():
        high, low = fetch_ohlc(r.symbol)
        target = r.signal_price * (1 + r.target_pct / 100)

        hit = (
            high >= target if r.direction == "BULLISH"
            else low <= r.signal_price * (1 - r.target_pct / 100)
        )

        report.append(f"{'✅' if hit else '❌'} {r.symbol}")

    send("📊 EOD Signal Outcome\n" + "\n".join(report))

if __name__ == "__main__":
    main()
