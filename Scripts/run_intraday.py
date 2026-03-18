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
ALERT_LOG_FILE = "data/alerted_today.csv"
MODEL_FILE = "data/ai_model.pkl"


# -----------------------------
# Load Stage1
# -----------------------------
def load_stage1():
    if not os.path.exists(CACHE_FILE):
        return []
    df = pd.read_csv(CACHE_FILE)
    return df["symbol"].dropna().tolist()


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
# Smart Money Detection
# -----------------------------
def smart_money_score(df):

    # 1. Volume Accumulation
    vol_short = df["Volume"].rolling(5).mean().iloc[-1]
    vol_long = df["Volume"].rolling(20).mean().iloc[-1]
    vol_score = min((vol_short / vol_long) * 30, 30)

    # 2. Price Compression (coil)
    recent_range = df["High"].tail(10).max() - df["Low"].tail(10).min()
    price = df["Close"].iloc[-1]
    compression = 1 - (recent_range / price)
    compression_score = max(min(compression * 30, 30), 0)

    # 3. Higher Lows (accumulation structure)
    lows = df["Low"].tail(5).values
    hl_score = 20 if all(x < y for x, y in zip(lows, lows[1:])) else 0

    return vol_score + compression_score + hl_score


# -----------------------------
# ETA
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
# Analyze
# -----------------------------
def analyze(symbol, model):

    try:
        df = yf.download(symbol + ".NS", period="5d", interval="15m")

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

        df["volatility"] = df["Close"].pct_change().rolling(10).std()
        df["HH20"] = df["High"].rolling(20).max()

        df = df.dropna()

        latest = df.iloc[-1]
        entry = latest["Close"]

        volatility = latest["volatility"]
        distance_high = (latest["HH20"] - entry) / entry

        # -----------------------------
        # AI Score
        # -----------------------------
        features = np.array([[latest["RSI"],
                              latest["EMA20"],
                              latest["EMA50"],
                              volatility,
                              distance_high]])

        if model:
            try:
                ai_score = model.predict_proba(features)[0][1] * 100
            except:
                ai_score = 50
        else:
            ai_score = 50

        # -----------------------------
        # Smart Money Score
        # -----------------------------
        sm_score = smart_money_score(df)

        # -----------------------------
        # Final Score
        # -----------------------------
        final_score = (0.6 * ai_score) + (0.4 * sm_score)

        # -----------------------------
        # Entry Logic (EARLY ENTRY)
        # -----------------------------
        if (
            latest["EMA20"] > latest["EMA50"] and
            latest["RSI"] > 50 and
            final_score > 60
        ):

            sl = df["Low"].rolling(5).min().iloc[-1]
            risk = entry - sl
            tp = entry + 2 * risk

            return {
                "symbol": symbol,
                "entry": round(entry, 2),
                "sl": round(sl, 2),
                "tp": round(tp, 2),
                "score": round(final_score, 1),
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

    if not ("09:30" <= now.strftime("%H:%M") <= "15:30"):
        print("Outside market hours.")
        return

    # Load model
    model = None
    if os.path.exists(MODEL_FILE):
        try:
            model = joblib.load(MODEL_FILE)
            print("✅ AI model loaded")
        except:
            print("Model load failed")

    symbols = load_stage1()
    alerted = load_alerted()

    print(f"Scanning {len(symbols)} stocks...")

    signals = []

    for s in symbols:
        signal = analyze(s, model)
        if signal and s not in alerted:
            signals.append(signal)
            save_alerted(s)

    if not signals:
        print("No signals")
        return

    # Top 27
    signals = sorted(signals, key=lambda x: x["score"], reverse=True)[:27]

    msg = "🚨 EARLY MOMENTUM SIGNALS\n\n"

    for s in signals:
        msg += (
            f"{s['symbol']} ({s['score']})\n"
            f"Entry: {s['entry']} | SL: {s['sl']} | TP: {s['tp']}\n"
            f"ETA: {s['eta']}\n\n"
        )

    send_alert(msg)


if __name__ == "__main__":
    main()