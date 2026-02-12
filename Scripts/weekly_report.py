import sys
import os
import pandas as pd
from datetime import datetime
import pytz

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from alerts.telegram_alerts import send_alert


SIGNALS_FILE = "data/signals.csv"


def main():

    if not os.path.exists(SIGNALS_FILE):
        print("No signals file found.")
        return

    df = pd.read_csv(SIGNALS_FILE)

    if df.empty:
        print("No signals available.")
        return

    # Filter current week
    df["date"] = pd.to_datetime(df["date"])
    today = pd.Timestamp.today()
    start_week = today - pd.Timedelta(days=today.weekday())
    weekly_df = df[df["date"] >= start_week]

    if weekly_df.empty:
        print("No weekly signals.")
        return

    total = len(weekly_df)

    target_hit = len(weekly_df[weekly_df["result"] == "🎯 TARGET HIT"])
    sl_hit = len(weekly_df[weekly_df["result"] == "❌ SL HIT"])
    open_trades = len(weekly_df[weekly_df["result"] == "⏳ STILL OPEN"])

    win_rate = round((target_hit / total) * 100, 2) if total > 0 else 0

    ist = pytz.timezone("Asia/Kolkata")
    current_time = datetime.now(ist).strftime("%H:%M")

    message = (
        f"📅 <b>WEEKLY PERFORMANCE REPORT</b> | {current_time}\n\n"
        f"Total Signals: {total}\n"
        f"🎯 Target Hit: {target_hit}\n"
        f"❌ SL Hit: {sl_hit}\n"
        f"⏳ Still Open: {open_trades}\n\n"
        f"Win Rate: {win_rate}%\n"
    )

    send_alert(message)


if __name__ == "__main__":
    main()