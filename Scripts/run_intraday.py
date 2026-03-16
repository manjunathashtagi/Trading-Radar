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
from scanners.ai_scoring import calculate_ai_score, estimate_eta


CACHE_FILE = "data/stage1_cache.csv"
SIGNALS_FILE = "data/signals.csv"
ALERT_LOG_FILE = "data/alerted_today.csv"


# -----------------------------
# Load Stage-1 stocks
# -----------------------------
def load_stage1_watchlist():

    if not os.path.exists(CACHE_FILE):
        return []

    df = pd.read_csv(CACHE_FILE)

    return df["symbol"].tolist()


# -----------------------------
# Prevent duplicate alerts
# -----------------------------
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


# -----------------------------
# Save signals for reports
# -----------------------------
def save_signals(signals):

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
        "score",
        "eta",
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


# -----------------------------
# Analyze stock
# -----------------------------
def analyze_symbol(symbol):

    try:

        ticker = yf.Ticker(symbol + ".NS")

        df = ticker.history(period="5d", interval="15m")

        if len(df) < 40:
            return None

        df["EMA20"] = df["Close"].ewm(span=20).mean()
        df["EMA50"] = df["Close"].ewm(span=50).mean()

        df["RSI"] = RSIIndicator(df["Close"], 14).rsi()

        df["HH20"] = df["High"].rolling(20).max()
        df["LL20"] = df["Low"].rolling(20).min()

        df["VOL_AVG"] = df["Volume"].rolling(20).mean()

        df["ATR"] = (df["High"] - df["Low"]).rolling(14).mean()

        latest = df.iloc[-1]
        prev = df.iloc[-2]

        entry = latest["Close"]

        volume_spike = latest["Volume"] > 1.2 * latest["VOL_AVG"]

        score = calculate_ai_score(df)

        if score < 50:
            return None


        # BUY
        if latest["EMA20"] > latest["EMA50"] and latest["RSI"] > 50:

            sl = df["Low"].rolling(5).min().iloc[-1]

            risk = entry - sl

            tp = entry + (2 * risk)

            eta = estimate_eta(entry, tp, latest["ATR"])

            return {
                "symbol": symbol,
                "action": "BUY",
                "entry": round(entry,2),
                "sl": round(sl,2),
                "tp": round(tp,2),
                "score": score,
                "eta": eta
            }


        # SELL
        if latest["EMA20"] < latest["EMA50"] and latest["RSI"] < 45:

            sl = df["High"].rolling(5).max().iloc[-1]

            risk = sl - entry

            tp = entry - (2 * risk)

            eta = estimate_eta(entry, tp, latest["ATR"])

            return {
                "symbol": symbol,
                "action": "SELL",
                "entry": round(entry,2),
                "sl": round(sl,2),
                "tp": round(tp,2),
                "score": score,
                "eta": eta
            }

        return None

    except:

        return None


# -----------------------------
# MAIN
# -----------------------------
def main():

    ist = pytz.timezone("Asia/Kolkata")

    now = datetime.now(ist)

    current_time = now.strftime("%H:%M")


    if not ("09:30" <= current_time <= "15:30"):
        print("Outside market hours.")
        return


    symbols = load_stage1_watchlist()

    print(f"Stage-1 stocks: {len(symbols)}")

    alerted = load_alerted()

    signals = []


    for symbol in symbols:

        signal = analyze_symbol(symbol)

        if signal and symbol not in alerted:

            signals.append(signal)

            save_alerted(symbol)


    if not signals:

        print("No new signals.")

        return


    # -----------------------------
    # AI ranking
    # -----------------------------
    signals = sorted(signals, key=lambda x: x["score"], reverse=True)


    # keep best 27
    signals = signals[:27]


    save_signals(signals)


    buy = [s for s in signals if s["action"] == "BUY"]
    sell = [s for s in signals if s["action"] == "SELL"]


    message = f"🚨 <b>TRADING RADAR</b> | {current_time}\n\n"


    if buy:

        message += f"🟢 BUY SIGNALS ({len(buy)})\n\n"

        for s in buy:

            message += (
                f"{s['symbol']}\n"
                f"Score: {s['score']}\n"
                f"Entry: {s['entry']} | SL: {s['sl']} | Target: {s['tp']}\n"
                f"ETA: {s['eta']}\n\n"
            )


    if sell:

        message += f"\n🔴 SELL SIGNALS ({len(sell)})\n\n"

        for s in sell:

            message += (
                f"{s['symbol']}\n"
                f"Score: {s['score']}\n"
                f"Entry: {s['entry']} | SL: {s['sl']} | Target: {s['tp']}\n"
                f"ETA: {s['eta']}\n\n"
            )


    send_alert(message)


if __name__ == "__main__":
    main()