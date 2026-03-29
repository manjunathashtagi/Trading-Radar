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

# ================= NSE UNIVERSE =================
def get_nse_universe():
    try:
        df = pd.read_csv(
            "https://archives.nseindia.com/content/equities/EQUITY_L.csv"
        )
        symbols = df["SYMBOL"].dropna().tolist()
        return symbols
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

# ================= SECTOR MOMENTUM =================
def get_top_movers(symbols):
    movers = []

    for stock in symbols[:300]:  # limit for speed
        try:
            df = yf.download(stock + ".NS", period="1d", interval="5m", progress=False)

            if df is None or df.empty:
                continue

            df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]

            change = (df["Close"].iloc[-1] - df["Open"].iloc[0]) / df["Open"].iloc[0]

            if change > 0.02:  # 2% movers
                movers.append((stock, change))

        except:
            continue

    movers = sorted(movers, key=lambda x: x[1], reverse=True)

    return [m[0] for m in movers[:30]]  # top 30

# ================= SNIPER LOGIC =================
def sniper(stock):
    df = fetch(stock)

    if df is None:
        return None

    # TREND
    ema20 = df["Close"].ewm(span=20).mean().iloc[-1]
    last = df["Close"].iloc[-1]

    trend = last > ema20

    # BREAKOUT
    recent = df.iloc[-6:]
    high = recent["High"].max()
    low = recent["Low"].min()

    breakout = last > high

    # VOLUME
    avg_vol = df["Volume"].rolling(20).mean().iloc[-1]
    vol = df["Volume"].iloc[-1]

    volume = vol > avg_vol * 2

    # MOMENTUM
    momentum = last > df["Close"].iloc[-5]

    if not (trend and breakout and volume and momentum):
        return None

    entry = last
    sl = low
    tp = entry + (entry - sl) * 1.8

    return {
        "stock": stock,
        "entry": round(entry,2),
        "sl": round(sl,2),
        "tp": round(tp,2),
        "time": datetime.now().strftime("%H:%M")
    }

# ================= MAIN =================
def main():

    universe = get_nse_universe()

    if not universe:
        print("❌ NSE load failed")
        return

    alerted = load_alerted()

    # 🚀 Step 1: Find leaders
    leaders = get_top_movers(universe)

    print(f"🔥 Leaders found: {len(leaders)}")

    results = []

    # 🚀 Step 2: Apply sniper only on leaders
    for stock in leaders:

        if stock in alerted:
            continue

        sig = sniper(stock)

        if sig:
            results.append(sig)
            save_alert(stock)
            save_signal(sig)

        time.sleep(0.3)

    if not results:
        print("⚠️ No institutional signals")
        return

    msg = "🏦 HEDGE FUND MODE SIGNALS\n\n"

    for r in results:
        msg += (
            f"{r['stock']}\n"
            f"Entry: {r['entry']} | SL: {r['sl']} | TP: {r['tp']}\n"
            f"Time: {r['time']}\n\n"
        )

    msg += "🔥 Top Momentum + Breakout + Volume"

    send(msg)


if __name__ == "__main__":
    main()