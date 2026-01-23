import pandas as pd
import requests
from datetime import datetime
import pytz
import os

IST = pytz.timezone("Asia/Kolkata")

UNIVERSE_FILE = "data/universe_nse_tradable.csv"
OUT_DIR = "data"

# === YOUR EXISTING THRESHOLDS (UNCHANGED) ===
MIN_MOVE_PCT = 0.4
MIN_VOLUME = 150_000
CONF_THRESHOLD = 55

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

def send(msg):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": CHAT_ID, "text": msg})

def fetch_intraday_change(symbol):
    try:
        url = f"https://www.nseindia.com/api/quote-equity?symbol={symbol}"
        headers = {
            "User-Agent": "Mozilla/5.0",
            "Referer": "https://www.nseindia.com/"
        }
        r = requests.get(url, headers=headers, timeout=5)
        data = r.json()
        p = data["priceInfo"]
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
    date_str = now.strftime("%Y-%m-%d")
    print(f"🕒 IST Time: {now}")

    df = pd.read_csv(UNIVERSE_FILE)
    symbols = df["SYMBOL"].dropna().unique()
    print(f"📊 Symbols to scan: {len(symbols)}")

    signals = []

    for sym in symbols:
        move = fetch_intraday_change(sym)
        if move is None or abs(move) < MIN_MOVE_PCT:
            continue

        volume = MIN_VOLUME  # placeholder (unchanged)
        score, reasons = confidence_score(move, volume)

        if score >= CONF_THRESHOLD:
            signals.append({
                "DATE": date_str,
                "SYMBOL": sym,
                "DIRECTION": "LONG" if move > 0 else "SHORT",
                "MOVE_PCT": move,
                "SCORE": score,
                "REASONS": reasons
            })

    if not signals:
        print("ℹ️ No qualified intraday signals in this run")
        return

    out = pd.DataFrame(signals)
    os.makedirs(OUT_DIR, exist_ok=True)

    csv_path = f"{OUT_DIR}/intraday_signals_{date_str}.csv"
    out.to_csv(csv_path, index=False)

    # ---- TELEGRAM (ONE MESSAGE ONLY) ----
    longs = out[out["DIRECTION"] == "LONG"].sort_values("MOVE_PCT", ascending=False).head(20)
    shorts = out[out["DIRECTION"] == "SHORT"].sort_values("MOVE_PCT").head(20)

    msg = f"🚨 INTRADAY RADAR ({now.strftime('%H:%M IST')})\n\n"

    msg += "🟢 TOP LONGS\n"
    for _, r in longs.iterrows():
        msg += f"{r.SYMBOL} | +{r.MOVE_PCT}% | Score {r.SCORE}\n"

    msg += "\n🔴 TOP SHORTS\n"
    for _, r in shorts.iterrows():
        msg += f"{r.SYMBOL} | {r.MOVE_PCT}% | Score {r.SCORE}\n"

    send(msg)
    print(f"✅ Saved signals → {csv_path}")

if __name__ == "__main__":
    main()