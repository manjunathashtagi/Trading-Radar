import yfinance as yf
import pandas as pd
import numpy as np
import requests
import os

# ================= CONFIG =================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

STOCKS = {
    "RELIANCE": "ENERGY",
    "TCS": "IT",
    "INFY": "IT",
    "HDFCBANK": "BANK",
    "ICICIBANK": "BANK",
    "SBIN": "BANK",
    "LT": "INFRA",
    "ITC": "FMCG",
    "BHARTIARTL": "TELCO",
    "ASIANPAINT": "FMCG",
    "AXISBANK": "BANK",
    "KOTAKBANK": "BANK",
    "MARUTI": "AUTO",
    "SUNPHARMA": "PHARMA",
    "TITAN": "CONSUMPTION",
    "ULTRACEMCO": "INFRA",
    "WIPRO": "IT",
    "NESTLEIND": "FMCG"
}

# ================= TELEGRAM =================
def send_telegram(msg):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        requests.post(url, data={"chat_id": CHAT_ID, "text": msg})
    except:
        pass

# ================= FII/DII =================
def get_fii_dii():
    try:
        url = "https://www.nseindia.com/api/fiidiiTradeReact"
        headers = {"User-Agent": "Mozilla/5.0"}

        session = requests.Session()
        session.get("https://www.nseindia.com", headers=headers)
        response = session.get(url, headers=headers)

        data = response.json()["data"]
        df = pd.DataFrame(data)
        latest = df.iloc[0]

        return float(latest["fiiNet"]), float(latest["diiNet"])
    except:
        return 0, 0

def get_bias(fii, dii):
    if dii > 0 and fii < 0:
        return "HIDDEN_BULLISH"
    elif fii > 0 and dii > 0:
        return "STRONG_BULLISH"
    elif fii < 0 and dii < 0:
        return "BEARISH"
    return "NEUTRAL"

# ================= DATA =================
def fetch(symbol):
    df = yf.download(symbol + ".NS", period="5d", interval="15m")
    if df.empty:
        return df

    df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]
    df = df.apply(pd.to_numeric, errors="coerce")
    df.dropna(inplace=True)
    return df

# ================= MARKET =================
def nifty_data():
    df = fetch("^NSEI")
    return df

def market_trend(df):
    if df.empty:
        return "NEUTRAL"
    return "BULLISH" if df["Close"].iloc[-1] > df["Open"].iloc[0] else "BEARISH"

# ================= FEATURES =================
def add_features(df):
    df["EMA20"] = df["Close"].ewm(span=20).mean()
    df["EMA50"] = df["Close"].ewm(span=50).mean()

    df["VOL_SPIKE"] = df["Volume"] / df["Volume"].rolling(20).mean()

    df["RS"] = df["Close"].pct_change(5)

    df.dropna(inplace=True)
    return df

# ================= SECTOR STRENGTH =================
def sector_strength():
    sector_perf = {}

    for stock, sector in STOCKS.items():
        df = fetch(stock)
        if df.empty:
            continue

        change = (df["Close"].iloc[-1] - df["Close"].iloc[-5]) / df["Close"].iloc[-5]

        if sector not in sector_perf:
            sector_perf[sector] = []

        sector_perf[sector].append(change)

    sector_avg = {k: np.mean(v) for k, v in sector_perf.items() if v}

    if not sector_avg:
        return []

    strong = sorted(sector_avg, key=sector_avg.get, reverse=True)

    return strong[:2]  # top 2 sectors

# ================= SIGNAL =================
def generate(stock, df, trend, bias, strong_sectors):
    df = add_features(df)
    if df.empty:
        return None

    latest = df.iloc[-1]
    score = 0

    # Trend
    if trend == "BULLISH" and latest["Close"] > latest["EMA20"]:
        score += 1

    # Volume
    if latest["VOL_SPIKE"] > 1.3:
        score += 1

    # Structure
    if latest["EMA20"] > latest["EMA50"]:
        score += 1

    # Relative strength
    if latest["RS"] > 0:
        score += 1

    # Sector filter 🔥
    if STOCKS[stock] in strong_sectors:
        score += 1

    # Bias
    if bias in ["HIDDEN_BULLISH", "STRONG_BULLISH"]:
        score += 1
    elif bias == "BEARISH":
        score -= 1

    confidence = round((score / 6) * 100, 1)

    if confidence < 65:
        return None

    entry = float(latest["Close"])

    return {
        "symbol": stock,
        "confidence": confidence,
        "entry": entry,
        "sl": round(entry * 0.98, 2),
        "tp": round(entry * 1.05, 2)
    }

# ================= MAIN =================
def run():
    fii, dii = get_fii_dii()
    bias = get_bias(fii, dii)

    nifty = nifty_data()
    trend = market_trend(nifty)

    strong_sectors = sector_strength()

    print(f"Market: {trend}, Bias: {bias}, Strong sectors: {strong_sectors}")

    signals = []

    for stock in STOCKS:
        df = fetch(stock)
        if df.empty:
            continue

        sig = generate(stock, df, trend, bias, strong_sectors)

        if sig:
            signals.append(sig)

    if not signals:
        send_telegram(
            f"⚠️ No signals\nMarket: {trend}\nBias: {bias}\nStrong: {strong_sectors}"
        )
        return

    msg = f"🚨 SMART MONEY SIGNALS\nMarket: {trend}\nBias: {bias}\nStrong Sectors: {strong_sectors}\n\n"

    for s in signals:
        msg += f"{s['symbol']} ({s['confidence']})\nEntry: {s['entry']} SL:{s['sl']} TP:{s['tp']}\n\n"

    send_telegram(msg)

# ================= RUN =================
if __name__ == "__main__":
    run()