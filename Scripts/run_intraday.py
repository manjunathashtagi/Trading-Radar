import sys
import os

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import pandas as pd
from datetime import datetime
from scanners.intraday_scanner import scan_intraday
from data_feed.nse_fetcher import fetch_nse_ohlc
from alerts.telegram_alerts import send_alert

SYMBOLS = ["RELIANCE", "ICICIBANK", "SBIN", "INFY"]
DATA_FILE = "data/signals.csv"

os.makedirs("data", exist_ok=True)

if not os.path.exists(DATA_FILE):
    pd.DataFrame(columns=[
        "time", "symbol", "signal", "price"
    ]).to_csv(DATA_FILE, index=False)

signals_df = pd.read_csv(DATA_FILE)

for symbol in SYMBOLS:
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
