import sys
import os
import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime
import pytz
from ta.momentum import RSIIndicator

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from alerts.telegram_alerts import send_alert

CACHE_FILE = "data/stage1_cache.csv"
SIGNALS_FILE = "data/signals.csv"
ALERT_LOG_FILE = "data/alerted_today.csv"
PRICE_LOG_FILE = "data/price_log.csv"


# ---------------------------------------------------
# Load Stage-1 shortlist
# ---------------------------------------------------
def load_stage1_watchlist():
    if not os.path.exists(CACHE_FILE):
        return []
    df = pd.read_csv(CACHE_FILE)
    return df["symbol"].tolist()


# ---------------------------------------------------
# Prevent duplicate alerts
# ---------------------------------------------------
def load_alerted():
    if os.path.exists(ALERT_LOG_FILE):
        return set(pd.read_csv(ALERT_LOG_FILE)["symbol"])
    return set()


def save_alerted(symbol):
    df = pd.DataFrame([[symbol]], columns=["symbol"])
    if os.path.exists(ALERT_LOG_FILE):
        df.to_csv(ALERT_LOG_FILE, mode="a", header=False, index=False)
    else:
        df.to_csv(ALERT_LOG_FILE, index=False)


# ---------------------------------------------------
# Save signals
# ---------------------------------------------------
def save_signals(signals):
    ist = pytz.timezone("Asia/Kolkata")
    now = datetime.now(ist)

    df = pd.DataFrame(signals)
    df["date"] = now.date()
    df["trigger_time"] = now.strftime("%H:%M:%S")
    df["result"] = ""

    cols = ["symbol", "action", "entry", "sl", "tp",
            "date", "trigger_time", "result"]

    df = df[cols]

    if os.path.exists(SIGNALS_FILE):
        existing = pd.read_csv(SIGNALS_FILE)
        combined = pd.concat([existing, df], ignore_index=True)
        combined.to_csv(SIGNALS_FILE, index=False)
    else:
        df.to_csv(SIGNALS_FILE, index=False)


# ---------------------------------------------------
# Log price snapshot
# ---------------------------------------------------
def log_price(symbol, price):
    ist = pytz.timezone("Asia/Kolkata")
    now = datetime.now(ist)

    row = pd.DataFrame([{
        "symbol": symbol,
        "date": now.date(),
        "time": now.strftime("%H:%M:%S"),
        "price": price
    }])

    if os.path.exists(PRICE_LOG_FILE):
        row.to_csv(PRICE_LOG_FILE, mode="a", header=False, index=False)
    else:
        row.to_csv(PRICE_LOG_FILE, index=False)


# ---------------------------------------------------
# Gainz-Style Signal Logic (15m)
# ---------------------------------------------------
def analyze_symbol(symbol):

    try:
        ticker = yf.Ticker(symbol + ".NS")
        df = ticker.history(period="5d", interval="15m")

        if len(df) < 50:
            return None

        df["EMA20"] = df["Close"].ewm(span=20).mean()
        df["EMA50"] = df["Close"].ewm(span=50).mean()
        df["RSI"] = RSIIndicator(df["Close"], window=14).rsi()

        df["HH20"] = df["High"].rolling(20).max()
        df["LL20"] = df["Low"].rolling(20).min()
        df["VOL_AVG"] = df["Volume"].rolling(20).mean()

        latest = df.iloc[-1]
        prev = df.iloc[-2]

        entry = latest["Close"]
        volume_spike = latest["Volume"] > 1.5 * latest["VOL_AVG"]

        # BUY Conditions
        if (
            latest["EMA20"] > latest["EMA50"] and
            entry > latest["EMA20"] and
            latest["RSI"] > 55 and
            entry > prev["HH20"] and
            volume_spike
        ):

            sl = df["Low"].rolling(5).min().iloc[-1]
            risk = entry - sl
            tp = entry + 2 * risk

            return {
                "symbol": symbol,
                "action": "BUY",
                "entry": round(entry, 2),
                "sl": round(sl, 2),
                "tp": round(tp, 2)
            }

        # SELL Conditions
        if (
            latest["EMA20"] < latest["EMA50"] and
            entry < latest["EMA20"] and
            latest["RSI"] < 45 and
            entry < prev["LL20"] and
            volume_spike
        ):

            sl = df["High"].rolling(5).max().iloc[-1]
            risk = sl - entry
            tp = entry - 2 * risk

            return {
                "symbol": symbol,
                "action": "SELL",
                "entry": round(entry, 2),
                "sl": round(sl, 2),
                "tp": round(tp, 2)
            }

        return None

    except:
        return None


# ---------------------------------------------------
# MAIN
# ---------------------------------------------------
def main():

    ist = pytz.timezone("Asia/Kolkata")
    now = datetime.now(ist)
    time_now = now.strftime("%H:%M")

    if not ("09:30" <= time_now <= "15:30"):
        print("Outside market hours.")
        return

    symbols = load_stage1_watchlist()
    if not symbols:
        print("No Stage-1 symbols.")
        return

    alerted = load_alerted()
    signals = []

    print(f"Scanning {len(symbols)} stocks...")

    for symbol in symbols:

        signal = analyze_symbol(symbol)

        if signal and symbol not in alerted:
            signals.append(signal)
            save_alerted(symbol)
            log_price(symbol, signal["entry"])

    if not signals:
        print("No new signals.")
        return

    save_signals(signals)

    buy = [s for s in signals if s["action"] == "BUY"]
    sell = [s for s in signals if s["action"] == "SELL"]

    message = f"🚨 <b>INTRADAY SIGNALS</b> | {time_now}\n\n"

    if buy:
        message += f"🟢 BUY SIGNALS ({len(buy)})\n\n"
        for s in buy:
            message += (
                f"{s['symbol']}\n"
                f"Entry: {s['entry']} | SL: {s['sl']} | Target: {s['tp']}\n\n"
            )

    if sell:
        message += f"\n🔴 SELL SIGNALS ({len(sell)})\n\n"
        for s in sell:
            message += (
                f"{s['symbol']}\n"
                f"Entry: {s['entry']} | SL: {s['sl']} | Target: {s['tp']}\n\n"
            )

    send_alert(message)


if __name__ == "__main__":
    main()