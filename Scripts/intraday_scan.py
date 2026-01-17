import pandas as pd
import requests
from datetime import datetime
import pytz
import os
import time

# ================= CONFIG =================
IST = pytz.timezone("Asia/Kolkata")

UNIVERSE_FILE = "data/universe_nse_tradable.csv"

# Momentum rules (your fixed requirements)
MIN_MOVE_PCT = 0.8
MIN_VOLUME = 250000
CONF_THRESHOLD = 70

# ORB (Early Evidence)
ORB_START = (9, 15)
ORB_END = (9, 30)
ORB_MIN_BREAK_PCT = 0.3
ORB_VOLUME_RATIO = 1.3

SLEEP_TIME = 0.05  # rate-limit protection

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# =========================================


# ---------- Telegram ----------
def send(msg):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("⚠️ Telegram not configured")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": msg})


# ---------- Live data ----------
def fetch_intraday(symbol):
    try:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}.NS?interval=5m&range=1d"
        r = requests.get(url, timeout=6)
        data = r.json()["chart"]["result"][0]

        quotes = data["indicators"]["quote"][0]
        closes = quotes["close"]
        volumes = quotes["volume"]

        if not closes or closes[-1] is None or closes[0] is None:
            return None

        pct_change = ((closes[-1] - closes[0]) / closes[0]) * 100
        total_volume = sum(v for v in volumes if v)

        return {
            "pct_change": pct_change,
            "volume": total_volume,
            "price": closes[-1]
        }

    except Exception:
        return None


# ---------- ORB (Early Evidence) ----------
def check_orb(symbol):
    try:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}.NS?interval=5m&range=1d"
        r = requests.get(url, timeout=6)
        data = r.json()["chart"]["result"][0]

        timestamps = data["timestamp"]
        quotes = data["indicators"]["quote"][0]
        closes = quotes["close"]
        volumes = quotes["volume"]

        orb_high = None
        orb_low = None
        orb_volume = 0
        total_volume = 0

        for ts, close, vol in zip(timestamps, closes, volumes):
            if close is None or vol is None:
                continue

            candle_time = datetime.fromtimestamp(ts, IST)
            total_volume += vol

            if (candle_time.hour, candle_time.minute) >= ORB_START and \
               (candle_time.hour, candle_time.minute) <= ORB_END:

                orb_high = close if orb_high is None else max(orb_high, close)
                orb_low = close if orb_low is None else min(orb_low, close)
                orb_volume += vol

        if orb_high is None or orb_volume == 0:
            return False

        last_price = closes[-1]
        if last_price is None:
            return False

        breakout_pct = ((last_price - orb_high) / orb_high) * 100
        vol_ratio = total_volume / orb_volume if orb_volume > 0 else 0

        if breakout_pct >= ORB_MIN_BREAK_PCT and vol_ratio >= ORB_VOLUME_RATIO:
            return True

        return False

    except Exception:
        return False


# ---------- Confidence ----------
def confidence_score(pct, vol):
    score = 0
    reasons = []

    if abs(pct) >= 1.0:
        score += 40
        reasons.append("Strong move")
    elif abs(pct) >= 0.8:
        score += 30
        reasons.append("Moderate move")

    if vol >= 400000:
        score += 40
        reasons.append("High volume")
    elif vol >= 250000:
        score += 30
        reasons.append("Decent volume")

    return score, reasons


# ---------- MAIN ----------
def main():
    now = datetime.now(IST)
    print(f"🕒 IST Time: {now}")

    if not os.path.exists(UNIVERSE_FILE):
        raise FileNotFoundError(f"❌ Missing {UNIVERSE_FILE}")

    universe = pd.read_csv(UNIVERSE_FILE)
    print(f"📊 Symbols to scan: {len(universe)}")

    alerts = []

    for i, symbol in enumerate(universe["SYMBOL"], 1):

        # STEP 1: Early evidence (ORB)
        if not check_orb(symbol):
            continue

        # STEP 2: Momentum confirmation
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
            alerts.append((symbol, price, pct, conf))

        if i % 100 == 0:
            print(f"✅ Processed {i} stocks")

        time.sleep(SLEEP_TIME)

    if not alerts:
        print("ℹ️ No qualified intraday signals in this run")
        return

    msg = "🚨 Intraday Trade Alerts (ORB + Momentum)\n\n"
    for s, price, pct, conf in alerts:
        msg += f"{s}\nPrice: {price:.2f}\nΔ {pct:.2f}% | Conf {conf}\n\n"

    send(msg)
    print(f"📨 Sent {len(alerts)} alerts")


if __name__ == "__main__":
    main()