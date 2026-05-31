import yfinance as yf
import pandas as pd
import os
import requests
import time
import json
from datetime import datetime

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

DATA_DIR = "data"
ALERT_FILE = f"{DATA_DIR}/alerted_today.csv"
SIGNAL_FILE = f"{DATA_DIR}/signals.csv"
CONFIG_FILE = f"{DATA_DIR}/model_config.json"

os.makedirs(DATA_DIR, exist_ok=True)

# ================= TELEGRAM =================
def send(msg):
    """Send Telegram message immediately — no retry delay bloat."""
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{TOKEN}/sendMessage",
            data={"chat_id": CHAT_ID, "text": msg},
            timeout=10
        )
        if r.status_code != 200:
            print(f"Telegram error: {r.status_code} {r.text}")
    except Exception as e:
        print(f"Telegram exception: {e}")

# ================= CONFIG =================
def load_config():
    defaults = {
        "trend_min": 0.002,
        "volume_min": 1.5,
        "momentum_min": 0.003,
        "rsi_min": 50,
        "rsi_max": 75,
        "min_score": 60,
        "win_rate": 0,
        "total_trades": 0,
        "wins": 0
    }
    if not os.path.exists(CONFIG_FILE):
        return defaults
    try:
        loaded = json.load(open(CONFIG_FILE))
        # Merge: keep new keys from defaults if missing in saved config
        for k, v in defaults.items():
            loaded.setdefault(k, v)
        return loaded
    except Exception:
        return defaults

# ================= ALERT =================
def load_alerted():
    if not os.path.exists(ALERT_FILE):
        return set()
    try:
        df = pd.read_csv(ALERT_FILE)
        today = str(datetime.now().date())
        if "date" in df.columns:
            return set(df[df["date"] == today]["stock"].tolist())
    except Exception:
        pass
    return set()

def save_alert(stock):
    today = str(datetime.now().date())
    df = pd.DataFrame([[stock, today]], columns=["stock", "date"])
    df.to_csv(ALERT_FILE, mode="a", header=not os.path.exists(ALERT_FILE), index=False)

# ================= SAVE =================
def save_signal(data):
    df = pd.DataFrame([data])
    df.to_csv(SIGNAL_FILE, mode="a", header=not os.path.exists(SIGNAL_FILE), index=False)

# ================= STOCKS =================
def get_stage1_stocks():
    """Use Stage-1 cache if fresh (today's date), else fallback to NSE universe."""
    cache_file = f"{DATA_DIR}/stage1_cache.csv"
    try:
        if os.path.exists(cache_file):
            df = pd.read_csv(cache_file)
            if "date" in df.columns:
                today = str(datetime.now().date())
                df["date"] = df["date"].astype(str)
                today_df = df[df["date"] == today]
                if not today_df.empty:
                    symbols = today_df["symbol"].dropna().tolist()
                    print(f"✅ Stage-1 cache loaded: {len(symbols)} stocks")
                    return symbols
    except Exception as e:
        print(f"Stage-1 cache read error: {e}")

    # Fallback: fetch NSE EQ universe
    try:
        df = pd.read_csv("https://archives.nseindia.com/content/equities/EQUITY_L.csv")
        df.columns = df.columns.str.strip().str.upper()
        if "SERIES" in df.columns:
            df = df[df["SERIES"] == "EQ"]
        stocks = df["SYMBOL"].dropna().unique().tolist()
        print(f"⚠️ Stage-1 cache stale — using NSE universe: {len(stocks)} stocks")
        return stocks
    except Exception as e:
        print(f"❌ NSE fetch error: {e}")
        return []

# ================= FETCH =================
def fetch(stock):
    try:
        df = yf.download(stock + ".NS", period="5d", interval="5m", progress=False)
        if df.empty:
            return None
        df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]
        df = df.dropna()
        # Only keep today's candles
        today = str(datetime.now().date())
        df.index = pd.to_datetime(df.index)
        df = df[df.index.date == datetime.now().date()]
        return df if len(df) >= 10 else None
    except Exception:
        return None

# ================= INDICATORS =================
def compute_rsi(series, period=14):
    delta = series.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain / loss.replace(0, 1e-9)
    return 100 - (100 / (1 + rs))

def compute_vwap(df):
    tp = (df["High"] + df["Low"] + df["Close"]) / 3
    return (tp * df["Volume"]).cumsum() / df["Volume"].cumsum()

