import os
import pandas as pd
import yfinance as yf
import numpy as np
from ta.momentum import RSIIndicator
from ta.trend import EMAIndicator

CACHE_FILE = "data/stage1_cache.csv"
OUTPUT_FILE = "data/training_data.csv"


def load_symbols():

    if not os.path.exists(CACHE_FILE):
        print("stage1_cache.csv not found")
        return []

    df = pd.read_csv(CACHE_FILE)
    return df["symbol"].tolist()


def build_dataset():

    symbols = load_symbols()

    rows = []

    print(f"Building dataset from {len(symbols)} stocks")

    for symbol in symbols:

        try:

            ticker = yf.Ticker(symbol + ".NS")

            df = ticker.history(period="30d", interval="15m")

            if len(df) < 100:
                continue

            df["EMA20"] = EMAIndicator(df["Close"], window=20).ema_indicator()
            df["EMA50"] = EMAIndicator(df["Close"], window=50).ema_indicator()
            df["RSI"] = RSIIndicator(df["Close"], window=14).rsi()

            df["VOL_AVG"] = df["Volume"].rolling(20).mean()

            for i in range(60, len(df) - 8):

                row = df.iloc[i]

                rsi = row["RSI"]
                ema20 = row["EMA20"]
                ema50 = row["EMA50"]

                volatility = (df["High"].iloc[i] - df["Low"].iloc[i]) / row["Close"]

                volume_ratio = row["Volume"] / row["VOL_AVG"]

                distance_high = row["Close"] - df["High"].iloc[i-20:i].max()

                future_price = df["Close"].iloc[i + 8]

                move_pct = ((future_price - row["Close"]) / row["Close"]) * 100

                future_move = 1 if move_pct > 1 else 0

                rows.append({
                    "rsi": rsi,
                    "ema20": ema20,
                    "ema50": ema50,
                    "volatility": volatility,
                    "volume_ratio": volume_ratio,
                    "distance_high": distance_high,
                    "future_move": future_move
                })

        except:
            continue

    dataset = pd.DataFrame(rows)

    os.makedirs("data", exist_ok=True)

    dataset.to_csv(OUTPUT_FILE, index=False)

    print(f"Training data saved: {len(dataset)} rows")


if __name__ == "__main__":
    build_dataset()