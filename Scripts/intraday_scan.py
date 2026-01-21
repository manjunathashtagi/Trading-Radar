import pandas as pd
import requests
import os
from datetime import datetime
import pytz

# =========================
# CONFIG
# =========================
IST = pytz.timezone("Asia/Kolkata")

UNIVERSE_FILE = "data/universe_nse_tradable.csv"

MIN_MOVE_PCT = 0.5        # practical intraday move
MIN_VOLUME = 200000       # 2 lakh shares
CONF_THRESHOLD = 60       # relaxed but meaningful

# =========================
# TELEGRAM
# =========================
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

def send_telegram(message):
    if not BOT_TOKEN or not CHAT_ID:
        print("⚠️ Telegram credentials missing")
        return

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }

    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"❌ Telegram error: {e}")

# =========================
# SCORING LOGIC
# =========================
def confidence_score(pct_move, volume):
    score = 0
    reasons = []

    if abs(pct_move) >= 0.5:
        score += 25
        reasons.append("Momentum")

    if abs(pct_move) >= 1.0:
        score += 15
        reasons.append("Strong Move")

    if volume >= 200000:
        score += 20
        reasons.append("Liquidity")

    if volume >= 500000:
        score += 10
        reasons.append("High Volume")

    return score, ", ".join(reasons)

# =========================
# MAIN
# =========================
def main():
    now = datetime.now(IST)
    print(f"🕒 IST Time: {now}")

    if not os.path.exists(UNIVERSE_FILE):
        print("❌ Tradable universe not found")
        return

    df = pd.read_csv(UNIVERSE_FILE)
    print(f"📊 Symbols to scan: {len(df)}")

    # Safety conversions
    df["%CHNG"] = pd.to_numeric(df.get("%CHNG", 0), errors="coerce").fillna(0)
    df["VOLUME"] = pd.to_numeric(df.get("VOLUME", 0), errors="coerce").fillna(0)

    signals = []

    for _, r in df.iterrows():
        pct = r["%CHNG"]
        vol = r["VOLUME"]

        if abs(pct) < MIN_MOVE_PCT or vol < MIN_VOLUME:
            continue

        score, reasons = confidence_score(pct, vol)

        if score >= CONF_THRESHOLD:
            signals.append({
                "SYMBOL": r["SYMBOL"],
                "%MOVE": round(pct, 2),
                "SCORE": score,
                "REASONS": reasons
            })

    if not signals:
        print("ℹ️ No qualified intraday signals in this run")
        return

    out = pd.DataFrame(signals).sort_values("SCORE", ascending=False)

    # =========================
    # TELEGRAM MESSAGE
    # =========================
    msg = "🚨 <b>INTRADAY TRADE ALERTS</b>\n\n"

    for _, r in out.head(10).iterrows():
        emoji = "🟢" if r["%MOVE"] > 0 else "🔴"
        msg += (
            f"{emoji} <b>{r['SYMBOL']}</b>\n"
            f"Move: {r['%MOVE']}%\n"
            f"Score: {r['SCORE']}\n"
            f"Reason: {r['REASONS']}\n\n"
        )

    send_telegram(msg)

    print("🚨 INTRADAY SIGNALS")
    print(out.head(10).to_string(index=False))
    print("📨 Telegram alert sent")

# =========================
if __name__ == "__main__":
    main()