# ================= SCORE =================
def score_signal(trend, volume, momentum, rsi, near_vwap):
    score = 0
    score += min(trend * 5000, 25)       # up to 25 pts
    score += min((volume - 1) * 15, 25)  # up to 25 pts
    score += min(momentum * 5000, 25)    # up to 25 pts
    if 50 <= rsi <= 75:
        score += 15
    if near_vwap:
        score += 10
    return round(score, 2)

# ================= SNIPER =================
def sniper(stock, config):
    df = fetch(stock)
    if df is None or len(df) < 15:
        return None

    close = df["Close"]
    last = float(close.iloc[-1])

    # Price floor
    if last < 50:
        return None

    # ---- TREND: EMA20 > EMA50 (bullish structure) ----
    ema20 = float(close.ewm(span=20).mean().iloc[-1])
    ema50 = float(close.ewm(span=50).mean().iloc[-1])
    if ema20 <= ema50:
        return None

    trend = (last - ema20) / ema20
    if trend < config["trend_min"]:
        return None

    # ---- RSI: not overbought, not oversold ----
    rsi = float(compute_rsi(close).iloc[-1])
    if not (config["rsi_min"] <= rsi <= config["rsi_max"]):
        return None

    # ---- VOLUME surge ----
    avg_vol = float(df["Volume"].rolling(20).mean().iloc[-1])
    vol = float(df["Volume"].iloc[-1])
    if avg_vol == 0:
        return None
    volume_ratio = vol / avg_vol
    if volume_ratio < config["volume_min"]:
        return None

    # ---- MOMENTUM (5-bar) ----
    if len(close) < 6:
        return None
    momentum = float((close.iloc[-1] - close.iloc[-5]) / close.iloc[-5])
    if momentum < config["momentum_min"]:
        return None

    # ---- VWAP: price above VWAP (buy-side confirmation) ----
    vwap = float(compute_vwap(df).iloc[-1])
    near_vwap = last > vwap * 0.998  # within 0.2% above VWAP

    # ---- BREAKOUT: near recent high (entry timing) ----
    recent = df.iloc[-8:]
    high = float(recent["High"].max())
    low = float(recent["Low"].min())
    distance_to_high = (high - last) / high
    is_breakout = distance_to_high < 0.005  # within 0.5% of recent high

    if not is_breakout:
        return None

    # ---- COMPOSITE SCORE ----
    score = score_signal(trend, volume_ratio, momentum, rsi, near_vwap)
    if score < config.get("min_score", 60):
        return None

    return {
        "stock": stock,
        "entry": round(last, 2),
        "sl": round(low, 2),
        "tp": round(last * 1.025, 2),
        "trend": round(trend, 4),
        "volume": round(volume_ratio, 2),
        "momentum": round(momentum, 4),
        "rsi": round(rsi, 1),
        "vwap": round(vwap, 2),
        "score": score,
        "date": str(datetime.now().date()),
        "time": datetime.now().strftime("%H:%M"),
        "result": "OPEN"
    }

# ================= MAIN =================
def main():
    config = load_config()
    alerted = load_alerted()
    stocks = get_stage1_stocks()

    if not stocks:
        send("⚠️ Trading Radar: No stocks loaded for scan.")
        return

    print(f"🔍 Scanning {len(stocks)} stocks...")
    results = []

    for stock in stocks:
        if stock in alerted:
            continue
        try:
            sig = sniper(stock, config)
            if sig:
                results.append(sig)
                save_alert(stock)
                save_signal(sig)
        except Exception as e:
            print(f"Error on {stock}: {e}")
        time.sleep(0.15)

    if not results:
        print("⚠️ No signals this scan")
        return

    results = sorted(results, key=lambda x: x["score"], reverse=True)
    top = results[:5]  # send top 5 only (quality > quantity)

    win_rate = config.get("win_rate", 0)
    msg = f"🚀 TRADING RADAR SIGNALS (WinRate: {win_rate}%)\n"
    msg += f"Time: {datetime.now().strftime('%H:%M')} | Found: {len(results)}\n\n"

    for r in top:
        msg += (
            f"📈 {r['stock']} [Score:{r['score']}]\n"
            f"Entry: ₹{r['entry']}  SL: ₹{r['sl']}  TP: ₹{r['tp']}\n"
            f"RSI: {r['rsi']}  Vol: {r['volume']}x  Mom: {r['momentum']}\n\n"
        )

    send(msg)
    print(f"✅ Sent {len(top)} signals")

if __name__ == "__main__":
    main()
