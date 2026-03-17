import sys
import os
import pandas as pd
import numpy as np
import yfinance as yf
import joblib
from datetime import datetime
import pytz
from ta.momentum import RSIIndicator
from ta.trend import EMAIndicator

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from alerts.telegram_alerts import send_alert


CACHE_FILE = "data/stage1_cache.csv"
SIGNALS_FILE = "data/signals.csv"
ALERT_LOG_FILE = "data/alerted_today.csv"
MODEL_FILE = "data/ai_model.pkl"


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
# Save signals
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
# AI + Momentum Engine
# -----------------------------
def analyze_symbol(symbol, model):

    try:

        ticker = yf.Ticker(symbol + ".NS")

        df = ticker.history(period="30d", interval="15m")

        if len(df) < 80:
            return None

        df["EMA20"] = EMAIndicator(df["Close"], window=20).ema_indicator()
        df["EMA50"] = EMAIndicator(df["Close"], window=50).ema_indicator()

        df["RSI"] = RSIIndicator(df["Close"], window=14).rsi()

        df["VOL_AVG"] = df["Volume"].rolling(20).mean()

        latest = df.iloc[-1]

        entry = latest["Close"]

        # -----------------------------
        # Feature creation for AI
        # -----------------------------
        volatility = (latest["High"] - latest["Low"]) / latest["Close"]

        volume_ratio = latest["Volume"] / latest["VOL_AVG"]

        distance_high = entry - df["High"].rolling(20).max().iloc[-2]

        features = np.array([[
            latest["RSI"],
            latest["EMA20"],
            latest["EMA50"],
            volatility,
            volume_ratio,
            distance_high
        ]])

        ai_prob = model.predict_proba(features)[0][1]

        ai_score = ai_prob * 100


        # -----------------------------
        # Early Momentum Detection
        # -----------------------------
        volatility_20 = df["Close"].pct_change().rolling(20).std()
        volatility_5 = df["Close"].pct_change().rolling(5).std()

        squeeze = volatility_5.iloc[-1] < 0.6 * volatility_20.iloc[-1]

        volume_accum = df["Volume"].rolling(10).mean().iloc[-1] > 1.2 * df["Volume"].rolling(30).mean().iloc[-1]

        ema_slope = (df["EMA20"].iloc[-1] - df["EMA20"].iloc[-5]) / df["EMA20"].iloc[-5]

        early_score = 0

        if squeeze:
            early_score += 20

        if volume_accum:
            early_score += 20

        if ema_slope > 0.01:
            early_score += 20

        final_score = ai_score + early_score

        if final_score < 70:
            return None

        sl = df["Low"].rolling(5).min().iloc[-1]

        risk = entry - sl

        tp = entry + (risk * 2)

        # ETA estimate
        momentum = df["Close"].pct_change().iloc[-1]

        if momentum > 0.01:
            eta = "30m"
        elif momentum > 0.005:
            eta = "1h"
        else:
            eta = "2h"

        return {
            "symbol": symbol,
            "action": "BUY",
            "entry": round(entry,2),
            "sl": round(sl,2),
            "tp": round(tp,2),
            "score": round(final_score,1),
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

    if not ("09:20" <= time_now <= "15:30"):
        print("Outside market hours.")
        return

    if not os.path.exists(MODEL_FILE):
        print("AI model not found")
        return

    model = joblib.load(MODEL_FILE)

    symbols = load_stage1_watchlist()

    print(f"Stage-1 stocks: {len(symbols)}")

    alerted = load_alerted()

    signals = []

    for symbol in symbols:

        signal = analyze_symbol(symbol, model)

        if signal and symbol not in alerted:

            signals.append(signal)

            save_alerted(symbol)

    if not signals:

        print("No new signals.")

        return

    signals = sorted(signals, key=lambda x: x["score"], reverse=True)

    signals = signals[:27]

    save_signals(signals)

    message = f"🚨 <b>AI MOMENTUM RADAR</b> | {time_now}\n\n"

    for s in signals:

        message += (
            f"{s['symbol']} | Score {s['score']}\n"
            f"Entry: {s['entry']} | SL: {s['sl']} | Target: {s['tp']}\n"
            f"ETA: {s['eta']}\n\n"
        )

    send_alert(message)


if __name__ == "__main__":
    main()