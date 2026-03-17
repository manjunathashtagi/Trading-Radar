import os
import pandas as pd
import joblib
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score


TRAIN_FILE = "data/training_data.csv"
MODEL_FILE = "data/ai_model.pkl"


def train_model():

    if not os.path.exists(TRAIN_FILE):
        print("training_data.csv not found")
        return

    df = pd.read_csv(TRAIN_FILE)

    if len(df) < 50:
        print("Not enough training data")
        return

    features = [
        "rsi",
        "ema20",
        "ema50",
        "volatility",
        "volume_ratio",
        "distance_high"
    ]

    X = df[features]
    y = df["future_move"]

    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=0.2,
        random_state=42
    )

    model = RandomForestClassifier(
        n_estimators=200,
        max_depth=8,
        random_state=42
    )

    model.fit(X_train, y_train)

    predictions = model.predict(X_test)

    accuracy = accuracy_score(y_test, predictions)

    print(f"Model Accuracy: {accuracy:.2f}")

    joblib.dump(model, MODEL_FILE)

    print("AI model saved → data/ai_model.pkl")


if __name__ == "__main__":
    train_model()