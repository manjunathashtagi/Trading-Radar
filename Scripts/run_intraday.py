import yfinance as yf
import pandas as pd
import os
import requests
import time
import json
from datetime import datetime

# ================= CONFIG =================
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

DATA_DIR = "data"
ALERT_FILE = f"{DATA_DIR}/alerted_today.csv"
SIGNAL_FILE = f"{DATA_DIR}/signals.csv"
CONFIG_FILE = f"{DATA_DIR}/model_config.json"

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

# ================= LOAD CONFIG =================
def load_config():
    if not os.path.exists(CONFIG_FILE):
        return {
            "trend_min": 0,
            "breakout_min": 0.002,
            "volume_min": 1.5,
            "momentum_min": 0.003
        }
    with open(CONFIG_FILE, "r") as f:
        return json.load(f)

# ================= NSE UNIVERSE =================
def get_nse_universe():
    try:
        df = pd.read_csv(
            "https://archives.nseindia.com/content/equities/EQUITY_L.csv"
        )
        return df["SYMBOL"].dropna().tolist()
    except:
        return []

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

# ================= FETCH =================
def fetch(stock):
    try:
        df = yf.download(
            stock + ".NS",
            period="1d",
            interval="5m",
            progress=False
        )

        if df is None or df.empty:
            return None

        df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]
        df = df.dropna()

        if len(df) < 30:
            return None

        return df

    except:
        return None

# ================= HYBRID SNIPER =================
def sniper(stock):

    df = fetch(stock)
    if df is None:
        return None

    config = load_config()

    last = df["Close"].iloc[-1]
    ema20 = df["Close"].ewm(span=20).mean().iloc[-1]

    # -----------------------------
    # TREND
    # -----------------------------
    trend_strength = (last - ema20) / ema20
    trend_ok = trend_strength > config["trend_min"]

    # -----------------------------
    # BREAKOUT
    # -----------------------------
    recent = df.iloc[-6:]
    high = recent["High"].max()
    low = recent["Low"].min()

    breakout_strength = (last - high) / high
    breakout = breakout_strength > config["breakout_min"]

    # -----------------------------
    # CONTINUATION LOGIC (NEW)
    # -----------------------------
    strong_trend = trend_strength > 0.003
    continuation = last > df["Close"].iloc[-3]

    # -----------------------------
    # VOLUME
    # -----------------------------
    avg_vol = df["Volume"].rolling(20).mean().iloc[-1]
    vol = df["Volume"].iloc[-1]
    volume_strength = vol / avg_vol
    volume_ok = volume_strength > config["volume_min"]

    # -----------------------------
    # MOMENTUM
    # -----------------------------
    momentum_strength = (last - df["Close"].iloc[-5]) / df["Close"].iloc[-5]
    momentum_ok = momentum_strength > config["momentum_min"]

    # -----------------------------
    # FINAL DECISION (HYBRID)
    # -----------------------------
    if not trend_ok:
        return None

    if not volume_ok:
        return None

    if not momentum_ok:
        return None

    # 🔥 KEY CHANGE HERE
    if not (breakout or (strong_trend and continuation)):
        return None

    # -----------------------------
    # TRADE LEVELS
    # -----------------------------
    entry = last
    sl = low
    tp = entry + (entry - sl) * 1.8

    return {
        "stock": stock,
        "entry": round(entry,2),
        "sl": round(sl,2),
        "tp": round(tp,2),
        "time": datetime.now().strftime("%H:%M:%S"),
        "date": str(datetime.now().date()),
        "result": "OPEN",

        # AI FEATURES
        "trend": round(trend_strength,4),
        "breakout": round(breakout_strength,4),
        "volume": round(volume_strength,2),
        "momentum": round(momentum_strength,4)
    }

# ================= MAIN =================
def main():

    universe = get_nse_universe()
    alerted = load_alerted()

    results = []

    for stock in universe[:200]:  # speed control

        try:
            if stock in alerted:
                continue

            sig = sniper(stock)

            if sig:
                results.append(sig)
                save_alert(stock)
                save_signal(sig)

            time.sleep(0.2)

        except:
            continue

    if not results:
        print("⚠️ No signals")
        return

    # Sort by momentum strength
    results = sorted(results, key=lambda x: x["momentum"], reverse=True)

    msg = "🚀 HYBRID MODE (BREAKOUT + CONTINUATION)\n\n"

    for r in results[:10]:
        msg += (
            f"{r['stock']}\n"
            f"Entry: {r['entry']} | SL: {r['sl']} | TP: {r['tp']}\n\n"
        )

    send(msg)

if __name__ == "__main__":
    main()