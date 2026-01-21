import pandas as pd
import requests
from datetime import datetime
import pytz
import os

IST = pytz.timezone("Asia/Kolkata")

UNIVERSE_FILE = "data/universe_nse_tradable.csv"

# === PRACTICAL PROFESSIONAL THRESHOLDS ===
MIN_MOVE_PCT = 0.4          # relaxed, realistic
MIN_VOLUME = 150_000
CONF_THRESHOLD = 55

def fetch_intraday_change(symbol):
    """
    Fetch intraday % change using NSE quote API
    """
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

        volume = MIN_VOLUME  # placeholder (can be enhanced later)

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

    out = pd.DataFrame(signals).sort_values("SCORE", ascending=False)

    print("🚨 INTRADAY SIGNALS")
    print(out.head(10).to_string(index=False))

if __name__ == "__main__":
    main()