import os
import pandas as pd
import numpy as np
import yfinance as yf
import time
from ta.momentum import RSIIndicator

CACHE_FILE = "data/stage1_cache.csv"
OUTPUT_FILE = "data/training_data.csv"

def safe_fetch(symbol):
    for _ in range(3):
        try:
            df = yf.download(symbol, period="5d", interval="15m", progress=False)
            if not df.empty:
                return df
        except:
            time.sleep(1)
    return None


def build():

    if not os.path.exists(CACHE_FILE):
        print("❌ stage1_cache.csv not found")
        return

    df_cache = pd.read_csv(CACHE_FILE)

    # 🔥 FIX column mismatch
    if "symbol" in df_cache.columns:
        symbols = df_cache["symbol"].dropna().unique().tolist()
    elif "stock" in df_cache.columns:
        symbols = df_cache["stock"].dropna().unique().tolist()
    else:
        print("❌ Invalid stage1_cache format")
        return

    print(f"✅ Loaded symbols: {len(symbols)}")

    rows = []

    for symbol in symbols:
        try:
            print(f"Processing: {symbol}")

            df = safe_fetch(symbol + ".NS")

            if df is None:
                print(f"❌ Skipping {symbol}")
                continue

            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)

            df = df.dropna()

            if df.empty or len(df) < 50:
                continue

            df["EMA20"] = df["Close"].ewm(span=20).mean()
            df["EMA50"] = df["Close"].ewm(span=50).mean()
            df["RSI"] = RSIIndicator(df["Close"], window=14).rsi()

            df["VOL_SHORT"] = df["Volume"].rolling(10).mean()
            df["VOL_LONG"] = df["Volume"].rolling(30).mean()
            df["HH20"] = df["High"].rolling(20).max()
            df["volatility"] = df["Close"].pct_change().rolling(10).std()

            df = df.dropna()

            for i in range(30, len(df) - 5):
                try:
                    row = df.iloc[i]
                    current_price = row["Close"]
                    future_price = df["Close"].iloc[i + 5]

                    move = (future_price - current_price) / current_price
                    target = 1 if move > 0.02 else 0

                    rows.append({
                        "RSI": float(row["RSI"]),
                        "EMA20": float(row["EMA20"]),
                        "EMA50": float(row["EMA50"]),
                        "volatility": float(row["volatility"]),
                        "volume_ratio": float(row["VOL_SHORT"] / row["VOL_LONG"]),
                        "distance_high": float((row["HH20"] - current_price) / current_price),
                        "target": int(target)
                    })
                except:
                    continue

            time.sleep(0.3)

        except Exception as e:
            print(f"Error {symbol}: {e}")
            continue

    print(f"Total rows generated: {len(rows)}")

    os.makedirs("data", exist_ok=True)

    if not rows:
        pd.DataFrame([{
            "RSI": 50, "EMA20": 100, "EMA50": 100,
            "volatility": 0.01, "volume_ratio": 1,
            "distance_high": 0.02, "target": 0
        }]).to_csv(OUTPUT_FILE, index=False)
        return

    df_final = pd.DataFrame(rows)
    df_final = df_final.replace([np.inf, -np.inf], np.nan).dropna()

    df_final.to_csv(OUTPUT_FILE, index=False)
    print(f"✅ Training data saved: {len(df_final)} rows")


if __name__ == "__main__":
    build()