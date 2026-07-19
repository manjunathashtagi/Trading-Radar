import pandas as pd
import json
import os

SIGNAL_FILE = "data/signals.csv"
CONFIG_FILE = "data/model_config.json"

def main():

    if not os.path.exists(SIGNAL_FILE):
        return

    df = pd.read_csv(SIGNAL_FILE)
    df = df[df["result"].isin(["TARGET","SL"])]

    if len(df) < 20:
        print("Not enough data")
        return

    winners = df[df["result"] == "TARGET"]

    if winners.empty:
        return

    # Load existing config and update only the learned fields, instead of
    # overwriting the whole file. The previous version replaced the entire
    # config dict, which would have silently wiped rsi_min/rsi_max/min_score/
    # tp_pct/sl_pct/win_rate/total_trades/wins on every run.
    config = {}
    if os.path.exists(CONFIG_FILE):
        try:
            config = json.load(open(CONFIG_FILE))
        except Exception:
            config = {}

    config["trend_min"] = float(winners["trend"].mean() * 0.8)
    config["volume_min"] = float(winners["volume"].mean() * 0.8)
    config["momentum_min"] = float(winners["momentum"].mean() * 0.8)
    # "breakout" was never a field this system's signals actually carry
    # (only Scripts/debug_stock.py used that name) -- removed rather than
    # left in to crash with a KeyError the first time this had 20+ closed trades.

    with open(CONFIG_FILE,"w") as f:
        json.dump(config,f,indent=4)

    print("✅ Strategy updated")

if __name__ == "__main__":
    main()
