import sys
import os
import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime
import pytz
from ta.momentum import RSIIndicator
from alerts.telegram_alerts import send_alert

CACHE_FILE = "data/stage1_cache.csv"
SIGNALS_FILE = "data/signals.csv"
ALERT_LOG_FILE = "data/alerted_today.csv"


def load_stage1_watchlist():
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

    columns = [
        "symbol","action","entry","sl","tp",
        "score","eta","date","trigger_time","result"
    ]

    df = df[columns]

    if os.path.exists(SIGNALS_FILE):
        existing = pd.read_csv(SIGNALS_FILE)
        pd.concat([existing,df],ignore_index=True).to_csv(SIGNALS_FILE,index=False)
    else:
        df.to_csv(SIGNALS_FILE,index=False)


def estimate_eta():
    return "1-2h"


# ------------------------------
# PRE BREAKOUT DETECTOR
# ------------------------------
def detect_pre_breakout(df):

    last5_range = df["High"].tail(5).max() - df["Low"].tail(5).min()
    last20_range = df["High"].tail(20).max() - df["Low"].tail(20).min()

    # volatility squeeze
    squeeze = last5_range < (0.45 * last20_range)

    # higher lows
    lows = df["Low"].tail(5).values
    higher_lows = lows[4] > lows[3] > lows[2]

    # near resistance
    resistance = df["High"].tail(20).max()
    close = df["Close"].iloc[-1]
    near_resistance = close > resistance * 0.985

    return squeeze and higher_lows and near_resistance


# ------------------------------
# ANALYZE SYMBOL
# ------------------------------
def analyze_symbol(symbol):

    try:

        ticker = yf.Ticker(symbol + ".NS")
        df = ticker.history(period="5d", interval="15m")

        if len(df) < 40:
            return None

        df["EMA20"] = df["Close"].ewm(span=20).mean()
        df["EMA50"] = df["Close"].ewm(span=50).mean()
        df["RSI"] = RSIIndicator(df["Close"], window=14).rsi()

        latest = df.iloc[-1]

        entry = latest["Close"]

        # PRE BREAKOUT
        if detect_pre_breakout(df) and 48 < latest["RSI"] < 60:

            sl = df["Low"].tail(5).min()
            risk = entry - sl
            tp = entry + 2*risk

            score = 65

            return {
                "symbol":symbol,
                "action":"BUY",
                "entry":round(entry,2),
                "sl":round(sl,2),
                "tp":round(tp,2),
                "score":score,
                "eta":estimate_eta()
            }

        return None

    except:
        return None


# ------------------------------
# MAIN
# ------------------------------
def main():

    ist = pytz.timezone("Asia/Kolkata")
    time_now = datetime.now(ist).strftime("%H:%M")

    if not ("09:30" <= time_now <= "15:30"):
        print("Outside market hours.")
        return

    symbols = load_stage1_watchlist()

    alerted = load_alerted()

    signals = []

    for symbol in symbols:

        signal = analyze_symbol(symbol)

        if signal and symbol not in alerted:
            signals.append(signal)
            save_alerted(symbol)

    if not signals:
        print("No signals")
        return

    signals = sorted(signals,key=lambda x:x["score"],reverse=True)[:27]

    save_signals(signals)

    message = f"🚨 <b>PRE-BREAKOUT RADAR</b> | {time_now}\n\n"

    for s in signals:
        message += (
            f"{s['symbol']} | Score {s['score']}\n"
            f"Entry {s['entry']} | SL {s['sl']} | Target {s['tp']}\n"
            f"ETA {s['eta']}\n\n"
        )

    send_alert(message)


if __name__ == "__main__":
    main()