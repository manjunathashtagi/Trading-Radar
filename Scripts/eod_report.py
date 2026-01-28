import json
from pathlib import Path
from datetime import datetime
import pandas as pd
import yfinance as yf

from alerts.telegram_alerts import send_alert

ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT_DIR / "data"

TRADES_FILE = DATA_DIR / "trades_store.json"
UNIVERSE_FILE = DATA_DIR / "universe_nse_tradable.csv"


# ================= SAFE LOAD =================

def load_trades():
    if not TRADES_FILE.exists():
        return []
    return json.loads(TRADES_FILE.read_text())


def save_trades(trades):
    TRADES_FILE.write_text(json.dumps(trades, indent=2))


# ================= PRICE FETCH =================

def fetch_ltp(symbol):
    try:
        df = yf.Ticker(f"{symbol}.NS").history(period="1d", interval="5m")
        if df.empty:
            return None
        return df.iloc[-1]["Close"]
    except Exception:
        return None


# ================= MAIN EOD LOGIC =================

trades = load_trades()

if not trades:
    send_alert("📊 EOD REPORT\n\nNo intraday trades recorded today.")
    exit(0)

total = len(trades)
target_hit = 0
sl_hit = 0
open_trades = 0

long_trades = 0
short_trades = 0

pnl_points = 0.0

hit_symbols = []
sl_symbols = []

for trade in trades:
    symbol = trade["symbol"]
    side = trade["side"]
    entry = trade["entry"]
    target = trade["target"]
    sl = trade["stop_loss"]
    status = trade.get("status", "OPEN")

    ltp = fetch_ltp(symbol)
    if ltp is None:
        open_trades += 1
        continue

    if side == "LONG":
        if ltp >= target:
            trade["status"] = "TARGET_HIT"
            target_hit += 1
            pnl_points += (target - entry)
            hit_symbols.append(symbol)
        elif ltp <= sl:
            trade["status"] = "SL_HIT"
            sl_hit += 1
            pnl_points -= (entry - sl)
            sl_symbols.append(symbol)
        else:
            open_trades += 1

        long_trades += 1

    else:  # SHORT
        if ltp <= target:
            trade["status"] = "TARGET_HIT"
            target_hit += 1
            pnl_points += (entry - target)
            hit_symbols.append(symbol)
        elif ltp >= sl:
            trade["status"] = "SL_HIT"
            sl_hit += 1
            pnl_points -= (sl - entry)
            sl_symbols.append(symbol)
        else:
            open_trades += 1

        short_trades += 1


save_trades(trades)

# ================= REPORT =================

date_str = datetime.now().strftime("%Y-%m-%d")

msg = (
    f"📊 EOD INTRADAY REPORT ({date_str})\n\n"
    f"Total trades: {total}\n"
    f"🟢 Long trades: {long_trades}\n"
    f"🔴 Short trades: {short_trades}\n\n"
    f"🎯 Target hit: {target_hit}\n"
    f"🛑 SL hit: {sl_hit}\n"
    f"⏳ Still open: {open_trades}\n\n"
    f"📈 Net P&L (points): {round(pnl_points, 2)}\n"
)

if hit_symbols:
    msg += "\n✅ Target Hit:\n" + ", ".join(hit_symbols[:15])

if sl_symbols:
    msg += "\n\n❌ SL Hit:\n" + ", ".join(sl_symbols[:15])

send_alert(msg)