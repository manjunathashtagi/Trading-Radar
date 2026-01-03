import pandas as pd
import yfinance as yf
import requests
import os
from datetime import datetime

# ---------------- CONFIG ----------------
UNIVERSE_FILE = "data/universe_nse.csv"
OUTPUT_FILE = "data/universe_pre_market.csv"

NIFTY_SYMBOL = "^NSEI"

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

MIN_CONFIDENCE = 60
MAX_STOCKS_IN_ALERT = 20

# ---------------------------------------


def send_telegram(message: str):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("⚠️ Telegram credentials missing")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }

    try:
        requests.post(url, data=payload, timeout=10)
    except Exception as e:
        print("Telegram error:", e)


def get_nifty_change_pct():
    try:
        df = yf.download(NIFTY_SYMBOL, period="2d", interval="1d", progress=False)

        if df.empty or len(df) < 2:
            return 0.0

        close = df["Close"]

        # Handle Series / DataFrame edge case
        if isinstance(close, pd.DataFrame):
            close = close.iloc[:, 0]

        prev_close = float(close.iloc[-2])
        last_close = float(close.iloc[-1])

        return ((last_close - prev_close) / prev_close) * 100

    except Exception as e:
        print("NIFTY fetch failed:", e)
        return 0.0



def main():
    start_time = datetime.now()
    print("🚀 Premarket scan started at", start_time)

    # ---------------- LOAD UNIVERSE ----------------
    universe = pd.read_csv(UNIVERSE_FILE)
    symbols = universe["symbol"].dropna().unique().tolist()

    print(f"📊 Total symbols to scan: {len(symbols)}")

    nifty_change = get_nifty_change_pct()
    print(f"📉 NIFTY prev day change: {nifty_change:.2f}%")

    rows = []

    # ---------------- STOCK LOOP ----------------
    for i, symbol in enumerate(symbols, start=1):
        try:
            ticker = yf.Ticker(symbol + ".NS")
            hist = ticker.history(period="2d", interval="1d")

            if len(hist) < 2:
                continue

            prev_close = hist["Close"].iloc[-2]
            last_close = hist["Close"].iloc[-1]
            volume = hist["Volume"].iloc[-1]

            prev_day_change_pct = ((last_close - prev_close) / prev_close) * 100
            relative_strength = prev_day_change_pct - nifty_change

            confidence = 50
            if relative_strength > 0:
                confidence += 20
            if volume > hist["Volume"].mean():
                confidence += 15
            if prev_day_change_pct > 2:
                confidence += 15

            rows.append({
                "symbol": symbol,
                "prev_day_change_pct": round(prev_day_change_pct, 2),
                "relative_strength": round(relative_strength, 2),
                "confidence": confidence
            })

            if i % 50 == 0:
                print(f"✅ Processed {i} stocks")

        except Exception as e:
            print(f"❌ Error processing {symbol}: {e}")

    df = pd.DataFrame(rows)

    if df.empty:
        print("⚠️ No data collected")
        return

    # ---------------- FILTER & SAVE ----------------
    df = df[df["confidence"] >= MIN_CONFIDENCE]
    df = df.sort_values("confidence", ascending=False)
    df = df.head(MAX_STOCKS_IN_ALERT)

    os.makedirs("data", exist_ok=True)
    df.to_csv(OUTPUT_FILE, index=False)

    # ---------------- TELEGRAM ----------------
    if df.empty:
        print("ℹ️ No qualifying stocks today")
        return

    message = "*📊 Premarket Radar (High Confidence)*\n\n"
    for _, r in df.iterrows():
        message += (
            f"• `{r['symbol']}` | "
            f"Δ {r['prev_day_change_pct']}% | "
            f"RS {r['relative_strength']} | "
            f"Conf {r['confidence']}\n"
        )

    send_telegram(message)

    end_time = datetime.now()
    print("✅ Premarket scan completed at", end_time)
    print("⏱️ Duration:", end_time - start_time)


if __name__ == "__main__":
    main()
