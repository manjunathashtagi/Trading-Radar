import requests
import csv
from pathlib import Path

OUT_FILE = Path("artifacts/nse_all_symbols.txt")

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
    print("⬇️ Downloading NSE symbol master...")

    try:
        csv_text = download_symbol_master()
    except Exception as e:
        print(f"❌ Failed to download symbol master: {e}")
        print("⚠️ Using last cached symbols if available")

        if OUT_FILE.exists():
            print("✅ Cached symbol list found — continuing")
            return
        else:
            raise RuntimeError("No symbol source available")

    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    symbols = []
    reader = csv.DictReader(csv_text.splitlines())
    for row in reader:
        if row[" SERIES"] == "EQ":
            symbols.append(row["SYMBOL"].strip())

    symbols = sorted(set(symbols))

    OUT_FILE.write_text("\n".join(symbols))
    print(f"✅ Saved {len(symbols)} NSE symbols to {OUT_FILE}")


if __name__ == "__main__":
    main()
