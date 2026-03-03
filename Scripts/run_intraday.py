import os
import sys
import pandas as pd
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


# ---------------------------
# Load Stage-1 Watchlist
# ---------------------------
def load_stage1():
    if not os.path.exists(CACHE_FILE):
        return []
    df = pd.read_csv(CACHE_FILE)
    return df["symbol"].tolist()


# ---------------------------
# Prevent duplicate alerts
# ---------------------------
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


# ---------------------------
# Save Signals
# ---------------------------
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


# ---------------------------
# Hybrid Adaptive Engine
# ---------------------------
def analyze_symbol(symbol):

    try:
        df = yf.download(
            symbol + ".NS",
            period="5d",
            interval="15m",
            progress=False
        )

        if len(df) < 50:
            return None

        df["EMA20"] = df["Close"].ewm(span=20).mean()
        df["EMA50"] = df["Close"].ewm(span=50).mean()
        df["RSI"] = RSIIndicator(df["Close"], window=14).rsi()
        df["ATR"] = (df["High"] - df["Low"]).rolling(14).mean()

        latest = df.iloc[-1]
        entry = latest["Close"]
        atr = df["ATR"].iloc[-1]

        trend_strength = abs(latest["EMA20"] - latest["EMA50"]) / entry
        atr_ratio = atr / entry

        # -------- Regime Detection --------
        if trend_strength > 0.003 and atr_ratio > 0.005:
            regime = "TREND"
        elif trend_strength < 0.0015:
            regime = "RANGE"
        else:
            return None

        # -------- TREND MODE --------
        if regime == "TREND":

            recent_high = df["High"].rolling(12).max().iloc[-2]
            recent_low = df["Low"].rolling(12).min().iloc[-2]
            volume_avg = df["Volume"].rolling(20).mean().iloc[-2]

            volume_spike = latest["Volume"] > 1.3 * volume_avg

            body = abs(latest["Close"] - latest["Open"])
            candle_range = latest["High"] - latest["Low"]
            strong_candle = body > 0.4 * candle_range

            if (
                latest["EMA20"] > latest["EMA50"] and
                entry > recent_high and
                volume_spike and
                strong_candle
            ):
                sl = entry - atr
                tp = entry + 1.8 * (entry - sl)
                return {"symbol": symbol, "action": "BUY",
                        "entry": round(entry,2),
                        "sl": round(sl,2),
                        "tp": round(tp,2)}

            if (
                latest["EMA20"] < latest["EMA50"] and
                entry < recent_low and
                volume_spike and
                strong_candle
            ):
                sl = entry + atr
                tp = entry - 1.8 * (sl - entry)
                return {"symbol": symbol, "action": "SELL",
                        "entry": round(entry,2),
                        "sl": round(sl,2),
                        "tp": round(tp,2)}

        # -------- RANGE MODE --------
        if regime == "RANGE":

            if latest["RSI"] < 35:
                sl = entry - atr
                tp = entry + 1.3 * (entry - sl)
                return {"symbol": symbol, "action": "BUY",
                        "entry": round(entry,2),
                        "sl": round(sl,2),
                        "tp": round(tp,2)}

            if latest["RSI"] > 65:
                sl = entry + atr
                tp = entry - 1.3 * (sl - entry)
                return {"symbol": symbol, "action": "SELL",
                        "entry": round(entry,2),
                        "sl": round(sl,2),
                        "tp": round(tp,2)}

        return None

    except:
        return None


# ---------------------------
# MAIN
# ---------------------------
def main():

    ist = pytz.timezone("Asia/Kolkata")
    now = datetime.now(ist)
    time_now = now.strftime("%H:%M")

    if not ("09:30" <= time_now <= "14:45"):
        print("Outside trading window.")
        return

    symbols = load_stage1()
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

    if not signals:
        print("No new signals.")
        return

    save_signals(signals)

    message = f"🚨 <b>INTRADAY SIGNALS</b> | {time_now}\n\n"

    for s in signals:
        message += (
            f"{'🟢' if s['action']=='BUY' else '🔴'} {s['symbol']}\n"
            f"Entry: {s['entry']} | SL: {s['sl']} | Target: {s['tp']}\n\n"
        )

    send_alert(message)


if __name__ == "__main__":
    main()