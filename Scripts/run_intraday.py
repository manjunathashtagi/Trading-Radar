import yfinance as yf
import pandas as pd
import os
import requests
import time
from datetime import datetime

# ================= CONFIG =================
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

DATA_DIR = "data"
ALERT_FILE = f"{DATA_DIR}/alerted_today.csv"
SIGNAL_FILE = f"{DATA_DIR}/signals.csv"

STOCKS = [
    "RELIANCE","TCS","INFY","HDFCBANK","ICICIBANK","SBIN","ITC",
    "LT","AXISBANK","KOTAKBANK","BHARTIARTL","MARUTI",
    "TATASTEEL","JSWSTEEL","HINDALCO","ADANIENT",
    "TATAMOTORS","INDIGO","ZOMATO","SHRIRAMFIN"
]

os.makedirs(DATA_DIR, exist_ok=True)

# ================= TELEGRAM =================
def send(msg):
    try:
        requests.post(
            f"https://api.telegram.org/bot{TOKEN}/sendMessage",
            data={"chat_id": CHAT_ID, "text": msg}
        )
    except:
        pass

# ================= LOAD ALERT MEMORY =================
def load_alerted():
    if not os.path.exists(ALERT_FILE):
        return set()

    df = pd.read_csv(ALERT_FILE)
    today = str(datetime.now().date())

    return set(df[df["date"] == today]["stock"].tolist())

def save_alert(stock):
    today = str(datetime.now().date())

    df = pd.DataFrame([[stock, today]], columns=["stock","date"])

    if os.path.exists(ALERT_FILE):
        df.to_csv(ALERT_FILE, mode="a", header=False, index=False)
    else:
        df.to_csv(ALERT_FILE, index=False)

# ================= SAVE SIGNAL =================
def save_signal(data):
    df = pd.DataFrame([data])

    if os.path.exists(SIGNAL_FILE):
        df.to_csv(SIGNAL_FILE, mode="a", header=False, index=False)
    else:
        df.to_csv(SIGNAL_FILE, index=False)

# ================= FETCH =================
def fetch(symbol):
    try:
        df = yf.download(symbol + ".NS", period="1d", interval="5m", progress=False)
        if df is not None and not df.empty:
            df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]
            return df
    except:
        return None

# ================= LOGIC =================
def opening_blast(stock):
    df = fetch(stock)

    if df is None or len(df) < 5:
        return None

    first = df.iloc[:3]

    open_price = first["Open"].iloc[0]
    high_15 = first["High"].max()
    vol_15 = first["Volume"].sum()

    latest = df.iloc[-1]
    price = latest["Close"]

    avg_vol = df["Volume"].rolling(20).mean().iloc[-1]

    breakout = price > high_15
    vol_spike = vol_15 > (avg_vol * 2)
    strength = (price - open_price) / open_price

    score = 0
    if breakout: score += 40
    if vol_spike: score += 30
    if strength > 0.01: score += 20
    if strength > 0.02: score += 10

    if score < 60:
        return None

    return {
        "stock": stock,
        "score": score,
        "entry": round(price,2),
        "sl": round(open_price * 0.98,2),
        "tp": round(price * 1.04,2),
        "time": datetime.now().strftime("%H:%M")
    }

# ================= MAIN =================
def main():
    alerted = load_alerted()
    results = []

    for stock in STOCKS:
        try:
            sig = opening_blast(stock)

            if sig and stock not in alerted:
                results.append(sig)

                save_alert(stock)
                save_signal(sig)

            time.sleep(0.5)
        except:
            continue

    if not results:
        return  # no spam

    msg = "🚀 OPENING BLAST SIGNALS\n\n"

    for r in results:
        msg += (
            f"{r['stock']} ({r['score']})\n"
            f"Entry: {r['entry']} | SL: {r['sl']} | TP: {r['tp']}\n"
            f"Time: {r['time']}\n\n"
        )

    send(msg)

if __name__ == "__main__":
    main()