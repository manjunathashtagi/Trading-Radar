import pandas as pd
from pathlib import Path
from datetime import datetime

BASE_UNIVERSE = Path("data/nse_all_symbols.csv")
OUT_FILE = Path("data/universe_nse_tradable.csv")

# --- Filters (FINAL & SAFE) ---
MIN_VOLUME = 200_000        # liquidity filter
MAX_SYMBOLS = 750           # intraday practicality cap

def main():
    print(f"🚀 Building tradable universe @ {datetime.now()}")

    if not BASE_UNIVERSE.exists():
        raise FileNotFoundError(f"Base universe missing: {BASE_UNIVERSE}")

    df = pd.read_csv(BASE_UNIVERSE)

    if "SYMBOL" not in df.columns:
        raise ValueError("Base universe must contain SYMBOL column")

    # Ensure required columns
    if "VOLUME" not in df.columns:
        df["VOLUME"] = 1_000_000
    if "%CHNG" not in df.columns:
        df["%CHNG"] = 0.0

    # --- Liquidity filter ---
    tradable = df[df["VOLUME"] >= MIN_VOLUME].copy()

    # --- Rank by momentum proxy ---
    tradable = tradable.sort_values(
        by=["%CHNG", "VOLUME"],
        ascending=[False, False]
    )

    # --- Cap universe size ---
    tradable = tradable.head(MAX_SYMBOLS)

    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    tradable.to_csv(OUT_FILE, index=False)

    print(f"✅ Tradable universe created")
    print(f"📊 Total tradable symbols: {len(tradable)}")
    print(f"📄 Saved to: {OUT_FILE}")

if __name__ == "__main__":
    main()
