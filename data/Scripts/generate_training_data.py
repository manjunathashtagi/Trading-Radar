import pandas as pd
import yfinance as yf
from datetime import timedelta

SIGNALS_FILE = "data/signals.csv"
OUTPUT_FILE = "data/training_data.csv"


def build_dataset():

    if not pd.io.common.file_exists(SIGNALS_FILE):
        print("No signals.csv found")
        return

    signals = pd.read_csv(SIGNALS_FILE)

    rows = []

    for _, row in signals.iterrows():

        symbol = row["symbol"]
        entry = row["entry"]

        try:
            ticker = yf.Ticker(symbol + ".NS")
            df = ticker.history(period="5d", interval="15m")

            if len(df) < 40:
                continue

            latest = df.iloc[-1]

            rsi = latest["Close"]
            ema20 = df["Close"].ewm(span=20).mean().iloc[-1]
            ema50 = df["Close"].ewm(span=50).mean().iloc[-1]

            volatility = (df["High"] - df["Low"]).tail(20).mean()

            volume_ratio = latest["Volume"] / df["Volume"].rolling(20).mean().iloc[-1]

            distance_high = latest["Close"] - df["High"].rolling(20).max().iloc[-1]

            # label (did price move up?)
            future_price = df["Close"].iloc[-1]

            future_move = 1 if future_price > entry else 0

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

    dataset.to_csv(OUTPUT_FILE, index=False)

    print(f"Training data saved: {len(dataset)} rows")


if __name__ == "__main__":
    build_dataset()