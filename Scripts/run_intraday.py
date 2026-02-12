import sys
import os
import pandas as pd
from datetime import datetime
import pytz

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from scanners.intraday_scanner import scan_bulk
from alerts.telegram_alerts import send_alert

CACHE_FILE = "data/stage1_cache.csv"
ALERT_LOG_FILE = "data/alerted_today.csv"


def load_stage1_watchlist():
    if not os.path.exists(CACHE_FILE):
        return []

    df = pd.read_csv(CACHE_FILE)
    today = datetime.now(pytz.timezone("Asia/Kolkata")).date()

    if "date" in df.columns:
        df = df[pd.to_datetime(df["date"]).dt.date == today]

    return df["symbol"].tolist()


def load_alerted_symbols():
    if os.path.exists(ALERT_LOG_FILE):
        return set(pd.read_csv(ALERT_LOG_FILE)["symbol"])
    return set()


def save_alerted_symbol(symbol):
    df = pd.DataFrame([[symbol]], columns=["symbol"])
    if os.path.exists(ALERT_LOG_FILE):
        df.to_csv(ALERT_LOG_FILE, mode="a", header=False, index=False)
    else:
        df.to_csv(ALERT_LOG_FILE, index=False)


def main():

    ist = pytz.timezone("Asia/Kolkata")
    current_time = datetime.now(ist).strftime("%H:%M")

    stage1_symbols = load_stage1_watchlist()

    if not stage1_symbols:
        print("No Stage-1 symbols found.")
        return

    print(f"Bulk scanning {len(stage1_symbols)} stocks...")

    alerted_symbols = load_alerted_symbols()

    signals = scan_bulk(stage1_symbols)

    new_signals = [s for s in signals if s["symbol"] not in alerted_symbols]

    if not new_signals:
        print("No new signals.")
        return

    # Save alerted
    for s in new_signals:
        save_alerted_symbol(s["symbol"])

    # Sort by confidence
    new_signals = sorted(new_signals, key=lambda x: x["confidence"], reverse=True)

    buy_signals = [s for s in new_signals if s["action"] == "BUY"][:5]
    sell_signals = [s for s in new_signals if s["action"] == "SELL"][:5]

    # -------- BUY MESSAGE --------
    if buy_signals:
        buy_message = f"🟢 <b>BUY SIGNALS</b> | {current_time}\n\n"
        for s in buy_signals:
            buy_message += (
                f"<b>{s['symbol']}</b>\n"
                f"Entry: {round(s['entry'],2)} | "
                f"SL: {round(s['sl'],2)} | "
                f"Target: {round(s['tp'],2)} | "
                f"RR 1:{s['rr']}\n"
                f"{s['gap_tag']}: {s['gap']}% | "
                f"Conf {s['confidence']}%\n\n"
            )
        send_alert(buy_message)

    # -------- SELL MESSAGE --------
    if sell_signals:
        sell_message = f"🔴 <b>SELL SIGNALS</b> | {current_time}\n\n"
        for s in sell_signals:
            sell_message += (
                f"<b>{s['symbol']}</b>\n"
                f"Entry: {round(s['entry'],2)} | "
                f"SL: {round(s['sl'],2)} | "
                f"Target: {round(s['tp'],2)} | "
                f"RR 1:{s['rr']}\n"
                f"{s['gap_tag']}: {s['gap']}% | "
                f"Conf {s['confidence']}%\n\n"
            )
        send_alert(sell_message)


if __name__ == "__main__":
    main()