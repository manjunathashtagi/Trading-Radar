import yfinance as yf
import pandas as pd


def detect_early_momentum(symbols):

    strong = []

    for symbol in symbols:

        try:

            df = yf.download(
                symbol + ".NS",
                period="2d",
                interval="15m",
                progress=False
            )

            if len(df) < 30:
                continue

            df["range"] = df["High"] - df["Low"]

            compression = df["range"].rolling(10).mean().iloc[-1]
            avg_range = df["range"].rolling(40).mean().iloc[-1]

            volume_avg = df["Volume"].rolling(20).mean().iloc[-1]

            latest = df.iloc[-1]

            volume_spike = latest["Volume"] > 1.5 * volume_avg
            tight_range = compression < avg_range * 0.7

            if volume_spike and tight_range:
                strong.append(symbol)

        except:
            pass

    return strong