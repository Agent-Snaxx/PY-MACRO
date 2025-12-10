#!/usr/bin/env python3
"""
pymac.py - FINAL REVISED VERSION
Combines all fixes: Fast volume/crypto, no hangs, stable.
Adds: Trump Truth Social posts via requests (no external API key needed).
Fiscal tweets: Ultra-high priority (boost impact to 1.0 + quarantine).
"""

import time
import json
import sqlite3
import requests
from datetime import datetime, timedelta
from textblob import TextBlob
import yfinance as yf
import feedparser
import logging
import pandas as pd
from typing import List, Dict
from pycoingecko import CoinGeckoAPI

try:
    import pandas_ta as ta
    HAS_PANDAS_TA = True
except ImportError:
    HAS_PANDAS_TA = False
    print("pandas_ta not installed → RSI skipped. Run: pip install pandas_ta")

# ==============================
# CONFIG
# ==============================
CONFIG = {
    "LOOP_INTERVAL": 300,
    "DB_PATH": "macro_wire.db",
    "NEWS_SOURCES": [
        "https://rss.nytimes.com/services/xml/rss/nyt/Business.xml",
        "https://feeds.reuters.com/reuters/businessNews",
        "https://www.cnbc.com/id/100003114/device/rss/rss.html",
        "https://finance.yahoo.com/news/rssindex",
    ],
    "STOCK_SYMBOLS": ["SPY", "QQQ", "DIA", "IWM", "TLT", "GLD", "VIX"],
    "INDEX_SYMBOLS": {
        "SP_FUTURES": "ES=F",
        "SP_INDEX": "^GSPC",
        "NASDAQ": "^IXIC",
        "GOLD": "GC=F",
        "VIX": "^VIX",
        "ASIAN_SP": "^N225",        # Nikkei 225
        "EURO_SP": "^STOXX50E",
    },
    "CURRENCY_PAIRS": ["EURUSD=X", "USDJPY=X", "GBPUSD=X", "AUDUSD=X"],
    "CRYPTO_SYMBOLS": {"BTC": "bitcoin", "ETH": "ethereum"},
    "MACRO_KEYWORDS": [
        "fed", "fomc", "rate cut", "rate hike", "inflation", "cpi", "ppi",
        "jobs report", "nfp", "unemployment", "recession", "stagflation",
        "tariff", "trade war", "deficit", "debt ceiling", "shutdown"
    ],
    "TRUMP_TRUTH_URL": "https://truthsocial.com/@realDonaldTrump",
    "TRUMP_FISCAL_KEYWORDS": [  # Ultra-high priority triggers
        "economy", "stock market", "tariffs", "trade", "fed", "rates", "inflation",
        "jobs", "deficit", "debt", "tax", "budget", "wall street", "dow", "nasdaq"
    ],
    "IMPACT_THRESHOLD": 0.6,
    "MACRO_QUARANTINE_THRESHOLD": 0.8,
}

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    handlers=[logging.FileHandler("pymac.log", encoding='utf-8'), logging.StreamHandler()]
)
logger = logging.getLogger(__name__)
cg = CoinGeckoAPI()

# ==============================
# DB INIT
# ==============================
def init_db():
    conn = sqlite3.connect(CONFIG["DB_PATH"])
    cur = conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS news (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT, summary TEXT, link TEXT UNIQUE, pub_date TEXT,
            source TEXT, sentiment REAL, impact_score REAL, macro_score REAL,
            processed_at TEXT
        )
    ''')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS macro_quarantine (
            id INTEGER PRIMARY KEY, news_id INTEGER, trigger TEXT,
            tracked_since TEXT, last_update TEXT,
            FOREIGN KEY (news_id) REFERENCES news (id)
        )
    ''')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS stock_impact (
            news_id INTEGER, symbol TEXT, price_change REAL, volume_spike REAL,
            FOREIGN KEY (news_id) REFERENCES news (id)
        )
    ''')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS market_metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT, metric_type TEXT, symbol TEXT,
            value REAL, change_pct REAL, extra_data TEXT
        )
    ''')
    conn.commit()
    conn.close()
    logger.info("Database initialized.")

