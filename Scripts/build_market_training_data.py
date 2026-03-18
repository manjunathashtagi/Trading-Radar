import os
import pandas as pd
import numpy as np
import yfinance as yf
from ta.momentum import RSIIndicator

CACHE_FILE = "data/stage1_cache.csv"
OUTPUT_FILE = "data/training_data.csv"


def build():

    if not os.path.exists(CACHE_FILE):
        print("❌ No stage1 cache")
        return

    symbols = pd.read_csv(CACHE_FILE)["symbol"].tolist()

    rows = []

    print(f"Building dataset from {len(symbols)} stocks")

    for symbol in symbols[:100]:  # limit for stability

        try:
            df = yf.download(symbol + ".NS", period="5d", interval="15m")

            if len(df) < 50:
                continue

            df["EMA20"] = df["Close"].ewm(span=20).mean()
            df["EMA50"] = df["Close"].ewm(span=50).mean()
            df["RSI"] = RSIIndicator(df["Close"], window=14).rsi()

            df["VOL_SHORT"] = df["Volume"].rolling(10).mean()
            df["VOL_LONG"] = df["Volume"].rolling(30).mean()

            df["HH20"] = df["High"].rolling(20).max()

            df["volatility"] = df["Close"].pct_change().rolling(10).std()

            for i in range(30, len(df) - 5):

                try:
                    row = df.iloc[i]

                    future_price = df["Close"].iloc[i+5]
                    current_price = row["Close"]

                    move = (future_price - current_price) / current_price

                    target = 1 if move > 0.02 else 0

                    volume_ratio = row["VOL_SHORT"] / row["VOL_LONG"]
                    distance_high = (row["HH20"] - current_price) / current_price

                    rows.append({
                        "RSI": row["RSI"],
                        "EMA20": row["EMA20"],
                        "EMA50": row["EMA50"],
                        "volatility": row["volatility"],
                        "volume_ratio": volume_ratio,
                        "distance_high": distance_high,
                        "target": target
                    })

                except:
                    continue

        except:
            continue

    if not rows:
        print("❌ No training data generated")
        return

    df_final = pd.DataFrame(rows)

    # CLEAN DATA (IMPORTANT)
    df_final = df_final.replace([np.inf, -np.inf], np.nan)
    df_final = df_final.dropna()

    if df_final.empty:
        print("❌ Cleaned data is empty")
        return

    os.makedirs("data", exist_ok=True)

    df_final.to_csv(OUTPUT_FILE, index=False)

    print(f"✅ Training data saved: {len(df_final)} rows")


if __name__ == "__main__":
    build()