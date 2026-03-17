import pandas as pd
from sklearn.ensemble import RandomForestClassifier
import joblib

df = pd.read_csv("data/training_data.csv")

X = df[[
    "rsi",
    "ema20",
    "ema50",
    "volatility",
    "volume_ratio",
    "distance_high"
]]

y = df["target"]

model = RandomForestClassifier(
    n_estimators=300,
    max_depth=10,
    random_state=42
)

model.fit(X, y)

accuracy = model.score(X, y)
print(f"Model Accuracy: {round(accuracy, 2)}")

joblib.dump(model, "data/ai_model.pkl")

print("AI model saved")