# ==============================
# NEWS FETCH & PROCESS
# ==============================
def fetch_news() -> List[Dict]:
    articles = []
    for url in CONFIG["NEWS_SOURCES"]:
        try:
            feed = feedparser.parse(url)
            source_name = feed.feed.title if hasattr(feed.feed, 'title') else url
            for entry in feed.entries[:10]:
                summary = entry.summary if 'summary' in entry else getattr(entry, 'description', '')[:500]
                articles.append({
                    "title": entry.title,
                    "summary": summary,
                    "link": entry.link,
                    "pub_date": entry.published if 'published' in entry else datetime.now().isoformat(),
                    "source": source_name
                })
        except Exception as e:
            logger.warning(f"Feed failed: {url} → {e}")
    return articles

def fetch_trump_truth_posts() -> List[Dict]:
    """Fetch latest Trump posts from Truth Social via requests + basic scraping."""
    posts = []
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(CONFIG["TRUMP_TRUTH_URL"], headers=headers, timeout=10)
        if response.status_code == 200:
            from bs4 import BeautifulSoup  # Requires: pip install beautifulsoup4 lxml
            soup = BeautifulSoup(response.text, 'html.parser')
            # Target post containers (inspect Truth Social HTML; adjust selectors as needed)
            post_elements = soup.find_all('div', class_='status__content')[:5]  # Top 5 recent
            for elem in post_elements:
                text = elem.get_text(strip=True)[:500]
                if text:
                    posts.append({
                        "title": f"TRUMP TRUTH: {text[:100]}...",
                        "summary": text,
                        "link": CONFIG["TRUMP_TRUTH_URL"],
                        "pub_date": datetime.now().isoformat(),
                        "source": "Truth Social (@realDonaldTrump)"
                    })
    except Exception as e:
        logger.warning(f"Truth Social fetch failed: {e}")
    return posts

def analyze_sentiment(text: str) -> float:
    return TextBlob(text).sentiment.polarity

def score_macro_impact(text: str) -> float:
    text_lower = text.lower()
    matches = sum(1 for kw in CONFIG["MACRO_KEYWORDS"] if kw in text_lower)
    return min(matches / 3.0, 1.0)

def is_trump_fiscal(text: str) -> bool:
    """Check for fiscal keywords in Trump posts."""
    text_lower = text.lower()
    return any(kw in text_lower for kw in CONFIG["TRUMP_FISCAL_KEYWORDS"])

def score_stock_impact(symbol: str) -> Dict:
    try:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period="2d", interval="5m")
        if len(hist) < 24:
            return {"price_change": 0, "volume_spike": 0}
        recent = hist.iloc[-12:]
        baseline = hist.iloc[:-12]
        price_change = (recent['Close'].iloc[-1] - recent['Close'].iloc[0]) / recent['Close'].iloc[0]
        vol_spike = recent['Volume'].mean() / baseline['Volume'].mean() if baseline['Volume'].mean() > 0 else 1
        return {"price_change": round(price_change, 4), "volume_spike": round(vol_spike, 2)}
    except:
        return {"price_change": 0, "volume_spike": 0}

def compute_impact_score(article: Dict, sentiment: float, macro_score: float) -> float:
    base = abs(sentiment) * 0.4
    macro_boost = macro_score * 0.4
    hot_kw = 0.2 if any(k in article["title"].lower() for k in ["fed", "cpi", "jobs"]) else 0
    trump_fiscal_boost = 0.4 if "Truth Social" in article["source"] and is_trump_fiscal(article["title"] + article["summary"]) else 0
    return min(base + macro_boost + hot_kw + trump_fiscal_boost, 1.0)

def quarantine_macro(news_id: int, trigger: str):
    conn = sqlite3.connect(CONFIG["DB_PATH"])
    cur = conn.cursor()
    now = datetime.now().isoformat()
    cur.execute('''
        INSERT OR IGNORE INTO macro_quarantine (news_id, trigger, tracked_since, last_update)
        VALUES (?, ?, ?, ?)
    ''', (news_id, trigger, now, now))
    conn.commit()
    conn.close()

