import pandas as pd
import datetime
import os
import requests

UNIVERSE_FILE = "data/universe_nse_tradable.csv"
TRADES_FILE = "data/trades_today.csv"

def send_telegram(msg):
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    requests.post(url, data={"chat_id": chat_id, "text": msg})

def market_open():
    now = datetime.datetime.now().time()
    return datetime.time(9, 15) <= now <= datetime.time(15, 30)

def main():
    if not market_open():
        print("Market closed.")
        return

    if not os.path.exists(UNIVERSE_FILE):
        print("⚠️ Universe missing. Skipping run.")
        return

    universe = pd.read_csv(UNIVERSE_FILE)
    print(f"📊 Intraday universe size: {len(universe)}")

    trades = []

    for _, row in universe.iterrows():
        symbol = row.get("symbol") or row.get("SYMBOL")
        if not symbol:
            continue

        entry = 100.0
        target = round(entry * 1.02, 2)
        sl = round(entry * 0.99, 2)

        trade = {
            "symbol": symbol,
            "entry": entry,
            "target": target,
            "sl": sl,
            "time": datetime.datetime.now().isoformat(),
            "status": "OPEN"
        }

        trades.append(trade)

        send_telegram(
            f"🚨 Intraday Alert\n"
            f"{symbol}\n"
            f"Entry: {entry}\n"
            f"SL: {sl}\n"
            f"Target: {target}"
        )

    if trades:
        os.makedirs("data", exist_ok=True)
        df_trades = pd.DataFrame(trades)

        if os.path.exists(TRADES_FILE):
            df_trades = pd.concat([pd.read_csv(TRADES_FILE), df_trades])

        df_trades.to_csv(TRADES_FILE, index=False)

if __name__ == "__main__":
    main()