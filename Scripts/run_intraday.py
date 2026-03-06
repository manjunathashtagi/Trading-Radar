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


# -------------------------
# Load Stage-1 Watchlist
# -------------------------
def load_stage1():

    if not os.path.exists(CACHE_FILE):
        return []

    df = pd.read_csv(CACHE_FILE)

    if "symbol" in df.columns:
        return df["symbol"].tolist()

    return df.iloc[:, 0].tolist()


# -------------------------
# Prevent duplicate alerts
# -------------------------
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


# -------------------------
# Save signals for reports
# -------------------------
def save_signals(signals):

    ist = pytz.timezone("Asia/Kolkata")
    now = datetime.now(ist)

    df = pd.DataFrame(signals)

    df["date"] = now.date()
    df["trigger_time"] = now.strftime("%H:%M:%S")
    df["result"] = ""

    cols = [
        "symbol",
        "action",
        "entry",
        "sl",
        "tp",
        "score",
        "date",
        "trigger_time",
        "result"
    ]

    df = df[cols]

    if os.path.exists(SIGNALS_FILE):

        existing = pd.read_csv(SIGNALS_FILE)
        combined = pd.concat([existing, df], ignore_index=True)
        combined.to_csv(SIGNALS_FILE, index=False)

    else:

        df.to_csv(SIGNALS_FILE, index=False)


# -------------------------
# Momentum Scoring Engine
# -------------------------
def score_stock(df):

    latest = df.iloc[-1]

    score = 0

    if latest["EMA20"] > latest["EMA50"]:
        score += 25

    if latest["RSI"] > 55:
        score += 20

    if latest["Volume"] > 1.3 * df["VOL_AVG"].iloc[-1]:
        score += 20

    pct_move = ((latest["Close"] - df["Close"].iloc[-6]) /
                df["Close"].iloc[-6]) * 100

    if pct_move > 1.5:
        score += 20

    if latest["Close"] > df["High"].rolling(20).max().iloc[-2]:
        score += 15

    return score


# -------------------------
# ETA to target estimation
# -------------------------
def estimate_eta(df, entry, target):

    avg_move = df["Close"].diff().abs().tail(10).mean()

    distance = abs(target - entry)

    candles = distance / avg_move if avg_move != 0 else 10

    minutes = candles * 15

    if minutes < 60:
        return f"{int(minutes)}m", "⚡ Fast"

    if minutes < 180:
        return f"{int(minutes/60)}h", "📈 Intraday"

    return f"{int(minutes/60)}h+", "🐢 Slow"


# -------------------------
# Signal Engine
# -------------------------
def analyze(symbol):

    try:

        df = yf.download(symbol + ".NS",
                         period="5d",
                         interval="15m",
                         progress=False)

        if len(df) < 40:
            return None

        df["EMA20"] = df["Close"].ewm(span=20).mean()
        df["EMA50"] = df["Close"].ewm(span=50).mean()
        df["RSI"] = RSIIndicator(df["Close"], 14).rsi()
        df["VOL_AVG"] = df["Volume"].rolling(20).mean()

        latest = df.iloc[-1]
        prev = df.iloc[-2]

        entry = latest["Close"]

        score = score_stock(df)

        if score < 60:
            return None

        # BUY breakout or continuation
        if latest["EMA20"] > latest["EMA50"] and latest["RSI"] > 50:

            sl = df["Low"].rolling(5).min().iloc[-1]
            risk = entry - sl
            target = entry + (2 * risk)

            eta, speed = estimate_eta(df, entry, target)

            return {
                "symbol": symbol,
                "action": "BUY",
                "entry": round(entry, 2),
                "sl": round(sl, 2),
                "tp": round(target, 2),
                "score": score,
                "eta": eta,
                "speed": speed
            }

        return None

    except:
        return None


# -------------------------
# MAIN
# -------------------------
def main():

    ist = pytz.timezone("Asia/Kolkata")
    now = datetime.now(ist)

    time_now = now.strftime("%H:%M")

    if not ("09:30" <= time_now <= "15:00"):
        print("Outside trading window.")
        return

    symbols = load_stage1()

    print(f"Stage-1 stocks: {len(symbols)}")

    alerted = load_alerted()

    signals = []

    for s in symbols:

        signal = analyze(s)

        if signal and s not in alerted:
            signals.append(signal)
            save_alerted(s)

    if not signals:
        print("No new signals.")
        return

    # sort by score
    signals = sorted(signals, key=lambda x: x["score"], reverse=True)

    # keep best 12
    signals = signals[:12]

    save_signals(signals)

    message = f"🚨 <b>AI MOMENTUM SIGNALS</b> | {time_now}\n\n"

    for s in signals:

        message += (
            f"🟢 {s['symbol']} | Score {s['score']}\n"
            f"Entry {s['entry']} | SL {s['sl']} | Target {s['tp']}\n"
            f"ETA {s['eta']} {s['speed']}\n\n"
        )

    send_alert(message)


if __name__ == "__main__":
    main()