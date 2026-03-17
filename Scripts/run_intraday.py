import sys
import os
import pandas as pd
import numpy as np
import yfinance as yf
import joblib
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
MODEL_FILE = "data/ai_model.pkl"


# -----------------------------
# Load Stage-1 watchlist
# -----------------------------
def load_symbols():
    if not os.path.exists(CACHE_FILE):
        return []
    return pd.read_csv(CACHE_FILE)["symbol"].tolist()


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
# Save signals
# -----------------------------
def save_signals(signals):
    ist = pytz.timezone("Asia/Kolkata")
    now = datetime.now(ist)

    df = pd.DataFrame(signals)
    df["date"] = now.date()
    df["trigger_time"] = now.strftime("%H:%M:%S")
    df["result"] = ""

    cols = ["symbol", "action", "entry", "sl", "tp", "score", "eta",
            "date", "trigger_time", "result"]

    df = df[cols]

    if os.path.exists(SIGNALS_FILE):
        existing = pd.read_csv(SIGNALS_FILE)
        df = pd.concat([existing, df], ignore_index=True)

    df.to_csv(SIGNALS_FILE, index=False)


# -----------------------------
# ETA Prediction
# -----------------------------
def estimate_eta(volatility):
    if volatility > 0.02:
        return "30m"
    elif volatility > 0.015:
        return "1h"
    elif volatility > 0.01:
        return "2h"
    else:
        return "3-4h"


# -----------------------------
# Analyze symbol (CORE LOGIC)
# -----------------------------
def analyze(symbol, model):

    try:
        df = yf.download(symbol + ".NS", period="5d", interval="15m")

        if len(df) < 40:
            return None

        df["EMA20"] = df["Close"].ewm(span=20).mean()
        df["EMA50"] = df["Close"].ewm(span=50).mean()
        df["RSI"] = RSIIndicator(df["Close"], window=14).rsi()

        df["VOL_SHORT"] = df["Volume"].rolling(10).mean()
        df["VOL_LONG"] = df["Volume"].rolling(30).mean()

        df["HH20"] = df["High"].rolling(20).max()
        df["LL20"] = df["Low"].rolling(20).min()

        latest = df.iloc[-1]
        prev = df.iloc[-2]

        entry = latest["Close"]

        # -----------------------------
        # EARLY DETECTION LOGIC
        # -----------------------------

        recent_high = df["HH20"].iloc[-1]
        near_breakout = entry > 0.96 * recent_high

        range_10 = df["High"].rolling(10).max() - df["Low"].rolling(10).min()
        tight_range = (range_10.iloc[-1] / entry) < 0.025

        volume_build = latest["VOL_SHORT"] > latest["VOL_LONG"]

        trend_ok = latest["EMA20"] > latest["EMA50"]

        rsi_ok = 50 < latest["RSI"] < 65

        if not (near_breakout and tight_range and volume_build and trend_ok and rsi_ok):
            return None

        # -----------------------------
        # AI FEATURES
        # -----------------------------
        volatility = df["Close"].pct_change().rolling(10).std().iloc[-1]
        volume_ratio = latest["VOL_SHORT"] / latest["VOL_LONG"]
        distance_high = (recent_high - entry) / entry

        features = np.array([[latest["RSI"],
                              latest["EMA20"],
                              latest["EMA50"],
                              volatility,
                              volume_ratio,
                              distance_high]])

        try:
            ai_score = model.predict_proba(features)[0][1] * 100
        except:
            ai_score = 50

        # -----------------------------
        # FINAL SCORE
        # -----------------------------
        score = (
            ai_score +
            (10 if volume_build else 0) +
            (10 if trend_ok else 0) +
            (10 if near_breakout else 0)
        )

        # -----------------------------
        # TRADE SETUP
        # -----------------------------
        sl = df["Low"].rolling(5).min().iloc[-1]
        risk = entry - sl
        tp = entry + 2 * risk

        eta = estimate_eta(volatility)

        return {
            "symbol": symbol,
            "action": "BUY",
            "entry": round(entry, 2),
            "sl": round(sl, 2),
            "tp": round(tp, 2),
            "score": round(score, 2),
            "eta": eta
        }

    except:
        return None


# -----------------------------
# MAIN
# -----------------------------
def main():

    ist = pytz.timezone("Asia/Kolkata")
    now = datetime.now(ist)
    time_now = now.strftime("%H:%M")

    if not ("09:30" <= time_now <= "15:30"):
        print("Outside market hours.")
        return

    symbols = load_symbols()
    alerted = load_alerted()

    print(f"Scanning {len(symbols)} stocks...")

    try:
        model = joblib.load(MODEL_FILE)
    except:
        model = None

    signals = []

    for symbol in symbols:

        if symbol in alerted:
            continue

        result = analyze(symbol, model)

        if result:
            signals.append(result)
            save_alerted(symbol)

    if not signals:
        print("No signals.")
        return

    # -----------------------------
    # SORT & PICK TOP 27
    # -----------------------------
    signals = sorted(signals, key=lambda x: x["score"], reverse=True)[:27]

    save_signals(signals)

    # -----------------------------
    # TELEGRAM MESSAGE
    # -----------------------------
    message = f"🚨 <b>AI EARLY MOMENTUM RADAR</b> | {time_now}\n\n"

    for s in signals:
        message += (
            f"🟢 {s['symbol']} | Score {s['score']}\n"
            f"Entry: {s['entry']} | SL: {s['sl']} | TP: {s['tp']}\n"
            f"ETA: {s['eta']}\n\n"
        )

    send_alert(message)


if __name__ == "__main__":
    main()