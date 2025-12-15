#!/usr/bin/env python3
"""
production_scanner_e2.py

Features:
 - Prioritized universe: Top Gainers (computed) -> NIFTY500 -> user tickers -> fallback
 - Default interval 900s (15 minutes)
 - Deduplication of Telegram alerts with persistent signature store and cooldown (CLI configurable)
 - Scanners: PDH breakout, EMA20/50 cross, Supertrend, VWAP cross, volume spike, 1% spike-in-1-bar (scalper)
 - Aggregated Telegram message "🟦 STOCK PICKS" with buy, SL, targets, Est time, score
 - CLI flags for toggling scanners and thresholds
"""

from __future__ import annotations
import argparse
import json
import hashlib
import logging
import os
import sys
import time
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any, Tuple

import numpy as np
import pandas as pd
import requests
import yfinance as yf


TRADES_FILE = "trades_store.json"

# ----------------------
# Logging setup
# ----------------------
logger = logging.getLogger("production_scanner")
handler = logging.StreamHandler(sys.stdout)
fmt = "%(asctime)s %(levelname)s %(message)s"
handler.setFormatter(logging.Formatter(fmt))
logger.addHandler(handler)
logger.setLevel(logging.INFO)

# ----------------------
# Constants / defaults
# ----------------------
DEFAULT_INTERVAL = 900  # 15 minutes
DEFAULT_LIMIT = 100
ALERT_STORE_FILE = os.path.expanduser("~/.production_scanner_last_alerts.json")
ALERT_STORE_DEFAULT_COOLDOWN = 60 * 60 * 24  # 24 hours
NIFTY_CSV_URLS = [
    "https://www1.nseindia.com/content/indices/ind_nifty500list.csv",
    "https://www.nseindia.com/content/indices/ind_nifty500list.csv",
]

# ----------------------
# Utilities
# ----------------------
def load_universe_from_csv(path="data/universe_pre_market.csv"):
    if not os.path.isfile(path):
        logger.error("Universe CSV not found: %s", path)
        sys.exit(1)

    df = pd.read_csv(path)
    if "symbol" not in df.columns:
        logger.error("CSV missing 'symbol' column")
        sys.exit(1)

    symbols = df["symbol"].dropna().unique().tolist()
    logger.info("Loaded %d symbols from premarket CSV", len(symbols))
    return symbols


def set_debug(enabled: bool):
    logger.setLevel(logging.DEBUG if enabled else logging.INFO)
    if enabled:
        logger.debug("Debug logging enabled")

def safe_open_read_lines(path: str) -> List[str]:
    for enc in ("utf-8-sig", "utf-8", "utf-16"):
        try:
            with open(path, "r", encoding=enc) as fh:
                lines = [ln.strip() for ln in fh.readlines()]
                return [ln for ln in lines if ln]
        except Exception as e:
            logger.debug("read(%s,%s) failed: %s", path, enc, e)
    return []
    
def load_trades():
    if os.path.isfile(TRADES_FILE):
        with open(TRADES_FILE, "r") as f:
            return json.load(f)
    return []

def save_trades(trades):
    with open(TRADES_FILE, "w") as f:
        json.dump(trades, f, indent=2)

def trade_exists(trades, ticker):
    for t in trades:
        if t["ticker"] == ticker and t["status"] == "OPEN":
            return True
    return False

# ----------------------
# Column helpers / flatten
# ----------------------
def flatten_columns(df: pd.DataFrame) -> pd.DataFrame:
    new_cols = []
    fields = {"open", "high", "low", "close", "volume", "adj close", "adjclose", "price", "vwap"}
    for c in df.columns:
        if isinstance(c, tuple):
            chosen = None
            if len(c) > 1 and isinstance(c[1], str) and c[1].strip().lower() in fields:
                chosen = c[1]
            elif isinstance(c[0], str) and c[0].strip().lower() in fields:
                chosen = c[0]
            else:
                if len(c) > 1 and isinstance(c[1], str) and c[1].strip():
                    chosen = c[1]
                elif isinstance(c[0], str) and c[0].strip():
                    chosen = c[0]
                else:
                    chosen = "_".join(str(x) for x in c if x is not None)
            new_cols.append(str(chosen))
        else:
            new_cols.append(str(c))
    new_cols = [col.strip() for col in new_cols]
    df = df.copy()
    df.columns = new_cols
    return df

