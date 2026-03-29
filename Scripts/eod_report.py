import pandas as pd
import yfinance as yf
import os
from datetime import datetime
import requests

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

SIGNAL_FILE = "data/signals.csv"

def send(msg):
    try:
        requests.post(
            f"https://api.telegram.org/bot{TOKEN}/sendMessage",
            data={"chat_id": CHAT_ID, "text": msg}
        )
    except:
        pass

def check_result(row):
    try:
        df = yf.download(row["stock"] + ".NS", period="1d", interval="5m", progress=False)

        if df.empty:
            return "OPEN"

        df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]

        entry = row["entry"]
        sl = row["sl"]
        tp = row["tp"]

        for _, r in df.iterrows():
            if r["High"] >= tp:
                return "TARGET"
            if r["Low"] <= sl:
                return "SL"

        return "OPEN"

    except:
        return "OPEN"

def main():

    if not os.path.exists(SIGNAL_FILE):
        print("No signals")
        return

    df = pd.read_csv(SIGNAL_FILE)

    today = str(datetime.now().date())

    df_today = df[df["date"] == today]

    if df_today.empty:
        send("📊 EOD REPORT\nNo trades today")
        return

    wins = 0
    losses = 0
    open_trades = 0

    for i, row in df_today.iterrows():

        result = check_result(row)
        df.loc[i, "result"] = result

        if result == "TARGET":
            wins += 1
        elif result == "SL":
            losses += 1
        else:
            open_trades += 1

    total = len(df_today)
    winrate = round((wins / total) * 100, 2) if total > 0 else 0

    df.to_csv(SIGNAL_FILE, index=False)

    msg = (
        f"📊 EOD PERFORMANCE\n\n"
        f"Trades: {total}\n"
        f"🎯 Wins: {wins}\n"
        f"❌ Loss: {losses}\n"
        f"⏳ Open: {open_trades}\n"
        f"Win Rate: {winrate}%"
    )

    send(msg)

if __name__ == "__main__":
    main()