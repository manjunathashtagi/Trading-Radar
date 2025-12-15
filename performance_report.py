#!/usr/bin/env python3
"""
performance_report.py
Weekly / Monthly performance analytics
"""

import json, os, csv
from datetime import datetime, timedelta

TRADES_FILE = "trades_store.json"
ARTIFACTS = "artifacts"

def load_trades():
    if not os.path.isfile(TRADES_FILE):
        return []
    with open(TRADES_FILE) as f:
        return json.load(f)

def main(days=7):
    os.makedirs(ARTIFACTS, exist_ok=True)
    trades = load_trades()

    cutoff = datetime.utcnow() - timedelta(days=days)
    closed = []

    for t in trades:
        if t.get("status") == "CLOSED":
            ct = datetime.fromisoformat(t.get("eod_checked_at"))
            if ct >= cutoff:
                closed.append(t)

    wins = losses = 0
    r_total = 0

    for t in closed:
        risk = t["entry"] - t["sl"]
        reward = (t.get("exit_price", t["entry"]) - t["entry"])
        r = reward / risk if risk > 0 else 0
        r_total += r
        if r > 0:
            wins += 1
        else:
            losses += 1

    total = wins + losses
    winrate = (wins / total * 100) if total else 0
    expectancy = (r_total / total) if total else 0

    fname = f"{ARTIFACTS}/performance_{days}d.csv"
    with open(fname, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Metric", "Value"])
        w.writerow(["Trades", total])
        w.writerow(["Win Rate %", round(winrate,2)])
        w.writerow(["Expectancy (R)", round(expectancy,2)])

    print("Saved:", fname)

if __name__ == "__main__":
    main(7)
