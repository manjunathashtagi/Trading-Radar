import pandas as pd

TOTAL_MARKET_FILE = "MW-NIFTY-TOTAL-MARKET-03-Jan-2026.csv"
OUTPUT_FILE = "../data/universe_nse.csv"

# Possible column names that may contain stock symbols
SYMBOL_CANDIDATES = [
    "SYMBOL",
    "Symbol",
    "NSE Symbol",
    "NSE_SYMBOL",
    "Stock Code",
    "Security Code",
    "SECURITY",
    "NAME",
    "NAME OF COMPANY"
]

def main():
    df = pd.read_csv(TOTAL_MARKET_FILE)

    print("📋 Columns found in CSV:")
    for c in df.columns:
        print(" -", c)

    symbol_col = None
    for col in df.columns:
        if col.strip() in SYMBOL_CANDIDATES:
            symbol_col = col
            break

    if not symbol_col:
        # fallback: first column (common in NSE exports)
        symbol_col = df.columns[0]
        print(f"⚠️ Symbol column not explicitly found, using first column: {symbol_col}")

    universe = df[[symbol_col]].copy()
    universe.columns = ["symbol"]

    universe["symbol"] = universe["symbol"].astype(str).str.strip()

    # Drop obvious non-symbol rows
    universe = universe[
        universe["symbol"].str.len() <= 15
    ]

    universe["sector"] = "Unknown"

    universe = universe.drop_duplicates(subset=["symbol"])
    universe = universe.sort_values("symbol")

    universe.to_csv(OUTPUT_FILE, index=False)

    print("\n✅ Universe file created successfully")
    print(f"📄 Output: {OUTPUT_FILE}")
    print(f"📊 Total stocks: {len(universe)}")

if __name__ == "__main__":
    main()
