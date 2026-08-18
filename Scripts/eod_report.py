import pandas as pd
import json
import os
import requests
from datetime import datetime, timedelta

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
    Evaluate every OPEN signal using intraday (5-minute) bars starting from the
    signal's exact timestamp, not the whole trading day.

    Previous version used full daily High/Low, which includes price action
    BEFORE the signal fired. Since these are momentum/volume-surge stocks,
    the day's total range almost always exceeds the 1%/0.5% TP/SL band
    regardless of what happened after entry -- so it defaulted to the
    conservative "both touched -> SL" branch on nearly every signal
    (that's why All-Time win rate showed 0.1% with 2462/2462 marked SL).

    Yahoo only retains 5-minute history for ~60 days. Signals older than that
    fall back to daily bars (same limitation as before, but daily-only after
    60 days is unavoidable -- Yahoo simply doesn't have finer data that far back).
    """
    try:
        import yfinance as yf
    except ImportError:
        print("yfinance not available for EOD evaluation")
        return df

    today = datetime.now().date()
    open_mask = df["result"].astype(str).str.strip() == "OPEN"
    open_df = df[open_mask]

    if open_df.empty:
        print("📊 EOD: no open signals to evaluate")
        return df

    updated = 0
    # Yahoo only serves 5-minute bars for ~60 days. Decide intraday-vs-daily
    # PER ROW, not per symbol: previously one old signal for a stock forced
    # every signal for that stock (including yesterday's) onto whole-day bars,
    # which is exactly the contamination this function exists to avoid. It also
    # risked an empty 5m download (start beyond ~60d) silently skipping the
    # whole symbol.
    intraday_cutoff = today - timedelta(days=58)

    for symbol, group in open_df.groupby("stock"):
        if not symbol or str(symbol) == "nan":
            continue

        row_dates = pd.to_datetime(group["date"], errors="coerce").dt.date
        has_intraday_rows = (row_dates >= intraday_cutoff).any()
        has_daily_rows = (row_dates < intraday_cutoff).any()

        hist_i = None
        hist_d = None

        if has_intraday_rows:
            # Clamp start to the cutoff so the 5m request stays inside Yahoo's window
            i_start = max(row_dates.min(), intraday_cutoff)
            try:
                h = yf.download(f"{symbol}.NS", start=str(i_start), interval="5m", progress=False)
                if not h.empty:
                    h.columns = [x[0] if isinstance(x, tuple) else x for x in h.columns]
                    if h.index.tz is not None:
                        # Signal times are written by run_intraday.py via
                        # datetime.now() on a GitHub Actions runner = UTC.
                        # Must normalize to UTC, not IST.
                        h.index = h.index.tz_convert("UTC").tz_localize(None)
                    hist_i = h
            except Exception:
                hist_i = None

        if has_daily_rows:
            try:
                h = yf.download(f"{symbol}.NS", start=str(row_dates.min()), interval="1d", progress=False)
                if not h.empty:
                    h.columns = [x[0] if isinstance(x, tuple) else x for x in h.columns]
                    h.index = h.index.astype(str).str[:10]
                    hist_d = h
            except Exception:
                hist_d = None

        for idx, row in group.iterrows():
            sig_date = str(row["date"])
            try:
                tp = float(row["tp"])
                sl = float(row["sl"])
                r_date = pd.to_datetime(sig_date).date()
            except (ValueError, TypeError):
                continue

            if r_date >= intraday_cutoff:
                if hist_i is None:
                    continue
                sig_time = str(row.get("time", "03:45"))
                try:
                    sig_ts = pd.Timestamp(f"{sig_date} {sig_time}")
                except Exception:
                    sig_ts = pd.Timestamp(f"{sig_date} 03:45")
                window = hist_i[hist_i.index >= sig_ts]
            else:
                if hist_d is None:
                    continue
                window = hist_d[hist_d.index >= sig_date]

            if window.empty:
                continue

            result = None
            for _, bar in window.iterrows():
                hit_tp = bar["High"] >= tp
                hit_sl = bar["Low"] <= sl
                if hit_tp and hit_sl:
                    result = "SL"  # ambiguous same-bar order -- conservative
                elif hit_tp:
                    result = "TARGET"
                elif hit_sl:
                    result = "SL"
                if result:
                    break

            if result:
                df.at[idx, "result"] = result
                updated += 1

    print(f"📊 EOD: evaluated {updated} open signals (intraday where available)")
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
            # Tighten filters when performing poorly.
            # trend_min/momentum_min are NOT raised here -- real win/loss data
            # showed winners had LOWER trend/momentum than losers.
            #
            # min_score is FROZEN as of this patch, not just left alone like
            # trend_min/momentum_min: factor_audit.py on 2,449 closed trades
            # showed the score itself was inversely correlated with winning
            # (lowest-score quintile: 43.6% win rate; highest: 32.5%), because
            # the score formula rewarded the same high trend/momentum that
            # loses more. Raising min_score was therefore filtering FOR worse
            # trades, which is almost certainly why 2,400+ trades of tightening
            # (60->76) never moved the win rate. The score formula itself has
            # been changed (score_signal in run_intraday.py) to reward the low
            # end of the trend/momentum band instead of the high end. Leave
            # min_score frozen here until there's a real batch of signals
            # scored under the NEW formula -- auto-raising it again before that
            # data exists would just repeat the same mistake blind.
            config["volume_min"] = round(min(config["volume_min"] + 0.1, 3.0), 2)
            print("📉 Tightening volume_min only (win rate below 45%). "
                  "min_score frozen pending data under the corrected score formula.")
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