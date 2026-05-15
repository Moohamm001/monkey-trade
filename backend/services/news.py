import feedparser
import requests
from datetime import datetime
from typing import List


RSS_FEEDS = {
    "Reuters Markets": "https://feeds.reuters.com/reuters/businessNews",
    "Yahoo Finance": "https://finance.yahoo.com/news/rssindex",
    "Seeking Alpha": "https://seekingalpha.com/market_currents.xml",
    "MarketWatch": "https://feeds.marketwatch.com/marketwatch/topstories",
    "CNBC": "https://www.cnbc.com/id/100003114/device/rss/rss.html",
}

STRATEGY_KEYWORDS = [
    "accumulation", "markup", "distribution", "markdown",
    "institutional", "smart money", "breakout", "earnings growth",
    "revenue growth", "profit", "fundamental", "undervalued",
    "insider buying", "short squeeze", "volume surge",
    "52-week high", "52-week low", "oversold", "overbought",
]


def fetch_market_news(limit: int = 30) -> List[dict]:
    articles = []
    for source, url in RSS_FEEDS.items():
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:8]:
                pub = entry.get("published_parsed") or entry.get("updated_parsed")
                pub_str = datetime(*pub[:6]).isoformat() if pub else ""
                text = (entry.get("title", "") + " " + entry.get("summary", "")).lower()
                relevance = sum(1 for kw in STRATEGY_KEYWORDS if kw in text)
                articles.append({
                    "title": entry.get("title", ""),
                    "summary": entry.get("summary", "")[:200],
                    "link": entry.get("link", ""),
                    "source": source,
                    "published": pub_str,
                    "strategy_relevance": relevance,
                    "tags": [kw for kw in STRATEGY_KEYWORDS if kw in text],
                })
        except Exception:
            continue

    articles.sort(key=lambda x: (x["strategy_relevance"], x["published"]), reverse=True)
    return articles[:limit]


def fetch_stock_news(ticker: str, limit: int = 10) -> List[dict]:
    import yfinance as yf
    t = yf.Ticker(ticker)
    try:
        news = t.news or []
        result = []
        for item in news[:limit]:
            result.append({
                "title": item.get("title", ""),
                "link": item.get("link", ""),
                "publisher": item.get("publisher", ""),
                "published": datetime.fromtimestamp(item.get("providerPublishTime", 0)).isoformat(),
                "thumbnail": item.get("thumbnail", {}).get("resolutions", [{}])[0].get("url", "") if item.get("thumbnail") else "",
            })
        return result
    except Exception:
        return []
