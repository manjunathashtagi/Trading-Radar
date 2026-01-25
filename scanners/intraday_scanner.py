# scanners/intraday_scanner.py

def scan_intraday(symbol, ohlc):
    """
    Minimal intraday signal generator.
    This is a SAFE placeholder implementation.
    """

    open_ = ohlc["open"]
    close = ohlc["close"]

    pct_change = ((close - open_) / open_) * 100

    signals = []

    # Simple momentum logic (for now)
    if pct_change >= 5:
        signals.append({
            "side": "LONG",
            "pct": pct_change,
            "confidence": 65
        })

    elif pct_change <= -5:
        signals.append({
            "side": "SHORT",
            "pct": pct_change,
            "confidence": 65
        })

    return signals
