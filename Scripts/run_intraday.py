import sys, os
sys.path.insert(0, os.path.abspath(""))

import pandas as pd
from datetime import datetime
from alerts.telegram_alerts import send_alert
from data_feed.nse_fetcher import fetch_nse_ohlc
from data_feed.nse_universe import get_all_nse_symbols
from data_feed.stage1_filter import stage1_shortlist
from analytics.sector_strength import sector_strength
from scanners.intraday_scanner import scan_intraday
from analytics.trade_tracker import check_trade

os.makedirs("data", exist_ok=True)

try:
    trades = pd.read_csv("data/signals.csv")
except:
    trades = pd.DataFrame(columns=["time","symbol","signal","price","sl","tp","status","confidence"])

# ---- STAGE 1 ----
universe = get_all_nse_symbols()
stage1 = stage1_shortlist(universe)
sectors = sector_strength(stage1)

send_alert(f"📡 Stage-1 ready | {len(stage1)} stocks")

today = datetime.now().date()
alerted = set(trades[pd.to_datetime(trades["time"]).dt.date == today]["symbol"])

# ---- STAGE 2 ----
for _, row in stage1.iterrows():
    sym = row["symbol"]
    if sym in alerted:
        continue

    df = fetch_nse_ohlc(sym)
    if df.empty:
        continue

    res = scan_intraday(df, sector_bonus=10)
    if not res:
        continue

    side, price, atr, conf = res
    sl = price - atr if side == "BUY" else price + atr
    tp = price + 2*atr if side == "BUY" else price - 2*atr

    send_alert(
        f"🚨 <b>{side}</b> {sym}\n"
        f"Price: {round(price,2)}\n"
        f"Confidence: {conf}%\n"
        f"SL: {round(sl,2)} | TP: {round(tp,2)}"
    )

    trades.loc[len(trades)] = [
        datetime.now(), sym, side, price, sl, tp, "OPEN", conf
    ]

# ---- TRACK OPEN TRADES ----
for i, r in trades[trades["status"]=="OPEN"].iterrows():
    df = fetch_nse_ohlc(r["symbol"])
    if df.empty:
        continue
    status = check_trade(r, df["close"].iloc[-1])
    if status != "OPEN":
        trades.at[i,"status"] = status
        send_alert(f"📌 {r['symbol']} {status}")

trades.to_csv("data/signals.csv", index=False)
