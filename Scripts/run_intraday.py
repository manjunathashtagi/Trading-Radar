import os
import sys
import pandas as pd
import numpy as np
import yfinance as yf
import pytz
import joblib
from datetime import datetime
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
# Load Stage-1
# -----------------------------
def load_stage1():
    if not os.path.exists(CACHE_FILE):
        return []
    df = pd.read_csv(CACHE_FILE)
    return df["symbol"].dropna().tolist()


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

    if os.path.exists(SIGNALS_FILE):
        existing = pd.read_csv(SIGNALS_FILE)
        df = pd.concat([existing, df], ignore_index=True)

    df.to_csv(SIGNALS_FILE, index=False)


# -----------------------------
# ETA Calculator
# -----------------------------
def estimate_eta(volatility):
    if volatility < 0.005:
        return "3-5h"
    elif volatility < 0.01:
        return "2-3h"
    elif volatility < 0.02:
        return "1-2h"
    else:
        return "30-60m"


# -----------------------------
# Analyze symbol
# -----------------------------
def analyze(symbol, model):

    try:
        df = yf.download(symbol + ".NS", period="5d", interval="15m")

        # FIX yfinance
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        for col in ["Open", "High", "Low", "Close", "Volume"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")

        df = df.dropna()

        if len(df) < 50:
            return None

        # Indicators
        df["EMA20"] = df["Close"].ewm(span=20).mean()
        df["EMA50"] = df["Close"].ewm(span=50).mean()
        df["RSI"] = RSIIndicator(df["Close"], window=14).rsi()

        df["VOL_SHORT"] = df["Volume"].rolling(10).mean()
        df["VOL_LONG"] = df["Volume"].rolling(30).mean()

        df["HH20"] = df["High"].rolling(20).max()
        df["LL20"] = df["Low"].rolling(20).min()

        df["volatility"] = df["Close"].pct_change().rolling(10).std()

        df = df.dropna()

        latest = df.iloc[-1]
        prev = df.iloc[-2]

        entry = latest["Close"]

        volume_ratio = latest["VOL_SHORT"] / latest["VOL_LONG"]
        distance_high = (latest["HH20"] - entry) / entry
        volatility = latest["volatility"]

        # -----------------------------
        # AI Score
        # -----------------------------
        features = np.array([[latest["RSI"],
                              latest["EMA20"],
                              latest["EMA50"],
                              volatility,
                              volume_ratio,
                              distance_high]])

        if model:
            try:
                prob = model.predict_proba(features)[0][1]
                score = prob * 100
            except:
                score = 50
        else:
            score = 50

        # -----------------------------
        # Signal Logic
        # -----------------------------
        volume_spike = latest["Volume"] > 1.3 * latest["VOL_LONG"]

        if (
            latest["EMA20"] > latest["EMA50"] and
            latest["RSI"] > 55 and
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
                "tp": round(tp, 2),
                "score": round(score, 1),
                "eta": estimate_eta(volatility)
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
    time_now = now.strftime("%H:%M")

    if not ("09:30" <= time_now <= "15:30"):
        print("Outside market hours.")
        return

    # Load AI model
    model = None
    if os.path.exists(MODEL_FILE):
        try:
            model = joblib.load(MODEL_FILE)
            print("✅ AI model loaded")
        except:
            print("❌ Model load failed")
    else:
        print("⚠️ No AI model found")

    symbols = load_stage1()
    alerted = load_alerted()

    print(f"Stage-1 stocks: {len(symbols)}")

    signals = []

    for symbol in symbols:
        signal = analyze(symbol, model)
        if signal and symbol not in alerted:
            signals.append(signal)
            save_alerted(symbol)

    if not signals:
        print("No new signals.")
        return

    # -----------------------------
    # Rank Top Signals
    # -----------------------------
    signals = sorted(signals, key=lambda x: x["score"], reverse=True)[:27]

    save_signals(signals)

    # -----------------------------
    # Telegram Message
    # -----------------------------
    msg = f"🚨 INTRADAY SIGNALS ({len(signals)})\n\n"

    for s in signals:
        msg += (
            f"{s['symbol']} ({s['score']})\n"
            f"Entry: {s['entry']} | SL: {s['sl']} | TP: {s['tp']}\n"
            f"ETA: {s['eta']}\n\n"
        )

    send_alert(msg)


if __name__ == "__main__":
    main()