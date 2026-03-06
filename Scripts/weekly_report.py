import os
import sys
import pandas as pd
from datetime import datetime

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from alerts.telegram_alerts import send_alert

SIGNALS_FILE = "data/signals.csv"


def main():

    if not os.path.exists(SIGNALS_FILE):
        send_alert("📅 WEEKLY REPORT\nNo signals file found.")
        return

    df = pd.read_csv(SIGNALS_FILE)

    if df.empty:
        send_alert("📅 WEEKLY REPORT\nNo signals recorded.")
        return

    # Convert to pure date (no timezone)
    df["date"] = pd.to_datetime(df["date"]).dt.date

    today = datetime.today().date()

    # Monday of current week
    start_week = today - pd.Timedelta(days=today.weekday())

    df["date"] = pd.to_datetime(df["date"]).dt.tz_localize(None)
    start_week = pd.Timestamp.today().normalize() - pd.Timedelta(days=pd.Timestamp.today().weekday())

    weekly_df = df[df["date"] >= start_week]

    if weekly_df.empty:
        send_alert("📅 WEEKLY REPORT\nNo signals this week.")
        return

    total = len(weekly_df)
    wins = len(weekly_df[weekly_df["result"] == "🎯 TARGET HIT"])
    losses = len(weekly_df[weekly_df["result"] == "❌ SL HIT"])
    open_trades = len(weekly_df[weekly_df["result"] == "⏳ OPEN"])

    win_rate = round((wins / total) * 100, 2) if total > 0 else 0

    message = (
        f"📅 <b>WEEKLY PERFORMANCE REPORT</b>\n\n"
        f"Total Signals: {total}\n"
        f"🎯 Wins: {wins}\n"
        f"❌ Losses: {losses}\n"
        f"⏳ Open: {open_trades}\n\n"
        f"Win Rate: {win_rate}%"
    )

    send_alert(message)


if __name__ == "__main__":
    main()