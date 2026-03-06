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


# ---------------------------------------------------
# Load Stage-1 watchlist
# ---------------------------------------------------
def load_stage1():

    if not os.path.exists(CACHE_FILE):
        return []

    df = pd.read_csv(CACHE_FILE)

    if "symbol" in df.columns:
        return df["symbol"].tolist()

    return df.iloc[:, 0].tolist()


# ---------------------------------------------------
# Prevent duplicate alerts
# ---------------------------------------------------
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


# ---------------------------------------------------
# Save signals
# ---------------------------------------------------
def save_signals(signals):

    ist = pytz.timezone("Asia/Kolkata")
    now = datetime.now(ist)

    df = pd.DataFrame(signals)

    df["date"] = now.date()
    df["trigger_time"] = now.strftime("%H:%M:%S")
    df["result"] = ""

    cols = ["symbol", "action", "entry", "sl", "tp", "date", "trigger_time", "result"]
    df = df[cols]

    if os.path.exists(SIGNALS_FILE):

        existing = pd.read_csv(SIGNALS_FILE)
        combined = pd.concat([existing, df], ignore_index=True)
        combined.to_csv(SIGNALS_FILE, index=False)

    else:

        df.to_csv(SIGNALS_FILE, index=False)


# ---------------------------------------------------
# Momentum scoring
# ---------------------------------------------------
def score_symbol(symbol):

    try:

        df = yf.download(
            symbol + ".NS",
            period="3d",
            interval="15m",
            progress=False
        )

        if len(df) < 30:
            return 0

        df["EMA20"] = df["Close"].ewm(span=20).mean()
        df["EMA50"] = df["Close"].ewm(span=50).mean()
        df["RSI"] = RSIIndicator(df["Close"], window=14).rsi()

        latest = df.iloc[-1]

        score = 0

        # Trend
        if latest["EMA20"] > latest["EMA50"]:
            score += 30

        # RSI strength
        if latest["RSI"] > 52:
            score += 20

        # price acceleration
        pct_move = ((latest["Close"] - df["Close"].iloc[-8]) /
                    df["Close"].iloc[-8]) * 100

        if pct_move > 1.2:
            score += 20

        # volume
        vol_avg = df["Volume"].rolling(20).mean().iloc[-1]

        if latest["Volume"] > 1.05 * vol_avg:
            score += 20

        # near breakout
        recent_high = df["High"].rolling(12).max().iloc[-2]

        if latest["Close"] > recent_high * 0.97:
            score += 10

        return score

    except:
        return 0


# ---------------------------------------------------
# Rank stocks
# ---------------------------------------------------
def rank_symbols(symbols):

    scores = []

    for symbol in symbols:

        s = score_symbol(symbol)
        scores.append((symbol, s))

    ranked = sorted(scores, key=lambda x: x[1], reverse=True)

    return [x[0] for x in ranked[:80]]


# ---------------------------------------------------
# Signal detection
# ---------------------------------------------------
def analyze_symbol(symbol):

    try:

        df = yf.download(
            symbol + ".NS",
            period="5d",
            interval="15m",
            progress=False
        )

        if len(df) < 40:
            return None

        df["EMA20"] = df["Close"].ewm(span=20).mean()
        df["EMA50"] = df["Close"].ewm(span=50).mean()
        df["RSI"] = RSIIndicator(df["Close"], window=14).rsi()

        df["ATR"] = (df["High"] - df["Low"]).rolling(14).mean()

        latest = df.iloc[-1]
        prev = df.iloc[-2]

        entry = latest["Close"]
        atr = df["ATR"].iloc[-1]

        vol_avg = df["Volume"].rolling(20).mean().iloc[-1]

        volume_spike = latest["Volume"] > 1.05 * vol_avg

        # BUY breakout
        if (
            latest["EMA20"] > latest["EMA50"] and
            latest["RSI"] > 52 and
            volume_spike and
            entry > prev["High"]
        ):

            sl = entry - atr
            tp = entry + 2 * (entry - sl)

            return {
                "symbol": symbol,
                "action": "BUY",
                "entry": round(entry, 2),
                "sl": round(sl, 2),
                "tp": round(tp, 2)
            }

        # SELL breakdown
        if (
            latest["EMA20"] < latest["EMA50"] and
            latest["RSI"] < 48 and
            volume_spike and
            entry < prev["Low"]
        ):

            sl = entry + atr
            tp = entry - 2 * (sl - entry)

            return {
                "symbol": symbol,
                "action": "SELL",
                "entry": round(entry, 2),
                "sl": round(sl, 2),
                "tp": round(tp, 2)
            }

        return None

    except:
        return None


# ---------------------------------------------------
# MAIN
# ---------------------------------------------------
def main():

    ist = pytz.timezone("Asia/Kolkata")
    now = datetime.now(ist)

    current_time = now.strftime("%H:%M")

    if not ("09:30" <= current_time <= "15:00"):
        print("Outside trading window.")
        return

    symbols = load_stage1()

    if not symbols:
        print("No Stage-1 stocks.")
        return

    print(f"Stage-1 stocks: {len(symbols)}")

    symbols = rank_symbols(symbols)

    print(f"Scanning top momentum stocks: {len(symbols)}")

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

    save_signals(signals)

    message = f"🚨 <b>INTRADAY SIGNALS</b> | {current_time}\n\n"

    for s in signals:

        message += (
            f"{'🟢' if s['action']=='BUY' else '🔴'} {s['symbol']}\n"
            f"Entry: {s['entry']} | SL: {s['sl']} | Target: {s['tp']}\n\n"
        )

    send_alert(message)


if __name__ == "__main__":
    main()