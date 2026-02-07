import sys, os
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, PROJECT_ROOT)

import pandas as pd
from datetime import datetime
from alerts.telegram_alerts import send_alert
from scanners.intraday_scanner import scan_intraday
from data_feed.nse_fetcher import fetch_nse_ohlc
from data_feed.nse_universe import get_all_nse_symbols
from data_feed.stage1_filter import stage1_shortlist

DATA_FILE = "data/signals.csv"
os.makedirs("data", exist_ok=True)

today = datetime.now().date()
already_alerted = set(
    signals_df[
        pd.to_datetime(signals_df["time"]).dt.date == today
    ]["symbol"].tolist()
)

if symbol in already_alerted:
    continue

if not os.path.exists(DATA_FILE):
    pd.DataFrame(columns=["time", "symbol", "signal", "price"]).to_csv(DATA_FILE, index=False)

signals_df = pd.read_csv(DATA_FILE)

# -------- STAGE 1 (ONCE PER DAY) --------
universe_df = get_all_nse_symbols()
shortlist = stage1_shortlist(universe_df)

send_alert(
    f"📡 Stage-1 (cached)\n"
    f"Shortlisted stocks: {len(shortlist)}"
)

# -------- STAGE 2 --------
for symbol in shortlist:
    df = fetch_nse_ohlc(symbol)
    if df.empty:
        continue

    result = scan_intraday(symbol, df)
    if result:
        side, price = result

        send_alert(
            f"🚨 <b>{side} SIGNAL</b>\n"
            f"Stock: {symbol}\n"
            f"Price: {round(price,2)}\n"
            f"TF: 15m\n"
            f"Strategy: Alpha"
        )

        signals_df.loc[len(signals_df)] = [
            datetime.now(), symbol, side, price
        ]

signals_df.to_csv(DATA_FILE, index=False)
