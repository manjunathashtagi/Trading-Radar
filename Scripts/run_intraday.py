import sys
import os
import pandas as pd
from datetime import datetime

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from scanners.intraday_scanner import scan_intraday
from alerts.telegram_alerts import send_alert

CACHE_FILE = "data/stage1_cache.csv"
ALERT_LOG_FILE = "data/alerted_today.csv"
READY_LOG_FILE = "data/stage1_ready_sent.txt"


def load_stage1_watchlist():
    if not os.path.exists(CACHE_FILE):
        return pd.DataFrame()

    df = pd.read_csv(CACHE_FILE)
    today = datetime.now().date()

    if "date" in df.columns:
        df = df[pd.to_datetime(df["date"]).dt.date == today]

    return df


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
    print(f"Scanning {len(stage1_df)} stocks...")

def send_stage1_ready_once(count):
    today = str(datetime.now().date())
    if os.path.exists(READY_LOG_FILE):
        with open(READY_LOG_FILE, "r") as f:
            if f.read().strip() == today:
                return

    send_alert(f"📡 Stage-1 ready | {count} stocks")
    with open(READY_LOG_FILE, "w") as f:
        f.write(today)


def main():
    stage1_df = load_stage1_watchlist()

    if stage1_df.empty:
        return

    send_stage1_ready_once(len(stage1_df))

    alerted_symbols = load_alerted_symbols()

    for _, row in stage1_df.iterrows():
        symbol = row["symbol"]

        if symbol in alerted_symbols:
            continue

        signal = scan_intraday(symbol)

        if signal and signal["action"] in ["BUY", "SELL"]:

            message = (
                f"🚨 <b>{signal['action']} SIGNAL</b>\n\n"
                f"Stock: <b>{symbol}</b>\n"
                f"Sector: {signal['sector']}\n"
                f"{signal['gap_tag']}: {signal['gap']}%\n\n"
                f"Entry: {round(signal['entry'], 2)}\n"
                f"SL: {round(signal['sl'], 2)} ({signal['sl_percent']}%)\n"
                f"Target: {round(signal['tp'], 2)}\n"
                f"RR: 1:{signal['rr']}\n"
                f"Confidence: {signal['confidence']}%\n\n"
                f"Time: {datetime.now().strftime('%H:%M')}"
            )

            send_alert(message)
            save_alerted_symbol(symbol)


if __name__ == "__main__":
    main()