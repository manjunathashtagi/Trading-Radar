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
            data={"chat_id": CHAT_ID, "text": msg, "parse_mode": "HTML"},
            timeout=5
        )
    except:
        print("❌ Telegram failed")

# ================= ALERT MEMORY =================
def load_alerted():
    if not os.path.exists(ALERT_FILE):
        return set()

    df = pd.read_csv(ALERT_FILE)

    if "date" not in df.columns:
        return set()

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

# ================= FETCH (FIXED) =================
def fetch(stock):
    try:
        stock = stock.strip().upper()

        df = yf.download(stock + ".NS", period="1d", interval="5m", progress=False)

        # 🔥 Retry once (Yahoo unstable)
        if df is None or df.empty:
            time.sleep(1)
            df = yf.download(stock + ".NS", period="1d", interval="5m", progress=False)

        if df is None or df.empty:
            print(f"⚠️ Skipping {stock}")
            return None

        # 🔥 Flatten columns
        df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]

        # 🔥 Ensure required columns
        required = ["Open","High","Low","Close","Volume"]
        if not all(col in df.columns for col in required):
            return None

        df = df.dropna()

        return df

    except Exception as e:
        print(f"❌ Error {stock}: {e}")
        return None

# ================= SNIPER LOGIC =================
def sniper_signal(stock):
    df = fetch(stock)

    if df is None or len(df) < 20:
        return None

    df = df.copy()

    recent = df.iloc[-6:]

    high_range = recent["High"].max()
    low_range = recent["Low"].min()

    range_pct = (high_range - low_range) / low_range

    # 🔥 Tight range (coil)
    tight_range = range_pct < 0.01

    # 🔥 Higher lows (accumulation)
    higher_lows = all(recent["Low"].diff().dropna() > -0.05)

    # 🔥 Volume build-up (IMPROVED)
    avg_vol = df["Volume"].rolling(20).mean().iloc[-1]
    recent_vol = recent["Volume"].mean()
    volume_build = recent_vol > avg_vol * 1.8

    # 🔥 Pressure near breakout
    last_price = df["Close"].iloc[-1]
    near_high = last_price > (high_range * 0.996)

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
        "time": datetime.now().strftime("%H:%M"),
        "date": str(datetime.now().date())
    }

# ================= MAIN =================
def main():

    # 🔥 Ensure files exist (fix Git errors)
    if not os.path.exists(ALERT_FILE):
        pd.DataFrame(columns=["stock","date"]).to_csv(ALERT_FILE, index=False)

    alerted = load_alerted()
    results = []

    for stock in STOCKS:
        try:
            sig = sniper_signal(stock)

            if sig and stock not in alerted:
                results.append(sig)

                save_alert(stock)
                save_signal(sig)

            time.sleep(0.7)  # 🔥 rate limit

        except Exception as e:
            print(f"Loop error {stock}: {e}")
            continue

    if not results:
        print("⚠️ No signals")
        return

    results = sorted(results, key=lambda x: x["score"], reverse=True)

    msg = "🎯 <b>SNIPER MODE PRO++</b>\n\n"

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