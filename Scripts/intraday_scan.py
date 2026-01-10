import pandas as pd
import yfinance as yf
import requests
import os
from datetime import datetime, time, timezone, timedelta

UNIVERSE_FILE = "data/universe_nse_tradable.csv"
TRADES_FILE = "data/trades_today.csv"

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

MIN_CONFIDENCE = 70
MAX_ALERTS_PER_RUN = 3
VOLUME_MULTIPLIER = 1.3

MARKET_OPEN = time(9, 15)
MARKET_CLOSE = time(15, 15)
IST = timezone(timedelta(hours=5, minutes=30))


def market_is_open():
    return MARKET_OPEN <= datetime.now(IST).time() <= MARKET_CLOSE


def send_telegram(msg):
    if not TELEGRAM_BOT_TOKEN:
        return
    requests.post(
        f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
        data={"chat_id": TELEGRAM_CHAT_ID, "text": msg},
        timeout=10
    )


def main():
    if not market_is_open():
        print("Market closed")
        return

    os.makedirs("data", exist_ok=True)

    # Load existing ledger if exists
    if os.path.exists(TRADES_FILE):
        trades_df = pd.read_csv(TRADES_FILE)
        traded_symbols = set(trades_df["symbol"])
    else:
        trades_df = pd.DataFrame()
        traded_symbols = set()

    universe = pd.read_csv(UNIVERSE_FILE)
    alerts = []

    for symbol in universe["symbol"]:
        if symbol in traded_symbols:
            continue  # avoid duplicates same day

        try:
            df = yf.Ticker(symbol + ".NS").history(period="1d", interval="5m")
            if df.empty or len(df) < 6:
                continue

            orb_high = df["High"].iloc[:3].max()
            orb_low = df["Low"].iloc[:3].min()
            last = df.iloc[-1]

            if last["Close"] <= orb_high:
                continue

            vol_ratio = last["Volume"] / df["Volume"].mean()
            if vol_ratio < VOLUME_MULTIPLIER:
                continue

            confidence = 80
            entry = round(last["Close"], 2)
            sl = round(orb_low, 2)
            target = round(entry * 1.02, 2)

            alerts.append({
                "symbol": symbol,
                "entry": entry,
                "sl": sl,
                "target": target,
                "confidence": confidence,
                "time": datetime.now(IST).strftime("%H:%M"),
                "status": "OPEN"
            })

            if len(alerts) >= MAX_ALERTS_PER_RUN:
                break

        except Exception:
            continue

    if not alerts:
        print("No new intraday trades")
        return

    new_df = pd.DataFrame(alerts)
    final_df = pd.concat([trades_df, new_df], ignore_index=True)
    final_df.to_csv(TRADES_FILE, index=False)

    msg = "*🚨 Intraday Trades*\n\n"
    for a in alerts:
        msg += (
            f"{a['symbol']}\n"
            f"Entry {a['entry']} | SL {a['sl']} | TGT {a['target']}\n"
            f"Conf {a['confidence']} @ {a['time']}\n\n"
        )

    send_telegram(msg)
    print("Trades appended")


if __name__ == "__main__":
    main()
