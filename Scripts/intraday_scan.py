import pandas as pd
import requests
from datetime import datetime
import pytz
import os

IST = pytz.timezone("Asia/Kolkata")

UNIVERSE_FILE = "data/universe_nse_tradable.csv"
TRADES_FILE = "data/trades_today.csv"

MIN_MOVE_PCT = 0.4
MIN_VOLUME = 150_000
CONF_THRESHOLD = 55

TG_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TG_CHAT = os.getenv("TELEGRAM_CHAT_ID")

def send_tg(msg):
    if not TG_TOKEN or not TG_CHAT:
        return
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": TG_CHAT, "text": msg})

def fetch_intraday_change(symbol):
    try:
        url = f"https://www.nseindia.com/api/quote-equity?symbol={symbol}"
        headers = {
            "User-Agent": "Mozilla/5.0",
            "Referer": "https://www.nseindia.com/"
        }
        r = requests.get(url, headers=headers, timeout=5)
        p = r.json()["priceInfo"]
        return round(((p["lastPrice"] - p["previousClose"]) / p["previousClose"]) * 100, 2)
    except Exception:
        return None

def confidence_score(move, volume):
    score = 0
    reasons = []

    if abs(move) >= 0.4:
        score += 25; reasons.append("Momentum")
    if abs(move) >= 0.8:
        score += 20; reasons.append("Strong Move")
    if volume >= 150_000:
        score += 20; reasons.append("Liquidity")

    return score, ", ".join(reasons)

def main():
    now = datetime.now(IST)
    print(f"🕒 IST Time: {now}")

    df = pd.read_csv(UNIVERSE_FILE)
    symbols = df["SYMBOL"].dropna().unique()

    rows = []

    for sym in symbols:
        move = fetch_intraday_change(sym)
        if move is None or abs(move) < MIN_MOVE_PCT:
            continue

        score, reasons = confidence_score(move, MIN_VOLUME)
        if score < CONF_THRESHOLD:
            continue

        rows.append({
            "TIME": now.strftime("%Y-%m-%d %H:%M"),
            "SYMBOL": sym,
            "MOVE": move,
            "SIDE": "LONG" if move > 0 else "SHORT",
            "SCORE": score,
            "REASONS": reasons
        })

    if not rows:
        print("ℹ️ No qualified intraday signals")
        return

    out = pd.DataFrame(rows).sort_values("SCORE", ascending=False)

    # 👉 Persist trades (APPEND, not overwrite)
    os.makedirs("data", exist_ok=True)
    if os.path.exists(TRADES_FILE):
        out.to_csv(TRADES_FILE, mode="a", header=False, index=False)
    else:
        out.to_csv(TRADES_FILE, index=False)

    # 👉 Telegram (ONE MESSAGE)
    longs = out[out["SIDE"] == "LONG"].head(20)
    shorts = out[out["SIDE"] == "SHORT"].head(20)

    msg = "🚨 INTRADAY SIGNALS\n\n"

    if not longs.empty:
        msg += "🟢 TOP LONGS\n"
        for _, r in longs.iterrows():
            msg += f"{r.SYMBOL} | {r.MOVE}% | Score {r.SCORE}\n"
        msg += "\n"

    if not shorts.empty:
        msg += "🔴 TOP SHORTS\n"
        for _, r in shorts.iterrows():
            msg += f"{r.SYMBOL} | {r.MOVE}% | Score {r.SCORE}\n"

    send_tg(msg)

if __name__ == "__main__":
    main()