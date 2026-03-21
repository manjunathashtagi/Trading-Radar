import yfinance as yf
import pandas as pd
import numpy as np
import requests
import joblib
import os
from datetime import datetime

# ================= CONFIG =================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
MODEL_FILE = "model.pkl"

# ================= TELEGRAM =================
def send_telegram(msg):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        requests.post(url, data={"chat_id": CHAT_ID, "text": msg})
    except:
        pass

# ================= LOAD MODEL =================
model = None
if os.path.exists(MODEL_FILE):
    model = joblib.load(MODEL_FILE)
    print("✅ AI model loaded")
else:
    print("⚠️ No model found")

# ================= SECTOR MAP =================
SECTORS = {
    "STEEL": ["JSWSTEEL.NS", "TATASTEEL.NS", "JINDALSTEL.NS"],
    "BANK": ["SBIN.NS", "BANKBARODA.NS", "UNIONBANK.NS"],
    "IT": ["TCS.NS", "INFY.NS", "TECHM.NS"],
    "PHARMA": ["SUNPHARMA.NS", "LUPIN.NS"],
    "TELECOM": ["IDEA.NS", "BHARTIARTL.NS"]
}

# ================= INDICATORS =================
def add_indicators(df):
    df["EMA20"] = df["Close"].ewm(span=20).mean()
    df["EMA50"] = df["Close"].ewm(span=50).mean()

    delta = df["Close"].diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / loss
    df["RSI"] = 100 - (100 / (1 + rs))

    return df

# ================= SECTOR STRENGTH =================
def get_strong_sectors():
    strong = []

    for sector, stocks in SECTORS.items():
        changes = []

        for s in stocks:
            try:
                df = yf.download(s, period="1d", interval="15m", progress=False)
                if df.empty:
                    continue

                change = (df["Close"].iloc[-1] - df["Open"].iloc[0]) / df["Open"].iloc[0]
                changes.append(change)
            except:
                continue

        if len(changes) > 0:
            avg = sum(changes) / len(changes)
            if avg > 0.015:
                strong.append(sector)

    return strong

# ================= SCAN =================
def run_scan():
    print("Running scan...")

    strong_sectors = get_strong_sectors()

    if strong_sectors:
        send_telegram(f"🔥 STRONG SECTORS: {', '.join(strong_sectors)}")

    symbols = []
    for s in strong_sectors:
        symbols.extend(SECTORS[s])

    if not symbols:
        print("No strong sectors")
        return

    signals = []

    for symbol in symbols:
        try:
            df = yf.download(symbol, period="5d", interval="15m", progress=False)
            if df.empty:
                continue

            # flatten columns
            df.columns = [col[0] if isinstance(col, tuple) else col for col in df.columns]

            df = add_indicators(df)

            latest = df.iloc[-1]

            # breakout
            breakout = latest["Close"] > df["High"].rolling(20).max().iloc[-2]
            if not breakout:
                continue

            # volume
            if latest["Volume"] < df["Volume"].rolling(20).mean().iloc[-1] * 1.5:
                continue

            volatility = df["Close"].pct_change().std()
            distance_high = (latest["Close"] - df["High"].max()) / df["High"].max()

            # AI features (FIXED)
            features = pd.DataFrame([{
                "RSI": latest["RSI"],
                "EMA20": latest["EMA20"],
                "EMA50": latest["EMA50"],
                "volatility": volatility,
                "distance_high": distance_high
            }])

            score = 60
            if model:
                score = model.predict_proba(features)[0][1] * 100

            if score < 65:
                continue

            entry = latest["Close"]
            sl = entry * 0.98
            tp = entry * 1.04

            msg = f"""
🚨 SIGNAL: {symbol}
Score: {round(score,1)}

Entry: {round(entry,2)}
SL: {round(sl,2)}
TP: {round(tp,2)}
"""

            send_telegram(msg)

            signals.append({
                "symbol": symbol,
                "entry": entry,
                "sl": sl,
                "tp": tp,
                "score": score,
                "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            })

        except Exception as e:
            print("Error:", symbol, e)

    # save signals
    if signals:
        file_path = "data/signals.csv"

        if os.path.exists(file_path):
            old = pd.read_csv(file_path)
            new = pd.DataFrame(signals)
            combined = pd.concat([old, new])
        else:
            combined = pd.DataFrame(signals)

        combined.to_csv(file_path, index=False)

# ================= EOD =================
def generate_eod():
    file_path = "data/signals.csv"

    if not os.path.exists(file_path):
        send_telegram("⚠️ No trades today")
        return

    df = pd.read_csv(file_path)

    today = datetime.now().strftime("%Y-%m-%d")
    df_today = df[df["time"].str.contains(today)]

    if df_today.empty:
        send_telegram("⚠️ No trades today")
        return

    wins = 0
    losses = 0

    for _, row in df_today.iterrows():
        symbol = row["symbol"]
        entry = row["entry"]
        sl = row["sl"]
        tp = row["tp"]

        df_price = yf.download(symbol, period="1d", interval="5m", progress=False)

        if df_price.empty:
            continue

        if df_price["High"].max() >= tp:
            wins += 1
        elif df_price["Low"].min() <= sl:
            losses += 1

    total = wins + losses

    msg = f"""
📊 EOD REPORT

Total Trades: {total}
Wins: {wins}
Losses: {losses}
Accuracy: {round((wins/total)*100,2) if total>0 else 0}%
"""

    send_telegram(msg)

# ================= MAIN =================
if __name__ == "__main__":
    now = datetime.now().hour

    if now < 15:
        run_scan()
    else:
        generate_eod()