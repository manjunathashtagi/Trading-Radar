import pandas as pd
import requests
from datetime import datetime
import pytz
import os

IST = pytz.timezone("Asia/Kolkata")

UNIVERSE_FILE = "data/universe_nse_tradable.csv"
TRADES_FILE = "data/trades_today.csv"

MIN_MOVE_PCT = 0.4
MIN_VOLUME = 150_000
CONF_THRESHOLD = 55
TARGET_PCT = 1.0   # expected move (can be dynamic later)

def send(msg):
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat = os.getenv("TELEGRAM_CHAT_ID")
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    requests.post(url, data={"chat_id": chat, "text": msg})

def fetch_price(symbol):
    url = f"https://www.nseindia.com/api/quote-equity?symbol={symbol}"
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json",
        "Referer": "https://www.nseindia.com/"
    }
    r = requests.get(url, headers=headers, timeout=5)
    data = r.json()["priceInfo"]
    return data["lastPrice"], data["previousClose"]

def confidence_score(move):
    score = 25
    reasons = ["Momentum"]
    if abs(move) >= 0.8:
        score += 20
        reasons.append("Strong Move")
    score += 20
    reasons.append("Liquidity")
    return score, reasons

def main():
    now = datetime.now(IST)

    df = pd.read_csv(UNIVERSE_FILE)
    trades = []

    for sym in df["SYMBOL"]:
        try:
            last, prev = fetch_price(sym)
        except Exception:
            continue

        move = round(((last - prev) / prev) * 100, 2)

        if abs(move) < MIN_MOVE_PCT:
            continue

        score, reasons = confidence_score(move)
        if score < CONF_THRESHOLD:
            continue

        direction = "BULLISH" if move > 0 else "BEARISH"

        trades.append({
            "date": now.date(),
            "time": now.strftime("%H:%M"),
            "symbol": sym,
            "direction": direction,
            "signal_price": last,
            "target_pct": TARGET_PCT,
            "score": score
        })

        emoji = "🟢" if move > 0 else "🔴"
        send(
            f"{emoji} {sym}\n"
            f"Move: {move}%\n"
            f"Direction: {direction}\n"
            f"Expected: {TARGET_PCT}%\n"
            f"Score: {score}"
        )

    if trades:
        os.makedirs("data", exist_ok=True)
        pd.DataFrame(trades).to_csv(
            TRADES_FILE,
            mode="a",
            header=not os.path.exists(TRADES_FILE),
            index=False
        )

if __name__ == "__main__":
    main()
