import yfinance as yf
import pandas as pd
import numpy as np
import os
import requests
import joblib

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

# ================= FETCH =================
def fetch(symbol):
    ticker = symbol if symbol.startswith("^") else symbol + ".NS"
    try:
        df = yf.download(ticker, period="5d", interval="15m")
        if df.empty:
            return df

        df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]
        df = df.apply(pd.to_numeric, errors="coerce")
        df.dropna(inplace=True)
        return df
    except:
        return pd.DataFrame()

# ================= MARKET =================
def market_return():
    df = fetch("^NSEI")
    if df.empty:
        return 0
    return (df["Close"].iloc[-1] - df["Open"].iloc[0]) / df["Open"].iloc[0]

# ================= FEATURES =================
def features(df):
    df["ret"] = df["Close"].pct_change()
    df["vol_ratio"] = df["Volume"] / df["Volume"].rolling(20).mean()
    df["momentum"] = df["Close"] - df["Close"].shift(5)
    return df.dropna()

# ================= SIGNAL =================
def signal(stock, model, mkt_ret):
    df = fetch(stock)
    if df.empty or len(df) < 30:
        return None

    df = features(df)
    latest = df.iloc[-1]

    stock_ret = (df["Close"].iloc[-1] - df["Open"].iloc[0]) / df["Open"].iloc[0]

    score = 50

    # RELATIVE STRENGTH (🔥 KEY FIX)
    if stock_ret > mkt_ret:
        score += 15

    # VOLUME BURST
    if latest["vol_ratio"] > 1.8:
        score += 15

    # MOMENTUM
    if latest["momentum"] > 0:
        score += 10

    # AI
    if model:
        X = pd.DataFrame([[latest["ret"], latest["vol_ratio"], latest["momentum"]]],
                         columns=["ret","vol_ratio","momentum"])
        score += model.predict_proba(X)[0][1] * 20

    if score < 65:
        return None

    price = latest["Close"]

    return {
        "stock": stock,
        "score": round(score,1),
        "entry": round(price,2),
        "sl": round(price*0.98,2),
        "tp": round(price*1.05,2)
    }

# ================= MAIN =================
def main():
    model = joblib.load(MODEL_FILE) if os.path.exists(MODEL_FILE) else None

    mkt_ret = market_return()
    trend = "BULLISH" if mkt_ret > 0 else "BEARISH"

    print(f"Market: {trend}")

    results = []

    for s in STOCKS:
        sig = signal(s, model, mkt_ret)
        if sig:
            results.append(sig)

    if not results:
        send(f"⚠️ Market {trend} - No strong signals")
        return

    msg = f"🚀 SMART MONEY SIGNALS\nMarket: {trend}\n\n"

    for r in results[:5]:
        msg += f"{r['stock']} ({r['score']})\n"
        msg += f"Entry: {r['entry']} | SL: {r['sl']} | TP: {r['tp']}\n\n"

    send(msg)

if __name__ == "__main__":
    main()