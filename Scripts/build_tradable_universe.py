import pandas as pd
from pathlib import Path
from datetime import datetime

INPUT_FILE = Path("data/nse_all_symbols.csv")
OUTPUT_FILE = Path("data/universe_nse_tradable.csv")

def main():
    print(f"🚀 Building tradable universe @ {datetime.now()}")

    if not INPUT_FILE.exists():
        raise FileNotFoundError(f"❌ Missing {INPUT_FILE}")

    df = pd.read_csv(INPUT_FILE)

    if "SYMBOL" not in df.columns:
        raise ValueError("❌ SYMBOL column missing")

    # --- VERY LIGHT CLEANING ONLY ---
    df["SYMBOL"] = df["SYMBOL"].astype(str).str.strip()
    df = df[df["SYMBOL"].str.len() > 0]

    # Remove duplicates
    df = df.drop_duplicates(subset=["SYMBOL"])

    # 🔑 IMPORTANT: DO NOT FILTER BY VOLUME / %CHNG HERE
    # Premarket must remain loose

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUTPUT_FILE, index=False)

    print(f"✅ Tradable universe created")
    print(f"📊 Total tradable symbols: {len(df)}")
    print(f"📄 Saved to: {OUTPUT_FILE}")

if __name__ == "__main__":
    main()