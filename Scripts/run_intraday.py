import sys
import os
import pandas as pd
from datetime import datetime

# Ensure project root in path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from scanners.intraday_scanner import scan_intraday
from alerts.telegram_alerts import send_alert

CACHE_FILE = "data/stage1_cache.csv"
ALERT_LOG_FILE = "data/alerted_today.csv"


def load_stage1_watchlist():
    if not os.path.exists(CACHE_FILE):
        print("No Stage-1 cache found.")
        return pd.DataFrame()

    df = pd.read_csv(CACHE_FILE)

    # Ensure today's data only
    today = datetime.now().date()
    df = df[pd.to_datetime(df["date"]).dt.date == today]

    return df


def load_alerted_symbols():
    if os.path.exists(ALERT_LOG_FILE):
        df = pd.read_csv(ALERT_LOG_FILE)
        return set(df["symbol"])
    return set()


def save_alerted_symbol(symbol):
    df = pd.DataFrame([[symbol]], columns=["symbol"])
    if os.path.exists(ALERT_LOG_FILE):
        df.to_csv(ALERT_LOG_FILE, mode="a", header=False, index=False)
    else:
        df.to_csv(ALERT_LOG_FILE, index=False)


def main():
    stage1_df = load_stage1_watchlist()

    if stage1_df.empty:
        print("Stage-1 list empty. Nothing to scan.")
        return

    send_alert(f"📡 Stage-1 ready | {len(stage1_df)} stocks")

    alerted_symbols = load_alerted_symbols()

    for _, row in stage1_df.iterrows():
        symbol = row["symbol"]

        if symbol in alerted_symbols:
            continue  # Avoid repeat alerts same day

        try:
            signal = scan_intraday(symbol)

            if signal and signal.get("action") in ["BUY", "SELL"]:
                message = (
                    f"🚨 <b>{signal['action']} SIGNAL</b>\n"
                    f"Stock: {symbol}\n"
                    f"Entry: {signal['entry']}\n"
                    f"SL: {signal['sl']}\n"
                    f"TP: {signal['tp']}\n"
                    f"Confidence: {signal.get('confidence', 0)}%"
                )

                send_alert(message)
                save_alerted_symbol(symbol)

        except Exception as e:
            print(f"Error scanning {symbol}: {e}")


if __name__ == "__main__":
    main()