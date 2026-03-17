import sys
import os
import pandas as pd
import numpy as np
import yfinance as yf
import joblib
from datetime import datetime
import pytz
from ta.momentum import RSIIndicator
from ta.trend import EMAIndicator
from ta.volatility import AverageTrueRange

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from alerts.telegram_alerts import send_alert

CACHE_FILE = "data/stage1_cache.csv"
SIGNALS_FILE = "data/signals.csv"
ALERT_LOG_FILE = "data/alerted_today.csv"
MODEL_FILE = "data/ai_model.pkl"

# -----------------------------
# Sector mapping
# -----------------------------
SECTOR_MAP = {
    "POWER":["ADANIPOWER","TATAPOWER","NTPC","TORNTPOWER"],
    "DEFENSE":["BDL","BEL","HAL","GRSE"],
    "RAIL":["IRCON","RVNL","TEXRAIL","RAILTEL"],
    "CHEMICAL":["SOLARINDS","SRF","NAVINFLUOR","AARTIIND"],
    "IT":["INFY","TCS","HCLTECH","LTIM"],
    "BANK":["HDFCBANK","ICICIBANK","AXISBANK","SBIN"]
}

# -----------------------------
# Load stage1 stocks
# -----------------------------
def load_stage1_watchlist():

    if not os.path.exists(CACHE_FILE):
        return []

    df = pd.read_csv(CACHE_FILE)

    return df["symbol"].tolist()

# -----------------------------
# Prevent duplicate alerts
# -----------------------------
def load_alerted():

    if os.path.exists(ALERT_LOG_FILE):
        return set(pd.read_csv(ALERT_LOG_FILE)["symbol"])

    return set()

def save_alerted(symbol):

    df = pd.DataFrame([[symbol]], columns=["symbol"])

    if os.path.exists(ALERT_LOG_FILE):
        df.to_csv(ALERT_LOG_FILE, mode="a", header=False, index=False)
    else:
        df.to_csv(ALERT_LOG_FILE, index=False)

# -----------------------------
# Save signals
# -----------------------------
def save_signals(signals):

    ist = pytz.timezone("Asia/Kolkata")
    now = datetime.now(ist)

    df = pd.DataFrame(signals)

    df["date"] = now.date()
    df["trigger_time"] = now.strftime("%H:%M:%S")
    df["result"] = ""

    columns = [
        "symbol","action","entry","sl","tp",
        "score","eta","date","trigger_time","result"
    ]

    df = df[columns]

    if os.path.exists(SIGNALS_FILE):

        existing = pd.read_csv(SIGNALS_FILE)
        combined = pd.concat([existing, df], ignore_index=True)
        combined.to_csv(SIGNALS_FILE,index=False)

    else:

        df.to_csv(SIGNALS_FILE,index=False)

# -----------------------------
# Sector score
# -----------------------------
def get_sector_score(symbol):

    for sector,stocks in SECTOR_MAP.items():

        if symbol in stocks:

            moves = []

            for s in stocks:

                try:
                    t = yf.Ticker(s+".NS")
                    d = t.history(period="2d", interval="15m")

                    change = (d["Close"].iloc[-1]-d["Close"].iloc[-5]) / d["Close"].iloc[-5]

                    moves.append(change)

                except:
                    pass

            if len(moves)==0:
                return 0

            sector_move = np.mean(moves)

            if sector_move>0.02:
                return 20

            if sector_move>0.01:
                return 10

    return 0

