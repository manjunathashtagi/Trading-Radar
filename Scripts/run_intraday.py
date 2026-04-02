import yfinance as yf
import pandas as pd
import os
import requests
import time
import json
from datetime import datetime

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

# ================= CONFIG =================
def load_config():
    if not os.path.exists(CONFIG_FILE):
        return {
            "trend_min": 0.0,
            "volume_min": 1.5,
            "momentum_min": 0.003,
            "win_rate": 0,
            "total_trades": 0,
            "wins": 0
        }
    return json.load(open(CONFIG_FILE))

# ================= ALERT =================
def load_alerted():
    if not os.path.exists(ALERT_FILE):
        return set()
    df = pd.read_csv(ALERT_FILE)
    today = str(datetime.now().date())
    return set(df[df["date"] == today]["stock"].tolist()) if "date" in df.columns else set()

def save_alert(stock):
    today = str(datetime.now().date())
    df = pd.DataFrame([[stock, today]], columns=["stock","date"])
    df.to_csv(ALERT_FILE, mode="a", header=not os.path.exists(ALERT_FILE), index=False)

# ================= SAVE =================
def save_signal(data):
    df = pd.DataFrame([data])
    df.to_csv(SIGNAL_FILE, mode="a", header=not os.path.exists(SIGNAL_FILE), index=False)

# ================= STOCKS =================
def get_stocks():
    df = pd.read_csv("https://archives.nseindia.com/content/equities/EQUITY_L.csv")
    df = df[df["SERIES"] == "EQ"]
    return df["SYMBOL"].tolist()[:300]

# ================= FETCH =================
def fetch(stock):
    try:
        df = yf.download(stock + ".NS", period="1d", interval="5m", progress=False)
        if df.empty:
            return None
        df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]
        return df.dropna()
    except:
        return None

# ================= AI SCORING =================
def score_signal(trend, volume, momentum):
    return round((trend*100 + volume*2 + momentum*100), 2)

# ================= SNIPER =================
def sniper(stock, config):

    df = fetch(stock)
    if df is None or len(df) < 30:
        return None

    last = df["Close"].iloc[-1]

    if last < 50:
        return None

    ema20 = df["Close"].ewm(span=20).mean().iloc[-1]
    trend = (last - ema20) / ema20

    if trend < config["trend_min"]:
        return None

    recent = df.iloc[-6:]
    high = recent["High"].max()
    low = recent["Low"].min()

    distance = (high - last) / high
    early = distance < 0.003

    avg_vol = df["Volume"].rolling(20).mean().iloc[-1]
    vol = df["Volume"].iloc[-1]

    if avg_vol == 0:
        return None

    volume = vol / avg_vol

    if volume < config["volume_min"]:
        return None

    momentum = (last - df["Close"].iloc[-5]) / df["Close"].iloc[-5]

    if momentum < config["momentum_min"]:
        return None

    if not early:
        return None

    score = score_signal(trend, volume, momentum)

    return {
        "stock": stock,
        "entry": round(last,2),
        "sl": round(low,2),
        "tp": round(last*1.025,2),
        "trend": round(trend,4),
        "volume": round(volume,2),
        "momentum": round(momentum,4),
        "score": score,
        "date": str(datetime.now().date()),
        "time": datetime.now().strftime("%H:%M"),
        "result": "OPEN"
    }

# ================= MAIN =================
def main():

    config = load_config()
    alerted = load_alerted()

    results = []

    for stock in get_stocks():

        if stock in alerted:
            continue

        sig = sniper(stock, config)

        if sig:
            results.append(sig)
            save_alert(stock)
            save_signal(sig)

        time.sleep(0.2)

    if not results:
        print("⚠️ No signals")
        return

    results = sorted(results, key=lambda x: x["score"], reverse=True)

    msg = f"🚀 AI SNIPER (WinRate: {config['win_rate']}%)\n\n"

    for r in results[:10]:
        msg += f"{r['stock']} ({r['score']})\nEntry:{r['entry']} SL:{r['sl']} TP:{r['tp']}\n\n"

    send(msg)

if __name__ == "__main__":
    main()