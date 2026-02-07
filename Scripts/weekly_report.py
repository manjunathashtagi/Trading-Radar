import pandas as pd
from datetime import datetime, timedelta
from alerts.telegram_alerts import send_alert

df = pd.read_csv("data/signals.csv")
df["time"] = pd.to_datetime(df["time"])

week_df = df[df["time"] >= datetime.now() - timedelta(days=7)]

send_alert(
    f"📊 <b>WEEKLY REPORT</b>\n"
    f"Total signals: {len(week_df)}"
)
