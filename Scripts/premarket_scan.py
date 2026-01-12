import pandas as pd
import datetime
import os
import requests

UNIVERSE_OUT = "data/universe_nse_tradable.csv"

def send_telegram(msg):
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    requests.post(url, data={"chat_id": chat_id, "text": msg})

def main():
    start = datetime.datetime.now()
    print(f"🚀 Premarket scan started at {start}")

    # 👇 TEMP universe (replace with full NSE later)
    df = pd.read_csv("data/universe_nse.csv")

    tradable = []
    for _, row in df.iterrows():
        change = float(row.get("%CHNG", 0))
        if abs(change) >= 2:
            tradable.append({
                "symbol": row["SYMBOL"],
                "prev_day_change_pct": change
            })

    tradable_df = pd.DataFrame(tradable)
    os.makedirs("data", exist_ok=True)
    tradable_df.to_csv(UNIVERSE_OUT, index=False)

    send_telegram(
        f"📊 Premarket Radar\n"
        f"Total symbols scanned: {len(df)}\n"
        f"Tradable universe: {len(tradable_df)}"
    )

    print("✅ Premarket scan completed")

if __name__ == "__main__":
    main()