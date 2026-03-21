import yfinance as yf
import pandas as pd
import numpy as np
import os
import requests
import joblib
from datetime import datetime
from sklearn.ensemble import RandomForestClassifier

# ==============================
# CONFIG
# ==============================
DATA_DIR = "data"
TRADES_FILE = f"{DATA_DIR}/trades_log.csv"
MODEL_FILE = f"{DATA_DIR}/ai_model.pkl"
SECTOR_FILE = f"{DATA_DIR}/sector_map.csv"

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

STOCKS = [
    "RELIANCE","TCS","INFY","HDFCBANK","ICICIBANK",
    "SBIN","AXISBANK","ITC","LT","BAJFINANCE",
    "JSWSTEEL","TATASTEEL","JINDALSTEL","VODAFONEIDEA"
]

# ==============================
# TELEGRAM
# ==============================
def send_telegram(msg):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": msg})
    except:
        pass

# ==============================
# FETCH DATA
# ==============================
def fetch_data(symbol):
    df = yf.download(symbol + ".NS", period="5d", interval="15m")

    if df.empty:
        return None

    df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]

    for col in ["Open","High","Low","Close","Volume"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df.dropna(inplace=True)
    return df

# ==============================
# FEATURES
# ==============================
def compute_features(df):
    df["returns"] = df["Close"].pct_change()
    df["ma20"] = df["Close"].rolling(20).mean()
    df["vol_avg"] = df["Volume"].rolling(20).mean()

    df["momentum"] = df["Close"] > df["ma20"]
    df["volume_spike"] = df["Volume"] > df["vol_avg"]

    df.dropna(inplace=True)
    return df

# ==============================
# AI MODEL
# ==============================
def load_model():
    if os.path.exists(MODEL_FILE):
        return joblib.load(MODEL_FILE)
    return None

# ==============================
# SECTOR INTELLIGENCE
# ==============================
def get_sector_strength():
    if not os.path.exists(SECTOR_FILE):
        return {}

    sector_df = pd.read_csv(SECTOR_FILE)
    sector_scores = {}

    for sector in sector_df["sector"].unique():
        stocks = sector_df[sector_df["sector"] == sector]["symbol"]

        moves = []

        for s in stocks:
            try:
                df = yf.download(s + ".NS", period="1d", interval="15m")
                if df.empty:
                    continue

                change = (df["Close"].iloc[-1] - df["Open"].iloc[0]) / df["Open"].iloc[0]
                moves.append(change)
            except:
                continue

        if moves:
            sector_scores[sector] = np.mean(moves)

    return sector_scores

def send_sector_summary(sector_strength):
    if not sector_strength:
        return

    sorted_sec = sorted(sector_strength.items(), key=lambda x: x[1], reverse=True)

    msg = "📊 Sector Strength:\n\n"
    for sec, val in sorted_sec[:5]:
        msg += f"{sec}: {round(val*100,2)}%\n"

    send_telegram(msg)

# ==============================
# SIGNAL GENERATION
# ==============================
def generate_signal(symbol, df, model):
    last = df.iloc[-1]

    score = 0

    if last["momentum"]:
        score += 30
    if last["volume_spike"]:
        score += 30
    if last["returns"] > 0:
        score += 20

    ai_score = 0
    if model:
        X = pd.DataFrame([{
            "entry": last["Close"],
            "sl": last["Close"] * 0.98,
            "tp": last["Close"] * 1.04,
            "score": score
        }])
        ai_score = model.predict_proba(X)[0][1] * 100

    final_score = (score + ai_score) / 2

    return {
        "symbol": symbol,
        "entry": last["Close"],
        "sl": last["Close"] * 0.98,
        "tp": last["Close"] * 1.04,
        "score": round(final_score, 1)
    }

# ==============================
# SAVE TRADE
# ==============================
def save_trade(signal):
    now = datetime.now()

    row = pd.DataFrame([{
        "symbol": signal["symbol"],
        "entry": signal["entry"],
        "sl": signal["sl"],
        "tp": signal["tp"],
        "score": signal["score"],
        "date": now.date(),
        "time": now.strftime("%H:%M"),
        "status": "OPEN",
        "exit_price": None,
        "exit_time": None
    }])

    if os.path.exists(TRADES_FILE):
        row.to_csv(TRADES_FILE, mode="a", header=False, index=False)
    else:
        row.to_csv(TRADES_FILE, index=False)

# ==============================
# LIVE PRICE
# ==============================
def get_price(symbol):
    try:
        df = yf.download(symbol + ".NS", period="1d", interval="1m")
        return df["Close"].iloc[-1]
    except:
        return None

# ==============================
# UPDATE TRADES
# ==============================
def update_trades():
    if not os.path.exists(TRADES_FILE):
        return

    df = pd.read_csv(TRADES_FILE)

    for i, row in df.iterrows():
        if row["status"] != "OPEN":
            continue

        price = get_price(row["symbol"])
        if price is None:
            continue

        if price >= row["tp"]:
            df.at[i, "status"] = "WIN"
            df.at[i, "exit_price"] = price
            df.at[i, "exit_time"] = datetime.now()

        elif price <= row["sl"]:
            df.at[i, "status"] = "LOSS"
            df.at[i, "exit_price"] = price
            df.at[i, "exit_time"] = datetime.now()

    df.to_csv(TRADES_FILE, index=False)

# ==============================
# EOD REPORT
# ==============================
def generate_eod():
    if not os.path.exists(TRADES_FILE):
        return

    df = pd.read_csv(TRADES_FILE)
    df["date"] = pd.to_datetime(df["date"]).dt.date

    today = datetime.now().date()
    df = df[df["date"] == today]

    wins = len(df[df["status"] == "WIN"])
    losses = len(df[df["status"] == "LOSS"])
    open_trades = len(df[df["status"] == "OPEN"])

    total = len(df)
    acc = (wins / total * 100) if total > 0 else 0

    msg = f"""
📊 EOD REPORT

Total: {total}
Wins: {wins}
Losses: {losses}
Open: {open_trades}
Accuracy: {acc:.1f}%
"""

    send_telegram(msg)

# ==============================
# TRAIN AI
# ==============================
def train_ai():
    if not os.path.exists(TRADES_FILE):
        return

    df = pd.read_csv(TRADES_FILE)
    df = df[df["status"].isin(["WIN","LOSS"])]

    if len(df) < 20:
        return

    df["target"] = df["status"].apply(lambda x: 1 if x == "WIN" else 0)

    X = df[["entry","sl","tp","score"]]
    y = df["target"]

    model = RandomForestClassifier()
    model.fit(X, y)

    joblib.dump(model, MODEL_FILE)

# ==============================
# MARKET TREND
# ==============================
def market_trend():
    df = yf.download("^NSEI", period="1d", interval="15m")
    if df.empty:
        return "NEUTRAL"

    if df["Close"].iloc[-1] > df["Open"].iloc[0]:
        return "BULLISH"
    return "BEARISH"

# ==============================
# MAIN SCANNER
# ==============================
def run_scan():
    model = load_model()

    trend = market_trend()
    send_telegram(f"Market: {trend}")

    if trend == "BEARISH":
        send_telegram("⚠️ Market weak — trade carefully")

    sector_strength = get_sector_strength()
    send_sector_summary(sector_strength)

    sector_df = pd.read_csv(SECTOR_FILE) if os.path.exists(SECTOR_FILE) else pd.DataFrame()
    sector_map = dict(zip(sector_df.get("symbol", []), sector_df.get("sector", [])))

    signals = []

    for stock in STOCKS:
        df = fetch_data(stock)
        if df is None:
            continue

        df = compute_features(df)
        sig = generate_signal(stock, df, model)

        sector = sector_map.get(stock, None)

        if sector:
            strength = sector_strength.get(sector, 0)

            if strength > 0:
                sig["score"] += 10
            else:
                sig["score"] -= 10

        if sig["score"] > 60:
            signals.append(sig)
            save_trade(sig)

    if signals:
        msg = "🚨 SIGNALS\n\n"
        for s in signals:
            msg += f"""{s['symbol']} ({s['score']})
Entry: {s['entry']:.2f}
SL: {s['sl']:.2f}
TP: {s['tp']:.2f}

"""
        send_telegram(msg)
    else:
        print("No signals")

# ==============================
# MAIN
# ==============================
def main():
    now = datetime.now().hour

    if now < 15:
        run_scan()
        update_trades()
    else:
        update_trades()
        generate_eod()
        train_ai()

if __name__ == "__main__":
    main()