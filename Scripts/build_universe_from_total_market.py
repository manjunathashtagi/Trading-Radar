from pathlib import Path
import pandas as pd

# --------------------------------------------------
# INPUTS
# --------------------------------------------------

# Preferred input (always present, generated earlier)
SYMBOL_MASTER = Path("artifacts/nse_all_symbols.txt")

# Optional fallback CSV (manual / legacy)
TOTAL_MARKET_CSV = Path("Scripts/MW-NIFTY-TOTAL-MARKET-03-Jan-2026.csv")

# --------------------------------------------------
# OUTPUT (MANDATORY for intraday)
# --------------------------------------------------

OUTPUT_FILE = Path("artifacts/tradable_universe.txt")

# --------------------------------------------------
# MAIN
# --------------------------------------------------

def main():
    symbols = []

    # 1️⃣ Preferred source: NSE symbol master
    if SYMBOL_MASTER.exists():
        print("✅ Using NSE symbol master")
        symbols = [
            s.strip()
            for s in SYMBOL_MASTER.read_text().splitlines()
            if s.strip()
        ]

    # 2️⃣ Fallback: total market CSV
    elif TOTAL_MARKET_CSV.exists():
        print("⚠️ NSE symbol master missing, using total market CSV")

        df = pd.read_csv(TOTAL_MARKET_CSV)
        symbol_col = df.columns[0]

        symbols = (
            df[symbol_col]
            .astype(str)
            .str.strip()
            .tolist()
        )

    else:
        raise RuntimeError("❌ No universe source available")

    # --------------------------------------------------
    # CLEAN & NORMALIZE
    # --------------------------------------------------

    symbols = sorted(
        set(s for s in symbols if 1 <= len(s) <= 15)
    )

    # --------------------------------------------------
    # WRITE OUTPUT (ONE SYMBOL PER LINE)
    # --------------------------------------------------

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text("\n".join(symbols))

    print("✅ Tradable universe created successfully")
    print(f"📄 Output: {OUTPUT_FILE}")
    print(f"📊 Total stocks: {len(symbols)}")


if __name__ == "__main__":
    main()
