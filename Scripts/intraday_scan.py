import pandas as pd
import requests
from datetime import datetime
import pytz
import os
import time

IST = pytz.timezone("Asia/Kolkata")

UNIVERSE_FILE = "data/universe_nse_tradable.csv"

MIN_MOVE_PCT = 1.0
MIN_VOLUME = 300000
CONF_THRESHOLD = 80

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# --------------------------------------------------
# Telegram helper
# --------------------------------------------------
def send(msg):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("⚠️ Telegram not configured")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": msg})


# --------------------------------------------------
# Fetch live intraday data (NSE endpoint via Yahoo)
# --------------------------------------------------
def fetch_intraday(symbol):
    try:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}.NS?interval=5m&range=1d"
        r = requests.get(url, timeout=5)
        data = r.json()["chart"]["result"][0]

        close = data["indicators"]["quote"][0]["close"]
        volume = data["indicators"]["quote"][0]["volume"]

        if len(close) < 2 or close[-1] is None or close[-2] is None:
            return None

        pct_change = ((close[-1] - close[0]) / close[0]) * 100
        vol = sum(v for v in volume if v)

        return {
            "pct_change": pct_change,
            "volume": vol,
            "price": close[-1]
        }

    except Exception:
        return None


# --------------------------------------------------
# Confidence scoring
# --------------------------------------------------
def confidence_score(pct, vol):
    score = 0
    reasons = []

    if abs(pct) >= 2:
        score += 40
        reasons.append("Strong move")

    if vol >= 500000:
        score += 40
        reasons.append("High volume")
    elif vol >= 300000:
        score += 20
        reasons.append("Decent volume")

    return score, reasons


# --------------------------------------------------
# Main intraday scan
# --------------------------------------------------
def main():
    now = datetime.now(IST)
    print(f"🕒 IST Time: {now}")

    if not os.path.exists(UNIVERSE_FILE):
        raise FileNotFoundError(f"❌ Missing {UNIVERSE_FILE}")

    universe = pd.read_csv(UNIVERSE_FILE)

    print(f"📊 Symbols to scan: {len(universe)}")

    trades = []

    for i, symbol in enumerate(universe["SYMBOL"], 1):
        data = fetch_intraday(symbol)
        if not data:
            continue

        pct = data["pct_change"]
        vol = data["volume"]
        price = data["price"]

        if abs(pct) < MIN_MOVE_PCT or vol < MIN_VOLUME:
            continue

        conf, reasons = confidence_score(pct, vol)

        if conf >= CONF_THRESHOLD:
            trades.append((symbol, pct, price, conf))

        if i % 100 == 0:
            print(f"✅ Processed {i} stocks")

        time.sleep(0.05)  # avoid rate-limit

    if not trades:
        print("ℹ️ No new intraday signals found in this run")
        return

    msg = "🚨 Intraday Trade Alerts (Full NSE Scan)\n\n"
    for s, pct, price, conf in trades:
        msg += f"{s}\nPrice: {price:.2f}\nΔ {pct:.2f}% | Conf {conf}\n\n"

    send(msg)
    print(f"📨 Sent {len(trades)} alerts")


if __name__ == "__main__":
    main()