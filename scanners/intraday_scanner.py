import pandas as pd
import numpy as np
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from scanners.intraday_scanner import scan_intraday

def confidence_score(trend, momentum, atr_ok, structure, sector_bonus=0):
    score = 0
    score += 25 if trend else 0
    score += 25 if momentum else 0
    score += 20 if atr_ok else 0
    score += 20 if structure else 0
    score += sector_bonus
    return min(score, 100)

def scan_intraday(symbol: str, df: pd.DataFrame):
    if len(df) < 200:
        return None

    df["ema50"] = df["close"].ewm(span=50).mean()
    df["ema200"] = df["close"].ewm(span=200).mean()

    trend_bull = df["ema50"].iloc[-1] > df["ema200"].iloc[-1]
    trend_bear = df["ema50"].iloc[-1] < df["ema200"].iloc[-1]

    delta = df["close"].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    rs = gain.rolling(14).mean() / loss.rolling(14).mean()
    df["rsi"] = 100 - (100 / (1 + rs))

    rsi_now = df["rsi"].iloc[-1]
    rsi_prev = df["rsi"].iloc[-2]

    momentum_bull = rsi_now > 55 and rsi_now > rsi_prev
    momentum_bear = rsi_now < 45 and rsi_now < rsi_prev

    tr = np.maximum(
        df["high"] - df["low"],
        np.maximum(
            abs(df["high"] - df["close"].shift()),
            abs(df["low"] - df["close"].shift())
        )
    )
    atr = tr.rolling(14).mean()
    atr_ok = atr.iloc[-1] > atr.rolling(20).mean().iloc[-1]

    structure_bull = df["close"].iloc[-1] > df["high"].rolling(5).max().iloc[-2]
    structure_bear = df["close"].iloc[-1] < df["low"].rolling(5).min().iloc[-2]

    body = abs(df["close"].iloc[-1] - df["open"].iloc[-1])
    rng = df["high"].iloc[-1] - df["low"].iloc[-1]
    strong = rng > 0 and body / rng > 0.6

    if trend_bull and momentum_bull and atr_ok and structure_bull and strong:
        return "BUY", df["close"].iloc[-1]

    if trend_bear and momentum_bear and atr_ok and structure_bear and strong:
        return "SELL", df["close"].iloc[-1]

conf = confidence_score(
    trend_bull or trend_bear,
    momentum_bull or momentum_bear,
    atr_ok,
    structure_bull or structure_bear,
    sector_bonus=10  # filled later
)

return side, price, conf
