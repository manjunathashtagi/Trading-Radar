import sys
import os
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


# -----------------------------
# Load Stage-1 Watchlist
# -----------------------------
def load_stage1():

    if not os.path.exists(CACHE_FILE):
        return []

    df = pd.read_csv(CACHE_FILE)

    if "symbol" in df.columns:
        return df["symbol"].tolist()

    return df.iloc[:,0].tolist()


# -----------------------------
# Prevent Duplicate Alerts
# -----------------------------
def load_alerted():

    if not os.path.exists(ALERT_LOG_FILE):
        return set()

    df = pd.read_csv(ALERT_LOG_FILE)

    if "date" in df.columns:
        today = datetime.now(pytz.timezone("Asia/Kolkata")).date()
        df = df[df["date"] == str(today)]

    return set(df["symbol"])
def save_alerted(symbol):

    df = pd.DataFrame([[symbol]], columns=["symbol"])

    if os.path.exists(ALERT_LOG_FILE):
        df.to_csv(ALERT_LOG_FILE, mode="a", header=False, index=False)
    else:
        df.to_csv(ALERT_LOG_FILE, index=False)


# -----------------------------
# Save Signals for EOD
# -----------------------------
def save_signals(signals):

    ist = pytz.timezone("Asia/Kolkata")
    now = datetime.now(ist)

    df = pd.DataFrame(signals)

    df["date"] = now.date()
    df["trigger_time"] = now.strftime("%H:%M:%S")
    df["result"] = ""

    cols = [
        "symbol","action","entry","sl","tp",
        "date","trigger_time","result"
    ]

    df = df[cols]

    if os.path.exists(SIGNALS_FILE):

        existing = pd.read_csv(SIGNALS_FILE)
        combined = pd.concat([existing, df], ignore_index=True)

        combined.to_csv(SIGNALS_FILE, index=False)

    else:
        df.to_csv(SIGNALS_FILE, index=False)


# -----------------------------
# Signal Logic
# -----------------------------
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
        prev = df.iloc[-2]

        entry = latest["Close"]
        atr = df["ATR"].iloc[-1]

        volume_avg = df["Volume"].rolling(20).mean().iloc[-2]
        volume_spike = latest["Volume"] > 1.2 * volume_avg


        # ---------------------------------
        # 1️⃣ Gap Continuation
        # ---------------------------------

        if (
            latest["EMA20"] > latest["EMA50"] and
            latest["RSI"] > 60 and
            entry > latest["EMA20"] and
            volume_spike
        ):

            sl = entry - atr
            tp = entry + 2 * (entry - sl)

            return {
                "symbol": symbol,
                "action": "BUY",
                "entry": round(entry,2),
                "sl": round(sl,2),
                "tp": round(tp,2)
            }


        # ---------------------------------
        # 2️⃣ Pullback Trend (LTFOODS style)
        # ---------------------------------

        if (
            latest["EMA20"] > latest["EMA50"] and
            latest["RSI"] > 55 and
            prev["Low"] <= prev["EMA20"] and
            latest["Close"] > prev["High"]
        ):

            sl = df["Low"].rolling(5).min().iloc[-1]
            risk = entry - sl
            tp = entry + 2 * risk

            return {
                "symbol": symbol,
                "action": "BUY",
                "entry": round(entry,2),
                "sl": round(sl,2),
                "tp": round(tp,2)
            }


        # ---------------------------------
        # 3️⃣ Breakout Expansion
        # ---------------------------------

        recent_high = df["High"].rolling(12).max().iloc[-2]
        recent_low = df["Low"].rolling(12).min().iloc[-2]

        if (
            latest["EMA20"] > latest["EMA50"] and
            entry > recent_high and
            volume_spike
        ):

            sl = entry - atr
            tp = entry + 1.8 * (entry - sl)

            return {
                "symbol": symbol,
                "action": "BUY",
                "entry": round(entry,2),
                "sl": round(sl,2),
                "tp": round(tp,2)
            }


        if (
            latest["EMA20"] < latest["EMA50"] and
            entry < recent_low and
            volume_spike
        ):

            sl = entry + atr
            tp = entry - 1.8 * (sl - entry)

            return {
                "symbol": symbol,
                "action": "SELL",
                "entry": round(entry,2),
                "sl": round(sl,2),
                "tp": round(tp,2)
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