# ----------------------
# Indicators / scanners
# ----------------------
def compute_vwap(df: pd.DataFrame) -> pd.Series:
    tp = (df["High"] + df["Low"] + df["Close"]) / 3.0
    v = df["Volume"].replace(0, np.nan).fillna(0)
    cum_tp_v = (tp * v).cumsum()
    cum_v = v.cumsum()
    vwap = (cum_tp_v / cum_v).ffill()
    return vwap

def ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()

def supertrend(df: pd.DataFrame, period: int = 10, multiplier: float = 3.0) -> pd.Series:
    hl2 = (df["High"] + df["Low"]) / 2.0
    tr1 = df["High"] - df["Low"]
    tr2 = (df["High"] - df["Close"].shift(1)).abs()
    tr3 = (df["Low"] - df["Close"].shift(1)).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.rolling(window=period, min_periods=1).mean()
    upper_basic = hl2 + multiplier * atr
    lower_basic = hl2 - multiplier * atr

    upper_band = upper_basic.copy()
    lower_band = lower_basic.copy()

    for i in range(1, len(df)):
        if upper_basic.iloc[i] < upper_band.iloc[i-1] or df["Close"].iloc[i-1] > upper_band.iloc[i-1]:
            upper_band.iloc[i] = upper_basic.iloc[i]
        else:
            upper_band.iloc[i] = upper_band.iloc[i-1]

        if lower_basic.iloc[i] > lower_band.iloc[i-1] or df["Close"].iloc[i-1] < lower_band.iloc[i-1]:
            lower_band.iloc[i] = lower_basic.iloc[i]
        else:
            lower_band.iloc[i] = lower_band.iloc[i-1]

    st = pd.Series(index=df.index, dtype="int8")
    direction = 1
    for i in range(len(df)):
        if i == 0:
            st.iloc[i] = 1
            continue
        cur_close = df["Close"].iloc[i]
        if cur_close > upper_band.iloc[i-1]:
            direction = 1
        elif cur_close < lower_band.iloc[i-1]:
            direction = -1
        st.iloc[i] = direction
    return st

def detect_breakout(ticker: str, df: pd.DataFrame, lookback: int = 20) -> Optional[dict]:
    try:
        if "Close" not in df.columns or "High" not in df.columns:
            return None
        if len(df) < lookback + 1:
            return None
        latest = df["Close"].iloc[-1]
        prev_high = df["High"].iloc[-(lookback + 1):-1].max()
        if pd.isna(latest) or pd.isna(prev_high):
            return None
        if float(latest) > float(prev_high):
            return {
                "ticker": ticker,
                "timestamp": datetime.utcnow().isoformat(),
                "latest_close": float(latest),
                "prev_high": float(prev_high),
                "lookback": lookback,
            }
    except Exception:
        logger.exception("Error in detect_breakout for %s", ticker)
    return None

# ----------------------
# Top gainers / prioritized universe
# ----------------------
def get_percent_change_for_tickers(tickers: List[str], period: str = "2d", interval: str = "5m", timeout: int = 30) -> Dict[str, float]:
    pct = {}
    for t in tickers:
        try:
            df = yf.download(t, period=period, interval=interval, auto_adjust=False, progress=False, threads=False, timeout=timeout)
            if df is None or df.empty:
                continue
            df = flatten_columns(df)
            if "Close" not in df.columns:
                continue
            latest_close = float(df["Close"].iloc[-1])
            # attempt to get prior day last close
            try:
                uniq_dates = pd.Index(df.index.normalize()).unique()
                if len(uniq_dates) >= 2:
                    prev_date = uniq_dates[-2]
                    prev_close = float(df.loc[df.index.normalize() == prev_date, "Close"].iloc[-1])
                else:
                    prev_close = float(df["Close"].iloc[0])
            except Exception:
                prev_close = float(df["Close"].iloc[0])
            if prev_close == 0:
                continue
            pct_change = (latest_close - prev_close) / prev_close * 100.0
            pct[t] = pct_change
        except Exception as e:
            logger.debug("get_pct change failed for %s: %s", t, e)
            continue
    return pct



