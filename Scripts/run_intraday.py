import sys
import os
import pandas as pd
from datetime import datetime

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from scanners.intraday_scanner import scan_bulk
from alerts.telegram_alerts import send_alert

CACHE_FILE = "data/stage1_cache.csv"
ALERT_LOG_FILE = "data/alerted_today.csv"
READY_LOG_FILE = "data/stage1_ready_sent.txt"


def load_stage1_watchlist():
    if not os.path.exists(CACHE_FILE):
        return []

    df = pd.read_csv(CACHE_FILE)
    today = datetime.now().date()

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
    stage1_symbols = load_stage1_watchlist()

    if not stage1_symbols:
        print("No Stage-1 symbols found.")
        return

    print(f"Bulk scanning {len(stage1_symbols)} stocks...")
    send_stage1_ready_once(len(stage1_symbols))

    alerted_symbols = load_alerted_symbols()

    signals = scan_bulk(stage1_symbols)

    # Remove already alerted stocks
    new_signals = [s for s in signals if s["symbol"] not in alerted_symbols]

    if not new_signals:
        print("No new signals.")
        return

    # Save alerted symbols
    for s in new_signals:
        save_alerted_symbol(s["symbol"])

    # --- Combined Telegram Message ---
    message = f"🚨 <b>INTRADAY SIGNALS ({len(new_signals)})</b>\n\n"

    for s in new_signals:
        message += (
            f"<b>{s['action']} | {s['symbol']}</b>\n"
            f"Sector: {s['sector']}\n"
            f"{s['gap_tag']}: {s['gap']}%\n"
            f"Entry: {round(s['entry'],2)} | "
            f"SL: {round(s['sl'],2)} ({s['sl_percent']}%) | "
            f"Target: {round(s['tp'],2)} | "
            f"RR: 1:{s['rr']} | "
            f"Conf: {s['confidence']}%\n\n"
        )

    message += f"Time: {datetime.now().strftime('%H:%M')}"

    send_alert(message)


if __name__ == "__main__":
    main()