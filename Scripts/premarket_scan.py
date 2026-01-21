import pandas as pd
from datetime import datetime
import pytz
import os

IST = pytz.timezone("Asia/Kolkata")

BASE = "data/nse_all_symbols.csv"
OUT = "data/universe_nse_tradable.csv"

def main():
    now = datetime.now(IST)
    print(f"🚀 Premarket scan @ {now}")

    df = pd.read_csv(BASE)

    df["VOLUME"] = pd.to_numeric(df.get("VOLUME", 0))
    df["%CHNG"] = pd.to_numeric(df.get("%CHNG", 0))

    # Pre-market only filters liquidity
    tradable = df[df["VOLUME"] >= 200_000][["SYMBOL", "VOLUME", "%CHNG"]]

    os.makedirs("data", exist_ok=True)
    tradable.to_csv(OUT, index=False)

    print(f"📊 Total tradable stocks: {len(tradable)}")
    print(f"📄 Saved to: {OUT}")

if __name__ == "__main__":
    main()