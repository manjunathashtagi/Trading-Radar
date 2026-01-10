import pandas as pd
import zipfile
import io
import requests
from datetime import datetime, timedelta
import os

OUTPUT_FILE = "data/nse_all_symbols.csv"

def download_latest_bhavcopy():
    """
    Downloads the most recent available NSE equity bhavcopy
    """
    base_url = "https://archives.nseindia.com/content/historical/EQUITIES"

    for i in range(1, 8):  # look back up to 7 days
        day = datetime.today() - timedelta(days=i)
        year = day.strftime("%Y")
        month = day.strftime("%b").upper()
        date_str = day.strftime("%d%b%Y").upper()

        url = f"{base_url}/{year}/{month}/cm{date_str}bhav.csv.zip"

        try:
            r = requests.get(url, timeout=10)
            if r.status_code == 200:
                return r.content
        except Exception:
            continue

    raise RuntimeError("❌ Unable to download NSE bhavcopy")


def main():
    os.makedirs("data", exist_ok=True)

    print("⬇️ Downloading NSE bhavcopy...")
    zip_bytes = download_latest_bhavcopy()

    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as z:
        csv_name = z.namelist()[0]
        df = pd.read_csv(z.open(csv_name))

    # Keep only EQ series (normal equity)
    df = df[df["SERIES"] == "EQ"]

    symbols = sorted(df["SYMBOL"].dropna().unique())

    out = pd.DataFrame({"symbol": symbols})
    out.to_csv(OUTPUT_FILE, index=False)

    print(f"✅ NSE symbol universe generated")
    print(f"📊 Total symbols: {len(out)}")
    print(f"📄 Output: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
