import sys
import os
import pandas as pd
import requests
from datetime import datetime
import pytz

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from alerts.telegram_alerts import send_alert

CACHE_FILE = "data/stage1_cache.csv"
ALERT_LOG_FILE = "data/alerted_today.csv"
SIGNALS_FILE = "data/signals.csv"
PRICE_LOG_FILE = "data/price_log.csv"


# ---------------------------------------------------
# Fetch LTP from NSE
# ---------------------------------------------------
def fetch_ltp(symbol):

    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json"
    }

    try:
        session = requests.Session()
        session.get("https://www.nseindia.com", headers=headers, timeout=10)

        url = f"https://www.nseindia.com/api/quote-equity?symbol={symbol}"
        r = session.get(url, headers=headers, timeout=10)

        data = r.json()
        return float(data["priceInfo"]["lastPrice"])

    except:
        return None


# ---------------------------------------------------
# Load Stage-1 Watchlist
# ---------------------------------------------------
def load_stage1_watchlist():

    if not os.path.exists(CACHE_FILE):
        return []

    df = pd.read_csv(CACHE_FILE)
    return df["symbol"].tolist()


# ---------------------------------------------------
# Price Logging
# ---------------------------------------------------
def log_prices(symbol_prices):

    os.makedirs("data", exist_ok=True)

    ist = pytz.timezone("Asia/Kolkata")
    now = datetime.now(ist)

    rows = []

    for symbol, price in symbol_prices.items():
        rows.append({
            "symbol": symbol,
            "date": now.date(),
            "time": now.strftime("%H:%M:%S"),
            "price": price
        })

    df = pd.DataFrame(rows)

    if os.path.exists(PRICE_LOG_FILE):
        df.to_csv(PRICE_LOG_FILE, mode="a", header=False, index=False)
    else:
        df.to_csv(PRICE_LOG_FILE, index=False)


# ---------------------------------------------------
# Prevent Duplicate Alerts
# ---------------------------------------------------
def load_alerted_symbols():
    if os.path.exists(ALERT_LOG_FILE):
        return set(pd.read_csv(ALERT_LOG_FILE)["symbol"])
    return set()


def save_alerted_symbol(symbol):
    df = pd.DataFrame([[symbol]], columns=["symbol"])
    if os.path.exists(ALERT_LOG_FILE):
        df.to_csv(ALERT_LOG_FILE, mode="a", header=False, index=False)
    else:
        df.to_csv(ALERT_LOG_FILE, index=False)


# ---------------------------------------------------
# Save Signals
# ---------------------------------------------------
def save_signals(signals):

    os.makedirs("data", exist_ok=True)

    ist = pytz.timezone("Asia/Kolkata")
    now = datetime.now(ist)

    df = pd.DataFrame(signals)

    df["date"] = now.date()
    df["trigger_time"] = now.strftime("%H:%M:%S")
    df["result"] = ""

    columns = [
        "symbol",
        "action",
        "entry",
        "sl",
        "tp",
        "date",
        "trigger_time",
        "result"
    ]

    df = df[columns]

    if os.path.exists(SIGNALS_FILE):
        existing = pd.read_csv(SIGNALS_FILE)
        combined = pd.concat([existing, df], ignore_index=True)
        combined.to_csv(SIGNALS_FILE, index=False)
    else:
        df.to_csv(SIGNALS_FILE, index=False)


# ---------------------------------------------------
# Simple Signal Logic (RR 1:2)
# ---------------------------------------------------
def generate_signal(symbol, price):

    # Example: Momentum breakout logic
    # You can replace with your GENZ logic

    risk_percent = 1.0

    # Example random condition placeholder
    # Replace with your real signal conditions

    if price > 0:

        entry = price
        sl = round(price * (1 - risk_percent / 100), 2)
        tp = round(price + (price - sl) * 2, 2)

        return {
            "symbol": symbol,
            "action": "BUY",
            "entry": entry,
            "sl": sl,
            "tp": tp,
            "confidence": 80
        }

    return None


# ---------------------------------------------------
# MAIN
# ---------------------------------------------------
def main():

    ist = pytz.timezone("Asia/Kolkata")
    now = datetime.now(ist)
    current_time = now.strftime("%H:%M")

    # Run only during market hours
    if not ("09:15" <= current_time <= "15:30"):
        print("Outside market hours.")
        return

    stage1_symbols = load_stage1_watchlist()

    if not stage1_symbols:
        print("No Stage-1 symbols.")
        return

    print(f"Scanning {len(stage1_symbols)} stocks...")

    symbol_prices = {}
    signals = []

    alerted_symbols = load_alerted_symbols()

    for symbol in stage1_symbols:

        price = fetch_ltp(symbol)

        if price is None:
            continue

        symbol_prices[symbol] = price

        signal = generate_signal(symbol, price)

        if signal and symbol not in alerted_symbols:
            signals.append(signal)
            save_alerted_symbol(symbol)

    # Log prices every run
    if symbol_prices:
        log_prices(symbol_prices)

    if not signals:
        print("No new signals.")
        return

    # Sort by confidence
    signals = sorted(signals, key=lambda x: x["confidence"], reverse=True)

    save_signals(signals)

    # Telegram Message
    message = f"🚨 <b>INTRADAY SIGNALS</b> | {current_time}\n\n"

    for s in signals[:10]:  # limit to top 10
        message += (
            f"{'🟢' if s['action']=='BUY' else '🔴'} {s['symbol']}\n"
            f"Entry: {s['entry']} | SL: {s['sl']} | Target: {s['tp']}\n"
            f"Conf: {s['confidence']}%\n\n"
        )

    send_alert(message)


if __name__ == "__main__":
    main()