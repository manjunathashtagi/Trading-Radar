import pandas as pd
import requests
from datetime import datetime, time
import pytz
import os

# ================= CONFIG =================
IST = pytz.timezone("Asia/Kolkata")

UNIVERSE_FILE = "data/universe_nse_tradable.csv"
STATE_FILE = "data/signals_sent_today.csv"

# Momentum thresholds
MIN_MOVE = 0.35
MIN_VOL_MULT = 1.8
RS_THRESHOLD = 0.4
CONF_THRESHOLD = 65

# ORB thresholds (fallback)
ORB_MOVE = 0.25
ORB_VOL_MULT = 1.4

# Telegram
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# ================= HELPERS =================
def send(msg):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    requests.post(url, data={"chat_id": CHAT_ID, "text": msg})

def confidence(move, vol_mult, rs, mode):
    score = 0
    reasons = []

    if move >= 0.25:
        score += 25
        reasons.append("Price acceptance")

    if vol_mult >= 1.4:
        score += 25
        reasons.append("Volume expansion")

    if rs >= 0.4:
        score += 25
        reasons.append("Relative strength")

    if mode == "Momentum" and move >= 0.8:
        score += 15
        reasons.append("Momentum burst")

    return score, reasons

def market_regime(df):
    expanding = df["%CHNG"].abs().mean()
    if expanding >= 0.5:
        return "Momentum"
    return "ORB"

# ================= MAIN =================
def main():
    now = datetime.now(IST)
    print(f"🕒 IST Time: {now}")

    if not os.path.exists(UNIVERSE_FILE):
        print("❌ Tradable universe missing")
        return

    df = pd.read_csv(UNIVERSE_FILE)
    print(f"📊 Symbols to scan: {len(df)}")

    sent = set()
    if os.path.exists(STATE_FILE):
        sent = set(pd.read_csv(STATE_FILE)["SYMBOL"])

    mode = market_regime(df)
    print(f"🧠 Market Mode: {mode}")

    alerts = []

    for _, r in df.iterrows():
        sym = r["SYMBOL"]
        if sym in sent:
            continue

        move = float(r.get("%CHNG", 0))
        vol = float(r.get("VOLUME", 0))
        avg_vol = float(r.get("AVG_VOLUME", vol / 2))
        vol_mult = vol / avg_vol if avg_vol > 0 else 0
        rs = float(r.get("RS", move))

        if mode == "Momentum":
            if abs(move) < MIN_MOVE or vol_mult < MIN_VOL_MULT or abs(rs) < RS_THRESHOLD:
                continue
        else:
            if abs(move) < ORB_MOVE or vol_mult < ORB_VOL_MULT:
                continue

        conf, reasons = confidence(abs(move), vol_mult, abs(rs), mode)
        if conf < CONF_THRESHOLD:
            continue

        side = "BUY" if move > 0 else "SELL"

        msg = (
            f"🚨 Intraday Trade Alert\n\n"
            f"{sym}\n"
            f"Mode: {mode}\n"
            f"Side: {side}\n"
            f"Move: {move:.2f}%\n"
            f"Vol x: {vol_mult:.2f}\n"
            f"RS: {rs:.2f}\n"
            f"Confidence: {conf}\n"
            f"Reason: {', '.join(reasons)}"
        )

        send(msg)
        alerts.append(sym)

    if alerts:
        pd.DataFrame({"SYMBOL": alerts}).to_csv(STATE_FILE, index=False)
        print(f"✅ Alerts sent: {len(alerts)}")
    else:
        print("ℹ️ No qualified intraday signals in this run")

if __name__ == "__main__":
    main()