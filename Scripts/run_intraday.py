import os
import sys
import pandas as pd
import time
from datetime import datetime
import pytz

# ✅ FIX: ADD PROJECT ROOT PATH
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from alerts.telegram_alerts import send_alert
from data_feed.nse_fetch import get_session, get_quote

STAGE1_FILE = "data/stage1_cache.csv"
ALERT_FILE = "data/alerted_today.csv"


def load_alerted():
    if not os.path.exists(ALERT_FILE):
        return set()

    df = pd.read_csv(ALERT_FILE)

    if "stock" not in df.columns:
        return set()

    return set(df["stock"].dropna().tolist())


def save_alert(stock):
    df = pd.DataFrame([{"stock": stock}])

    if os.path.exists(ALERT_FILE):
        df.to_csv(ALERT_FILE, mode="a", header=False, index=False)
    else:
        df.to_csv(ALERT_FILE, index=False)


def main():

    if not os.path.exists(STAGE1_FILE):
        print("❌ No stage1 cache")
        return

    df = pd.read_csv(STAGE1_FILE)

    if "symbol" not in df.columns:
        print("❌ Invalid stage1 file")
        return

    symbols = df["symbol"].dropna().tolist()

    alerted = load_alerted()

    session = get_session()

    ist = pytz.timezone("Asia/Kolkata")
    now = datetime.now(ist)

    signals = []

    for stock in symbols:

        if stock in alerted:
            continue

        data = get_quote(session, stock)

        if not data:
            continue

        price = data["price"]
        open_price = data["open"]
        high = data["high"]
        volume = data["volume"]

        # 🚀 OPENING BLAST LOGIC
        breakout = price > open_price * 1.01 and price >= high

        # 🔥 SMART MONEY (volume proxy)
        volume_spike = volume and volume > 1.5

        if breakout and volume_spike:

            entry = price
            sl = price * 0.985
            tp = price * 1.03

            msg = (
                f"🚀 NSE BLAST SIGNAL\n\n"
                f"{stock}\n"
                f"Entry: {round(entry,2)}\n"
                f"SL: {round(sl,2)}\n"
                f"TP: {round(tp,2)}"
            )

            send_alert(msg)
            save_alert(stock)

            signals.append(stock)

        time.sleep(0.2)

    print(f"✅ Signals found: {len(signals)}")


if __name__ == "__main__":
    main()