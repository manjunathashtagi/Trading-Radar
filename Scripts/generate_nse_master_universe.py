import requests
import pandas as pd
from pathlib import Path

OUT_FILE = Path("data/nse_all_symbols.csv")

def download_symbol_master():
    url = "https://archives.nseindia.com/content/equities/EQUITY_L.csv"
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "text/csv"
    }
    r = requests.get(url, headers=headers, timeout=30)
    r.raise_for_status()
    return r.text

def main():
    print("⬇️ Downloading NSE symbol master (EQUITY_L.csv)")

    csv_text = download_symbol_master()

    rows = []
    for line in csv_text.splitlines()[1:]:
        parts = line.split(",")
        if len(parts) < 2:
            continue
        symbol = parts[0].strip()
        series = parts[1].strip()

        if series == "EQ":
            rows.append(symbol)

    df = pd.DataFrame(sorted(set(rows)), columns=["SYMBOL"])

    # Columns expected by scanners
    df["VOLUME"] = 1_000_000
    df["%CHNG"] = 0.0

    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT_FILE, index=False)

    print(f"✅ NSE master universe created")
    print(f"📊 Total symbols: {len(df)}")
    print(f"📄 Saved to: {OUT_FILE}")

if __name__ == "__main__":
    main()