def process_news_batch(articles: List[Dict]):
    conn = sqlite3.connect(CONFIG["DB_PATH"])
    cur = conn.cursor()
    for art in articles:
        cur.execute("SELECT id FROM news WHERE link = ?", (art["link"],))
        if cur.fetchone():
            continue
        full_text = art["title"] + " " + art["summary"]
        sentiment = analyze_sentiment(full_text)
        macro_score = score_macro_impact(full_text)
        impact_score = compute_impact_score(art, sentiment, macro_score)
        cur.execute('''
            INSERT INTO news (title, summary, link, pub_date, source, sentiment, impact_score, macro_score, processed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (art["title"], art["summary"], art["link"], art["pub_date"], art["source"],
              sentiment, impact_score, macro_score, datetime.now().isoformat()))
        news_id = cur.lastrowid
        if impact_score > CONFIG["IMPACT_THRESHOLD"]:
            for sym in CONFIG["STOCK_SYMBOLS"]:
                impact = score_stock_impact(sym)
                if abs(impact["price_change"]) > 0.005 or impact["volume_spike"] > 1.5:
                    cur.execute('''
                        INSERT INTO stock_impact (news_id, symbol, price_change, volume_spike)
                        VALUES (?, ?, ?, ?)
                    ''', (news_id, sym, impact["price_change"], impact["volume_spike"]))
        if macro_score > CONFIG["MACRO_QUARANTINE_THRESHOLD"] or ("Truth Social" in art["source"] and is_trump_fiscal(full_text)):
            trigger = next((k for k in CONFIG["MACRO_KEYWORDS"] if k in full_text.lower()), "trump_fiscal") if not is_trump_fiscal(full_text) else "TRUMP_FISCAL_ULTRA"
            quarantine_macro(news_id, trigger)
        priority = "ULTRA-HIGH" if impact_score > 0.9 else "HIGH" if impact_score > 0.7 else "MED" if impact_score > 0.4 else "LOW"
        logger.info(f"[{priority}] {art['title'][:70]} | I:{impact_score:.2f} M:{macro_score:.2f} | Source: {art['source']}")
    conn.commit()
    conn.close()

# ==============================
# SAFE YF FETCH
# ==============================
def safe_yf_fetch(symbol: str, period: str = "2d") -> Dict:
    if symbol in ["bitcoin", "ethereum"]:
        return {"price": None, "change": 0.0}
    try:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period=period, interval="5m", auto_adjust=False)
        if hist.empty or len(hist) < 2:
            return {"price": None, "change": 0.0}
        current = hist['Close'].iloc[-1]
        prev = hist['Close'].iloc[-2]
        change = (current - prev) / prev * 100 if prev != 0 else 0
        return {"price": round(current, 2), "change": round(change, 2)}
    except Exception as e:
        logger.debug(f"yfinance failed: {symbol} → {e}")
        return {"price": None, "change": 0.0}

# ==============================
# FAST CRYPTO METRICS (NO RSI HANG)
# ==============================
def fetch_crypto_metrics() -> Dict:
    metrics = {}
    try:
        prices = cg.get_price(ids='bitcoin,ethereum', vs_currencies='usd', include_24hr_change='true')
        metrics["BTC_price"] = {
            "value": round(prices['bitcoin']['usd'], 2),
            "rsi": "N/A",  # Skip to avoid hang
            "change": round(prices['bitcoin']['usd_24h_change'], 2)
        }
        metrics["ETH_price"] = {
            "value": round(prices['ethereum']['usd'], 2),
            "rsi": "N/A",
            "change": round(prices['ethereum']['usd_24h_change'], 2)
        }

        global_data = cg.get_global()
        mc = global_data.get('data', {}).get('market_cap_percentage', {})
        metrics["btc_dominance"] = round(mc.get('bitcoin', 0), 2)
        metrics["eth_dominance"] = round(mc.get('ethereum', 0), 2)

        eth_info = cg.get_coin_by_id('ethereum')
        md = eth_info.get('market_data', {})
        metrics["eth_circ_supply"] = md.get('circulating_supply', 0)
        metrics["eth_total_supply"] = md.get('total_supply', 0)

    except Exception as e:
        logger.warning(f"Crypto error: {e}")
    return metrics

# ==============================
# FAST TOP VOLUME (PRE-SELECTED TICKERS)
# ==============================
def fetch_top_stocks_by_volume(top_n=10):
    HIGH_VOLUME_TICKERS = [
        "NVDA", "TSLA", "AAPL", "AMD", "META", "AMZN", "MSFT", "GOOGL", "SMCI", "HOOD"
    ]
    try:
        data = yf.download(HIGH_VOLUME_TICKERS, period="1d", progress=False, auto_adjust=False, threads=True)
        volumes = {}
        for t in HIGH_VOLUME_TICKERS:
            if t in data.columns.levels[0]:
                vol = data[t]['Volume'].iloc[-1]
                if pd.notna(vol):
                    volumes[t] = vol
        return sorted(volumes.items(), key=lambda x: x[1], reverse=True)[:top_n]
    except:
        return [("N/A", 0)] * top_n

# ==============================
# MARKET SNAPSHOT
# ==============================
def print_market_snapshot():
    print("\n" + "="*80)
    print(" MARKET SNAPSHOT (ASCII SAFE)")
    print("="*80)

    indices = {name: safe_yf_fetch(sym) for name, sym in CONFIG["INDEX_SYMBOLS"].items()}
    for name, d in indices.items():
        trend = "[UP]" if d["change"] > 0 else "[DOWN]" if d["change"] < 0 else "[FLAT]"
        price_str = f"{d['price']}" if d["price"] is not None else "N/A"
        print(f"{name:12}: {price_str:>10}  {trend} {d['change']:>+6.2f}%")

    print("\n[TOP 10 VOLUME]")
    top_vol = fetch_top_stocks_by_volume()
    for t, v in top_vol:
        print(f"  {t}: {v:,.0f}")

    print("\n[CRYPTO]")
    crypto = fetch_crypto_metrics()
    for coin in ["BTC", "ETH"]:
        key = f"{coin}_price"
        if key in crypto and crypto[key]:
            p = crypto[key].get("value", "N/A")
            r = crypto[key].get("rsi", "N/A")
            c = crypto[key].get("change", 0)
            trend = "[UP]" if c > 0 else "[DOWN]" if c < 0 else "[FLAT]"
            print(f"  {coin}: ${p} | RSI: {r} | {trend} {c:+.2f}%")
        else:
            print(f"  {coin}: [No data]")

    print("\n[CURRENCIES %CHANGE]")
    curr = fetch_currency_trends()
    for p, c in curr.items():
        trend = "[UP]" if c > 0 else "[DOWN]" if c < 0 else "[FLAT]"
        print(f"  {p}: {trend} {c:+.2f}%")

    print("="*80)

def fetch_currency_trends():
    trends = {}
    for sym in CONFIG["CURRENCY_PAIRS"]:
        data = safe_yf_fetch(sym, period="1d")
        if data["change"] != 0:
            trends[sym] = data["change"]
    return trends

# ==============================
# MAIN LOOP
# ==============================
def main():
    init_db()
    logger.info("pymac.py STARTED - With Trump Truth Social + Fiscal Ultra-Priority")

    while True:
        try:
            start = time.time()
            articles = fetch_news()
            trump_posts = fetch_trump_truth_posts()
            all_articles = articles + trump_posts
            if all_articles:
                process_news_batch(all_articles)

            conn = sqlite3.connect(CONFIG["DB_PATH"])
            metrics = {
                **{name: safe_yf_fetch(sym) for name, sym in CONFIG["INDEX_SYMBOLS"].items()},
                **fetch_crypto_metrics(),
                **{"curr_" + k: v for k, v in fetch_currency_trends().items()}
            }
            cur = conn.cursor()
            now = datetime.now().isoformat()
            for k, v in metrics.items():
                if isinstance(v, dict):
                    val = v.get("price") or v.get("value")
                    chg = v.get("change", 0)
                    extra = json.dumps({kk: vv for kk, vv in v.items() if kk not in ["price", "value", "change"]})
                else:
                    val = v
                    chg = 0
                    extra = None
                cur.execute('''
                    INSERT INTO market_metrics (timestamp, metric_type, symbol, value, change_pct, extra_data)
                    VALUES (?, 'metric', ?, ?, ?, ?)
                ''', (now, k, val, chg, extra))
            conn.commit()
            conn.close()

            print_market_snapshot()

            elapsed = time.time() - start
            time.sleep(max(0, CONFIG["LOOP_INTERVAL"] - elapsed))

        except KeyboardInterrupt:
            logger.info("Shutdown.")
            break
        except Exception as e:
            logger.error(f"Loop error: {e}")
            time.sleep(30)

if __name__ == "__main__":
    main()
