import pandas as pd
import zipfile
import io
import requests
from datetime import datetime, timedelta
import os

OUTPUT_FILE = "data/nse_all_symbols.csv"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "Connection": "keep-alive",
}

def download_latest_bhavcopy():
    base = "https://archives.nseindia.com/content/historical/EQUITIES"
    session = requests.Session()
    session.headers.update(HEADERS)

    # hit homepage first (important for cookies)
    session.get("https://www.nseindia.com", timeout=10)

    for i in range(1, 8):
        day = datetime.today() - timedelta(days=i)
        year = day.strftime("%Y")
        month = day.strftime("%b").upper()
        date_str = day.strftime("%d%b%Y").upper()

        url = f"{base}/{year}/{month}/cm{date_str}bhav.csv.zip"

        try:
            r = session.get(url, timeout=15)
            if r.status_code == 200:
                return r.content
        except Exception:
            continue

    return None


def main():
    os.makedirs("data", exist_ok=True)

    print("⬇️ Downloading NSE bhavcopy...")
    zip_bytes = download_latest_bhavcopy()

    if zip_bytes is None:
        if os.path.exists(OUTPUT_FILE):
            print("⚠️ NSE blocked request — using previous universe")
            return
        else:
            raise RuntimeError("❌ NSE bhavcopy unavailable and no fallback exists")

    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as z:
        csv_name = z.namelist()[0]
        df = pd.read_csv(z.open(csv_name))

    df = df[df["SERIES"] == "EQ"]
    symbols = sorted(df["SYMBOL"].dropna().unique())

    pd.DataFrame({"symbol": symbols}).to_csv(OUTPUT_FILE, index=False)

    print(f"✅ NSE universe generated: {len(symbols)} symbols")


if __name__ == "__main__":
    main()

