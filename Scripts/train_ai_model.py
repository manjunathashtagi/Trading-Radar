import os
import pandas as pd
import joblib
from sklearn.ensemble import RandomForestClassifier

DATA_FILE = "data/training_data.csv"
MODEL_FILE = "data/ai_model.pkl"

def main():

    # ❌ File missing
    if not os.path.exists(DATA_FILE):
        print("❌ training_data.csv not found")
        return

    try:
        df = pd.read_csv(DATA_FILE)
    except:
        print("❌ training_data.csv corrupted")
        return

    # ❌ Empty file
    if df.empty or len(df.columns) == 0:
        print("❌ training_data.csv is empty")
        return

    # Required columns check
    required_cols = ["RSI","EMA20","EMA50","volatility","volume_ratio","distance_high","target"]

    for col in required_cols:
        if col not in df.columns:
            print(f"❌ Missing column: {col}")
            return

    # ❌ Not enough data
    if len(df) < 100:
        print(f"❌ Not enough data ({len(df)} rows)")
        return

    X = df[["RSI","EMA20","EMA50","volatility","volume_ratio","distance_high"]]
    y = df["target"]

    model = RandomForestClassifier(n_estimators=100)
    model.fit(X, y)

    os.makedirs("data", exist_ok=True)
    joblib.dump(model, MODEL_FILE)

    print(f"✅ Model trained successfully on {len(df)} rows")


if __name__ == "__main__":
    main()