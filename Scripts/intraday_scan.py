"""
Intraday Scanner
----------------
This module contains the intraday signal generation logic.

It receives a pandas DataFrame with intraday OHLCV data
and returns trading signals based on short-term momentum.
"""

from typing import List, Dict
import pandas as pd


def scan_intraday(symbol: str, df: pd.DataFrame) -> List[Dict]:
    """
    Scan intraday data and return trading signals.

    Parameters:
    - symbol: Stock symbol (string)
    - df: Pandas DataFrame with columns:
          open, high, low, close, volume

    Returns:
    - List of signal dictionaries
    """

    # ================= SAFETY CHECKS =================

    if df is None:
        return []

    if not isinstance(df, pd.DataFrame):
        return []

    if len(df) < 3:
        return []

    required_cols = {"open", "high", "low", "close", "volume"}
    if not required_cols.issubset(df.columns):
        return []

    # ================= LAST TWO CANDLES =================

    last_candle = df.iloc[-1]
    prev_candle = df.iloc[-2]

    try:
        last_close = float(last_candle["close"])
        prev_close = float(prev_candle["close"])
    except Exception:
        return []

    if prev_close == 0:
        return []

    # ================= MOMENTUM CALCULATION =================

    pct_change = ((last_close - prev_close) / prev_close) * 100

    signals = []

    # ================= SIGNAL RULES =================
    # Intraday-safe momentum thresholds

    if pct_change >= 0.5:
        signals.append({
            "side": "LONG",
            "pct": round(pct_change, 2),
            "confidence": 65
        })

    elif pct_change <= -0.5:
        signals.append({
            "side": "SHORT",
            "pct": round(pct_change, 2),
            "confidence": 65
        })

    return signals