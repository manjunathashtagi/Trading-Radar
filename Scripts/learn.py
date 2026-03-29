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

    config = {
        "trend_min": float(winners["trend"].mean()*0.8),
        "breakout_min": float(winners["breakout"].mean()*0.8),
        "volume_min": float(winners["volume"].mean()*0.8),
        "momentum_min": float(winners["momentum"].mean()*0.8)
    }

    with open(CONFIG_FILE,"w") as f:
        json.dump(config,f,indent=4)

    print("✅ Strategy updated")

if __name__ == "__main__":
    main()