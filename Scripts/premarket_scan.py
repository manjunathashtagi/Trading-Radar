import pandas as pd
from datetime import datetime
import pytz
import os

IST = pytz.timezone("Asia/Kolkata")

BASE_UNIVERSE = "data/nse_all_symbols.csv"
OUTPUT_UNIVERSE = "data/universe_nse_tradable.csv"

MIN_VOLUME = 300000
MIN_MOVE = 1.2

def main():
    now = datetime.now(IST)
    print(f"🚀 Premarket scan @ {now}")

    df = pd.read_csv(BASE_UNIVERSE)

    df["VOLUME"] = pd.to_numeric(df["VOLUME"], errors="coerce")
    df["%CHNG"] = pd.to_numeric(df["%CHNG"], errors="coerce")

    tradable = df[
        (df["VOLUME"] >= MIN_VOLUME) &
        (df["%CHNG"].abs() >= MIN_MOVE)
    ][["SYMBOL", "%CHNG", "VOLUME"]]

    os.makedirs("data", exist_ok=True)
    tradable.to_csv(OUTPUT_UNIVERSE, index=False)

    print(f"✅ Tradable universe: {len(tradable)} stocks")

if __name__ == "__main__":
    main()