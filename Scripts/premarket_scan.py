import pandas as pd
from datetime import datetime
import pytz
from pathlib import Path

IST = pytz.timezone("Asia/Kolkata")

BASE_UNIVERSE = "data/nse_all_symbols.csv"
OUTPUT_UNIVERSE = "data/universe_nse_tradable.csv"

def main():
    now = datetime.now(IST)
    print(f"🚀 Premarket scan @ {now}")

    if not Path(BASE_UNIVERSE).exists():
        raise FileNotFoundError(f"❌ Missing {BASE_UNIVERSE}")

    df = pd.read_csv(BASE_UNIVERSE)

    if "SYMBOL" not in df.columns:
        raise ValueError("❌ SYMBOL column missing in base universe")

    # --- CLEAN ONLY (NO FILTERING) ---
    df["SYMBOL"] = df["SYMBOL"].astype(str).str.strip()
    df = df[df["SYMBOL"].str.len() > 0]
    df = df.drop_duplicates(subset=["SYMBOL"])

    # Save full universe for intraday scanner
    Path("data").mkdir(exist_ok=True)
    df[["SYMBOL"]].to_csv(OUTPUT_UNIVERSE, index=False)

    print(f"✅ Tradable universe prepared")
    print(f"📊 Total tradable stocks: {len(df)}")
    print(f"📄 Saved to: {OUTPUT_UNIVERSE}")

if __name__ == "__main__":
    main()