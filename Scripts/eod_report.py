import json
from pathlib import Path
from datetime import date
from alerts.telegram_alerts import send_alert
import sys


ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT_DIR))
TRADES_FILE = Path("data/trades_store.json")

if not TRADES_FILE.exists():
    send_alert("📊 EOD REPORT\n\nNo intraday trades recorded today.")
    exit()

trades = json.loads(TRADES_FILE.read_text())

total = len(trades)
targets = sum(1 for t in trades if t["status"] == "TARGET_HIT")
sl = sum(1 for t in trades if t["status"] == "SL_HIT")
open_ = sum(1 for t in trades if t["status"] == "OPEN")

long_targets = sum(1 for t in trades if t["side"] == "LONG" and t["status"] == "TARGET_HIT")
short_targets = sum(1 for t in trades if t["side"] == "SHORT" and t["status"] == "TARGET_HIT")

msg = f"""
📊 EOD INTRADAY SUMMARY ({date.today()})

Total Trades: {total}

🎯 Target Hit: {targets}
   🟢 Long: {long_targets}
   🔴 Short: {short_targets}

🛑 Stop Loss Hit: {sl}
⏳ Still Open: {open_}

(Based on actual price movement, not alerts)
"""

send_alert(msg)
