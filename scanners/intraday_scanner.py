import pandas as pd
from nsepython import equity_history, nse_eq
from datetime import datetime, timedelta
import numpy as np


def calculate_atr(df, period=14):
    df["H-L"] = df["HIGH"] - df["LOW"]
    df["H-PC"] = abs(df["HIGH"] - df["CLOSE"].shift(1))
    df["L-PC"] = abs(df["LOW"] - df["CLOSE"].shift(1))
    df["TR"] = df[["H-L", "H-PC", "L-PC"]].max(axis=1)
    atr = df["TR"].rolling(period).mean()
    return atr.iloc[-1]


def scan_intraday(symbol):
    try:
        to_d = datetime.now()
        from_d = to_d - timedelta(days=20)

        df = equity_history(
            symbol,
            "EQ",
            from_d.strftime("%d-%m-%Y"),
            to_d.strftime("%d-%m-%Y")
        )

        if df is None or len(df) < 20:
            print(f"{symbol}: Not enough data")
            return None

        df = df.tail(20)
        last = df.iloc[-1]
        prev = df.iloc[-2]

        close_now = last["CLOSE"]
        atr = calculate_atr(df)

        if np.isnan(atr) or atr == 0:
            print(f"{symbol}: ATR invalid")
            return None

        # 🔥 Slightly relaxed breakout
        if close_now >= prev["HIGH"] * 0.998:
            action = "BUY"
            entry = close_now
            sl = entry - atr
            tp = entry + (2 * atr)

        elif close_now <= prev["LOW"] * 1.002:
            action = "SELL"
            entry = close_now
            sl = entry + atr
            tp = entry - (2 * atr)

        else:
            print(f"{symbol}: No breakout")
            return None

        risk_distance = abs(entry - sl)
        rr = abs(tp - entry) / risk_distance if risk_distance != 0 else 0
        sl_percent = (risk_distance / entry) * 100

        quote = nse_eq(symbol)
        gap_percent = quote["priceInfo"]["pChange"]
        gap_direction = "Gap Up" if gap_percent > 0 else "Gap Down"
        sector = quote.get("industry", "Unknown")

        confidence = 60
        if rr >= 2:
            confidence += 10
        if abs(gap_percent) >= 2:
            confidence += 10
        if sl_percent < 1:
            confidence += 10

        confidence = min(confidence, 95)

        print(f"{symbol}: SIGNAL FOUND")

        return {
            "action": action,
            "entry": entry,
            "sl": sl,
            "tp": tp,
            "rr": round(rr, 2),
            "sl_percent": round(sl_percent, 2),
            "gap": round(gap_percent, 2),
            "gap_tag": gap_direction,
            "sector": sector,
            "confidence": confidence
        }

    except Exception as e:
        print(f"{symbol}: Error {e}")
        return None