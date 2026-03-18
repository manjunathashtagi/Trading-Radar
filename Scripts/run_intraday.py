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
# Sector Mapping
# -----------------------------
SECTOR_MAP = {
    "POWER": ["ADANIPOWER","TATAPOWER","NTPC"],
    "DEFENSE": ["BDL","BEL","HAL"],
    "RAIL": ["IRCON","RVNL","RAILTEL"],
    "CHEMICAL": ["SOLARINDS","SRF","NAVINFLUOR"],
    "IT": ["INFY","TCS","HCLTECH"],
    "BANK": ["HDFCBANK","ICICIBANK","AXISBANK"]
}


# -----------------------------
# Load symbols
# -----------------------------
def load_symbols():
    if not os.path.exists(CACHE_FILE):
        return []
    return pd.read_csv(CACHE_FILE)["symbol"].tolist()


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
# Market Direction (NIFTY)
# -----------------------------
def get_market_trend():
    try:
        df = yf.download("^NSEI", period="1d", interval="15m")
        ema20 = df["Close"].ewm(span=20).mean().iloc[-1]
        price = df["Close"].iloc[-1]

        if price > ema20:
            return "BULLISH"
        else:
            return "BEARISH"
    except:
        return "NEUTRAL"


# -----------------------------
# Sector Strength
# -----------------------------
def get_sector_score(symbol):

    for sector, stocks in SECTOR_MAP.items():
        if symbol in stocks:
            moves = []

            for s in stocks:
                try:
                    d = yf.download(s+".NS", period="1d", interval="15m")
                    change = (d["Close"].iloc[-1] - d["Close"].iloc[-5]) / d["Close"].iloc[-5]
                    moves.append(change)
                except:
                    continue

            if not moves:
                return 0

            avg_move = np.mean(moves)

            if avg_move > 0.02:
                return 20
            elif avg_move > 0.01:
                return 10

    return 0


# -----------------------------
# ETA
# -----------------------------
def estimate_eta(vol):
    if vol > 0.02:
        return "30m"
    elif vol > 0.015:
        return "1h"
    else:
        return "2h"


# -----------------------------
# CORE ANALYSIS
# -----------------------------
def analyze(symbol, model, market_trend):

    try:
        df = yf.download(symbol + ".NS", period="5d", interval="15m")

        if len(df) < 50:
            return None

        df["EMA20"] = df["Close"].ewm(span=20).mean()
        df["EMA50"] = df["Close"].ewm(span=50).mean()
        df["RSI"] = RSIIndicator(df["Close"], window=14).rsi()

        df["VOL_SHORT"] = df["Volume"].rolling(10).mean()
        df["VOL_LONG"] = df["Volume"].rolling(30).mean()

        df["HH20"] = df["High"].rolling(20).max()

        latest = df.iloc[-1]
        entry = latest["Close"]

        # -----------------------------
        # Early detection
        # -----------------------------
        near_breakout = entry > 0.96 * df["HH20"].iloc[-1]

        range_10 = df["High"].rolling(10).max() - df["Low"].rolling(10).min()
        tight_range = (range_10.iloc[-1] / entry) < 0.025

        volume_build = latest["VOL_SHORT"] > latest["VOL_LONG"]

        trend_ok = latest["EMA20"] > latest["EMA50"]

        rsi_ok = 50 < latest["RSI"] < 65

        if not (near_breakout and tight_range and volume_build and trend_ok and rsi_ok):
            return None

        # -----------------------------
        # AI Prediction
        # -----------------------------
        volatility = df["Close"].pct_change().rolling(10).std().iloc[-1]
        volume_ratio = latest["VOL_SHORT"] / latest["VOL_LONG"]
        distance_high = (df["HH20"].iloc[-1] - entry) / entry

        features = np.array([[latest["RSI"], latest["EMA20"], latest["EMA50"],
                              volatility, volume_ratio, distance_high]])

        try:
            prob = model.predict_proba(features)[0][1]
            ai_score = prob * 100
        except:
            ai_score = 50

        if ai_score < 60:
            return None

        # -----------------------------
        # Relative strength
        # -----------------------------
        nifty = yf.download("^NSEI", period="1d", interval="15m")
        n_move = (nifty["Close"].iloc[-1] - nifty["Close"].iloc[-5]) / nifty["Close"].iloc[-5]
        s_move = (df["Close"].iloc[-1] - df["Close"].iloc[-5]) / df["Close"].iloc[-5]

        rs_score = 20 if s_move > n_move else 0

        # -----------------------------
        # Sector score
        # -----------------------------
        sector_score = get_sector_score(symbol)

        # -----------------------------
        # Market filter
        # -----------------------------
        market_score = 10 if market_trend == "BULLISH" else -10

        # -----------------------------
        # Final score
        # -----------------------------
        score = ai_score + rs_score + sector_score + market_score

        sl = df["Low"].rolling(5).min().iloc[-1]
        risk = entry - sl
        tp = entry + 2 * risk

        eta = estimate_eta(volatility)

        return {
            "symbol": symbol,
            "action": "BUY",
            "entry": round(entry,2),
            "sl": round(sl,2),
            "tp": round(tp,2),
            "score": round(score,1),
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

    if os.path.exists(MODEL_FILE):
    model = joblib.load(MODEL_FILE)
else:
    print("AI model missing → fallback mode")
    model = None

    symbols = load_symbols()
    alerted = load_alerted()

    market_trend = get_market_trend()

    print(f"Market: {market_trend}")
    print(f"Scanning {len(symbols)} stocks...")

    signals = []

    for symbol in symbols:

        if symbol in alerted:
            continue

        s = analyze(symbol, model, market_trend)

        if s:
            signals.append(s)
            save_alerted(symbol)

    if not signals:
        print("No signals.")
        return

    signals = sorted(signals, key=lambda x: x["score"], reverse=True)[:27]

    save_signals(signals)

    message = f"🚨 <b>AI PRO RADAR</b> | {time_now}\nMarket: {market_trend}\n\n"

    for s in signals:
        message += (
            f"{s['symbol']} | Score {s['score']}\n"
            f"Entry: {s['entry']} | SL: {s['sl']} | TP: {s['tp']}\n"
            f"ETA: {s['eta']}\n\n"
        )

    send_alert(message)


if __name__ == "__main__":
    main()