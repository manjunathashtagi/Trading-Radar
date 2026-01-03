import pandas as pd
import yfinance as yf
import datetime as dt
import json
import os
import requests

# ================= CONFIG =================
DATE = dt.date.today().strftime("%Y%m%d")
WATCHLIST = f"radar_watchlist_{DATE}.csv"
STATE_FILE = f"alerted_today_{DATE}.json"

MAX_TRADES_PER_DAY = 3

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# ================= TELEGRAM =================
def send_telegram(msg):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": msg})

# ================= STATE =================
def load_alerted():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            return set(json.load(f))
    return set()

def save_alerted(alerted):
    with open(STATE_FILE, "w") as f:
        json.dump(sorted(list(alerted)), f)

# ================= ORB =================
def get_orb_high(df):
    orb = df.between_time("09:15", "09:45")
    if orb.empty:
        return None
    return orb["High"].max()

# ================= CONFIDENCE =================
def confidence_grade(score):
    if score >= 8:
        return "A (High)"
    if score >= 6:
        return "B (Medium)"
    return "C (Low)"

# ================= EVALUATE =================
def evaluate_stock(row):
    symbol = row["symbol"]
    bucket_pct = row["target_bucket"]

    df = yf.download(symbol + ".NS", period="1d", interval="15m", progress=False)
    if len(df) < 30:
        return None

    df["EMA9"] = df["Close"].ewm(span=9).mean()
    df["EMA21"] = df["Close"].ewm(span=21).mean()
    df["VWAP"] = (
        (df["Volume"] * (df["High"] + df["Low"] + df["Close"]) / 3).cumsum()
        / df["Volume"].cumsum()
    )
    df["ATR"] = (df["High"] - df["Low"]).rolling(14).mean()

    last = df.iloc[-1]
    prev = df.iloc[-2]

    score = 0

    # ORB
    orb_high = get_orb_high(df)
    if orb_high and last["Close"] > orb_high:
        score += 2
    else:
        return None

    # VWAP + EMA
    if last["Close"] > last["VWAP"] and last["EMA9"] > last["EMA21"]:
        score += 2
    else:
        return None

    # Volume
    avg_vol = df["Volume"].rolling(5).mean().iloc[-1]
    if last["Volume"] >= avg_vol * 1.5:
        score += 2

    # Relative Strength
    if row["relative_strength_pct"] >= 1.0:
        score += 2

    # Sector Strength
    if row["sector_strength"] >= 1.0:
        score += 2

    entry_low = max(prev["High"], last["EMA9"], last["VWAP"])
    entry_high = last["High"]

    stop_loss = min(
        prev["Low"],
        last["EMA21"],
        last["VWAP"] - 0.5 * last["ATR"]
    )

    pct = float(bucket_pct.replace("%", ""))
    target = entry_high * (1 + pct / 100)

    risk = entry_high - stop_loss
    reward = target - entry_high

    if risk <= 0 or reward / risk < 1.5:
        return None

    return {
        "entry": f"{round(entry_low,2)}–{round(entry_high,2)}",
        "sl": round(stop_loss, 2),
        "target": round(target, 2),
        "confidence": confidence_grade(score),
        "score": score
    }

# ================= MAIN =================
def main():
    if not os.path.exists(WATCHLIST):
        return

    watch = pd.read_csv(WATCHLIST)
    alerted = load_alerted()

    if len(alerted) >= MAX_TRADES_PER_DAY:
        return

    for _, row in watch.iterrows():
        if len(alerted) >= MAX_TRADES_PER_DAY:
            break

        symbol = row["symbol"]
        if symbol in alerted:
            continue

        result = evaluate_stock(row)
        if not result:
            continue

        msg = (
            f"📈 BUY SETUP ({row['target_bucket']})\n\n"
            f"Stock: {symbol}\n"
            f"Sector: {row['sector']}\n"
            f"Confidence: {result['confidence']}\n\n"
            f"Buy Zone: {result['entry']}\n"
            f"Stop Loss: {result['sl']}\n"
            f"Target: {result['target']}\n\n"
            f"Context:\n"
            f"• Relative strength vs NIFTY\n"
            f"• Strong sector\n"
            f"• VWAP + EMA alignment\n"
            f"• ORB breakout\n\n"
            f"Trade {len(alerted)+1}/{MAX_TRADES_PER_DAY}"
        )

        send_telegram(msg)
        alerted.add(symbol)

    save_alerted(alerted)

if __name__ == "__main__":
    main()
