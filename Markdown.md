pymac.py – Automated Macro Intelligence Engine
Real-time macro news intelligence, market impact scoring, and cross-asset monitoring.

pymac.py is a fully automated macro-analysis engine that continuously ingests global news, indexes macro-sensitive events, scores market impact, tracks stock/crypto/currency reactions, and stores all results in a structured SQLite database.

This system is designed for:

Macro traders

Crypto analysts

Quantitative researchers

Automated strategy pipelines

Alerting & sentiment systems

Hedge-fund style real-time macro feeds

🔍 Key Capabilities
✔ Global Financial News Ingestion

Pulls real-time news from:

New York Times – Business

Reuters – Business

CNBC

Yahoo Finance

Plus:

✔ Built-in Trump Truth Social Scraper

Captures latest posts from @realDonaldTrump and automatically elevates fiscal-related posts to ULTRA-HIGH priority.

Fiscal keywords include:

“rates”, “Fed”, “tariffs”, “jobs”, “inflation”, “deficit”, “stock market”, “Dow”, “Nasdaq”, “budget”, etc.

🧠 Market Impact Scoring Engine

Each article or Trump post is evaluated using:

1. Sentiment Polarity Weighting

via TextBlob (-1 → +1)

2. Macro Keyword Density Score

Matches against a curated list of high-signal macro terms:

fed, fomc, inflation, cpi, ppi, jobs report, recession,
tariff, trade war, deficit, shutdown, etc.

3. Hot Event Detection

+20% boost if the article references:
fed, cpi, jobs

4. Trump Fiscal Boost

+40% weighting for fiscal-policy Trump posts.

🚨 Macro Quarantine System

Events that exceed 0.8 macro-sensitivity OR are Trump fiscal posts are stored in:

macro_quarantine


Tracked until the underlying macro situation resolves.

📊 Cross-Market Reaction Tracking

For any event with impact_score > 0.6, the system checks real-time reactions in:

US Index Futures

S&P Futures (ES=F)

S&P Index (^GSPC)

Nasdaq (^IXIC)

VIX (^VIX)

Nikkei (^N225)

STOXX50E (^STOXX50E)

High-Volume Equities

Top names: NVDA, TSLA, AMD, META, SMCI, HOOD, etc.

Crypto

BTC (via CoinGecko)

ETH

BTC/ETH dominance

Supply metrics

Currencies (% change)

EURUSD

USDJPY

GBPUSD

AUDUSD

🧱 Database Schema
news
Column	Description
id	Primary key
title	News headline
summary	Text summary
link	Unique article link
source	Feed source
sentiment	Polarity score
impact_score	Final score (0–1)
macro_score	Macro sensitivity
processed_at	Timestamp
macro_quarantine

Tracks macro-critical events that require follow-up.

stock_impact

Reaction metrics per symbol:

price change

volume spike

market_metrics

Stores all market snapshot values every loop cycle.

📦 Installation
1. Clone repo
git clone https://github.com/yourname/pymac
cd pymac

2. Create virtual environment
python3 -m venv myenv
source myenv/bin/activate


(Windows)

myenv\Scripts\activate

3. Install dependencies
pip install -r requirements.txt


Recommended packages:

requests
beautifulsoup4
lxml
feedparser
textblob
yfinance
pandas
pycoingecko
pandas_ta
sqlite3-binary

▶ Running the Engine
python3 pymac.py


By default it:

Runs forever

Refreshes every 300 seconds

Logs activity to pymac.log

Prints an ASCII market dashboard like:

MARKET SNAPSHOT
SP_FUTURES:  5054.25 [UP] +0.82%
NASDAQ:     18752.44 [DOWN] -0.12%
BTC: $103,822 [UP] +1.43%

📡 Architecture Overview
┌──────────────────────┐
│ fetch_news()         │
│ Trump Truth fetch    │
└──────────┬───────────┘
           ▼
┌──────────────────────┐
│ NLP + Macro Scoring  │
│ Sentiment + Keywords │
└──────────┬───────────┘
           ▼
┌──────────────────────┐
│ Compute Impact Score │
│ Store in SQLite      │
└──────────┬───────────┘
           ▼
┌──────────────────────┐
│ Market Reaction Scan │
│ Stocks / FX / Crypto │
└──────────┬───────────┘
           ▼
┌──────────────────────┐
│ Quarantine System    │
│ Track macro threats  │
└──────────────────────┘

🛠 Troubleshooting
Truth Social errors

If HTML changes, update the selector:

soup.find_all('div', class_='status__content')

RSS feed errors

Normal — some feeds rate-limit occasionally.

pandas_ta hangs

RSI intentionally disabled in this version.
