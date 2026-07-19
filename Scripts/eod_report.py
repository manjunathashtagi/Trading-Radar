import pandas as pd
import json
import os
import requests
from datetime import datetime

CONFIG_FILE = "data/model_config.json"
SIGNAL_FILE = "data/signals.csv"

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

def send(msg):
    if not TOKEN or not CHAT_ID:
        print(msg)
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{TOKEN}/sendMessage",
            data={"chat_id": CHAT_ID, "text": msg},
            timeout=10
        )
    except Exception as e:
        print(f"Telegram error: {e}")

def load_config():
    defaults = {
        "trend_min": 0.002, "volume_min": 1.5, "momentum_min": 0.003,
        "rsi_min": 50, "rsi_max": 75, "min_score": 60,
        "win_rate": 0, "total_trades": 0, "wins": 0
    }
    if not os.path.exists(CONFIG_FILE):
        return defaults
    try:
        loaded = json.load(open(CONFIG_FILE))
        for k, v in defaults.items():
            loaded.setdefault(k, v)
        return loaded
    except Exception:
        return defaults

def evaluate_open_signals(df):
    """
    Evaluate every OPEN signal -- not just ones raised today. Walks forward
    day-by-day from each signal's own date to today using daily OHLC and marks
    the first day TP or SL was touched. A signal only stays OPEN if neither
    has been touched on any trading day since it was raised.

    Previously this only checked `date == today`, so any signal that didn't
    resolve on its own generation day was silently orphaned as OPEN forever --
    that's why signals.csv had zero closed trades across 34 trading days.

    If both TP and SL are touched on the same day, SL is assumed to have
    happened first -- daily bars can't tell intraday order, so this is the
    conservative (not optimistic) assumption.
    """
    try:
        import yfinance as yf
    except ImportError:
        print("yfinance not available for EOD evaluation")
        return df

    open_mask = df["result"].astype(str).str.strip() == "OPEN"
    open_df = df[open_mask]

    if open_df.empty:
        print("📊 EOD: no open signals to evaluate")
        return df

    updated = 0
    # One yfinance call per symbol (covering its earliest pending date to today),
    # not one per row -- avoids re-downloading the same stock's history repeatedly.
    for symbol, group in open_df.groupby("stock"):
        if not symbol or str(symbol) == "nan":
            continue

        start_date = str(group["date"].min())
        try:
            hist = yf.download(f"{symbol}.NS", start=start_date, interval="1d", progress=False)
            if hist.empty:
                continue
            hist.columns = [c[0] if isinstance(c, tuple) else c for c in hist.columns]
            hist.index = hist.index.astype(str).str[:10]  # normalize to YYYY-MM-DD
        except Exception:
            continue

        for idx, row in group.iterrows():
            sig_date = str(row["date"])
            try:
                tp = float(row["tp"])
                sl = float(row["sl"])
            except (ValueError, TypeError):
                continue

            window = hist[hist.index >= sig_date]
            if window.empty:
                continue

            result = None
            for _, day in window.iterrows():
                hit_tp = day["High"] >= tp
                hit_sl = day["Low"] <= sl
                if hit_tp and hit_sl:
                    result = "SL"  # ambiguous same-day order -- conservative
                elif hit_tp:
                    result = "TARGET"
                elif hit_sl:
                    result = "SL"
                if result:
                    break

            if result:
                df.at[idx, "result"] = result
                updated += 1

    print(f"📊 EOD: evaluated {updated} open signals (across all pending dates)")
    return df

def main():
    today = str(datetime.now().date())

    if not os.path.exists(SIGNAL_FILE):
        send("📊 EOD Report\nNo signals file found.")
        print("No signal file")
        return

    df = pd.read_csv(SIGNAL_FILE)

    # Auto-evaluate open signals
    df = evaluate_open_signals(df)
    df.to_csv(SIGNAL_FILE, index=False)

    # Today's closed trades only
    df["date"] = df["date"].astype(str)
    today_df = df[df["date"] == today]
    closed = today_df[today_df["result"].isin(["TARGET", "SL"])]

    wins = len(closed[closed["result"] == "TARGET"])
    losses = len(closed[closed["result"] == "SL"])
    open_trades = len(today_df[today_df["result"] == "OPEN"])
    total_closed = wins + losses

    win_rate_today = round((wins / total_closed * 100), 1) if total_closed > 0 else 0

    # All-time stats
    all_closed = df[df["result"].isin(["TARGET", "SL"])]
    all_wins = len(all_closed[all_closed["result"] == "TARGET"])
    all_total = len(all_closed)
    all_time_wr = round((all_wins / all_total * 100), 1) if all_total > 0 else 0

    # Update config with adaptive learning
    config = load_config()
    config["win_rate"] = all_time_wr
    config["total_trades"] = all_total
    config["wins"] = all_wins

    if all_total >= 10:
        if all_time_wr < 45:
            # Tighten filters when performing poorly
            config["volume_min"] = round(min(config["volume_min"] + 0.1, 3.0), 2)
            config["momentum_min"] = round(min(config["momentum_min"] + 0.001, 0.015), 4)
            config["min_score"] = min(config.get("min_score", 60) + 2, 80)
            config["trend_min"] = round(min(config["trend_min"] + 0.001, 0.01), 4)
            print("📉 Tightening filters (win rate below 45%)")
        elif all_time_wr > 60:
            # Relax slightly when performing well
            config["volume_min"] = round(max(config["volume_min"] - 0.05, 1.3), 2)
            config["min_score"] = max(config.get("min_score", 60) - 1, 55)
            print("📈 Relaxing filters (win rate above 60%)")

    json.dump(config, open(CONFIG_FILE, "w"), indent=2)

    # Build EOD message
    msg = (
        f"📊 EOD REPORT — {today}\n\n"
        f"Today's Signals:\n"
        f"✅ Wins:   {wins}\n"
        f"❌ Losses: {losses}\n"
        f"⏳ Open:   {open_trades}\n"
        f"Win Rate Today: {win_rate_today}%\n\n"
        f"All-Time:\n"
        f"Total Closed: {all_total} | Win Rate: {all_time_wr}%\n\n"
        f"Config Updated:\n"
        f"Vol Min: {config['volume_min']}x | Mom Min: {config['momentum_min']} | Score: {config.get('min_score', 60)}"
    )

    send(msg)
    print("✅ EOD done:", config)

if __name__ == "__main__":
    main()
