import pandas as pd
import datetime
import os
import shutil
import requests

BASE_UNIVERSE = "data/universe_nse.csv"
OUTPUT_UNIVERSE = "data/universe_nse_tradable.csv"

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

    os.makedirs("data", exist_ok=True)

    if not os.path.exists(BASE_UNIVERSE):
        raise RuntimeError("❌ Base universe missing")

    df = pd.read_csv(BASE_UNIVERSE)
    print(f"📊 Total symbols to scan: {len(df)}")

    tradable = []

    for _, row in df.iterrows():
        try:
            pct = float(row.get("%CHNG", 0))
            if abs(pct) >= 2:
                tradable.append({
                    "symbol": row["SYMBOL"],
                    "prev_day_change_pct": pct
                })
        except Exception:
            continue

    tradable_df = pd.DataFrame(tradable)

    if tradable_df.empty:
        print("⚠️ No tradable stocks → using full universe")
        shutil.copy(BASE_UNIVERSE, OUTPUT_UNIVERSE)
        used = "fallback universe"
    else:
        tradable_df.to_csv(OUTPUT_UNIVERSE, index=False)
        used = f"{len(tradable_df)} tradable stocks"

    send_telegram(
        f"📊 Premarket Radar\n"
        f"Scanned: {len(df)} stocks\n"
        f"Universe used: {used}"
    )

    print("✅ Premarket completed")

if __name__ == "__main__":
    main()