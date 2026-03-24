import yfinance as yf
import pandas as pd
import numpy as np
import os
import requests
import joblib
import time
import warnings
import logging

# 🔥 COMPLETE SILENCE
warnings.filterwarnings("ignore")
logging.getLogger("yfinance").setLevel(logging.CRITICAL)

# ================= CONFIG =================
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
MODEL_FILE = "model.pkl"

STOCKS = [
    "RELIANCE","TCS","INFY","HDFCBANK","ICICIBANK","SBIN","ITC",
    "LT","AXISBANK","KOTAKBANK","BHARTIARTL","MARUTI",
    "TATASTEEL","JSWSTEEL","HINDALCO","ADANIENT",
    "TATAMOTORS","INDIGO","ZOMATO"
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

# ================= SAFE DOWNLOAD (ULTIMATE FIX) =================
def fetch_data(ticker):
    try:
        # METHOD 1
        df = yf.download(
            ticker,
            period="5d",
            interval="15m",
            progress=False,
            threads=False
        )
        if df is not None and not df.empty:
            return df
    except:
        pass

    try:
        # METHOD 2 (fallback - different API)
        df = yf.Ticker(ticker).history(period="5d", interval="15m")
        if df is not None and not df.empty:
            return df
    except:
        pass

    return None


def safe_download(symbol):
    tickers = [symbol + ".NS", symbol] if not symbol.startswith("^") else [symbol]

    for ticker in tickers:
        for _ in range(2):
            df = fetch_data(ticker)

            if df is not None and not df.empty:
                df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]

                for col in ["Open","High","Low","Close","Volume"]:
                    if col in df.columns:
                        df[col] = pd.to_numeric(df[col], errors="coerce")

                df.dropna(inplace=True)
                return df

            time.sleep(1)

    return None  # silent fail

# ================= MARKET =================
def market_return():
    df = safe_download("^NSEI")

    if df is None or len(df) < 5:
        return 0

    return (df["Close"].iloc[-1] - df["Open"].iloc[0]) / df["Open"].iloc[0]

# ================= FEATURES =================
def features(df):
    df["ret"] = df["Close"].pct_change()
    df["vol_ratio"] = df["Volume"] / df["Volume"].rolling(20).mean()
    df["momentum"] = df["Close"] - df["Close"].shift(5)
    return df.dropna()

# ================= SIGNAL =================
def generate_signal(stock, model, mkt_ret):
    df = safe_download(stock)

    if df is None or len(df) < 30:
        return None

    df = features(df)
    latest = df.iloc[-1]

    stock_ret = (df["Close"].iloc[-1] - df["Open"].iloc[0]) / df["Open"].iloc[0]

    score = 50

    if stock_ret > mkt_ret:
        score += 15

    if latest["vol_ratio"] > 1.8:
        score += 15

    if latest["momentum"] > 0:
        score += 10

    if model:
        X = pd.DataFrame(
            [[latest["ret"], latest["vol_ratio"], latest["momentum"]]],
            columns=["ret","vol_ratio","momentum"]
        )
        score += model.predict_proba(X)[0][1] * 20

    if score < 65:
        return None

    price = latest["Close"]

    return {
        "stock": stock,
        "score": round(score,1),
        "entry": round(price,2),
        "sl": round(price * 0.98,2),
        "tp": round(price * 1.05,2)
    }

# ================= MAIN =================
def main():
    model = joblib.load(MODEL_FILE) if os.path.exists(MODEL_FILE) else None

    mkt_ret = market_return()

    trend = "BULLISH" if mkt_ret > 0 else "BEARISH" if mkt_ret < 0 else "NEUTRAL"

    print(f"Market: {trend}")

    results = []

    for stock in STOCKS:
        sig = generate_signal(stock, model, mkt_ret)

        if sig:
            results.append(sig)

        time.sleep(0.6)  # safer delay

    if not results:
        send(f"⚠️ Market {trend} - No strong signals")
        return

    msg = f"🚀 SMART MONEY SIGNALS\nMarket: {trend}\n\n"

    for r in results[:5]:
        msg += (
            f"{r['stock']} ({r['score']})\n"
            f"Entry: {r['entry']} | SL: {r['sl']} | TP: {r['tp']}\n\n"
        )

    if trend == "BEARISH":
        msg += "\n⚠️ Market Bearish - Trade Carefully"

    send(msg)

if __name__ == "__main__":
    main()