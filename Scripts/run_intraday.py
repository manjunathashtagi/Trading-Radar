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

# ================= STOCK FILTER =================
def get_strong_stocks():
    try:
        df = pd.read_csv(
            "https://archives.nseindia.com/content/equities/EQUITY_L.csv"
        )

        df = df[df["SERIES"] == "EQ"]

        # Take first 300 liquid stocks
        stocks = df["SYMBOL"].dropna().tolist()[:300]

        return stocks

    except:
        return []

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

# ================= SNIPER LOGIC =================
def sniper(stock):

    df = fetch(stock)
    if df is None:
        return None

    last = df["Close"].iloc[-1]

    # ❌ Avoid junk stocks
    if last < 50:
        return None

    ema20 = df["Close"].ewm(span=20).mean().iloc[-1]

    # ================= TREND =================
    trend_strength = (last - ema20) / ema20
    if trend_strength < 0:
        return None

    # ================= RANGE =================
    recent = df.iloc[-6:]
    high = recent["High"].max()
    low = recent["Low"].min()

    # ================= EARLY ENTRY =================
    distance_to_high = (high - last) / high
    early_breakout = distance_to_high < 0.003  # 🔥 key fix

    # ================= CONTINUATION =================
    strong_trend = trend_strength > 0.003
    continuation = last > df["Close"].iloc[-3]

    # ================= VOLUME =================
    avg_vol = df["Volume"].rolling(20).mean().iloc[-1]
    vol = df["Volume"].iloc[-1]

    if avg_vol == 0:
        return None

    volume_strength = vol / avg_vol

    if volume_strength < 1.5:
        return None

    # ================= MOMENTUM =================
    momentum_strength = (last - df["Close"].iloc[-5]) / df["Close"].iloc[-5]

    if momentum_strength < 0.003:
        return None

    # ================= FINAL CONDITION =================
    if not (early_breakout or (strong_trend and continuation)):
        return None

    # ================= TRADE LEVELS =================
    entry = last
    sl = low
    tp = entry * 1.025  # 🔥 better target

    return {
        "stock": stock,
        "entry": round(entry,2),
        "sl": round(sl,2),
        "tp": round(tp,2),
        "time": datetime.now().strftime("%H:%M"),
        "date": str(datetime.now().date())
    }

# ================= MAIN =================
def main():

    universe = get_strong_stocks()
    alerted = load_alerted()

    results = []

    for stock in universe:

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

    # Sort by strongest momentum
    results = sorted(results, key=lambda x: x["entry"], reverse=True)

    msg = "🚀 EARLY BREAKOUT SNIPER\n\n"

    for r in results[:10]:
        msg += (
            f"{r['stock']}\n"
            f"Entry: {r['entry']} | SL: {r['sl']} | TP: {r['tp']}\n\n"
        )

    msg += "⚡ Entry BEFORE breakout (not late)"

    send(msg)

if __name__ == "__main__":
    main()