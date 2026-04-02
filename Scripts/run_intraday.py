import requests
import pandas as pd
import os
import time
from datetime import datetime

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

DATA_DIR = "data"
ALERT_FILE = f"{DATA_DIR}/alerted_today.csv"

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

# ================= LOAD ALERTED =================
def load_alerted():
    if not os.path.exists(ALERT_FILE):
        return set()

    df = pd.read_csv(ALERT_FILE)
    today = str(datetime.now().date())

    if "date" not in df.columns:
        return set()

    return set(df[df["date"] == today]["stock"].tolist())

def save_alert(stock):
    today = str(datetime.now().date())
    df = pd.DataFrame([[stock, today]], columns=["stock", "date"])

    if os.path.exists(ALERT_FILE):
        df.to_csv(ALERT_FILE, mode="a", header=False, index=False)
    else:
        df.to_csv(ALERT_FILE, index=False)

# ================= NSE FETCH =================
def get_nse_gainers():
    url = "https://www.nseindia.com/api/live-analysis-variations?index=gainers"

    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json"
    }

    session = requests.Session()
    session.get("https://www.nseindia.com", headers=headers)

    try:
        res = session.get(url, headers=headers)
        data = res.json()

        stocks = []

        for item in data["NIFTY"]["data"]:
            symbol = item["symbol"]
            change = float(item["pChange"])

            if change > 0.5:  # 🔥 filter like your app
                stocks.append({
                    "symbol": symbol,
                    "price": float(item["lastPrice"]),
                    "change": change
                })

        return stocks

    except:
        return []

# ================= SNIPER =================
def generate_signal(stock):
    price = stock["price"]
    change = stock["change"]

    # 🔥 Strong momentum condition
    if change < 1:
        return None

    entry = price
    sl = price * 0.99
    tp = price * 1.02

    return {
        "stock": stock["symbol"],
        "entry": round(entry, 2),
        "sl": round(sl, 2),
        "tp": round(tp, 2),
        "score": round(change, 2)
    }

# ================= MAIN =================
def main():

    alerted = load_alerted()

    stocks = get_nse_gainers()

    if not stocks:
        print("❌ No NSE data")
        return

    results = []

    for s in stocks:
        if s["symbol"] in alerted:
            continue

        sig = generate_signal(s)

        if sig:
            results.append(sig)
            save_alert(sig["stock"])

        time.sleep(0.2)

    if not results:
        print("⚠️ No signals")
        return

    results = sorted(results, key=lambda x: x["score"], reverse=True)

    msg = "🚀 LIVE NSE MOMENTUM SIGNALS\n\n"

    for r in results[:5]:
        msg += (
            f"{r['stock']} ({r['score']}%)\n"
            f"Entry: {r['entry']} | SL: {r['sl']} | TP: {r['tp']}\n\n"
        )

    send(msg)

if __name__ == "__main__":
    main()