import yfinance as yf
import pandas as pd
import numpy as np
import os
import requests
import joblib
from datetime import datetime

# ================= CONFIG =================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

DATA_PATH = "data"
MODEL_FILE = f"{DATA_PATH}/ai_model.pkl"
SIGNALS_FILE = f"{DATA_PATH}/signals.csv"

# ================= TELEGRAM =================
def send_telegram(msg):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": msg})
    except:
        pass

# ================= FETCH =================
def fetch(symbol):
    try:
        if symbol.startswith("^"):
            ticker = symbol
        else:
            ticker = symbol + ".NS"

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
def market_trend():
    df = fetch("^NSEI")

    if df.empty:
        return "NEUTRAL"

    try:
        open_price = float(df["Open"].iloc[0])
        close_price = float(df["Close"].iloc[-1])

        if close_price > open_price * 1.003:
            return "BULLISH"
        elif close_price < open_price * 0.997:
            return "BEARISH"
        else:
            return "NEUTRAL"
    except:
        return "NEUTRAL"

# ================= SECTOR =================
def get_sector(symbol):
    try:
        sector_map = pd.read_csv(f"{DATA_PATH}/sector_map.csv")
        row = sector_map[sector_map["Symbol"] == symbol]
        if not row.empty:
            return row.iloc[0]["Sector"]
    except:
        pass
    return "UNKNOWN"

def sector_strength():
    try:
        df = pd.read_csv(SIGNALS_FILE)

        if df.empty:
            return []

        sector_perf = df.groupby("sector")["score"].mean()
        strong = sector_perf[sector_perf > 60].index.tolist()

        return strong
    except:
        return []

# ================= FEATURES =================
def calculate_features(df):
    df["returns"] = df["Close"].pct_change()
    df["vol_avg"] = df["Volume"].rolling(10).mean()

    return df

# ================= SIGNAL =================
def generate_signal(symbol, model, strong_sectors):
    df = fetch(symbol)

    if df.empty or len(df) < 20:
        return None

    df = calculate_features(df)

    latest = df.iloc[-1]

    volume_spike = latest["Volume"] > latest["vol_avg"] * 1.5
    breakout = latest["Close"] > df["High"].rolling(20).max().iloc[-2]

    sector = get_sector(symbol)

    score = 0

    if volume_spike:
        score += 20
    if breakout:
        score += 25
    if sector in strong_sectors:
        score += 15

    # AI boost
    try:
        features = np.array([[latest["returns"], latest["Volume"]]])
        ai_pred = model.predict(features)[0]

        if ai_pred == 1:
            score += 25
    except:
        pass

    if score < 60:
        return None

    entry = latest["Close"]
    sl = entry * 0.98
    tp = entry * 1.04

    return {
        "symbol": symbol,
        "score": round(score, 1),
        "entry": round(entry, 2),
        "sl": round(sl, 2),
        "tp": round(tp, 2),
        "sector": sector
    }

# ================= MAIN =================
def run_scan():
    print("Running scan...")

    trend = market_trend()
    strong_sectors = sector_strength()

    print("Market:", trend)
    print("Strong sectors:", strong_sectors)

    # Load AI
    if os.path.exists(MODEL_FILE):
        model = joblib.load(MODEL_FILE)
        print("✅ AI model loaded")
    else:
        model = None
        print("⚠️ No AI model")

    symbols = [
        "RELIANCE","TCS","INFY","HDFCBANK","ICICIBANK",
        "SBIN","ITC","LT","AXISBANK","KOTAKBANK",
        "TATASTEEL","JSWSTEEL","HINDALCO","ADANIENT",
        "BHARTIARTL","MARUTI","M&M","SUNPHARMA"
    ]

    signals = []

    for symbol in symbols:
        sig = generate_signal(symbol, model, strong_sectors)

        if sig:
            signals.append(sig)

    if not signals:
        print("No signals")
        return

    df = pd.DataFrame(signals)
    df.to_csv(SIGNALS_FILE, index=False)

    msg = "🚨 EARLY MOMENTUM SIGNALS\n"
    msg += f"Market: {trend}\n\n"

    for s in signals:
        msg += f"{s['symbol']} ({s['score']})\n"
        msg += f"Entry: {s['entry']} | SL: {s['sl']} | TP: {s['tp']}\n\n"

    send_telegram(msg)

# ================= RUN =================
def main():
    run_scan()

if __name__ == "__main__":
    main()