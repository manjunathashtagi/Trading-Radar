import numpy as np

def scan_intraday(df, sector_bonus=0):
    if len(df) < 200:
        return None

    ema50 = df["close"].ewm(span=50).mean()
    ema200 = df["close"].ewm(span=200).mean()
    trend_bull = ema50.iloc[-1] > ema200.iloc[-1]
    trend_bear = ema50.iloc[-1] < ema200.iloc[-1]

    delta = df["close"].diff()
    rsi = 100 - (100 / (1 + delta.clip(lower=0).rolling(14).mean()
                       / (-delta.clip(upper=0)).rolling(14).mean()))

    mom_bull = rsi.iloc[-1] > 55 and rsi.iloc[-1] > rsi.iloc[-2]
    mom_bear = rsi.iloc[-1] < 45 and rsi.iloc[-1] < rsi.iloc[-2]

    tr = np.maximum(
        df["high"] - df["low"],
        np.maximum(abs(df["high"] - df["close"].shift()),
                   abs(df["low"] - df["close"].shift()))
    )
    atr = tr.rolling(14).mean()
    atr_ok = atr.iloc[-1] > atr.rolling(20).mean().iloc[-1]

    struct_bull = df["close"].iloc[-1] > df["high"].rolling(5).max().iloc[-2]
    struct_bear = df["close"].iloc[-1] < df["low"].rolling(5).min().iloc[-2]

    score = (
        (25 if trend_bull or trend_bear else 0) +
        (25 if mom_bull or mom_bear else 0) +
        (20 if atr_ok else 0) +
        (20 if struct_bull or struct_bear else 0) +
        sector_bonus
    )

    if trend_bull and mom_bull and atr_ok and struct_bull:
        return "BUY", df["close"].iloc[-1], atr.iloc[-1], score

    if trend_bear and mom_bear and atr_ok and struct_bear:
        return "SELL", df["close"].iloc[-1], atr.iloc[-1], score

    return None
