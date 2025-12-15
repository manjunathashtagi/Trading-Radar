#!/usr/bin/env python3
"""
eod_report_e2.py — Trade-aware End-of-Day Report

Evaluates OPEN trades from trades_store.json
Checks intraday high/low AFTER alert time
Marks TARGET HIT / SL HIT / OPEN / NO_DATA / NO_BARS
Saves CSV + sends Telegram summary
"""

from __future__ import annotations
import os
import json
import csv
from datetime import datetime, timezone
from typing import List, Dict
import requests
import yfinance as yf

# ---------------- CONFIG ----------------
TRADES_FILE = "trades_store.json"
ARTIFACTS_DIR = "artifacts"
TIMEFRAME = "5m"      # intraday resolution
LOOKBACK_DAYS = "2d"  # enough to cover alert → close

# ----------------------------------------

def ensure_dirs():
    os.makedirs(ARTIFACTS_DIR, exist_ok=True)

def load_trades() -> List[Dict]:
    if not os.path.isfile(TRADES_FILE):
        print("No trades_store.json found — skipping EOD")
        return []
    with open(TRADES_FILE, "r") as f:
        return json.load(f)

def save_trades(trades: List[Dict]):
    with open(TRADES_FILE, "w") as f:
        json.dump(trades, f, indent=2)

def telegram_send(text: str):
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat:
        return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    requests.post(url, json={"chat_id": chat, "text": text})

def fetch_intraday(ticker: str):
    df = yf.download(
    ticker,
    period=LOOKBACK_DAYS,
    interval=TIMEFRAME,
    auto_adjust=False,
    progress=False,
    threads=False,
    )
    return df if df is not None and not df.empty else None

def evaluate_trade(trade: Dict) -> Dict:
    df = fetch_intraday(trade["ticker"])
    if df is None:
        trade["eod_status"] = "NO_DATA"
        return trade

    alert_time = datetime.fromisoformat(trade["alert_time"]).replace(tzinfo=timezone.utc)
    df = df[df.index >= alert_time]

    if df.empty:
        trade["eod_status"] = "NO_BARS"
        return trade

    high = df["High"].max()
    low = df["Low"].min()

    target = trade.get("target1")
    sl = trade.get("sl")

    if target is None or sl is None:
        trade["eod_status"] = "INVALID_TRADE"
        trade["status"] = "CLOSED"
        trade["exit_price"] = None
        trade["eod_checked_at"] = datetime.utcnow().isoformat()
        return trade

    if high >= target:
        trade["eod_status"] = "TARGET HIT"
        trade["exit_price"] = target
        trade["status"] = "CLOSED"
    elif low <= sl:
        trade["eod_status"] = "SL HIT"
        trade["exit_price"] = sl
        trade["status"] = "CLOSED"
    else:
        trade["eod_status"] = "OPEN"


    trade["eod_checked_at"] = datetime.utcnow().isoformat()
    return trade

def main():
    ensure_dirs()
    trades = load_trades()
    if not trades:
        return

    updated = []
    rows = []

    # include all possible statuses
    stats = {
        "TARGET HIT": 0,
        "SL HIT": 0,
        "OPEN": 0,
        "NO_DATA": 0,
        "NO_BARS": 0,
    }

    for t in trades:
        if t.get("status") != "OPEN":
            updated.append(t)
            continue

        t = evaluate_trade(t)
        status = t.get("eod_status", "UNKNOWN")
        stats[status] = stats.get(status, 0) + 1

        if status in ("TARGET HIT", "SL HIT"):
            t["status"] = "CLOSED"

        rows.append([
            t["ticker"],
            t["entry"],
            t.get("target1"),
            t["sl"],
            status,
            t.get("exit_price"),
        ])


        updated.append(t)

    save_trades(updated)

    stamp = datetime.utcnow().strftime("%Y%m%d")
    out = f"{ARTIFACTS_DIR}/eod_report_{stamp}.csv"

    with open(out, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Ticker", "Entry", "Target", "SL", "Result", "Exit Price"])
        w.writerows(rows)

    print("Saved EOD report:", out)

    summary = (
        "📊 EOD TRADE REPORT\n\n"
        f"🎯 Target Hit: {stats['TARGET HIT']}\n"
        f"❌ SL Hit: {stats['SL HIT']}\n"
        f"⏳ Open: {stats['OPEN']}\n"
        f"📉 No Data: {stats['NO_DATA']}\n"
        f"📭 No Bars: {stats['NO_BARS']}\n"
        f"\nReport: {out}"
    )

    telegram_send(summary)

if __name__ == "__main__":
    main()