# -----------------------------
# Analyze stock
# -----------------------------
def analyze_symbol(symbol, model):

    try:

        ticker = yf.Ticker(symbol+".NS")

        df = ticker.history(period="30d", interval="15m")

        if len(df)<80:
            return None

        df["EMA20"]=EMAIndicator(df["Close"],window=20).ema_indicator()
        df["EMA50"]=EMAIndicator(df["Close"],window=50).ema_indicator()

        df["RSI"]=RSIIndicator(df["Close"],window=14).rsi()

        df["VOL_AVG"]=df["Volume"].rolling(20).mean()

        atr=AverageTrueRange(df["High"],df["Low"],df["Close"],window=14)

        df["ATR"]=atr.average_true_range()

        latest=df.iloc[-1]

        entry=latest["Close"]

        # liquidity filter
        traded_value=latest["Close"]*latest["Volume"]

        if traded_value<20000000:
            return None

        # AI features
        volatility=(latest["High"]-latest["Low"])/latest["Close"]
        volume_ratio=latest["Volume"]/latest["VOL_AVG"]
        distance_high=entry-df["High"].rolling(20).max().iloc[-2]

        features=np.array([[latest["RSI"],latest["EMA20"],latest["EMA50"],
                            volatility,volume_ratio,distance_high]])

        ai_prob=model.predict_proba(features)[0][1]

        ai_score=ai_prob*100

        # volatility squeeze
        vol20=df["Close"].pct_change().rolling(20).std()
        vol5=df["Close"].pct_change().rolling(5).std()

        squeeze=vol5.iloc[-1]<0.6*vol20.iloc[-1]

        early_score=20 if squeeze else 0

        # volume accumulation
        vol_acc=df["Volume"].rolling(10).mean().iloc[-1] > 1.2*df["Volume"].rolling(30).mean().iloc[-1]

        if vol_acc:
            early_score+=20

        # momentum acceleration
        momentum=df["Close"].pct_change().iloc[-1]

        if momentum>0.005:
            early_score+=20

        # relative strength vs nifty
        nifty=yf.Ticker("^NSEI")
        nd=nifty.history(period="5d", interval="15m")

        n_move=(nd["Close"].iloc[-1]-nd["Close"].iloc[-5])/nd["Close"].iloc[-5]
        s_move=(df["Close"].iloc[-1]-df["Close"].iloc[-5])/df["Close"].iloc[-5]

        rs=s_move-n_move

        rs_score=20 if rs>0.01 else 0

        # sector bonus
        sector_score=get_sector_score(symbol)

        final_score=ai_score+early_score+rs_score+sector_score

        if final_score<70:
            return None

        # ATR based target
        sl=df["Low"].rolling(5).min().iloc[-1]

        tp=entry + df["ATR"].iloc[-1]*2

        # ETA
        if momentum>0.01:
            eta="30m"
        elif momentum>0.005:
            eta="1h"
        else:
            eta="2h"

        return {
            "symbol":symbol,
            "action":"BUY",
            "entry":round(entry,2),
            "sl":round(sl,2),
            "tp":round(tp,2),
            "score":round(final_score,1),
            "eta":eta
        }

    except:
        return None

# -----------------------------
# MAIN
# -----------------------------
def main():

    ist=pytz.timezone("Asia/Kolkata")

    now=datetime.now(ist)

    time_now=now.strftime("%H:%M")

    if not ("09:20"<=time_now<="15:30"):
        print("Outside market hours.")
        return

    if not os.path.exists(MODEL_FILE):
        print("AI model not found")
        return

    model=joblib.load(MODEL_FILE)

    symbols=load_stage1_watchlist()

    print(f"Stage-1 stocks: {len(symbols)}")

    alerted=load_alerted()

    signals=[]

    for symbol in symbols:

        signal=analyze_symbol(symbol,model)

        if signal and symbol not in alerted:

            signals.append(signal)

            save_alerted(symbol)

    if not signals:
        print("No new signals.")
        return

    signals=sorted(signals,key=lambda x:x["score"],reverse=True)

    signals=signals[:27]

    save_signals(signals)

    message=f"🚨 <b>AI MOMENTUM RADAR</b> | {time_now}\n\n"

    for s in signals:

        message+=(
            f"{s['symbol']} | Score {s['score']}\n"
            f"Entry: {s['entry']} | SL: {s['sl']} | Target: {s['tp']}\n"
            f"ETA: {s['eta']}\n\n"
        )

    send_alert(message)

if __name__=="__main__":
    main()