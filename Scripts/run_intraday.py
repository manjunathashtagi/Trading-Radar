import yfinance as yf
import pandas as pd
import numpy as np
import os
import requests
import joblib
from datetime import datetime

# ================= CONFIG =================
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

MODEL_FILE = "model.pkl"

STOCKS = [
    "RELIANCE","TCS","INFY","HDFCBANK","ICICIBANK","SBIN","ITC","LT",
    "AXISBANK","KOTAKBANK","BHARTIARTL","ASIANPAINT","MARUTI","HCLTECH",
    "WIPRO","ULTRACEMCO","TITAN","BAJFINANCE","NESTLEIND","POWERGRID",
    "NTPC","ONGC","ADANIENT","ADANIPORTS","JSWSTEEL","TATASTEEL",
    "HINDALCO","COALINDIA","DRREDDY","SUNPHARMA","CIPLA","DIVISLAB"
]

SECTOR_MAP = {
    "INFY":"IT","TCS":"IT","HCLTECH":"IT","WIPRO":"IT",
    "RELIANCE":"ENERGY","ONGC":"ENERGY","COALINDIA":"ENERGY",
    "ICICIBANK":"BANK","HDFCBANK":"BANK","SBIN":"BANK","AXISBANK":"BANK",
    "SUNPHARMA":"PHARMA","DRREDDY":"PHARMA","CIPLA":"PHARMA",
}

# ================= TELEGRAM =================
def send_telegram(msg):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": msg})
    except:
        pass

# ================= FETCH =================
def fetch(symbol):
    try:
        ticker = symbol if symbol.startswith("^") else symbol + ".NS"

        df = yf.download(ticker, period="5d", interval="15m")

        if df.empty:
            return df

        df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]

        for col in ["Open", "High", "Low", "Close", "Volume"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")

        df.dropna(inplace=True)
        return df

    except Exception as e:
        print(f"Fetch error {symbol}: {e}")
        return pd.DataFrame()

# ================= FEATURES =================
def add_features(df):
    df["ret"] = df["Close"].pct_change()
    df["vol_spike"] = df["Volume"] / df["Volume"].rolling(20).mean()
    df["ma20"] = df["Close"].rolling(20).mean()
    df["ma50"] = df["Close"].rolling(50).mean()
    df["momentum"] = df["Close"] - df["Close"].shift(10)
    return df.dropna()

# ================= MARKET TREND =================
def market_trend():
    df = fetch("^NSEI")

    if df.empty:
        return "NEUTRAL", "NEUTRAL"

    close = df["Close"].iloc[-1]
    open_ = df["Open"].iloc[0]

    if close > open_:
        return "BULLISH", "LONG"
    elif close < open_:
        return "BEARISH", "SHORT"
    else:
        return "NEUTRAL", "NEUTRAL"

# ================= SECTOR STRENGTH =================
def sector_strength():
    scores = {}

    for stock in STOCKS:
        sector = SECTOR_MAP.get(stock)
        if not sector:
            continue

        df = fetch(stock)
        if df.empty:
            continue

        change = (df["Close"].iloc[-1] - df["Close"].iloc[-5]) / df["Close"].iloc[-5]

        scores.setdefault(sector, []).append(change)

    strong = []
    for sector, vals in scores.items():
        if np.mean(vals) > 0:
            strong.append(sector)

    return strong

# ================= AI MODEL =================
def load_model():
    if os.path.exists(MODEL_FILE):
        model = joblib.load(MODEL_FILE)
        print("✅ AI model loaded")
        return model
    return None

# ================= SIGNAL =================
def generate_signal(stock, df, model, market_bias, strong_sectors):
    df = add_features(df)

    if df.empty:
        return None

    latest = df.iloc[-1]

    features = pd.DataFrame([[
        latest["ret"],
        latest["vol_spike"],
        latest["momentum"]
    ]], columns=["ret","vol_spike","momentum"])

    score = 50

    if model:
        score = model.predict_proba(features)[0][1] * 100

    # Boost logic
    if SECTOR_MAP.get(stock) in strong_sectors:
        score += 5

    if market_bias == "LONG":
        score += 5
    elif market_bias == "SHORT":
        score -= 5

    # Smart money (volume spike)
    if latest["vol_spike"] > 1.5:
        score += 5

    if score < 60:
        return None

    entry = latest["Close"]
    sl = entry * 0.98
    tp = entry * 1.04

    return {
        "stock": stock,
        "score": round(score,1),
        "entry": round(entry,2),
        "sl": round(sl,2),
        "tp": round(tp,2)
    }

# ================= MAIN SCAN =================
def run_scan():
    model = load_model()

    trend, bias = market_trend()
    sectors = sector_strength()

    print(f"Market: {trend}, Bias: {bias}, Strong sectors: {sectors}")

    signals = []

    for stock in STOCKS:
        df = fetch(stock)
        if df.empty:
            continue

        sig = generate_signal(stock, df, model, bias, sectors)
        if sig:
            signals.append(sig)

    if not signals:
        send_telegram(f"⚠️ Market {trend} - No strong signals")
        print("No signals")
        return

    msg = f"🚨 SIGNALS\nMarket: {trend}\n\n"

    for s in signals[:5]:
        msg += (
            f"{s['stock']} ({s['score']})\n"
            f"Entry: {s['entry']} | SL: {s['sl']} | TP: {s['tp']}\n\n"
        )

    send_telegram(msg)

# ================= MAIN =================
def main():
    run_scan()

if __name__ == "__main__":
    main()