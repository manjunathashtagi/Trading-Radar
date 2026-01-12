import requests
import csv
import pandas as pd
from pathlib import Path

OUT_FILE = Path("data/nse_all_symbols.csv")
FALLBACK_FILE = Path("Scripts/MW-NIFTY-TOTAL-MARKET-03-Jan-2026.csv")

def download_symbol_master():
    url = "https://archives.nseindia.com/content/equities/EQUITY_L.csv"
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "text/csv",
        "Referer": "https://www.nseindia.com/"
    }
    r = requests.get(url, headers=headers, timeout=30)
    r.raise_for_status()
    return r.text

def parse_nse_csv(csv_text):
    symbols = []
    reader = csv.DictReader(csv_text.splitlines())

    for row in reader:
        series = row.get(" SERIES", "").strip()
        symbol = row.get("SYMBOL", "").strip()

        if series == "EQ" and symbol:
            symbols.append(symbol)

    return sorted(set(symbols))

def fallback_from_total_market():
    print("⚠️ Using fallback MW Total Market CSV")

    if not FALLBACK_FILE.exists():
        raise RuntimeError("❌ No fallback CSV available")

    df = pd.read_csv(FALLBACK_FILE)
    if "SYMBOL" not in df.columns:
        raise RuntimeError("Fallback CSV missing SYMBOL column")

    return sorted(set(df["SYMBOL"].dropna().astype(str)))

def main():
    print("⬇️ Downloading NSE symbol master (EQUITY_L.csv)")

    try:
        csv_text = download_symbol_master()
        symbols = parse_nse_csv(csv_text)
    except Exception as e:
        print(f"❌ NSE download/parse failed: {e}")
        symbols = []

    if not symbols:
        symbols = fallback_from_total_market()

    df = pd.DataFrame(symbols, columns=["SYMBOL"])
    df["VOLUME"] = 1_000_000
    df["%CHNG"] = 0.0

    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT_FILE, index=False)

    print("✅ NSE master universe created")
    print(f"📊 Total symbols: {len(df)}")
    print(f"📄 Saved to: {OUT_FILE}")

if __name__ == "__main__":
    main()
