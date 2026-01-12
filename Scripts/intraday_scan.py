import pandas as pd
from datetime import datetime
import pytz
import os
import requests

IST = pytz.timezone("Asia/Kolkata")

UNIVERSE_FILE = "data/universe_nse_tradable.csv"
TRADES_FILE = "data/trades_today.csv"

BOT = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT = os.getenv("TELEGRAM_CHAT_ID")

def send(msg):
    if not BOT:
        return
    requests.post(
        f"https://api.telegram.org/bot{BOT}/sendMessage",
        data={"chat_id": CHAT, "text": msg}
    )

def market_open(now):
    return (
        now.weekday() < 5 and
        (now.hour > 9 or (now.hour == 9 and now.minute >= 15)) and
        now.hour < 15
    )

def confidence_score(pct, vol):
    score = 0
    reasons = []

    if abs(pct) >= 2:
        score += 40
        reasons.append("Strong price move")

    if vol >= 1_000_000:
        score += 30
        reasons.append("High volume")

    if abs(pct) >= 3:
        score += 30
        reasons.append("Momentum breakout")

    return min(score, 100), reasons

def main():
    now = datetime.now(IST)
    print(f"🕒 IST Time: {now}")

    if not market_open(now):
        print("Market closed")
        return

    if not os.path.exists(UNIVERSE_FILE):
        print("Universe missing")
        return

    universe = pd.read_csv(UNIVERSE_FILE)
    trades = []

    for _, r in universe.iterrows():
        conf, reasons = confidence_score(r["%CHNG"], r["VOLUME"])
        if conf < 70:
            continue

        entry = round(100 + abs(r["%CHNG"]), 2)
        target = round(entry * 1.02, 2)
        sl = round(entry * 0.99, 2)

        trade = {
            "symbol": r["SYMBOL"],
            "entry": entry,
            "target": target,
            "sl": sl,
            "confidence": conf,
            "reasons": "; ".join(reasons),
            "time": now.strftime("%H:%M"),
            "status": "OPEN"
        }
        trades.append(trade)

        send(
            f"🚨 Intraday Alert\n\n"
            f"{r['SYMBOL']}\n"
            f"Entry: {entry}\n"
            f"Target: {target}\n"
            f"SL: {sl}\n"
            f"Confidence: {conf}\n"
            f"Why: {', '.join(reasons)}"
        )

    if trades:
        df = pd.DataFrame(trades)
        if os.path.exists(TRADES_FILE):
            df = pd.concat([pd.read_csv(TRADES_FILE), df])
        df.to_csv(TRADES_FILE, index=False)

if __name__ == "__main__":
    main()