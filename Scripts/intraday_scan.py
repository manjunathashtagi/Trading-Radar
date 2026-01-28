import sys
import time
from pathlib import Path
from datetime import datetime
import pandas as pd
import yfinance as yf

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from alerts.telegram_alerts import send_alert
from scanners.intraday_scanner import scan_intraday

DATA_DIR = ROOT_DIR / "data"
UNIVERSE_FILE = DATA_DIR / "universe_nse_tradable.csv"

MAX_SYMBOLS = 150   # keep Yahoo safe


# ================= MARKET METRICS =================

def fetch_intraday_df(symbol):
    try:
        df = yf.Ticker(f"{symbol}.NS").history(
            period="2d",
            interval="5m",
            auto_adjust=True
        )
        return df if not df.empty else None
    except Exception:
        return None


def calculate_atr(df, period=14):
    hl = df["High"] - df["Low"]
    hc = (df["High"] - df["Close"].shift()).abs()
    lc = (df["Low"] - df["Close"].shift()).abs()
    tr = pd.concat([hl, hc, lc], axis=1).max(axis=1)
    return tr.rolling(period).mean().iloc[-1]


def calculate_vwap(df):
    tp = (df["High"] + df["Low"] + df["Close"]) / 3
    return (tp * df["Volume"]).sum() / df["Volume"].sum()


def get_pdh_pdl(df):
    df = df.copy()
    df["date"] = df.index.date
    days = sorted(df["date"].unique())
    if len(days) < 2:
        return None, None
    prev = df[df["date"] == days[-2]]
    return prev["High"].max(), prev["Low"].min()


def calculate_levels(price, atr, vwap, pdh, pdl, side):
    if side == "LONG":
        target_candidates = [
            price + 1.2 * atr,
            pdh,
            vwap + 0.5 * atr
        ]
        target = min(t for t in target_candidates if t and t > price)

        sl_candidates = [
            price - 0.8 * atr,
            vwap,
            pdl
        ]
        sl = max(s for s in sl_candidates if s and s < price)

    else:
        target_candidates = [
            price - 1.2 * atr,
            pdl,
            vwap - 0.5 * atr
        ]
        target = max(t for t in target_candidates if t and t < price)

        sl_candidates = [
            price + 0.8 * atr,
            vwap,
            pdh
        ]
        sl = min(s for s in sl_candidates if s and s > price)

    return round(price, 2), round(sl, 2), round(target, 2)


# ================= MAIN =================

universe = pd.read_csv(UNIVERSE_FILE)
universe.columns = universe.columns.str.lower()
universe = universe.head(MAX_SYMBOLS)

long_msgs, short_msgs = [], []

for _, row in universe.iterrows():
    symbol = row["symbol"]

    df = fetch_intraday_df(symbol)
    if df is None or len(df) < 30:
        continue

    atr = calculate_atr(df)
    if atr is None or atr < 0.3:
        continue

    vwap = calculate_vwap(df)
    pdh, pdl = get_pdh_pdl(df)
    if not pdh or not pdl:
        continue

    price = df.iloc[-1]["Close"]

    signals = scan_intraday(symbol, df)

    for s in signals:
        entry, sl, target = calculate_levels(
            price, atr, vwap, pdh, pdl, s["side"]
        )

        line = (
            f"{symbol} | {s['pct']:+.2f}% | Score {s['confidence']} | "
            f"{'Buy' if s['side']=='LONG' else 'Sell'} {entry} | "
            f"SL {sl} | Target {target}"
        )

        if s["side"] == "LONG":
            long_msgs.append(line)
        else:
            short_msgs.append(line)

    time.sleep(0.2)


# ================= TELEGRAM =================

if long_msgs or short_msgs:
    now = datetime.now().strftime("%H:%M IST")
    msg = f"🚨 INTRADAY RADAR ({now})\n\n"

    if long_msgs:
        msg += "🟢 TOP LONGS\n" + "\n".join(long_msgs[:15]) + "\n\n"

    if short_msgs:
        msg += "🔴 TOP SHORTS\n" + "\n".join(short_msgs[:15])

    send_alert(msg)