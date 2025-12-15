#!/usr/bin/env python3
"""
premarket_universe_builder.py
Runs at 8:30 AM IST
Builds NIFTY1000-based watchlist using:
- Recent price momentum (top gainers)
- Morning / overnight news (RSS)
Outputs: data/universe_pre_market.csv
AWS-safe (no NSE scraping)
"""

import pandas as pd
import yfinance as yf
import feedparser
import re
from datetime import datetime
from pathlib import Path

DATA_DIR = "data"
BASE_UNIVERSE = f"{DATA_DIR}/nifty1000.csv"
OUT_CSV = f"{DATA_DIR}/universe_pre_market.csv"

TOP_GAINERS_COUNT = 80   # configurable

# ---------------- NEWS KEYWORDS ----------------
KEYWORDS = {
    "order": 3,
    "contract": 3,
    "results": 3,
    "profit": 2,
    "merger": 3,
    "acquisition": 3,
    "approval": 3,
    "buyback": 2,
    "dividend": 2,
    "upgrade": 2,
    "expansion": 2,
    "launch": 2,
    "regulatory": 3,
}

RSS_FEEDS = [
    "https://www.moneycontrol.com/rss/results.xml",
    "https://www.moneycontrol.com/rss/latestnews.xml",
    "https://feeds.finance.yahoo.com/rss/2.0/headline?s=IN&region=IN&lang=en-IN",
    "https://news.google.com/rss/search?q=india+stock+market",
]

# ------------------------------------------------

def load_nifty1000():
    df = pd.read_csv(BASE_UNIVERSE)
    df.columns = [c.strip().lower() for c in df.columns]

    if "symbol" not in df.columns:
        raise ValueError("nifty1000.csv must contain a SYMBOL column")

    # Add .NS suffix if missing
    symbols = (
        df["symbol"]
        .astype(str)
        .str.strip()
        .apply(lambda x: x + ".NS" if not x.endswith(".NS") else x)
        .unique()
        .tolist()
    )

    return symbols


def get_top_gainers(symbols, top_n=80):
    scores = []

    for s in symbols:
        try:
            df = yf.download(
                s,
                period="3d",
                interval="1d",
                auto_adjust=False,
                progress=False,
            )

            if df is None or len(df) < 2:
                continue

            prev_close = df["Close"].iloc[-2].item()
            last_close = df["Close"].iloc[-1].item()
            if prev_close <= 0:
                continue

            pct_change = (last_close - prev_close) / prev_close * 100.0
            scores.append((s, round(pct_change, 2)))

        except Exception:
            continue

    scores.sort(key=lambda x: x[1], reverse=True)
    return scores[:top_n]


def scan_news(symbols):
    news_hits = {}

    for url in RSS_FEEDS:
        feed = feedparser.parse(url)
        for e in feed.entries:
            title = e.get("title", "").lower()
            summary = e.get("summary", "").lower()
            text = f"{title} {summary}"

            for sym in symbols:
                base = sym.replace(".NS", "").lower()
                if base in text:
                    score = 0
                    reasons = []
                    for k, v in KEYWORDS.items():
                        if re.search(rf"\b{k}\b", text):
                            score += v
                            reasons.append(k)
                    if score > 0:
                        news_hits.setdefault(sym, {"score": 0, "reasons": set()})
                        news_hits[sym]["score"] += score
                        news_hits[sym]["reasons"].update(reasons)

    return news_hits

def priority(news_score, price_score):
    if news_score >= 6 or price_score >= 3:
        return "HIGH"
    if news_score >= 3 or price_score >= 1:
        return "MEDIUM"
    return "LOW"

def main():
    symbols = load_nifty1000()

    print(f"Loaded NIFTY1000 symbols: {len(symbols)}")

    top_gainers = dict(get_top_gainers(symbols))
    news = scan_news(symbols)

    rows = []

    combined = set(top_gainers.keys()) | set(news.keys())

    for sym in combined:
        ns = news.get(sym, {}).get("score", 0)
        ps = top_gainers.get(sym, 0)
        reason = []

        if sym in top_gainers:
            reason.append("Top gainer")
        if sym in news:
            reason.append("News")

        rows.append({
            "symbol": sym,
            "news_score": ns,
            "price_score": ps,
            "reason": " + ".join(reason),
            "priority": priority(ns, ps),
        })

    out = pd.DataFrame(rows).sort_values(
        by=["priority", "news_score", "price_score"],
        ascending=[True, False, False]
    )

    out.to_csv(OUT_CSV, index=False)
    print("Generated:", OUT_CSV, "rows:", len(out))

if __name__ == "__main__":
    main()
