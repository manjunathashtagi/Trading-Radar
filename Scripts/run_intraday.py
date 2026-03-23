import yfinance as yf
import pandas as pd
import numpy as np
import requests
import os
import joblib

# ================= CONFIG =================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

MODEL_FILE = "model.pkl"

STOCKS = [
    "RELIANCE", "TCS", "INFY", "HDFCBANK", "ICICIBANK",
    "SBIN", "LT", "ITC", "BHARTIARTL", "ASIANPAINT",
    "AXISBANK", "KOTAKBANK", "MARUTI", "SUNPHARMA",
    "TITAN", "ULTRACEMCO", "WIPRO", "NESTLEIND"
]

# ================= TELEGRAM =================
def send_telegram(msg):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        requests.post(url, data={"chat_id": CHAT_ID, "text": msg})
    except:
        pass

# ================= DATA =================
def fetch_data(symbol):
    df = yf.download(symbol + ".NS", period="5d", interval="15m")

    if df.empty:
        return df

    # 🔥 flatten columns
    df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]

    # 🔥 ensure numeric
    for col in ["Open", "High", "Low", "Close", "Volume"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    df.dropna(inplace=True)
    return df

# ================= MARKET TREND =================
def market_trend():
    df = yf.download("^NSEI", period="1d", interval="15m")

    if df.empty:
        return "NEUTRAL"

    # 🔥 fix
    df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]

    df["Open"] = pd.to_numeric(df["Open"], errors="coerce")
    df["Close"] = pd.to_numeric(df["Close"], errors="coerce")

    df.dropna(inplace=True)

    if df.empty:
        return "NEUTRAL"

    open_price = float(df["Open"].iloc[0])
    close_price = float(df["Close"].iloc[-1])

    if close_price > open_price:
        return "BULLISH"
    else:
        return "BEARISH"

# ================= FEATURES =================
def add_features(df):
    df["EMA20"] = df["Close"].ewm(span=20).mean()
    df["EMA50"] = df["Close"].ewm(span=50).mean()

    df["RSI"] = 100 - (100 / (1 + (
        df["Close"].diff().clip(lower=0).rolling(14).mean() /
        df["Close"].diff().clip(upper=0).abs().rolling(14).mean()
    )))

    df["VOL_SPIKE"] = df["Volume"] / df["Volume"].rolling(20).mean()

    df.dropna(inplace=True)
    return df

# ================= SMART MONEY =================
def smart_money_score(df):
    latest = df.iloc[-1]

    score = 0

    if latest["VOL_SPIKE"] > 1.5:
        score += 1

    if latest["Close"] > latest["EMA20"]:
        score += 1

    if latest["EMA20"] > latest["EMA50"]:
        score += 1

    return score

# ================= SIGNAL =================
def generate_signal(symbol, df, trend):
    df = add_features(df)

    if df.empty:
        return None

    latest = df.iloc[-1]

    score = 0

    # Trend alignment
    if trend == "BULLISH" and latest["Close"] > latest["EMA20"]:
        score += 1

    if trend == "BEARISH" and latest["Close"] < latest["EMA20"]:
        score += 1

    # RSI
    if 50 < latest["RSI"] < 70:
        score += 1

    # Volume
    if latest["VOL_SPIKE"] > 1.3:
        score += 1

    # Smart money
    score += smart_money_score(df)

    confidence = round((score / 5) * 100, 1)

    if confidence < 60:
        return None

    entry = float(latest["Close"])
    sl = round(entry * 0.98, 2)
    tp = round(entry * 1.04, 2)

    return {
        "symbol": symbol,
        "confidence": confidence,
        "entry": entry,
        "sl": sl,
        "tp": tp
    }

# ================= MAIN SCAN =================
def run_scan():
    trend = market_trend()

    print(f"Market: {trend}")

    signals = []

    for stock in STOCKS:
        df = fetch_data(stock)

        if df.empty:
            continue

        signal = generate_signal(stock, df, trend)

        if signal:
            signals.append(signal)

    if not signals:
        send_telegram(f"⚠️ Market: {trend}\nNo strong signals found")
        return

    msg = f"🚨 EARLY MOMENTUM SIGNALS\nMarket: {trend}\n\n"

    for s in signals:
        msg += (
            f"{s['symbol']} ({s['confidence']})\n"
            f"Entry: {s['entry']} | SL: {s['sl']} | TP: {s['tp']}\n\n"
        )

    send_telegram(msg)

# ================= MAIN =================
def main():
    run_scan()

if __name__ == "__main__":
    main()