# ----------------------
# Alert dedupe persistence
# ----------------------
def _load_alert_store(store_file: str) -> Dict[str, Any]:
    try:
        if os.path.isfile(store_file):
            with open(store_file, "r", encoding="utf-8") as fh:
                return json.load(fh)
    except Exception:
        logger.debug("Failed to load alert store", exc_info=True)
    return {"signatures": {}}

def _save_alert_store(store_file: str, store: Dict[str, Any]):
    try:
        with open(store_file, "w", encoding="utf-8") as fh:
            json.dump(store, fh)
    except Exception:
        logger.debug("Failed to save alert store", exc_info=True)

def make_alert_signature_line(line: str) -> str:
    h = hashlib.sha1(line.encode("utf-8")).hexdigest()
    return h

def filter_new_alerts_message(lines: List[str], store_file: str, cooldown_seconds: int) -> List[str]:
    store = _load_alert_store(store_file)
    sigs = store.get("signatures", {})
    now_ts = int(time.time())
    new_lines = []
    for ln in lines:
        sig = make_alert_signature_line(ln)
        last_ts = sigs.get(sig)
        if last_ts and (now_ts - last_ts) < cooldown_seconds:
            logger.debug("Skipping duplicate alert (cooldown) for line: %s", ln)
            continue
        new_lines.append(ln)
        sigs[sig] = now_ts
    store["signatures"] = sigs
    _save_alert_store(store_file, store)
    return new_lines

# ----------------------
# Telegram utility
# ----------------------
def telegram_notify(text: str) -> bool:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        logger.debug("Telegram not configured (TELEGRAM_BOT_TOKEN/CHAT_ID).")
        return False
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}
    try:
        r = requests.post(url, json=payload, timeout=10)
        if r.status_code == 200:
            return True
        else:
            logger.warning("Telegram API returned %s: %s", r.status_code, r.text)
            return False
    except Exception as e:
        logger.debug("Telegram notify failed: %s", e)
        return False

