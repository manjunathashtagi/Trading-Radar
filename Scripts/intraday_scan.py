import sys
import time
from pathlib import Path
from datetime import datetime

import pandas as pd
import yfinance as yf

# ================= PATH SETUP =================

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from scanners.intraday_scanner import scan_intraday
from alerts.telegram_alerts import send_alert

# ================= CONFIG =================

DATA_DIR = ROOT_DIR / "data"
UNIVERSE_FILE = DATA_DIR / "universe_nse_tradable.csv"

MAX_SYMBOLS = 150          # keep Yahoo safe
SLEEP_SEC = 0.2            # rate-limit protection
MIN_ATR = 0.3              # ignore dead stocks

# ================= DATA FETCH =================

def fetch_intraday_df(symbol):
    try:
        df = yf.Ticker(f"{symbol}.NS").history(
            period="2d",
            interval="5m",
            auto_adjust=True
        )
        if df.empty:
            return None

        # 🔑 NORMALIZE COLUMN NAMES (CRITICAL FIX)
        df.columns = df.columns.str.lower()
        return df

    except Exception as e:
        print(f"Fetch failed for {symbol}: {e}")
        return None

# ================= INDICATORS =================

def calculate_atr(df, period=14):
    hl = df["high"] - df["low"]
    hc = (df["high"] - df["close"].shift()).abs()
    lc = (df["low"] - df["close"].shift()).abs()
    tr = pd.concat([hl, hc, lc], axis=1).max(axis=1)
    atr = tr.rolling(period).mean().iloc[-1]
    return atr


def calculate_vwap(df):
    tp = (df["high"] + df["low"] + df["close"]) / 3
    return (tp * df["volume"]).sum() / df["volume"].sum()


def get_pdh_pdl(df):
    df = df.copy()
    df["date"] = df.index.date
    days = sorted(df["date"].unique())
    if len(days) < 2:
        return None, None

    prev_day = df[df["date"] == days[-2]]
    return prev_day["high"].max(), prev_day["low"].min()


# ================= LEVEL CALCULATION =================

def calculate_levels(price, atr, vwap, pdh, pdl, side):
    if side == "LONG":
        targets = [
            price + 1.2 * atr,
            pdh,
            vwap + 0.5 * atr
        ]
        target = min(t for t in targets if t and t > price)

        stops = [
            price - 0.8 * atr,
            vwap,
            pdl
        ]
        sl = max(s for s in stops if s and s < price)

    else:  # SHORT
        targets = [
            price - 1.2 * atr,
            pdl,
            vwap - 0.5 * atr
        ]
        target = max(t for t in targets if t and t < price)

        stops = [
            price + 0.8 * atr,
            vwap,
            pdh
        ]
        sl = min(s for s in stops if s and s > price)

    return round(price, 2), round(sl, 2), round(target, 2)


# ================= MAIN =================

universe = pd.read_csv(UNIVERSE_FILE)
universe.columns = universe.columns.str.lower()
universe = universe.head(MAX_SYMBOLS)

long_msgs = []
short_msgs = []

for _, row in universe.iterrows():
    symbol = row["symbol"]

    df = fetch_intraday_df(symbol)
    if df is None or len(df) < 30:
        continue

    atr = calculate_atr(df)
    if atr is None or atr < MIN_ATR:
        continue

    vwap = calculate_vwap(df)
    pdh, pdl = get_pdh_pdl(df)
    if pdh is None or pdl is None:
        continue

    price = df.iloc[-1]["close"]

    signals = scan_intraday(symbol, df)

    for s in signals:
        entry, sl, target = calculate_levels(
            price, atr, vwap, pdh, pdl, s["side"]
        )

        msg = (
            f"{symbol} | {s['pct']:+.2f}% | Score {s['confidence']} | "
            f"{'Buy' if s['side']=='LONG' else 'Sell'} {entry} | "
            f"SL {sl} | Target {target}"
        )

        if s["side"] == "LONG":
            long_msgs.append(msg)
        else:
            short_msgs.append(msg)

    time.sleep(SLEEP_SEC)


# ================= TELEGRAM =================

if long_msgs or short_msgs:
    now = datetime.now().strftime("%H:%M IST")
    text = f"🚨 INTRADAY RADAR ({now})\n\n"

    if long_msgs:
        text += "🟢 TOP LONGS\n" + "\n".join(long_msgs[:15]) + "\n\n"

    if short_msgs:
        text += "🔴 TOP SHORTS\n" + "\n".join(short_msgs[:15])

    send_alert(text)