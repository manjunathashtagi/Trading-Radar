import sys
import os

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
import pandas as pd
from datetime import datetime
from alerts.telegram_alerts import send_alert

df = pd.read_csv("data/signals.csv")
df["time"] = pd.to_datetime(df["time"])

today = datetime.now().date()
today_df = df[df["time"].dt.date == today]

if today_df.empty:
    send_alert("📊 <b>EOD REPORT</b>\nNo signals today.")
else:
    send_alert(
        f"📊 <b>EOD REPORT</b>\n"
        f"Date: {today}\n"
        f"Signals: {len(today_df)}"
    )