# ----------------------
# Single-ticker analysis
# ----------------------
def analyze_ticker(ticker: str, df: pd.DataFrame, args) -> Optional[Dict[str, Any]]:
    """
    Analyze a single ticker DataFrame and produce signals and a mini trade plan.
    Returns dict with 'ticker', 'score' (int), 'lines' (list of pick-lines), 'findings' (details)
    """
    try:
        if df is None or df.empty:
            logger.debug("Empty dataframe for %s", ticker)
            return None

        df = flatten_columns(df)

        # Normalize column names
        col_map = {}
        for c in df.columns:
            lc = c.strip().lower()
            if lc in ("adj close", "adjclose"):
                col_map[c] = "Adj Close"
            elif lc == "open":
                col_map[c] = "Open"
            elif lc == "high":
                col_map[c] = "High"
            elif lc == "low":
                col_map[c] = "Low"
            elif lc == "close":
                col_map[c] = "Close"
            elif lc == "volume":
                col_map[c] = "Volume"
            elif lc == "vwap":
                col_map[c] = "VWAP"
            else:
                col_map[c] = c
        df = df.rename(columns=col_map)

        if df.columns.duplicated().any():
            df = df.groupby(level=0, axis=1).first()

        for col in ["Open", "High", "Low", "Close", "Adj Close", "Volume", "VWAP"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")

        price_cols = [c for c in ("Open", "High", "Low", "Close") if c in df.columns]
        if not price_cols:
            logger.debug("No price columns for %s after normalization", ticker)
            return None
        df = df.dropna(axis=0, how="all", subset=price_cols)
        if len(df) < 5:
            logger.debug("Not enough rows for %s (rows=%s)", ticker, len(df))
            return None

        if isinstance(df.index, pd.DatetimeIndex):
            df = df.sort_index()

        findings = {}
        score = 0

        # PDH breakout
        try:
            pdh = detect_breakout(ticker, df, lookback=args.pdh_lookback)
            if pdh:
                findings["pdh_breakout"] = pdh
                score += 1
        except Exception:
            logger.exception("Error running PDH for %s", ticker)

        # EMA cross
        try:
            if args.ema_cross and "Close" in df.columns:
                df["EMA20"] = ema(df["Close"], 20)
                df["EMA50"] = ema(df["Close"], 50)
                if len(df) >= 2:
                    prev_ema20 = df["EMA20"].iloc[-2]
                    prev_ema50 = df["EMA50"].iloc[-2]
                    cur_ema20 = df["EMA20"].iloc[-1]
                    cur_ema50 = df["EMA50"].iloc[-1]
                    if (prev_ema20 <= prev_ema50) and (cur_ema20 > cur_ema50):
                        findings["ema_cross"] = {"type": "bullish"}
                        score += 1
                    elif (prev_ema20 >= prev_ema50) and (cur_ema20 < cur_ema50):
                        findings["ema_cross"] = {"type": "bearish"}
        except Exception:
            logger.exception("Error computing EMA cross for %s", ticker)

        # Supertrend
        try:
            if args.supertrend_enabled and {"High", "Low", "Close"}.issubset(set(df.columns)):
                st = supertrend(df, period=args.supertrend_period, multiplier=args.supertrend_mult)
                findings["supertrend"] = {"current": int(st.iloc[-1])}
                if int(st.iloc[-1]) == 1:
                    score += 1
        except Exception:
            logger.exception("Error computing supertrend for %s", ticker)

        # VWAP cross (up/down/both)
        try:
            if args.vwap_cross and {"High", "Low", "Close", "Volume"}.issubset(set(df.columns)):
                vwap = compute_vwap(df)
                df["VWAP_COMPUTED"] = vwap
                if len(df) >= 2:
                    prev_close = df["Close"].iloc[-2]
                    prev_vwap = vwap.iloc[-2]
                    cur_close = df["Close"].iloc[-1]
                    cur_vwap = vwap.iloc[-1]
                    if args.vwap_cross in ("up", "both") and (prev_close <= prev_vwap and cur_close > cur_vwap):
                        findings["vwap_cross"] = {"type": "up"}
                        score += 1
                    if args.vwap_cross in ("down", "both") and (prev_close >= prev_vwap and cur_close < cur_vwap):
                        findings["vwap_cross"] = {"type": "down"}
                        # bearish not scored as buy signal
        except Exception:
            logger.exception("Error computing VWAP for %s", ticker)

        # Volume surge (compared to average)
        try:
            if "Volume" in df.columns and args.volume_surge_multiplier > 0:
                avg_vol = df["Volume"].tail(60).mean() if len(df) >= 60 else df["Volume"].mean()
                cur_vol = df["Volume"].iloc[-1]
                if avg_vol > 0 and cur_vol >= args.volume_surge_multiplier * avg_vol:
                    findings["volume_surge"] = {"mult": round(float(cur_vol / (avg_vol or 1)), 2)}
                    score += 1
        except Exception:
            logger.exception("Error computing volume surge for %s", ticker)

        # 1% spike-in-5min (scalper)
        try:
            if args.spike_pct and "Close" in df.columns:
                if len(df) >= 2:
                    prev_close = df["Close"].iloc[-2]
                    cur_close = df["Close"].iloc[-1]
                    if prev_close > 0 and ((cur_close - prev_close) / prev_close * 100.0) >= args.spike_pct:
                        findings["spike"] = {"pct": round((cur_close - prev_close) / prev_close * 100.0, 2)}
                        score += 1
        except Exception:
            logger.exception("Error computing spike for %s", ticker)

        # if no findings, skip
        if not findings:
            return None

        # Build trade plan:
        latest = float(df["Close"].iloc[-1])
        sl_pct = args.sl_pct if args.sl_pct is not None else 0.015
        # entry is latest price, SL below, targets conservative multiples (you can tune)
        entry = round(latest, 2)
        sl = round(latest * (1.0 - sl_pct), 2)
        tgt1 = round(latest * (1.0 + 0.02), 2)  # 2% target
        tgt2 = round(latest * (1.0 + 0.04), 2)  # 4% target
        # expected time window heuristic:
        # more signals -> shorter expected time; these are heuristics — tune for your strategy.
        expected_hours = 72
        if score >= 3:
            expected_hours = 24
        elif score == 2:
            expected_hours = 48
        elif score == 1:
            expected_hours = 72
        est_minutes = int(expected_hours * 60)

        # percent upside to tgt1 (for display)
        upside_pct = round((tgt1 - entry) / entry * 100.0, 2)

        # Construct a single pick line (consistent formatting, used for dedupe)
        # Example: "RELIANCE | Buy ₹1525.50 | Tgt ₹1571.27 | SL ₹1498.04 | Est ≈120m | +3.00% | score=2"
        pick_line = f"{ticker} | Buy ₹{entry:.2f} | Tgt ₹{tgt1:.2f} | SL ₹{sl:.2f} | Est ≈{est_minutes}m | +{upside_pct:.2f}% | score={score}"

        result = {
            "ticker": ticker,
            "score": score,
            "pick_line": pick_line,
            "findings": findings,
            "entry": entry,
            "sl": sl,
            "tgt1": tgt1,
            "tgt2": tgt2,
            "est_minutes": est_minutes,
            "timestamp": datetime.utcnow().isoformat(),
        }
        return result

    except Exception as e:
        logger.exception("analyze_ticker exception for %s: %s", ticker, e)
        return None

# ----------------------
# Runner / main loop
# ----------------------
def run_scanner(tickers: List[str], args):
    alerts_sent = 0
    try:
        while True:
            start = datetime.utcnow()
            logger.info("Run start: tickers=%d limit=%d", len(tickers), args.limit)
            found_picks = []
            checked = 0
            # iterate prioritized tickers (top gainers first)
            for t in tickers:
                if checked >= args.limit:
                    break
                checked += 1
                try:
                    # download recent bars
                    df = None
                    try:
                        df = yf.download(t, period="2d", interval="5m", auto_adjust=False, progress=False, threads=False, timeout=30)
                    except Exception as e:
                        logger.debug("yfinance download failed for %s: %s", t, e)
                        df = None
                    if df is None or df.empty:
                        continue
                        analysis = analyze_ticker(t, df, args)
                        if not analysis:
                            continue

                        found_picks.append(analysis)

                        trades = load_trades()
                        if not trade_exists(trades, analysis["ticker"]):
                            trades.append({
                                "ticker": analysis["ticker"],
                                "entry": analysis["entry"],
                                "target": analysis["tgt1"],   # ✅ EOD compatible
                                "sl": analysis["sl"],
                                "score": analysis["score"],
                                "alert_time": analysis["timestamp"],
                                "status": "OPEN"
                            })
                            save_trades(trades)


                except Exception as e:
                    logger.debug("ticker loop error %s: %s", t, e)
                time.sleep(args.sleep_between or 0.05)

            logger.info("Run finished: checked=%d found=%d", checked, len(found_picks))

            # Aggregate picks into message lines
            if found_picks:
                # Sort by score desc then ticker
                found_picks = sorted(found_picks, key=lambda x: (-x["score"], x["ticker"]))
                lines = [p["pick_line"] for p in found_picks]
                # Use dedupe filter before sending
                to_send = filter_new_alerts_message(lines, store_file=args.alert_store_file, cooldown_seconds=args.cooldown_seconds)
                if to_send:
                    header = "🟦 STOCK PICKS\n\n"
                    body = "\n".join(to_send)
                    picks_count = len(found_picks)
                    min_score = min(p["score"] for p in found_picks)
                    avg_score = round(sum(p["score"] for p in found_picks) / len(found_picks), 2)
                    footer = f"\n\nPicks: {picks_count}  |  MinScore: {min_score}  |  AvgScore: {avg_score:.2f}  |  Generated: {datetime.utcnow().isoformat()}"
                    message = header + body + footer
                    if args.telegram:
                        ok = telegram_notify(message)
                        if ok:
                            alerts_sent += len(to_send)
                            logger.info("Telegram sent: picks=%d alerts_sent_total=%d", len(to_send), alerts_sent)
                        else:
                            logger.warning("Telegram send failed.")
                    else:
                        # just log the message
                        logger.info("Prepared message:\n%s", message)
                else:
                    logger.info("No new picks to send (filtered by dedupe).")
            # Sleep until next run
            elapsed = (datetime.utcnow() - start).total_seconds()
            to_sleep = max(0, args.interval - elapsed)
            logger.debug("Sleeping %.1fs until next run", to_sleep)
            time.sleep(to_sleep)
    except KeyboardInterrupt:
        logger.info("Scanner interrupted by user.")
    except Exception as e:
        logger.exception("Scanner crashed: %s", e)

# ----------------------
# Argparser & main
# ----------------------
def parse_args():
    p = argparse.ArgumentParser(prog="production_scanner_e2.py", description="Trading scanners")
    p.add_argument("--tickers", help="Path to tickers file (one symbol per line).")
    p.add_argument("--nifty", action="store_true", help="Auto-download NIFTY500 constituents (if available).")
    p.add_argument("--interval", type=int, default=900, help="Seconds between scans (default 900 = 15 minutes).")
    p.add_argument("--limit", type=int, default=100, help="Max tickers per run.")
    p.add_argument("--debug", action="store_true", help="Enable debug logging.")
    p.add_argument("--sleep-between", type=float, default=0.1, help="Sleep secs between ticker downloads.")
    # thresholds / scanner toggles
    p.add_argument("--top-gainers-pct", dest="top_gainers_pct", type=float, default=2.0,
                   help="Top gainers threshold in percent (e.g. 2.0)")
    p.add_argument("--volume-surge-mult", dest="volume_surge_multiplier", type=float, default=1.5,
                   help="Volume surge multiplier (e.g. 1.5 -> 1.5x avg)")
    p.add_argument("--vwap-cross", dest="vwap_cross", choices=["up", "down", "both"], default="up",
                   help="VWAP cross direction (up/down/both)")
    p.add_argument("--supertrend", dest="supertrend_enabled", action="store_true",
                   help="Enable supertrend change alerts")
    p.add_argument("--supertrend-period", dest="supertrend_period", type=int, default=10,
                   help="Supertrend ATR period")
    p.add_argument("--supertrend-mult", dest="supertrend_mult", type=float, default=3.0,
                   help="Supertrend multiplier")
    p.add_argument("--ema-cross", dest="ema_cross", action="store_true", help="Enable EMA20/50 crossover alerts")
    p.add_argument("--pdh-lookback", dest="pdh_lookback", type=int, default=20,
                   help="Lookback for PDH breakout (bars)")
    p.add_argument("--spike-pct", dest="spike_pct", type=float, default=1.0,
                   help="Spike percent for 1-bar (5min) scalper (e.g. 1.0)")
    p.add_argument("--telegram", action="store_true", help="Send Telegram alerts if env vars present.")
    p.add_argument("--cooldown", dest="cooldown", type=int, default=900,
                   help="Cooldown (seconds) to dedupe repeated identical alerts (default 900)")
    # Escape percent sign in help strings by doubling it: %%
    p.add_argument("--sl-pct", dest="sl_pct", type=float, default=0.015,
                   help="Stop loss percent (e.g. 0.015 = 1.5%%)")
                   
        # persistent dedupe store file (where we save last alert signature + timestamp)
    p.add_argument(
        "--alert-store-file",
        dest="alert_store_file",
        type=str,
        default="alert_store.json",
        help="Path to JSON file used to dedupe alerts between runs (default: alert_store.json)"
    )

    # cooldown used by filter_new_alerts_message()
    p.add_argument(
        "--cooldown-seconds",
        dest="cooldown_seconds",
        type=int,
        default=900,
        help="Minimum seconds before sending the same alert again (default 900 = 15 minutes)"
    )

    return p.parse_args()


def main():
    args = parse_args()
    set_debug(args.debug)
    logger.info("Final scanner config: interval=%ds limit=%d", args.interval, args.limit)

    # Build prioritized universe
    tickers = load_universe_from_csv()
    logger.info("Loaded universe from CSV: %d stocks", len(tickers))
    if not tickers:
        logger.error("Universe empty. Provide tickers file or enable --nifty.")
        sys.exit(1)

    logger.info("Final universe size: %d", len(tickers))

    if args.telegram:
        token = os.environ.get("TELEGRAM_BOT_TOKEN")
        chat = os.environ.get("TELEGRAM_CHAT_ID")
        if token and chat:
            logger.info("Telegram configured (bot+chat).")
        else:
            logger.warning("Telegram requested but TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID not set; disabling telegram.")
            args.telegram = False

    run_scanner(tickers, args)

if __name__ == "__main__":
    main()
