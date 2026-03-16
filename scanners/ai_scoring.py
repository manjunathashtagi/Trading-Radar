import numpy as np


def calculate_ai_score(df):

    latest = df.iloc[-1]
    prev = df.iloc[-2]

    score = 0

    # Trend strength
    if latest["EMA20"] > latest["EMA50"]:
        score += 20

    # Momentum acceleration
    momentum = (latest["Close"] - prev["Close"]) / prev["Close"]

    if momentum > 0.004:
        score += 20
    elif momentum > 0.002:
        score += 15
    elif momentum > 0.001:
        score += 10

    # Volume expansion
    if latest["Volume"] > 1.5 * latest["VOL_AVG"]:
        score += 20
    elif latest["Volume"] > 1.2 * latest["VOL_AVG"]:
        score += 10

    # RSI strength
    if latest["RSI"] > 65:
        score += 20
    elif latest["RSI"] > 55:
        score += 15
    elif latest["RSI"] > 50:
        score += 10

    # Breakout detection
    if latest["Close"] > prev["HH20"]:
        score += 20

    return score


def estimate_eta(entry, target, atr):

    if atr == 0:
        return "Unknown"

    distance = abs(target - entry)

    candles_needed = distance / atr

    minutes = candles_needed * 15

    if minutes < 60:
        return f"{int(minutes)}m"

    if minutes < 180:
        return f"{round(minutes/60,1)}h"

    return f"{round(minutes/60,1)}h+"