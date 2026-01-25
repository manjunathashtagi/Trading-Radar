import yfinance as yf
from datetime import datetime


def fetch_realtime_ohlc(symbol: str):
    """
    Fetch near-realtime OHLC data for a symbol.
    This is a SAFE placeholder implementation.
    """

    try:
        # Yahoo uses .NS for NSE stocks
        ticker = yf.Ticker(f"{symbol}.NS")

        data = ticker.history(period="1d", interval="5m")

        if data.empty:
            return None

        last = data.iloc[-1]

        return {
            "open": float(last["Open"]),
            "high": float(last["High"]),
            "low": float(last["Low"]),
            "close": float(last["Close"]),
            "volume": int(last["Volume"]),
            "time": datetime.now().isoformat()
        }

    except Exception as e:
        print(f"[ERROR] Failed fetching {symbol}: {e}")
        return None
