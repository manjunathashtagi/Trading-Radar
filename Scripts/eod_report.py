import pandas as pd
import json
import os

CONFIG_FILE = "data/model_config.json"
SIGNAL_FILE = "data/signals.csv"

def main():

    if not os.path.exists(SIGNAL_FILE):
        print("No data")
        return

    df = pd.read_csv(SIGNAL_FILE)

    wins = 0
    total = 0

    for _, row in df.iterrows():

        if row["result"] == "OPEN":
            continue

        total += 1

        if row["result"] == "TARGET":
            wins += 1

    if total == 0:
        return

    win_rate = round((wins / total) * 100, 2)

    config = json.load(open(CONFIG_FILE))

    config["win_rate"] = win_rate
    config["total_trades"] += total
    config["wins"] += wins

    # 🔥 AUTO LEARNING
    if win_rate < 50:
        config["volume_min"] += 0.1
        config["momentum_min"] += 0.001
    else:
        config["volume_min"] = max(1.5, config["volume_min"] - 0.05)

    json.dump(config, open(CONFIG_FILE, "w"), indent=2)

    print("Updated config:", config)

if __name__ == "__main__":
    main()