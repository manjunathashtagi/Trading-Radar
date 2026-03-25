import os
import pandas as pd
import yfinance as yf
import time
from datetime import datetime
import pytz

from alerts.telegram_alerts import send_alert

ALERTED_FILE = "data/alerted_today.csv"
SIGNALS_FILE = "data/signals.csv"
STAGE1_FILE = "data/stage1_cache.csv"


def safe_fetch(symbol):
    for _ in range(3):
        try:
            df = yf.download(symbol, period="5d", interval="5m", progress=False)
            if not df.empty:
                return df
        except:
            time.sleep(1)
    return None


def load_alerted():
    if not os.path.exists(ALERTED_FILE):
        return set()

    df = pd.read_csv(ALERTED_FILE)

    if "stock" not in df.columns:
        return set()

    return set(df["stock"].tolist())


def save_alert(stock):
    df = pd.DataFrame([{"stock": stock}])
    if os.path.exists(ALERTED_FILE):
        df.to_csv(ALERTED_FILE, mode="a", header=False, index=False)
    else:
        df.to_csv(ALERTED_FILE, index=False)


def main():

    if not os.path.exists(STAGE1_FILE):
        print("No stage1 cache")
        return

    df_stage1 = pd.read_csv(STAGE1_FILE)

    symbols = (
        df_stage1["symbol"].tolist()
        if "symbol" in df_stage1.columns
        else df_stage1["stock"].tolist()
    )

    alerted = load_alerted()

    ist = pytz.timezone("Asia/Kolkata")
    now = datetime.now(ist)

    signals = []

    for stock in symbols:

        if stock in alerted:
            continue

        df = safe_fetch(stock + ".NS")

        if df is None or len(df) < 20:
            continue

        df["EMA20"] = df["Close"].ewm(span=20).mean()

        latest = df.iloc[-1]

        price = latest["Close"]
        ema = latest["EMA20"]

        # 🚀 EARLY MOMENTUM LOGIC
        if price > ema:

            entry = price
            sl = price * 0.98
            tp = price * 1.03

            msg = (
                f"🚀 OPENING BLAST SIGNAL\n\n"
                f"{stock}\n"
                f"Entry: {round(entry,2)}\n"
                f"SL: {round(sl,2)}\n"
                f"TP: {round(tp,2)}"
            )

            send_alert(msg)

            save_alert(stock)

            signals.append({
                "symbol": stock,
                "action": "BUY",
                "entry": entry,
                "sl": sl,
                "tp": tp,
                "date": now.date(),
                "trigger_time": now.strftime("%H:%M:%S")
            })

        time.sleep(0.3)

    if signals:
        df_new = pd.DataFrame(signals)

        if os.path.exists(SIGNALS_FILE):
            df_new.to_csv(SIGNALS_FILE, mode="a", header=False, index=False)
        else:
            df_new.to_csv(SIGNALS_FILE, index=False)


if __name__ == "__main__":
    main()