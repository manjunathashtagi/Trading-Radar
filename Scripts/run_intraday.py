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


# ----------------------------
# Load Stage-1 Watchlist
# ----------------------------
def load_stage1_watchlist():
    if not os.path.exists(CACHE_FILE):
        return []

    df = pd.read_csv(CACHE_FILE)
    today = datetime.now().date()

    if "date" in df.columns:
        df = df[pd.to_datetime(df["date"]).dt.date == today]

    return df["symbol"].tolist()


# ----------------------------
# Load Already Alerted Stocks
# ----------------------------
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


# ----------------------------
# MAIN
# ----------------------------
def main():

    stage1_symbols = load_stage1_watchlist()

    if not stage1_symbols:
        print("No Stage-1 symbols found.")
        return

    print(f"Bulk scanning {len(stage1_symbols)} stocks...")

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

    # Sort by confidence
    new_signals = sorted(new_signals, key=lambda x: x["confidence"], reverse=True)

    buy_signals = [s for s in new_signals if s["action"] == "BUY"]
    sell_signals = [s for s in new_signals if s["action"] == "SELL"]

    message = f"🚨 <b>INTRADAY SIGNALS</b> | {datetime.now().strftime('%H:%M')}\n\n"

    if buy_signals:
        message += f"🟢 <b>BUY SIGNALS ({len(buy_signals)})</b>\n\n"
        for s in buy_signals:
            message += (
                f"<b>{s['symbol']}</b>\n"
                f"Entry: {round(s['entry'],2)} | "
                f"SL: {round(s['sl'],2)} | "
                f"Target: {round(s['tp'],2)} | "
                f"RR 1:{s['rr']}\n"
                f"{s['gap_tag']}: {s['gap']}%\n\n"
            )

    if sell_signals:
        message += f"🔴 <b>SELL SIGNALS ({len(sell_signals)})</b>\n\n"
        for s in sell_signals:
            message += (
                f"<b>{s['symbol']}</b>\n"
                f"Entry: {round(s['entry'],2)} | "
                f"SL: {round(s['sl'],2)} | "
                f"Target: {round(s['tp'],2)} | "
                f"RR 1:{s['rr']}\n"
                f"{s['gap_tag']}: {s['gap']}%\n\n"
            )

    send_alert(message)


if __name__ == "__main__":
    main()