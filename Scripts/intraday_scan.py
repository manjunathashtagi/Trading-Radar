import pandas as pd
import requests
from datetime import datetime
import pytz
import os

IST = pytz.timezone("Asia/Kolkata")

UNIVERSE_FILE = "data/universe_nse_tradable.csv"

# === PRACTICAL PROFESSIONAL THRESHOLDS ===
MIN_MOVE_PCT = 0.4
MIN_VOLUME = 150_000
CONF_THRESHOLD = 55

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# --------------------------------------------------
# Telegram helper
# --------------------------------------------------
def send(msg):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("⚠️ Telegram not configured")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": msg
    }
    requests.post(url, data=payload, timeout=10)


# --------------------------------------------------
# NSE intraday % move
# --------------------------------------------------
def fetch_intraday_change(symbol):
    try:
        url = f"https://www.nseindia.com/api/quote-equity?symbol={symbol}"
        headers = {
            "User-Agent": "Mozilla/5.0",
            "Accept": "application/json",
            "Referer": "https://www.nseindia.com/"
        }

        r = requests.get(url, headers=headers, timeout=5)
        data = r.json()

        price = data["priceInfo"]
        last = price["lastPrice"]
        prev = price["previousClose"]

        if prev == 0:
            return None

        return round(((last - prev) / prev) * 100, 2)

    except Exception:
        return None


# --------------------------------------------------
# Confidence scoring (UNCHANGED)
# --------------------------------------------------
def confidence_score(move_pct, volume):
    score = 0
    reasons = []

    if abs(move_pct) >= 0.4:
        score += 25
        reasons.append("Momentum")

    if abs(move_pct) >= 0.8:
        score += 20
        reasons.append("Strong Move")

    if volume >= 150_000:
        score += 20
        reasons.append("Liquidity")

    if volume >= 500_000:
        score += 15
        reasons.append("High Volume")

    return score, reasons


# --------------------------------------------------
# MAIN
# --------------------------------------------------
def main():
    now = datetime.now(IST)
    print(f"🕒 IST Time: {now}")

    if not os.path.exists(UNIVERSE_FILE):
        print("❌ Tradable universe not found")
        return

    df = pd.read_csv(UNIVERSE_FILE)

    if "SYMBOL" not in df.columns:
        print("❌ SYMBOL column missing")
        return

    symbols = df["SYMBOL"].dropna().unique()
    print(f"📊 Symbols to scan: {len(symbols)}")

    signals = []

    for sym in symbols:
        move = fetch_intraday_change(sym)
        if move is None:
            continue

        volume = MIN_VOLUME  # same logic as before

        if abs(move) < MIN_MOVE_PCT:
            continue

        score, reasons = confidence_score(move, volume)

        if score >= CONF_THRESHOLD:
            signals.append({
                "SYMBOL": sym,
                "%MOVE": move,
                "SCORE": score,
                "REASONS": ", ".join(reasons)
            })

    if not signals:
        print("ℹ️ No qualified intraday signals in this run")
        return

    out = pd.DataFrame(signals)

    # ---------------- TELEGRAM AGGREGATION ----------------
    long_df = out[out["%MOVE"] > 0].sort_values("SCORE", ascending=False).head(20)
    short_df = out[out["%MOVE"] < 0].sort_values("SCORE", ascending=False).head(20)

    msg = f"🚨 Intraday Radar ({now.strftime('%H:%M')} IST)\n\n"

    if not long_df.empty:
        msg += "🟢 TOP LONG SETUPS\n"
        for _, r in long_df.iterrows():
            msg += f"• {r['SYMBOL']}  {r['%MOVE']}% | Score {r['SCORE']}\n"
        msg += "\n"

    if not short_df.empty:
        msg += "🔴 TOP SHORT SETUPS\n"
        for _, r in short_df.iterrows():
            msg += f"• {r['SYMBOL']}  {r['%MOVE']}% | Score {r['SCORE']}\n"
        msg += "\n"

    msg += f"Universe scanned: {len(symbols)} stocks"

    send(msg)


if __name__ == "__main__":
    main()