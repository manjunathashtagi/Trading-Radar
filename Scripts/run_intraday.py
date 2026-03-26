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

# ================= ALERT MEMORY =================
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
def fetch(stock):
    try:
        df = yf.download(stock + ".NS", period="1d", interval="5m", progress=False)
        if df is not None and not df.empty:
            df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]
            return df
    except:
        return None

# ================= SNIPER LOGIC =================
def sniper_signal(stock):
    df = fetch(stock)

    if df is None or len(df) < 10:
        return None

    df = df.copy()

    # recent candles
    recent = df.iloc[-6:]

    high_range = recent["High"].max()
    low_range = recent["Low"].min()

    range_pct = (high_range - low_range) / low_range

    # 🔥 Tight range (coil)
    tight_range = range_pct < 0.01

    # 🔥 Higher lows (accumulation)
    higher_lows = all(recent["Low"].diff().dropna() > -0.1)

    # 🔥 Volume build-up
    avg_vol = df["Volume"].rolling(20).mean().iloc[-1]
    recent_vol = recent["Volume"].mean()
    volume_build = recent_vol > avg_vol * 1.5

    # 🔥 Early breakout pressure
    last_price = df["Close"].iloc[-1]
    near_high = last_price > (high_range * 0.995)

    score = 0

    if tight_range: score += 25
    if higher_lows: score += 25
    if volume_build: score += 25
    if near_high: score += 25

    if score < 70:
        return None

    entry = last_price
    sl = low_range
    tp = entry + (entry - sl) * 1.5

    return {
        "stock": stock,
        "score": score,
        "entry": round(entry,2),
        "sl": round(sl,2),
        "tp": round(tp,2),
        "time": datetime.now().strftime("%H:%M")
    }

# ================= MAIN =================
def main():
    alerted = load_alerted()
    results = []

    for stock in STOCKS:
        try:
            sig = sniper_signal(stock)

            if sig and stock not in alerted:
                results.append(sig)

                save_alert(stock)
                save_signal(sig)

            time.sleep(0.5)
        except:
            continue

    if not results:
        return

    results = sorted(results, key=lambda x: x["score"], reverse=True)

    msg = "🎯 SNIPER MODE PRO++\n\n"

    for r in results:
        msg += (
            f"{r['stock']} ({r['score']})\n"
            f"Entry: {r['entry']} | SL: {r['sl']} | TP: {r['tp']}\n"
            f"Time: {r['time']}\n\n"
        )

    msg += "⚡ Early Entry BEFORE Breakout"

    send(msg)

if __name__ == "__main__":
    main()