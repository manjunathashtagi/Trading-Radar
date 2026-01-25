import json
from datetime import datetime
from pathlib import Path

from data.nse_realtime import fetch_realtime_ohlc
from scanners.intraday_scanner import scan_intraday
from alerts.telegram_alerts import send_alert
import pandas as pd
import sys


ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT_DIR))
# ================= CONFIG =================

DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)

TRADES_FILE = DATA_DIR / "trades_store.json"
UNIVERSE_FILE = DATA_DIR / "etf_universe.csv"

MIN_SCORE = 65

# ==========================================


def load_trades():
    if TRADES_FILE.exists():
        return json.loads(TRADES_FILE.read_text())
    return []


def save_trades(trades):
    TRADES_FILE.write_text(json.dumps(trades, indent=2))


def calculate_levels(price, side):
    price = round(price, 2)

    if side == "LONG":
        entry = price
        stop_loss = round(price * 0.70, 2)     # 30% SL
        target = round(price * 1.40, 2)        # 40% Target
    else:
        entry = price
        stop_loss = round(price * 1.30, 2)
        target = round(price * 0.60, 2)

    return entry, stop_loss, target


def trade_exists(trades, symbol, side):
    return any(
        t["symbol"] == symbol and
        t["side"] == side and
        t["status"] == "OPEN"
        for t in trades
    )


# ================= MAIN =================

universe = pd.read_csv(UNIVERSE_FILE)
trades = load_trades()

long_msgs = []
short_msgs = []

for _, row in universe.iterrows():
    symbol = row["symbol"]

    ohlc = fetch_realtime_ohlc(symbol)
    if not ohlc:
        continue

    price = ohlc["close"]

    signals = scan_intraday(symbol, ohlc)

    for s in signals:
        if s["confidence"] < MIN_SCORE:
            continue

        side = s["side"]  # LONG / SHORT
        pct = s["pct"]
        score = s["confidence"]

        # Avoid duplicate open trades
        if trade_exists(trades, symbol, side):
            continue

        entry, sl, target = calculate_levels(price, side)

        trade = {
            "symbol": symbol,
            "side": side,
            "entry": entry,
            "stop_loss": sl,
            "target": target,
            "status": "OPEN",
            "entry_time": datetime.now().isoformat(),
            "last_price": price
        }

        trades.append(trade)

        line = (
            f"{symbol} | {pct:+.2f}% | Score {score} | "
            f"{'Buy' if side=='LONG' else 'Sell'} {entry} | "
            f"SL {sl} | Target {target}"
        )

        if side == "LONG":
            long_msgs.append(line)
        else:
            short_msgs.append(line)

# ===== UPDATE EXISTING TRADES =====

for trade in trades:
    if trade["status"] != "OPEN":
        continue

    ltp = fetch_realtime_ohlc(trade["symbol"])["close"]
    trade["last_price"] = ltp

    if trade["side"] == "LONG":
        if ltp >= trade["target"]:
            trade["status"] = "TARGET_HIT"
        elif ltp <= trade["stop_loss"]:
            trade["status"] = "SL_HIT"
    else:
        if ltp <= trade["target"]:
            trade["status"] = "TARGET_HIT"
        elif ltp >= trade["stop_loss"]:
            trade["status"] = "SL_HIT"

save_trades(trades)

# ===== TELEGRAM MESSAGE =====

if long_msgs or short_msgs:
    now = datetime.now().strftime("%H:%M IST")
    msg = f"🚨 INTRADAY RADAR ({now})\n\n"

    if long_msgs:
        msg += "🟢 TOP LONGS\n" + "\n".join(long_msgs[:20]) + "\n\n"

    if short_msgs:
        msg += "🔴 TOP SHORTS\n" + "\n".join(short_msgs[:20])

    send_alert(msg)
