import pandas as pd
import datetime
import os
import shutil
import requests

# OUTPUT FILES
OUTPUT_UNIVERSE = "data/universe_nse_tradable.csv"
FALLBACK_UNIVERSE = "data/universe_nse.csv"   # existing 749 universe

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

    # Load base universe (749 for now – stable fallback)
    if not os.path.exists(FALLBACK_UNIVERSE):
        raise RuntimeError("❌ Base universe missing")

    df = pd.read_csv(FALLBACK_UNIVERSE)
    print(f"📊 Total symbols to scan: {len(df)}")

    tradable = []

    for _, row in df.iterrows():
        try:
            change = float(row.get("%CHNG", 0))
            if abs(change) >= 2:
                tradable.append({
                    "symbol": row["SYMBOL"],
                    "prev_day_change_pct": change
                })
        except Exception:
            continue

    tradable_df = pd.DataFrame(tradable)

    # 🔒 GUARANTEED OUTPUT
    if tradable_df.empty:
        print("⚠️ No tradable stocks found. Using fallback universe.")
        shutil.copy(FALLBACK_UNIVERSE, OUTPUT_UNIVERSE)
        used = "fallback universe"
    else:
        tradable_df.to_csv(OUTPUT_UNIVERSE, index=False)
        used = f"{len(tradable_df)} tradable stocks"

    send_telegram(
        f"📊 Premarket Radar\n"
        f"Scanned: {len(df)} stocks\n"
        f"Universe used: {used}"
    )

    end = datetime.datetime.now()
    print(f"✅ Premarket scan completed at {end}")
    print(f"⏱️ Duration: {end - start}")

if __name__ == "__main__":
    main()