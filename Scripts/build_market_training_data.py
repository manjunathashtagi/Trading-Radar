import pandas as pd
import numpy as np
import yfinance as yf
from ta.momentum import RSIIndicator

symbols_file = "data/stage1_cache.csv"
output_file = "data/training_data.csv"

symbols = pd.read_csv(symbols_file)["symbol"].tolist()

rows = []

print(f"Building dataset from {len(symbols)} stocks")

for symbol in symbols:
    try:
        df = yf.download(symbol + ".NS", period="10d", interval="15m")

        if len(df) < 100:
            continue

        df["EMA20"] = df["Close"].ewm(span=20).mean()
        df["EMA50"] = df["Close"].ewm(span=50).mean()
        df["RSI"] = RSIIndicator(df["Close"], window=14).rsi()

        df["VOL_SHORT"] = df["Volume"].rolling(10).mean()
        df["VOL_LONG"] = df["Volume"].rolling(30).mean()

        df["VOL_RATIO"] = df["VOL_SHORT"] / df["VOL_LONG"]

        df["VOLATILITY"] = df["Close"].pct_change().rolling(10).std()

        df["HH20"] = df["High"].rolling(20).max()
        df["DIST_HIGH"] = (df["HH20"] - df["Close"]) / df["Close"]

        # 🎯 FUTURE MOVE (KEY UPGRADE)
        future_high = df["High"].shift(-8).rolling(8).max()  # next 2 hours
        df["FUTURE_RETURN"] = (future_high - df["Close"]) / df["Close"]

        # Label: 3% move
        df["TARGET"] = (df["FUTURE_RETURN"] > 0.03).astype(int)

        for i in range(50, len(df) - 10):
            row = df.iloc[i]

            rows.append({
                "rsi": row["RSI"],
                "ema20": row["EMA20"],
                "ema50": row["EMA50"],
                "volatility": row["VOLATILITY"],
                "volume_ratio": row["VOL_RATIO"],
                "distance_high": row["DIST_HIGH"],
                "target": row["TARGET"]
            })

    except:
        continue

df_final = pd.DataFrame(rows)
df_final.dropna(inplace=True)

df_final.to_csv(output_file, index=False)

print(f"Training data saved: {len(df_final)} rows")