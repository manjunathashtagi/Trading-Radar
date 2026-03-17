import sys
import yfinance as yf
from ta.momentum import RSIIndicator

def analyze(symbol):

    ticker = yf.Ticker(symbol + ".NS")
    df = ticker.history(period="5d", interval="15m")

    if len(df) < 40:
        print("Not enough data")
        return

    df["EMA20"] = df["Close"].ewm(span=20).mean()
    df["EMA50"] = df["Close"].ewm(span=50).mean()
    df["RSI"] = RSIIndicator(df["Close"], window=14).rsi()

    df["HH20"] = df["High"].rolling(20).max()
    df["VOL_AVG"] = df["Volume"].rolling(20).mean()

    latest = df.iloc[-1]
    prev = df.iloc[-2]

    score = 0

    print("----- STOCK DIAGNOSTIC -----")
    print("Symbol:", symbol)

    trend = latest["EMA20"] > latest["EMA50"]
    print("EMA20 > EMA50:", trend)
    if trend:
        score += 20

    print("RSI:", round(latest["RSI"], 2))
    if latest["RSI"] > 55:
        score += 15
    elif latest["RSI"] > 48:
        score += 10

    momentum = (latest["Close"] - prev["Close"]) / prev["Close"]
    print("Momentum:", round(momentum * 100, 2), "%")

    if momentum > 0.004:
        score += 20
    elif momentum > 0.002:
        score += 15
    elif momentum > 0.001:
        score += 10

    volume_spike = latest["Volume"] > 1.3 * latest["VOL_AVG"]
    print("Volume spike:", volume_spike)
    if volume_spike:
        score += 20

    breakout = latest["Close"] > prev["HH20"]
    print("Breakout:", breakout)
    if breakout:
        score += 20

    print("Final Score:", score)

    if score >= 40:
        print("Signal: TRIGGERED")
    else:
        print("Signal: NOT TRIGGERED")


if __name__ == "__main__":

    if len(sys.argv) < 2:
        print("Usage: python Scripts/debug_stock.py SYMBOL")
        sys.exit()

    analyze(sys.argv[1])