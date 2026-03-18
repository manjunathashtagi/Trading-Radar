import os
import pandas as pd
import numpy as np
import yfinance as yf
from ta.momentum import RSIIndicator

CACHE_FILE = "data/stage1_cache.csv"
OUTPUT_FILE = "data/training_data.csv"


def build():

    # -----------------------------
    # Load symbols
    # -----------------------------
    if not os.path.exists(CACHE_FILE):
        print("❌ stage1_cache.csv not found")
        return

    df_cache = pd.read_csv(CACHE_FILE)

    if "symbol" not in df_cache.columns:
        print("❌ Invalid stage1_cache format")
        return

    symbols = df_cache["symbol"].dropna().unique().tolist()

    print(f"✅ Loaded symbols: {len(symbols)}")

    rows = []

    # -----------------------------
    # Loop stocks
    # -----------------------------
    for symbol in symbols:

        try:
            print(f"Processing: {symbol}")

            df = yf.download(symbol + ".NS", period="5d", interval="15m")

            # 🔥 FIX 1: flatten multi-index columns
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)

            # 🔥 FIX 2: ensure numeric 1D columns
            for col in ["Open", "High", "Low", "Close", "Volume"]:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce")

            df = df.dropna()

            if df.empty or len(df) < 50:
                continue

            # -----------------------------
            # Indicators
            # -----------------------------
            df["EMA20"] = df["Close"].ewm(span=20).mean()
            df["EMA50"] = df["Close"].ewm(span=50).mean()
            df["RSI"] = RSIIndicator(df["Close"], window=14).rsi()

            df["VOL_SHORT"] = df["Volume"].rolling(10).mean()
            df["VOL_LONG"] = df["Volume"].rolling(30).mean()

            df["HH20"] = df["High"].rolling(20).max()

            df["volatility"] = df["Close"].pct_change().rolling(10).std()

            df = df.dropna()

            if df.empty:
                continue

            # -----------------------------
            # Build dataset
            # -----------------------------
            for i in range(30, len(df) - 5):

                try:
                    row = df.iloc[i]

                    current_price = row["Close"]
                    future_price = df["Close"].iloc[i + 5]

                    move = (future_price - current_price) / current_price

                    target = 1 if move > 0.02 else 0

                    volume_ratio = row["VOL_SHORT"] / row["VOL_LONG"]
                    distance_high = (row["HH20"] - current_price) / current_price

                    rows.append({
                        "RSI": float(row["RSI"]),
                        "EMA20": float(row["EMA20"]),
                        "EMA50": float(row["EMA50"]),
                        "volatility": float(row["volatility"]),
                        "volume_ratio": float(volume_ratio),
                        "distance_high": float(distance_high),
                        "target": int(target)
                    })

                except:
                    continue

        except Exception as e:
            print(f"Error {symbol}: {e}")
            continue

    print(f"Total rows generated: {len(rows)}")

    # -----------------------------
    # Safety fallback
    # -----------------------------
    if not rows:

        print("⚠️ No real data → creating fallback dataset")

        df_dummy = pd.DataFrame([{
            "RSI": 50,
            "EMA20": 100,
            "EMA50": 100,
            "volatility": 0.01,
            "volume_ratio": 1,
            "distance_high": 0.02,
            "target": 0
        }])

        os.makedirs("data", exist_ok=True)
        df_dummy.to_csv(OUTPUT_FILE, index=False)

        print("✅ Dummy dataset created")
        return

    df_final = pd.DataFrame(rows)

    # -----------------------------
    # Clean data
    # -----------------------------
    df_final = df_final.replace([np.inf, -np.inf], np.nan)
    df_final = df_final.dropna()

    if df_final.empty:

        print("⚠️ Cleaned data empty → fallback dataset")

        df_dummy = pd.DataFrame([{
            "RSI": 50,
            "EMA20": 100,
            "EMA50": 100,
            "volatility": 0.01,
            "volume_ratio": 1,
            "distance_high": 0.02,
            "target": 0
        }])

        df_dummy.to_csv(OUTPUT_FILE, index=False)
        return

    # -----------------------------
    # Save dataset
    # -----------------------------
    os.makedirs("data", exist_ok=True)
    df_final.to_csv(OUTPUT_FILE, index=False)

    print(f"✅ Training data saved: {len(df_final)} rows")


if __name__ == "__main__":
    build()