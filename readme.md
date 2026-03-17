Trading Radar – AI Driven Momentum Detection System for NSE

Executive Summary
Trading Radar is an AI-assisted market scanning system designed to detect early momentum opportunities

in the Indian stock market (NSE).

 

The platform scans hundreds of stocks and analyzes volatility compression, volume accumulation,

sector momentum, relative strength vs index, and machine learning probability scores.

 

The objective is to surface high-probability setups before large price expansion so traders can

manually evaluate opportunities.

Problem Statement
Retail traders often face three challenges:

 

• Too many stocks to scan manually

• Late entries after breakouts

• Lack of structured signal discovery

 

Traditional scanners detect moves after they start.

Trading Radar focuses on identifying pre-breakout conditions.

System Architecture
Market Data

    ↓

Premarket Scanner

    ↓

Stage‑1 Watchlist (Top ~120 stocks)

    ↓

AI Momentum Engine

    ↓

Signal Ranking System

    ↓

Top Signals → Telegram Alerts

    ↓

Signals Database (signals.csv)

    ↓

End‑of‑Day Performance Analysis

    ↓

Weekly Performance Analytics

Detection Logic
Trading Radar evaluates several market factors simultaneously:

 

AI Momentum Model

The ML model evaluates RSI, EMA structure, volatility, volume patterns and breakout distance.

 

Volatility Compression

Low volatility often precedes large price movements.

 

Volume Accumulation

Gradual volume expansion may indicate institutional accumulation.

 

Momentum Acceleration

Short‑term price acceleration increases signal probability.

 

Relative Strength vs NIFTY

Stocks outperforming the index receive additional ranking weight.

 

Sector Strength

Stocks in strong sectors receive bonus ranking points.

 

Liquidity Filter

Stocks must meet a minimum traded value threshold to avoid illiquid instruments.

Signal Ranking
Final score calculation combines multiple factors:

 

AI Score

+ Momentum Score

+ Volume Accumulation Score

+ Relative Strength Score

+ Sector Strength Bonus

 

Only stocks above a defined threshold are considered signals.

The radar then selects the highest ranked signals.

Telegram Alert Example
AI MOMENTUM RADAR

 

ADANIPOWER | Score 92

Entry: 593

Stop Loss: 579

Target: 621

ETA: 1h

 

SOLARINDS | Score 88

Entry: 12160

Stop Loss: 11820

Target: 12840

ETA: 2h

Data Pipeline
Training Pipeline

 

build_market_training_data.py

       ↓

training_data.csv

       ↓

train_ai_model.py

       ↓

ai_model.pkl

 

The trained model is used by the intraday radar to generate predictions.

Automation
Trading Radar runs automatically using GitHub Actions.

 

Premarket Scanner – builds the stage‑1 watchlist

Intraday Scanner – generates signals and sends Telegram alerts

EOD Report – evaluates trade outcomes

Weekly Report – summarizes performance metrics

Repository Structure
Trading-Radar

 

Scripts/

run_intraday.py

eod_report.py

weekly_report.py

train_ai_model.py

build_market_training_data.py

debug_stock.py

 

alerts/

telegram_alerts.py

 

data/

ai_model.pkl

signals.csv

stage1_cache.csv

training_data.csv

 

.github/workflows/

trading_radar.yml

Future Improvements
• Reinforcement learning based prediction

• Sector rotation detection

• News sentiment analysis

• Options flow integration

• Institutional order flow detection

Disclaimer
Trading Radar is an experimental analytical tool.

 

It does not provide financial advice and does not guarantee profits.

Financial markets involve risk and users should conduct their own analysis

before making trading decisions.