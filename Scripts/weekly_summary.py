import pandas as pd
import glob
import os
import requests

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

def send_telegram(msg):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": msg})

def main():
    files = sorted(glob.glob("reports/eod/eod_report_*.csv"))[-5:]

    if not files:
        send_telegram("📊 WEEKLY RADAR SUMMARY\n\nNo EOD reports found this week.")
        return

    all_data = []

    for f in files:
        df = pd.read_csv(f)
        df["date"] = os.path.basename(f).replace("eod_report_", "").replace(".csv", "")
        all_data.append(df)

    data = pd.concat(all_data, ignore_index=True)

    total = len(data)
    hits = (data["target_hit"] == "YES").sum()
    hit_rate = round((hits / total) * 100, 2) if total else 0

    bucket_stats = (
        data.groupby("bucket")["target_hit"]
        .value_counts()
        .unstack(fill_value=0)
    )

    msg = (
        f"📊 WEEKLY RADAR SUMMARY\n\n"
        f"Trades: {total}\n"
        f"Targets Hit: {hits}\n"
        f"Hit Rate: {hit_rate}%\n\n"
    )

    for bucket in bucket_stats.index:
        yes = bucket_stats.loc[bucket].get("YES", 0)
        no = bucket_stats.loc[bucket].get("NO", 0)
        msg += f"{bucket} → Hit: {yes}, Miss: {no}\n"

    send_telegram(msg)

if __name__ == "__main__":
    main()
