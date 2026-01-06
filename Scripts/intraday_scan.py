import pandas as pd
import yfinance as yf
import requests
import os
from datetime import datetime, time

# ---------------- CONFIG ----------------
UNIVERSE_FILE = "data/universe_nse.csv"

NIFTY_SYMBOL = "^NSEI"

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

MIN_CONFIDENCE = 70          # relaxed from 80 (important)
MAX_ALERTS_PER_RUN = 3       # avoid spam
VOLUME_MULTIPLIER = 1.3      # reasonable, not too tight

MARKET_OPEN = time(9, 15)
MARKET_CLOSE = time(15, 15)

# ---------------------------------------


def send_telegram(message: str):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    try:
        requests.post(url, data=payload, timeout=10)
    except Exception as e:
        print("Telegram error:", e)


def market_is_open():
    now = datetime.now().time()
    return MARKET_OPEN <= now <= MARKET_CLOSE


def get_nifty_bias():
    try:
        df = yf.download(NIFTY_SYMBOL, period="1d", interval="5m", progress=False)
        if df.empty:
            return 0
        return 1 if df["Close"].iloc[-1] > df["Open"].iloc[0] else -1
    except:
        return 0


def main():
    if not market_is_open():
        print("Market closed. Exiting intraday scan.")
        return

    start_time = datetime.now()
    print("🚀 Intraday scan started at", start_time)

    universe = pd.read_csv(UNIVERSE_FILE)
    symbols = universe["symbol"].dropna().unique().tolist()

    print(f"📊 Scanning full universe: {len(symbols)} stocks")

    nifty_bias = get_nifty_bias()

    alerts = []
    scanned = 0
    passed_orb = 0

    for symbol in symbols:
        try:
            scanned += 1
            ticker = yf.Ticker(symbol + ".NS")

            df = ticker.history(period="1d", interval="5m")

            if df.empty or len(df) < 6:
                continue

            open_price = df["Open"].iloc[0]
            orb_high = df["High"].iloc[:3].max()
            orb_low = df["Low"].iloc[:3].min()

            last_close = df["Close"].iloc[-1]
            last_volume = df["Volume"].iloc[-1]
            avg_volume = df["Volume"].mean()

            breakout_up = last_close > orb_high
            breakout_down = last_close < orb_low

            if not breakout_up:
                continue

            passed_orb += 1

            if last_volume < avg_volume * VOLUME_MULTIPLIER:
                continue

            confidence = 50

            confidence += 15  # ORB breakout
            confidence += 15  # volume confirmation

            if nifty_bias > 0:
                confidence += 10

            if confidence < MIN_CONFIDENCE:
                continue

            entry = round(last_close, 2)
            stop_loss = round(orb_low, 2)
            target = round(entry * 1.02, 2)  # 2% default intraday

            alerts.append({
                "symbol": symbol,
                "entry": entry,
                "sl": stop_loss,
                "target": target,
                "confidence": confidence
            })

            if len(alerts) >= MAX_ALERTS_PER_RUN:
                break

        except Exception:
            continue

    if not alerts:
        print(
            f"No signals | Scanned: {scanned} | ORB passed: {passed_orb}"
        )
        return

    message = "*🚨 Intraday Trade Alerts (Full Market Scan)*\n\n"

    for a in alerts:
        message += (
            f"*{a['symbol']}*\n"
            f"Entry: {a['entry']}\n"
            f"SL: {a['sl']}\n"
            f"Target: {a['target']}\n"
            f"Confidence: {a['confidence']}\n\n"
        )

    send_telegram(message)

    print("✅ Intraday alerts sent")
    print("⏱️ Duration:", datetime.now() - start_time)


if __name__ == "__main__":
    main()