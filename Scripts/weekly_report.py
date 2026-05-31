import os
import sys
import pandas as pd
from datetime import datetime, timedelta

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from alerts.telegram_alerts import send_alert

SIGNALS_FILE = "data/signals.csv"

def main():
    today = datetime.today().date()
    period_label = "Weekly"
    days_back = 7

    # Support monthly report via env flag
    if os.getenv("REPORT_TYPE", "weekly").lower() == "monthly":
        days_back = 30
        period_label = "Monthly"

    start_date = today - timedelta(days=days_back)

    if not os.path.exists(SIGNALS_FILE):
        send_alert(f"📅 {period_label.upper()} REPORT\nNo signals file found.")
        return

    try:
        df = pd.read_csv(SIGNALS_FILE)
    except Exception as e:
        send_alert(f"📅 {period_label.upper()} REPORT\nError reading signals: {e}")
        return

    if df.empty:
        send_alert(f"📅 {period_label.upper()} REPORT\nNo signals recorded.")
        return

    # Normalise date column
    df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.date
    df = df.dropna(subset=["date"])

    period_df = df[df["date"] >= start_date]

    if period_df.empty:
        send_alert(f"📅 {period_label.upper()} REPORT\nNo signals in the last {days_back} days.")
        return

    total = len(period_df)
    wins = len(period_df[period_df["result"] == "TARGET"])
    losses = len(period_df[period_df["result"] == "SL"])
    open_trades = len(period_df[~period_df["result"].isin(["TARGET", "SL"])])
    closed = wins + losses

    win_rate = round((wins / closed * 100), 1) if closed > 0 else 0.0

    # Best performing stock
    best = ""
    if wins > 0:
        target_df = period_df[period_df["result"] == "TARGET"]
        symbol_col = "symbol" if "symbol" in target_df.columns else "stock"
        if symbol_col in target_df.columns:
            best_row = target_df.sort_values("score", ascending=False).iloc[0]
            best = f"\n🏆 Best Signal: {best_row[symbol_col]} (Score: {best_row.get('score', 'N/A')})"

    # Daily breakdown
    daily = period_df.groupby("date").apply(
        lambda x: pd.Series({
            "signals": len(x),
            "wins": (x["result"] == "TARGET").sum(),
            "losses": (x["result"] == "SL").sum()
        })
    ).reset_index()

    # Build daily table (last 7 days max in message)
    daily_lines = ""
    for _, row in daily.tail(7).iterrows():
        d = str(row["date"])
        w = int(row["wins"])
        l = int(row["losses"])
        s = int(row["signals"])
        daily_lines += f"  {d}: {s} signals | ✅{w} ❌{l}\n"

    message = (
        f"📅 {period_label.upper()} PERFORMANCE REPORT\n"
        f"Period: {start_date} → {today}\n\n"
        f"Total Signals: {total}\n"
        f"✅ Wins:   {wins}\n"
        f"❌ Losses: {losses}\n"
        f"⏳ Open:   {open_trades}\n"
        f"Win Rate: {win_rate}% (of {closed} closed){best}\n\n"
        f"Daily Breakdown:\n{daily_lines}"
    )

    send_alert(message)
    print(f"✅ {period_label} report sent.")

if __name__ == "__main__":
    main()
