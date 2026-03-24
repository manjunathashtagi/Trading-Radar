import yfinance as yf
import pandas as pd
import numpy as np
import os
import requests
import time
import warnings
import logging
from datetime import datetime

# ================= SILENCE =================
warnings.filterwarnings("ignore")
logging.getLogger("yfinance").setLevel(logging.CRITICAL)

# ================= CONFIG =================
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

STOCKS = [
    "RELIANCE","TCS","INFY","HDFCBANK","ICICIBANK","SBIN","ITC",
    "LT","AXISBANK","KOTAKBANK","BHARTIARTL","MARUTI",
    "TATASTEEL","JSWSTEEL","HINDALCO","ADANIENT",
    "TATAMOTORS","INDIGO","ZOMATO","SHRIRAMFIN"
]

# ================= TELEGRAM =================
def send(msg):
    try:
        requests.post(
            f"https://api.telegram.org/bot{TOKEN}/sendMessage",
            data={"chat_id": CHAT_ID, "text": msg}
        )
    except:
        pass

# ================= DATA FETCH =================
def fetch(symbol):
    try:
        df = yf.download(
            symbol + ".NS",
            period="1d",
            interval="5m",
            progress=False,
            threads=False
        )
        if df is not None and not df.empty:
            df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]
            return df
    except:
        pass
    return None

# ================= OPENING BLAST LOGIC =================
def opening_blast(stock):
    df = fetch(stock)

    if df is None or len(df) < 5:
        return None

    df = df.copy()

    # First 15 min candle
    first_15 = df.iloc[:3]

    open_price = first_15["Open"].iloc[0]
    high_15 = first_15["High"].max()
    vol_15 = first_15["Volume"].sum()

    # Latest candle
    latest = df.iloc[-1]
    current_price = latest["Close"]

    # Avg volume
    avg_vol = df["Volume"].rolling(20).mean().iloc[-1]

    # ================= CONDITIONS =================

    # 🔥 1. Breakout above first 15 min high
    breakout = current_price > high_15

    # 🔥 2. Volume explosion
    vol_spike = vol_15 > (avg_vol * 2)

    # 🔥 3. Price strength
    strength = (current_price - open_price) / open_price

    # 🔥 SCORE
    score = 0

    if breakout:
        score += 40

    if vol_spike:
        score += 30

    if strength > 0.01:
        score += 20

    if strength > 0.02:
        score += 10

    if score < 60:
        return None

    return {
        "stock": stock,
        "score": score,
        "entry": round(current_price,2),
        "sl": round(open_price * 0.98,2),
        "tp": round(current_price * 1.04,2)
    }

# ================= MARKET TREND (LIGHT FILTER) =================
def market_trend():
    try:
        df = yf.download("^NSEI", period="1d", interval="5m", progress=False)
        if df is None or df.empty:
            return "NEUTRAL"

        open_price = df["Open"].iloc[0]
        current = df["Close"].iloc[-1]

        change = (current - open_price) / open_price

        if change > 0.003:
            return "BULLISH"
        elif change < -0.003:
            return "BEARISH"
        else:
            return "NEUTRAL"
    except:
        return "NEUTRAL"

# ================= MAIN =================
def main():
    trend = market_trend()
    print("Market:", trend)

    results = []

    for stock in STOCKS:
        try:
            sig = opening_blast(stock)

            if sig:
                results.append(sig)

            time.sleep(0.5)
        except:
            continue

    if not results:
        send(f"⚠️ No Opening Blast Signals\nMarket: {trend}")
        return

    # Sort best first
    results = sorted(results, key=lambda x: x["score"], reverse=True)

    msg = f"🚀 OPENING BLAST SIGNALS\nMarket: {trend}\n\n"

    for r in results[:5]:
        msg += (
            f"{r['stock']} ({r['score']})\n"
            f"Entry: {r['entry']} | SL: {r['sl']} | TP: {r['tp']}\n\n"
        )

    msg += "\n⏰ Ideal Entry: 9:20–10:15"

    send(msg)

# ================= RUN =================
if __name__ == "__main__":
    main()