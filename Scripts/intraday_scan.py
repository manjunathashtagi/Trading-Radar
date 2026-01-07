import pandas as pd
import yfinance as yf
import requests
import os
from datetime import datetime, time, timezone, timedelta

# ---------------- CONFIG ----------------
UNIVERSE_FILE = "data/universe_nse.csv"
TRADES_FILE = "data/trades_today.csv"

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

MIN_CONFIDENCE = 70
MAX_ALERTS_PER_RUN = 3
VOLUME_MULTIPLIER = 1.3

MARKET_OPEN = time(9, 15)
MARKET_CLOSE = time(15, 15)

IST = timezone(timedelta(hours=5, minutes=30))
# ---------------------------------------


def send_telegram(message: str):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    requests.post(url, data={
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }, timeout=10)


def market_is_open():
    return MARKET_OPEN <= datetime.now(IST).time() <= MARKET_CLOSE


def detect_speed(candle_range_pct, volume_ratio):
    if candle_range_pct > 1.2 and volume_ratio > 1.8:
        return "⚡ Fast"
    elif candle_range_pct > 0.7:
        return "⏳ Normal"
    else:
        return "🐢 Slow"


def main():
    if not market_is_open():
        print("Market closed.")
        return

    universe = pd.read_csv(UNIVERSE_FILE)
    symbols = universe["symbol"].dropna().unique().tolist()

    os.makedirs("data", exist_ok=True)

    if not os.path.exists(TRADES_FILE):
        pd.DataFrame(columns=[
            "symbol", "entry", "sl", "target",
            "confidence", "speed", "alert_time", "status"
        ]).to_csv(TRADES_FILE, index=False)

    trades_df = pd.read_csv(TRADES_FILE)

    alerts = []

    for symbol in symbols:
        try:
            df = yf.Ticker(symbol + ".NS").history(period="1d", interval="5m")
            if df.empty or len(df) < 6:
                continue

            orb_high = df["High"].iloc[:3].max()
            orb_low = df["Low"].iloc[:3].min()
            last = df.iloc[-1]

            if last["Close"] <= orb_high:
                continue

            avg_vol = df["Volume"].mean()
            vol_ratio = last["Volume"] / avg_vol if avg_vol > 0 else 0

            if vol_ratio < VOLUME_MULTIPLIER:
                continue

            candle_range_pct = ((last["High"] - last["Low"]) / last["Low"]) * 100
            speed = detect_speed(candle_range_pct, vol_ratio)

            confidence = 50 + 15 + 15
            if confidence < MIN_CONFIDENCE:
                continue

            entry = round(last["Close"], 2)
            sl = round(orb_low, 2)
            target = round(entry * 1.02, 2)

            alerts.append({
                "symbol": symbol,
                "entry": entry,
                "sl": sl,
                "target": target,
                "confidence": confidence,
                "speed": speed,
                "alert_time": datetime.now(IST).strftime("%H:%M"),
                "status": "OPEN"
            })

            if len(alerts) >= MAX_ALERTS_PER_RUN:
                break

        except Exception:
            continue

    if not alerts:
        print("No intraday signals.")
        return

    new_trades = pd.DataFrame(alerts)
    new_trades.to_csv(TRADES_FILE, mode="a", header=False, index=False)

    msg = "*🚨 Intraday Trade Alerts*\n\n"
    for t in alerts:
        msg += (
            f"*{t['symbol']}*\n"
            f"Entry: {t['entry']} | SL: {t['sl']} | Target: {t['target']}\n"
            f"Confidence: {t['confidence']} | Speed: {t['speed']}\n\n"
        )

    send_telegram(msg)
    print("Intraday alerts sent.")


if __name__ == "__main__":
    main()