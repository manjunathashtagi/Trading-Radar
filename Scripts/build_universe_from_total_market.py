from pathlib import Path
import pandas as pd

# --------------------------------------------------
# INPUTS
# --------------------------------------------------

# Option A: NSE symbol master (preferred, always present)
SYMBOL_MASTER = Path("artifacts/nse_all_symbols.txt")

# Option B: Total market CSV (optional, fallback)
TOTAL_MARKET_CSV = Path("Scripts/MW-NIFTY-TOTAL-MARKET-03-Jan-2026.csv")

# --------------------------------------------------
# OUTPUT
# --------------------------------------------------

OUTPUT_FILE = Path("artifacts/tradable_universe.txt")

# --------------------------------------------------
# LOGIC
# --------------------------------------------------

def main():
    symbols = []

    # ---- Preferred source ----
    if SYMBOL_MASTER.exists():
        print("✅ Using NSE symbol master")
        symbols = [
            s.strip()
            for s in SYMBOL_MASTER.read_text().splitlines()
            if s.strip()
        ]

    # ---- Fallback source ----
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
    # CLEANUP
    # --------------------------------------------------

    symbols = sorted(set(s for s in symbols if len(s) <= 15))

    # --------------------------------------------------
    # WRITE OUTPUT
    # --------------------------------------------------

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text("\n".join(symbols))

    print(f"✅ Tradable universe created")
    print(f"📄 Output: {OUTPUT_FILE}")
    print(f"📊 Total stocks: {len(symbols)}")


if __name__ == "__main__":
    main()
