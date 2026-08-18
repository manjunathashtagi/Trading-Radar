"""
Factor audit for Trading Radar.

Buckets closed trades (TARGET/SL) into quintiles per feature and reports win
rate per bucket. Run this periodically -- weekly is reasonable -- to check
whether trend/momentum/volume/rsi/score are actually predictive, instead of
assuming the score formula or filter thresholds are working.

This is descriptive analysis of PAST trades, not a forecast. A feature that
looks predictive here can stop being predictive once the entry logic changes
(e.g. after the score_signal / breakout-confirmation patch), since the mix of
signals that fire will shift. Re-run this after enough new trades accumulate
under any rule change -- don't assume the old buckets still hold.

Usage:
    python factor_audit.py [path/to/signals.csv]

If TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID are set (same env vars as the other
scripts), the summary is also sent to Telegram; otherwise it just prints.
"""
import os
import sys
import requests
import pandas as pd

SIGNAL_FILE = sys.argv[1] if len(sys.argv) > 1 else "data/signals.csv"
FEATURES = ["trend", "momentum", "volume", "rsi", "score"]
N_BUCKETS = 5

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")


def send(msg):
    print(msg)
    if not TOKEN or not CHAT_ID:
        return
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{TOKEN}/sendMessage",
            data={"chat_id": CHAT_ID, "text": msg},
            timeout=10
        )
        if r.status_code != 200:
            print(f"Telegram error: {r.status_code} {r.text}")
    except Exception as e:
        print(f"Telegram exception: {e}")


def main():
    df = pd.read_csv(SIGNAL_FILE)
    closed = df[df["result"].isin(["TARGET", "SL"])].copy()
    if closed.empty:
        send("📐 Factor Audit\nNo closed trades (TARGET/SL) found.")
        return

    closed["win"] = (closed["result"] == "TARGET").astype(int)
    overall_wr = closed["win"].mean() * 100
    lines = [f"📐 FACTOR AUDIT — {len(closed)} closed trades, {overall_wr:.1f}% overall WR\n"]

    for col in FEATURES:
        if col not in closed.columns:
            continue
        closed[col] = pd.to_numeric(closed[col], errors="coerce")
        d = closed.dropna(subset=[col]).copy()
        if len(d) < N_BUCKETS * 10:
            continue
        try:
            d["bucket"] = pd.qcut(d[col], N_BUCKETS, duplicates="drop")
        except Exception:
            continue

        g = d.groupby("bucket", observed=True)["win"].agg(["mean", "count"])
        spread = (g["mean"].max() - g["mean"].min()) * 100
        direction = "low=better" if g["mean"].idxmax() == g.index[0] else \
                    "high=better" if g["mean"].idxmax() == g.index[-1] else "mixed"
        lines.append(f"{col}: spread {spread:.1f}pts ({direction})")
        for idx, row in g.iterrows():
            lines.append(f"  {row['mean']*100:.1f}% (n={int(row['count'])})")

    send("\n".join(lines))


if __name__ == "__main__":
    main()
