"""
News & Market Impact Intelligence (per news_feature.txt).

Pipeline:
  1. Fetch — pulls headlines in parallel from reliable, no-API-key sources
     (Yahoo Finance, MarketWatch, CNBC, NASDAQ, Investing.com, Seeking Alpha,
     WSJ Markets, Google News RSS, yfinance per-ticker feed).
  2. Classify — tags each article with event type, sentiment, tickers, sectors.
  3. Score — produces the 10-factor Signal Scoring framework, an overall
     opportunity/risk rating, and bull/base/bear scenario hints.
  4. Surface — returns a structured Intelligence payload the UI can render.

This module is intentionally rules-driven (regex + keyword lexicons + simple
heuristics) so it runs offline with zero paid APIs and zero ML inference cost.
The output schema matches Section 12 of news_feature.txt so an LLM layer can
be slotted in later without breaking the frontend contract.
"""
from __future__ import annotations

import json
import os
import re
import threading
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path
from typing import List, Optional
from urllib.parse import quote_plus

import feedparser
import requests


# ── Sources ────────────────────────────────────────────────────────────────────
# Selected for reliability (no API key, no rate-limit surprises) and signal
# density (markets/business-focused, low fluff). Each source is weighted by
# credibility — used later inside the signal-scoring framework.

def _gnews(query: str) -> str:
    """Build a Google News RSS URL for a given query."""
    from urllib.parse import quote_plus
    return f"https://news.google.com/rss/search?q={quote_plus(query)}&hl=en-US&gl=US&ceid=US:en"

RSS_FEEDS: dict[str, dict] = {
    "Yahoo Finance":   {"url": "https://finance.yahoo.com/news/rssindex",                          "weight": 7},
    "MarketWatch":     {"url": "https://feeds.marketwatch.com/marketwatch/topstories",             "weight": 8},
    "CNBC Business":   {"url": "https://www.cnbc.com/id/100003114/device/rss/rss.html",            "weight": 8},
    "CNBC Markets":    {"url": "https://www.cnbc.com/id/10000664/device/rss/rss.html",             "weight": 8},
    "NASDAQ":          {"url": "https://www.nasdaq.com/feed/rssoutbound?category=Markets",         "weight": 7},
    "Investing.com":   {"url": "https://www.investing.com/rss/news.rss",                           "weight": 6},
    "Seeking Alpha":   {"url": "https://seekingalpha.com/market_currents.xml",                     "weight": 7},
    "WSJ Markets":     {"url": "https://feeds.a.dj.com/rss/RSSMarketsMain.xml",                    "weight": 9},
    "Reuters Biz":     {"url": _gnews("site:reuters.com markets"),                                 "weight": 9},
    "Bloomberg":       {"url": _gnews("site:bloomberg.com markets"),                               "weight": 9},
    "FT Markets":      {"url": _gnews("site:ft.com markets"),                                      "weight": 9},

    # Targeted Smart-Money queries — fire alongside the general feeds.
    # Higher weight because the query already pre-filters to high-signal news.
    "SM · Politicians":    {"url": _gnews("Pelosi OR Trump OR Tuberville stock disclosure OR purchase OR sale"), "weight": 9},
    "SM · Buffett":        {"url": _gnews("Warren Buffett OR Berkshire Hathaway stake OR buys OR sells"),         "weight": 10},
    "SM · Activists":      {"url": _gnews("activist investor 13D filing stake stock"),                            "weight": 9},
    "SM · Hedge Funds":    {"url": _gnews("hedge fund 13F filing position OR stake stock"),                       "weight": 9},
    "SM · Burry":          {"url": _gnews("Michael Burry shorts OR buys OR position"),                            "weight": 10},
    "SM · Ackman":         {"url": _gnews("Bill Ackman Pershing Square stake OR buys OR sells"),                  "weight": 10},
    "SM · Icahn":          {"url": _gnews("Carl Icahn stake OR activist OR buys"),                                "weight": 10},
    "SM · Hindenburg":     {"url": _gnews("Hindenburg Research OR Muddy Waters short report"),                    "weight": 9},
    "SM · BlackRock":      {"url": _gnews("BlackRock OR Vanguard 13G OR 13F filing OR position"),                 "weight": 9},
    "SM · Mega-Cap CEOs":  {"url": _gnews("Elon Musk OR Jensen Huang OR Sam Altman announcement OR stock"),       "weight": 8},
    "SM · Insider Buying": {"url": _gnews("cluster insider buying CEO OR CFO purchases shares Form 4"),           "weight": 9},
    "SM · Whales":         {"url": _gnews("billionaire investor buys OR sells stake position"),                   "weight": 8},
}

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; MonkeyTradeNewsBot/1.0; +https://monkeytrade.app)",
    "Accept": "application/rss+xml, application/xml, text/xml, */*",
}
_SESSION = requests.Session()
_SESSION.headers.update(_HEADERS)


# ── Lexicons used by the rules engine ────────────────────────────────────────

POSITIVE_WORDS = {
    "beat", "beats", "surge", "surges", "soar", "soars", "rally", "rallies", "rallied",
    "jump", "jumps", "jumped", "climb", "climbs", "rise", "rises", "rose", "gain", "gains",
    "record high", "all-time high", "upgrade", "upgrades", "upgraded", "outperform",
    "strong", "robust", "exceed", "exceeds", "exceeded", "guidance raised", "raises guidance",
    "approval", "approved", "breakthrough", "expansion", "acquires", "acquisition",
    "buyback", "buybacks", "dividend hike", "raises dividend", "partnership",
    "contract win", "wins contract", "milestone", "boost", "boosted", "bullish",
    "accumulation", "insider buying", "cluster buy", "short squeeze",
    "earnings beat", "revenue beat", "profit beat", "blowout",
}

NEGATIVE_WORDS = {
    "miss", "misses", "missed", "slump", "slumps", "plunge", "plunges", "plunged",
    "tumble", "tumbles", "tumbled", "fall", "falls", "fell", "drop", "drops", "dropped",
    "crash", "crashes", "crashed", "downgrade", "downgrades", "downgraded", "underperform",
    "weak", "weakness", "warn", "warning", "warns", "guidance cut", "cuts guidance", "lowers guidance",
    "rejected", "rejection", "lawsuit", "investigation", "probe", "fraud", "scandal",
    "bankruptcy", "default", "delisting", "layoffs", "layoff", "fired", "resigned",
    "short seller", "shorted", "bearish", "distribution", "selloff", "sell-off",
    "recall", "halt", "halted", "suspended", "subpoena", "sec charges",
    "tariff", "sanctions", "ban", "banned", "restriction", "restrictions",
    "earnings miss", "revenue miss", "loss widens", "wider loss",
}

# Event-type pattern → human label + base impact horizon.
EVENT_PATTERNS: list[tuple[str, str, str]] = [
    (r"\b(earnings|q[1-4]\s+(?:results|report)|revenue|eps|guidance)\b",         "Earnings",         "short"),
    (r"\b(merger|acquir|takeover|buyout|tender offer|m&a)\b",                    "M&A",              "medium"),
    (r"\b(insider|form\s*4|cluster (?:buy|sell))\b",                             "Insider",          "medium"),
    (r"\b(13d|13g|13f|activist|stake|hedge fund)\b",                             "Institutional",    "medium"),
    (r"\b(fda|approval|clinical|phase\s*[123]|trial)\b",                         "Regulatory",       "short"),
    (r"\b(fed|fomc|powell|interest rate|rate (?:cut|hike|decision)|cpi|ppi|jobs report|nfp|unemployment)\b", "Macro", "medium"),
    (r"\b(tariff|sanction|china|geopolit|war|conflict|opec)\b",                  "Geopolitical",     "medium"),
    (r"\b(lawsuit|sec charges|doj|probe|investigation|subpoena|fraud)\b",        "Litigation",       "medium"),
    (r"\b(upgrade|downgrade|price target|reiterates|initiates coverage)\b",      "Analyst",          "short"),
    (r"\b(launch|unveils|announces|new product|partnership|contract|deal)\b",    "Product / Deal",   "short"),
    (r"\b(buyback|share repurchase|dividend|special dividend)\b",                "Capital Return",   "medium"),
    (r"\b(layoff|restructur|bankruptcy|chapter 11|going concern|default)\b",     "Restructuring",    "long"),
    (r"\b(short seller|short report|shorted|hindenburg|muddy waters)\b",         "Short Report",     "short"),
    (r"\b(ai|artificial intelligence|gpu|datacenter|llm|chatgpt|nvidia)\b",      "AI / Tech Theme",  "long"),
    (r"\b(oil|crude|wti|brent|opec|energy|gas)\b",                               "Energy",           "medium"),
    (r"\b(crypto|bitcoin|ethereum|btc|eth)\b",                                   "Crypto",           "short"),
]

# A pragmatic universe of common US tickers used to validate regex extractions.
# Avoids the avalanche of false positives that "any 1-5 caps word" would yield
# (CEO, USA, AI, IPO, …). Expanded as needed; missing tickers are simply not
# auto-tagged but the user can still search by ticker explicitly.
_COMMON_TICKERS = {
    "AAPL","MSFT","NVDA","AMZN","META","GOOGL","GOOG","TSLA","AVGO","TSM","ORCL","ADBE","CRM","AMD","INTC","QCOM","TXN","MU","NFLX","DIS",
    "JPM","BAC","WFC","GS","MS","C","BLK","SCHW","V","MA","AXP","PYPL","SQ","COIN","HOOD","SOFI","UPST","PLTR","SNOW","DDOG","NET",
    "BRK.B","BRKB","XOM","CVX","COP","SLB","OXY","PSX","VLO","EOG","BKR","HAL",
    "WMT","TGT","HD","LOW","COST","NKE","SBUX","MCD","KO","PEP","PG","CL","UL","UNH","JNJ","PFE","MRK","LLY","ABBV","BMY","TMO","DHR",
    "BA","CAT","DE","GE","HON","LMT","RTX","NOC","GD","UPS","FDX","UBER","LYFT","ABNB","DASH",
    "T","VZ","TMUS","CMCSA","CHTR","DIS","PARA","WBD","ROKU",
    "F","GM","RIVN","LCID","NIO","XPEV","LI","BYD","STLA",
    "ARM","SMCI","MRVL","LRCX","AMAT","KLAC","ASML","WDC","STX","ON","MCHP","ADI","NXPI",
    "SHOP","SPOT","TWLO","ZM","CRWD","ZS","PANW","FTNT","S","OKTA","MDB","TEAM","NOW","WDAY","INTU","CDNS","SNPS","ANSS","NOW",
    "MSTR","RIOT","MARA","CLSK","HUT","GLXY",
    "SPY","QQQ","IWM","DIA","VTI","VOO","XLK","XLF","XLE","XLY","XLV","XLI","XLU","XLB","XLRE","ARKK","SOXX","SMH","TLT","HYG","LQD","GLD","SLV","USO","UNG","TQQQ","SQQQ",
}

TICKER_REGEX = re.compile(r"\$([A-Z]{1,5})\b|\b([A-Z]{2,5})\b")

# Tickers that draw outsized attention and reflexive flow.
MEGA_CAP_TICKERS = {"AAPL", "MSFT", "NVDA", "GOOGL", "GOOG", "AMZN", "META", "TSLA", "BRK.B", "BRKB", "AVGO", "TSM"}


# ── Smart Money lexicon ──────────────────────────────────────────────────────
# Whose actions historically move price the most. Weights are additive boosts
# (in opportunity-points) when the entity is detected alongside a buy/sell verb.
# Tier ordering reflects historical "follow-the-money" alpha: research-backed
# billionaires > activists/13D filers > politicians (high attention) > mega
# institutions (slow capital) > mega-cap CEOs (announcement effects).
SMART_MONEY_ENTITIES: dict[str, dict] = {
    "Billionaire Investor": {
        "boost": 25,
        "names": [
            "warren buffett", "buffett", "berkshire hathaway", "berkshire",
            "michael burry", "burry", "scion asset",
            "bill ackman", "ackman", "pershing square",
            "carl icahn", "icahn",
            "ray dalio", "dalio", "bridgewater",
            "george soros", "soros",
            "david tepper", "tepper", "appaloosa",
            "stan druckenmiller", "druckenmiller",
            "bill miller", "miller value",
            "cathie wood", "ark invest", "ark investment",
            "daniel loeb", "third point",
            "steve cohen", "point72",
            "ken griffin", "citadel",
            "jim simons", "renaissance technologies",
            "paul tudor jones", "tudor investment",
            "seth klarman", "baupost",
            "howard marks", "oaktree",
            "leon cooperman", "cooperman",
            "david einhorn", "einhorn", "greenlight capital",
            "mohnish pabrai", "pabrai",
        ],
    },
    "Activist / Hedge Fund": {
        "boost": 22,
        "names": [
            "elliott management", "elliott", "paul singer",
            "starboard value", "jeff smith",
            "jana partners",
            "engine no. 1",
            "trian fund", "nelson peltz",
            "valueact capital",
            "third point",
            "scion asset",
            "hindenburg research", "hindenburg",
            "muddy waters", "carson block",
            "kerrisdale capital",
            "viceroy research",
        ],
    },
    "Politician": {
        "boost": 20,
        "names": [
            "trump", "donald trump",
            "pelosi", "nancy pelosi", "paul pelosi",
            "schumer", "chuck schumer",
            "mcconnell",
            "manchin",
            "ted cruz", "cruz",
            "tommy tuberville", "tuberville",
            "dan crenshaw",
            "ro khanna",
            "elizabeth warren",
            "bernie sanders",
            "aoc", "ocasio-cortez",
            "congressman", "congresswoman", "senator",
        ],
    },
    "Mega Institution": {
        "boost": 15,
        "names": [
            "blackrock", "larry fink",
            "vanguard",
            "state street",
            "fidelity",
            "t. rowe price", "t rowe price",
            "wellington management",
            "capital group", "capital research",
            "norges bank",
            "sovereign wealth fund",
        ],
    },
    "Mega-Cap CEO": {
        "boost": 12,
        "names": [
            "elon musk", "musk",
            "jensen huang", "huang",
            "tim cook",
            "mark zuckerberg", "zuckerberg",
            "sundar pichai", "pichai",
            "satya nadella", "nadella",
            "sam altman", "altman", "openai",
            "andy jassy", "jassy",
            "lisa su",
            "pat gelsinger",
            "jamie dimon", "dimon",
        ],
    },
}

# Verbs that turn an entity mention into a directional capital-flow signal.
# Canonical display names — collapses aliases ("trump"/"donald trump") into one.
SMART_MONEY_CANONICAL: dict[str, str] = {
    "trump": "Donald Trump", "donald trump": "Donald Trump",
    "pelosi": "Nancy Pelosi", "nancy pelosi": "Nancy Pelosi", "paul pelosi": "Paul Pelosi",
    "schumer": "Chuck Schumer", "chuck schumer": "Chuck Schumer",
    "mcconnell": "Mitch McConnell",
    "manchin": "Joe Manchin",
    "cruz": "Ted Cruz", "ted cruz": "Ted Cruz",
    "tuberville": "Tommy Tuberville", "tommy tuberville": "Tommy Tuberville",
    "dan crenshaw": "Dan Crenshaw",
    "ro khanna": "Ro Khanna",
    "elizabeth warren": "Elizabeth Warren",
    "bernie sanders": "Bernie Sanders",
    "aoc": "AOC", "ocasio-cortez": "AOC",
    "buffett": "Warren Buffett", "warren buffett": "Warren Buffett",
    "berkshire": "Berkshire Hathaway", "berkshire hathaway": "Berkshire Hathaway",
    "burry": "Michael Burry", "michael burry": "Michael Burry", "scion asset": "Michael Burry",
    "ackman": "Bill Ackman", "bill ackman": "Bill Ackman", "pershing square": "Bill Ackman",
    "icahn": "Carl Icahn", "carl icahn": "Carl Icahn",
    "dalio": "Ray Dalio", "ray dalio": "Ray Dalio", "bridgewater": "Bridgewater",
    "soros": "George Soros", "george soros": "George Soros",
    "tepper": "David Tepper", "david tepper": "David Tepper", "appaloosa": "David Tepper",
    "druckenmiller": "Stan Druckenmiller", "stan druckenmiller": "Stan Druckenmiller",
    "bill miller": "Bill Miller", "miller value": "Bill Miller",
    "cathie wood": "Cathie Wood", "ark invest": "Cathie Wood", "ark investment": "Cathie Wood",
    "loeb": "Daniel Loeb", "daniel loeb": "Daniel Loeb", "third point": "Daniel Loeb",
    "cohen": "Steve Cohen", "steve cohen": "Steve Cohen", "point72": "Steve Cohen",
    "griffin": "Ken Griffin", "ken griffin": "Ken Griffin", "citadel": "Citadel",
    "simons": "Jim Simons", "jim simons": "Jim Simons", "renaissance technologies": "Renaissance",
    "paul tudor jones": "Paul Tudor Jones", "tudor investment": "Paul Tudor Jones",
    "klarman": "Seth Klarman", "seth klarman": "Seth Klarman", "baupost": "Seth Klarman",
    "marks": "Howard Marks", "howard marks": "Howard Marks", "oaktree": "Howard Marks",
    "cooperman": "Leon Cooperman", "leon cooperman": "Leon Cooperman",
    "einhorn": "David Einhorn", "david einhorn": "David Einhorn", "greenlight capital": "David Einhorn",
    "pabrai": "Mohnish Pabrai", "mohnish pabrai": "Mohnish Pabrai",
    "elliott": "Elliott Management", "elliott management": "Elliott Management", "paul singer": "Elliott Management",
    "starboard value": "Starboard Value", "jeff smith": "Starboard Value",
    "jana partners": "JANA Partners",
    "engine no. 1": "Engine No. 1",
    "trian fund": "Trian / Peltz", "nelson peltz": "Trian / Peltz",
    "valueact capital": "ValueAct",
    "hindenburg": "Hindenburg Research", "hindenburg research": "Hindenburg Research",
    "muddy waters": "Muddy Waters", "carson block": "Muddy Waters",
    "kerrisdale capital": "Kerrisdale",
    "viceroy research": "Viceroy",
    "blackrock": "BlackRock", "larry fink": "BlackRock",
    "vanguard": "Vanguard",
    "state street": "State Street",
    "fidelity": "Fidelity",
    "t. rowe price": "T. Rowe Price", "t rowe price": "T. Rowe Price",
    "wellington management": "Wellington",
    "capital group": "Capital Group", "capital research": "Capital Group",
    "norges bank": "Norges Bank",
    "sovereign wealth fund": "Sovereign Wealth",
    "musk": "Elon Musk", "elon musk": "Elon Musk",
    "huang": "Jensen Huang", "jensen huang": "Jensen Huang",
    "tim cook": "Tim Cook",
    "zuckerberg": "Mark Zuckerberg", "mark zuckerberg": "Mark Zuckerberg",
    "pichai": "Sundar Pichai", "sundar pichai": "Sundar Pichai",
    "nadella": "Satya Nadella", "satya nadella": "Satya Nadella",
    "altman": "Sam Altman", "sam altman": "Sam Altman", "openai": "OpenAI / Altman",
    "jassy": "Andy Jassy", "andy jassy": "Andy Jassy",
    "lisa su": "Lisa Su",
    "pat gelsinger": "Pat Gelsinger",
    "dimon": "Jamie Dimon", "jamie dimon": "Jamie Dimon",
    "congressman": "Congressional Trade",
    "congresswoman": "Congressional Trade",
    "senator": "Congressional Trade",
}

SMART_MONEY_BUY_VERBS = {
    "buy", "buys", "bought", "buying", "purchase", "purchases", "purchased", "purchasing",
    "acquir", "acquires", "acquired", "acquiring",
    "discloses stake", "discloses position", "discloses new", "discloses",
    "files 13d", "files 13g", "files 13f", "13d filing", "13g filing", "13f filing",
    "accumulat", "accumulates", "accumulating",
    "raises stake", "increases position", "increases stake", "ups stake", "boosts stake",
    "new position", "added to", "adds to", "loaded up", "long position", "goes long",
    "betting on", "bullish on", "endorses",
    "invests", "invested", "investing in",
    "stake worth", "stake in", "position in",
    "owns", "owns more",
}

SMART_MONEY_SELL_VERBS = {
    "sell", "sells", "sold", "selling",
    "trim", "trims", "trimmed", "trimming",
    "reduce", "reduces", "reduced",
    "exit", "exits", "exited", "exiting",
    "dump", "dumps", "dumped",
    "liquidat", "liquidates", "liquidated",
    "short", "shorts", "shorting", "short position", "puts on short",
    "betting against", "bearish on",
    "warns on", "calls bubble", "calls top",
    "cuts stake", "lowers stake", "reduces stake",
}

# Historical analogs surfaced when an event type fires.
ANALOGS: dict[str, list[str]] = {
    "Macro":            ["2019 Fed easing pivot", "2020 emergency cuts → liquidity rally"],
    "AI / Tech Theme":  ["1995-2000 cloud/internet build-out", "2023 LLM capex super-cycle"],
    "Insider":          ["1990 Buffett Coca-Cola accumulation", "March 2020 CEO cluster buying"],
    "M&A":              ["Microsoft/Activision 2022", "Broadcom/VMware 2023"],
    "Short Report":     ["Hindenburg/Nikola 2020", "Muddy Waters/Luckin 2020"],
    "Regulatory":       ["FDA decisions historically ±20-40% one-day moves"],
    "Geopolitical":     ["Feb 2022 Russia/Ukraine — energy spike, growth selloff"],
    "Energy":           ["2022 OPEC+ cut → 7-day +15% crude"],
    "Earnings":         ["Avg S&P 500 single-stock earnings move ≈ ±5%"],
    "Crypto":           ["2020/2024 BTC halving cycles"],
    "Smart Money":      [
        "2023 Buffett TSMC entry — semis re-rated +40% over 12 months",
        "2022 Pelosi NVDA disclosure — +18% within 2 weeks (retail momentum)",
        "2020 Burry short on Tesla — preceded -65% drawdown over 18 months",
        "Cluster CEO buying after crashes — historically +20-40% over 12 months",
    ],
}


# ── Fetch layer ───────────────────────────────────────────────────────────────

def _fetch_feed(source: str, meta: dict) -> list[dict]:
    """Pull and lightly normalize a single RSS feed. Never raises."""
    try:
        # feedparser handles HTTP itself, but a pre-fetch with session gives us
        # better timeout/error control and lets us share a User-Agent.
        r = _SESSION.get(meta["url"], timeout=10)
        r.raise_for_status()
        feed = feedparser.parse(r.content)
    except Exception:
        return []

    out = []
    for entry in feed.entries[:40]:
        pub_struct = entry.get("published_parsed") or entry.get("updated_parsed")
        pub_iso    = (
            datetime(*pub_struct[:6], tzinfo=timezone.utc).isoformat()
            if pub_struct else ""
        )
        out.append({
            "title":            (entry.get("title") or "").strip(),
            "summary":          re.sub(r"<[^>]+>", "", entry.get("summary", ""))[:280].strip(),
            "link":             entry.get("link", ""),
            "source":           source,
            "source_weight":    meta["weight"],
            "published":        pub_iso,
        })
    return out


def _fetch_all_feeds() -> list[dict]:
    """Fan out RSS pulls across a thread pool — total wall time ≈ slowest feed."""
    articles: list[dict] = []
    with ThreadPoolExecutor(max_workers=min(10, len(RSS_FEEDS))) as pool:
        futures = {pool.submit(_fetch_feed, src, m): src for src, m in RSS_FEEDS.items()}
        for fut in as_completed(futures, timeout=20):
            try:
                articles.extend(fut.result() or [])
            except Exception:
                continue
    return articles


def _fetch_yahoo_ticker_news(ticker: str, limit: int = 12) -> list[dict]:
    """yfinance exposes Yahoo Finance's per-ticker news feed — most reliable
    ticker-specific source we have without an API key."""
    try:
        import yfinance as yf
        items = yf.Ticker(ticker).news or []
    except Exception:
        return []

    out = []
    for it in items[:limit]:
        # yfinance schema changed across versions; defensively probe both shapes.
        content = it.get("content") or it
        title   = content.get("title") or it.get("title", "")
        link    = (content.get("canonicalUrl") or {}).get("url") or it.get("link", "")
        summary = content.get("summary") or it.get("summary", "")
        ts      = it.get("providerPublishTime")
        pub_iso = (
            datetime.fromtimestamp(ts, tz=timezone.utc).isoformat() if ts
            else (content.get("pubDate") or "")
        )
        publisher = (content.get("provider") or {}).get("displayName") or it.get("publisher", "Yahoo Finance")
        out.append({
            "title":         title,
            "summary":       (summary or "")[:280],
            "link":           link,
            "source":         publisher,
            "source_weight":  6,
            "published":      pub_iso,
        })
    return out


def _fetch_google_news_for(query: str, limit: int = 15) -> list[dict]:
    """Google News RSS is the most reliable free way to search by ticker/topic.
    No API key, no rate-limit drama, results aggregated across every publisher."""
    url = (
        f"https://news.google.com/rss/search?q={quote_plus(query)}"
        "&hl=en-US&gl=US&ceid=US:en"
    )
    try:
        r = _SESSION.get(url, timeout=10)
        r.raise_for_status()
        feed = feedparser.parse(r.content)
    except Exception:
        return []

    out = []
    for entry in feed.entries[:limit]:
        pub_struct = entry.get("published_parsed") or entry.get("updated_parsed")
        pub_iso    = (
            datetime(*pub_struct[:6], tzinfo=timezone.utc).isoformat()
            if pub_struct else ""
        )
        # Google News titles look like "Headline — Publisher"
        title, _, pub = (entry.get("title") or "").rpartition(" - ")
        out.append({
            "title":         (title or entry.get("title", "")).strip(),
            "summary":       re.sub(r"<[^>]+>", "", entry.get("summary", ""))[:280],
            "link":           entry.get("link", ""),
            "source":         pub.strip() or "Google News",
            "source_weight":  6,
            "published":      pub_iso,
        })
    return out


# ── Intelligence layer (Sections 1-9 of news_feature.txt) ────────────────────

def _extract_tickers(text: str) -> list[str]:
    """Pull plausible tickers from text; validated against the common universe."""
    found: set[str] = set()
    for m in TICKER_REGEX.finditer(text):
        sym = (m.group(1) or m.group(2) or "").upper()
        if not sym:
            continue
        # $-prefixed forms are always accepted; bare tokens must look like tickers
        # AND appear in the common universe to suppress false positives.
        if m.group(1) or sym in _COMMON_TICKERS:
            found.add(sym)
    return sorted(found)


def _classify_event(text: str) -> tuple[str, str]:
    """Return (event_type, primary_horizon) for the first matched pattern."""
    low = text.lower()
    for pattern, label, horizon in EVENT_PATTERNS:
        if re.search(pattern, low):
            return label, horizon
    return "General", "short"


def _detect_smart_money(text: str) -> dict:
    """Identify big-name capital flow events.

    Returns:
        {
          "detected":   bool,
          "entities":   [{category, name, direction, boost}, …],
          "direction":  "buy" | "sell" | "neutral",  # majority vote
          "boost":      int,                          # total opportunity-pt boost (capped)
          "headline":   str,                          # one-liner for UI spotlight
        }
    """
    low = text.lower()
    has_buy  = any(v in low for v in SMART_MONEY_BUY_VERBS)
    has_sell = any(v in low for v in SMART_MONEY_SELL_VERBS)

    # Collect all matches (long names first so substrings are preferred-out later).
    raw_matches: list[tuple[str, str, int]] = []  # (name_lower, category, boost)
    for category, info in SMART_MONEY_ENTITIES.items():
        for name in sorted(info["names"], key=len, reverse=True):
            pattern = r"(?:^|[^a-z])" + re.escape(name) + r"(?:$|[^a-z])"
            if re.search(pattern, low):
                raw_matches.append((name, category, info["boost"]))

    # Dedupe: if "donald trump" matched, drop "trump"; if "warren buffett" matched,
    # drop "buffett". Keep the longer (more specific) alias.
    raw_matches.sort(key=lambda m: len(m[0]), reverse=True)
    kept: list[tuple[str, str, int]] = []
    for name, cat, boost in raw_matches:
        if any(name in other_name or other_name in name for other_name, _, _ in kept):
            continue
        kept.append((name, cat, boost))

    # Map each alias to its canonical display name, then dedupe again at the
    # canonical level so "Trump" + "Donald Trump" → single "Donald Trump" entity.
    canonical_seen: set[str] = set()
    entities: list[dict] = []
    for name, cat, boost in kept:
        canon = SMART_MONEY_CANONICAL.get(name, name.title())
        if canon in canonical_seen:
            continue
        canonical_seen.add(canon)
        entities.append({
            "category":  cat,
            "name":      canon,
            "direction": "buy" if has_buy and not has_sell else "sell" if has_sell and not has_buy else "neutral",
            "boost":     boost,
        })

    if not entities:
        return {"detected": False, "entities": [], "direction": "neutral", "boost": 0, "headline": ""}

    direction = (
        "buy"  if has_buy and not has_sell else
        "sell" if has_sell and not has_buy else
        "neutral"
    )
    # Cap the total boost so a long namedrop doesn't dominate the score.
    total_boost = min(35, sum(e["boost"] for e in entities))
    if direction == "neutral":
        total_boost //= 2  # mere mention without verb is a weaker signal

    top = entities[0]
    arrow = "→ BUY" if direction == "buy" else "→ SELL" if direction == "sell" else "(mentioned)"
    headline = f"{top['name']} {arrow}" + (f" +{len(entities) - 1} more" if len(entities) > 1 else "")

    return {
        "detected": True,
        "entities": entities,
        "direction": direction,
        "boost":     total_boost,
        "headline":  headline,
    }


def _sentiment(text: str) -> tuple[str, int]:
    """Returns (bullish|bearish|neutral, score in [-10, 10])."""
    low = text.lower()
    pos = sum(1 for w in POSITIVE_WORDS if w in low)
    neg = sum(1 for w in NEGATIVE_WORDS if w in low)
    raw = pos - neg
    if raw >= 2:   return "bullish", min(10, raw * 2)
    if raw <= -2:  return "bearish", max(-10, raw * 2)
    if raw == 1:   return "bullish", 3
    if raw == -1:  return "bearish", -3
    return "neutral", 0


def _signal_scores(article: dict, event_type: str, sentiment_score: int, smart_money: dict) -> dict:
    """The 10-factor framework from Section 8 of news_feature.txt.

    Every factor is on /10. Rules are intentionally simple and explainable —
    a later ML layer can recalibrate these weights from realized returns.
    A detected smart-money capital flow (Buffett buys, Pelosi files, etc.)
    boosts the relevant factors and adds an opportunity-point premium."""
    src_w   = article.get("source_weight", 5)
    sent_mag = abs(sentiment_score)
    tickers  = article.get("tickers") or []
    has_ticker = bool(tickers)
    has_megacap = any(t in MEGA_CAP_TICKERS for t in tickers)
    sm_detected = smart_money.get("detected", False)
    sm_buy   = sm_detected and smart_money["direction"] == "buy"
    sm_sell  = sm_detected and smart_money["direction"] == "sell"

    # Smart-money mention strengthens the institutional / insider / narrative axes.
    sm_inst_bump  = 4 if sm_detected else 0
    sm_narr_bump  = 3 if sm_detected else 0

    narrative   = min(10, max(2, sent_mag + (3 if event_type in {"AI / Tech Theme", "Macro", "M&A"} else 0) + sm_narr_bump))
    institutional = min(10, (10 if sm_detected else (9 if event_type in {"Insider", "Institutional", "M&A"} else (6 if event_type == "Analyst" else 4))))
    volume_conf = 5  # placeholder — wired up live when /api/news/ticker is called
    options_conf = 5
    insider_align = min(10, (9 if event_type == "Insider" else (6 if event_type in {"Institutional", "M&A"} else 4)) + sm_inst_bump)
    macro_align = 9 if event_type == "Macro" else (7 if event_type in {"Geopolitical", "Energy"} else 5)
    hist_success = {
        "Earnings": 6, "M&A": 7, "Insider": 8, "Institutional": 7, "Macro": 7,
        "Regulatory": 6, "Geopolitical": 5, "Analyst": 4, "Product / Deal": 5,
        "Capital Return": 7, "Restructuring": 4, "Short Report": 6,
        "AI / Tech Theme": 7, "Energy": 6, "Crypto": 5, "General": 4,
    }.get(event_type, 5)
    if sm_detected:
        hist_success = min(10, hist_success + 2)  # follow-the-money historically works
    valuation = 5  # neutral baseline without fundamentals
    momentum  = min(10, max(2, 5 + (sentiment_score // 2) + (2 if sm_buy else -2 if sm_sell else 0)))
    risk      = {
        "Short Report": 9, "Litigation": 8, "Restructuring": 9, "Regulatory": 7,
        "Geopolitical": 7, "Earnings": 6, "Crypto": 8, "Macro": 6,
    }.get(event_type, 5)
    if sm_buy:  risk = max(2, risk - 1)   # known-good buyer reduces downside risk
    if sm_sell: risk = min(10, risk + 1)  # known short-seller increases risk

    scores = {
        "Narrative Strength":     narrative,
        "Institutional Alignment": institutional,
        "Volume Confirmation":    volume_conf,
        "Options Flow":           options_conf,
        "Insider Alignment":      insider_align,
        "Macro Alignment":        macro_align,
        "Historical Success":     hist_success,
        "Valuation Support":      valuation,
        "Momentum Alignment":     momentum,
        "Risk Level":             risk,
    }

    # Aggregate: average of constructive factors minus risk penalty,
    # scaled into a 0-100 "opportunity score" plus credibility weighting.
    constructive = sum(v for k, v in scores.items() if k != "Risk Level") / 9.0
    opportunity  = int(round((constructive * 10) - (risk * 1.5) + (src_w - 5) * 2))
    opportunity += smart_money.get("boost", 0)        # smart-money premium
    if has_megacap:
        opportunity += 5                              # mega-cap attention/liquidity premium
    opportunity  = max(0, min(100, opportunity))
    if not has_ticker and opportunity > 60 and not sm_detected:
        opportunity -= 10  # un-actionable without a ticker (unless smart-money sector call)

    quality = "A" if opportunity >= 75 else "B" if opportunity >= 60 else "C" if opportunity >= 45 else "D"

    return {
        "factors":     scores,
        "opportunity": opportunity,
        "risk_total":  risk * 10,
        "quality":     quality,
    }


def _confidence(article: dict, sentiment_score: int, event_type: str) -> int:
    """0–100% confidence per Section 2."""
    base = 35
    base += min(25, article.get("source_weight", 5) * 2)          # credibility
    base += min(20, abs(sentiment_score) * 2)                     # signal strength
    if article.get("tickers"):                                    # actionable
        base += 10
    if event_type in {"Earnings", "M&A", "Insider", "Macro", "Regulatory"}:
        base += 5                                                 # event types with track record
    return max(0, min(100, base))


def _scenarios(event_type: str, direction: str, smart_money: dict | None = None) -> dict:
    """Bull / base / bear case templates per Section 9."""
    sm = smart_money or {}
    if sm.get("detected"):
        ent = sm["entities"][0]
        cat = ent["category"]
        name = ent["name"]
        if sm["direction"] == "buy":
            if cat == "Politician":
                return {
                    "bull": f"{name}'s disclosure goes viral on retail forums — reflexive buying drives gap-up + multi-day momentum.",
                    "base": f"Initial pop on the {name} news, then 50% retrace as the headline fades within a week.",
                    "bear": f"Stock is already extended — {name}'s buy is sold into; classic 'sell the news' reversal.",
                }
            if cat == "Billionaire Investor":
                return {
                    "bull": f"{name} is famously patient capital — initial mark-up confirms thesis, sustained accumulation over 3-12 months.",
                    "base": f"{name}'s entry establishes a floor; stock trades sideways-up as the market re-rates fundamentals.",
                    "bear": f"Position is small relative to AUM — could be a basket trade; price action fails to follow through.",
                }
            if cat == "Activist / Hedge Fund":
                return {
                    "bull": f"{name} forces strategic action (spin-off, buyback, sale) — re-rating begins within 60-90 days.",
                    "base": f"Activist pressure mounts gradually; management negotiates partial concessions; stock grinds higher.",
                    "bear": f"Board resists; proxy fight drags on; stock chops as uncertainty caps multiple expansion.",
                }
            if cat == "Mega Institution":
                return {
                    "bull": f"{name} is mechanical, sticky capital — passive inflows compound; multi-quarter tailwind.",
                    "base": f"Slow accumulation provides bid support; price drift higher with low volatility.",
                    "bear": f"Filing may be an index rebalance, not a thesis — limited follow-through on the news.",
                }
            return {
                "bull": f"{name}'s buy validates the thesis — momentum traders pile in, gap up holds.",
                "base": f"Initial pop fades within days back into prior range.",
                "bear": f"Sell-the-news — extended chart sees mean reversion.",
            }
        if sm["direction"] == "sell":
            if "Hindenburg" in name or "Muddy Waters" in name or cat == "Activist / Hedge Fund":
                return {
                    "bull": f"Short report rebutted by company + independent analysts — squeeze sends stock back to pre-report highs.",
                    "base": f"Initial 10-25% gap down; fundamentals partially confirm thesis; stock finds new lower range.",
                    "bear": f"Allegations confirmed — cascade lower as institutions exit, downgrades pile on, regulatory probe opens.",
                }
            return {
                "bull": f"{name}'s sale is dismissed as profit-taking or diversification — stock holds key support.",
                "base": f"Gap down + 1-2 weeks of weakness as the market digests the disclosure.",
                "bear": f"{name} is right — sustained de-rating, downgrades within 30 days, multiple compression.",
            }
        return {
            "bull": f"{name} attention drives follow-on coverage — momentum builds across retail + institutional.",
            "base": f"News fades within 48-72 hours; price reverts to prior trend.",
            "bear": f"Mere mention proves transient; volume dries up.",
        }
    if event_type == "Earnings":
        return {
            "bull": "Beat + guidance raise — gap up holds, momentum chasers extend the move 1-2 weeks.",
            "base": "In-line print — initial volatility fades within 1-3 sessions, stock retraces 50% of the move.",
            "bear": "Miss + guide-down — gap down, support breaks, downgrades follow within 48h.",
        }
    if event_type == "M&A":
        return {
            "bull": "Strategic premium accepted — target gaps to deal price, sector re-rated higher on read-through.",
            "base": "Deal completes near terms after regulatory scrutiny; target trades within 2-5% of offer.",
            "bear": "Regulatory or financing risk surfaces — spread widens, deal breaks → mean-reversion lower.",
        }
    if event_type == "Macro":
        return {
            "bull": "Dovish surprise — risk-on, growth and small caps outperform, dollar weakens.",
            "base": "In-line — initial chop, market reverts to prior trend within 1-2 sessions.",
            "bear": "Hawkish surprise — yields up, multiple compression, defensives outperform.",
        }
    if direction == "bullish":
        return {
            "bull": "Catalyst broadens — institutional follow-through, sector spillover.",
            "base": "Single-stock pop fades over 3-5 sessions back into prior range.",
            "bear": "Sell-the-news — gap up sold into; weakness signals exhausted demand.",
        }
    if direction == "bearish":
        return {
            "bull": "Capitulation print — bad news absorbed, stock reverses higher on volume.",
            "base": "Gradual de-rating, finds support 5-15% lower over 1-3 weeks.",
            "bear": "Cascade lower — stops trigger, multiple compression, downgrades pile on.",
        }
    return {
        "bull": "Positive read-through if confirmed by follow-on catalysts.",
        "base": "Market digests headline; no durable price impact.",
        "bear": "Risk surfaces in confirming data within 1-2 weeks.",
    }


def _recommendation(opportunity: int, confidence: int, has_ticker: bool, smart_money: dict) -> str:
    """Probabilistic guidance, not a buy/sell call (per Section 13)."""
    if smart_money.get("detected"):
        ent  = smart_money["entities"][0]
        cat  = ent["category"]
        name = ent["name"]
        if smart_money["direction"] == "buy":
            return (f"🎯 FOLLOW THE MONEY — {name} ({cat}) is buying. "
                    "These flows draw reflexive retail interest; confirm with volume before sizing, "
                    "stop below the prior consolidation low.")
        if smart_money["direction"] == "sell":
            return (f"⚠️ HEED THE WARNING — {name} ({cat}) is selling/shorting. "
                    "Reduce long exposure; wait for capitulation flush before counter-trading.")
        return (f"👀 ATTENTION CATALYST — {name} mentioned. Watch for follow-on flow & confirmation.")
    if not has_ticker:
        return "Watchlist — no specific ticker actionable."
    if opportunity >= 75 and confidence >= 70:
        return "High-probability setup — confirm with volume + flow before sizing."
    if opportunity >= 60:
        return "Tradeable setup — wait for trigger (POC reclaim / 5-min ORB)."
    if opportunity >= 45:
        return "Watchlist — let price action confirm before committing capital."
    return "No-action — insufficient edge."


def _enrich(article: dict) -> dict:
    """Run the full intelligence pipeline on a single article."""
    text       = f"{article.get('title','')} {article.get('summary','')}"
    tickers    = _extract_tickers(article.get("title", "") + " " + article.get("summary", ""))
    event, horizon = _classify_event(text)
    direction, sent_score = _sentiment(text)
    smart_money = _detect_smart_money(text)
    article["tickers"]    = tickers

    # If smart money is detected with a clear direction, let it dominate the
    # sentiment signal — a Burry short is bearish regardless of headline tone.
    if smart_money["detected"]:
        if smart_money["direction"] == "buy" and direction != "bullish":
            direction, sent_score = "bullish", max(sent_score, 5)
        elif smart_money["direction"] == "sell" and direction != "bearish":
            direction, sent_score = "bearish", min(sent_score, -5)
        # Promote the event type so the UI filter / spotlight can find it.
        if event in {"General", "Analyst"}:
            event = "Smart Money"

    scores = _signal_scores(article, event, sent_score, smart_money)
    conf   = _confidence(article, sent_score, event)
    if smart_money["detected"]:
        conf = min(100, conf + 10)  # named entities raise reliability

    article.update({
        "event_type":     event,
        "primary_horizon": horizon,
        "sentiment":      direction,
        "sentiment_score": sent_score,
        "tickers":        tickers,
        "smart_money":    smart_money,
        "is_megacap":     any(t in MEGA_CAP_TICKERS for t in tickers),
        "analogs":        ANALOGS.get(event, []),
        "signal":         scores,
        "confidence":     conf,
        "scenarios":      _scenarios(event, direction, smart_money),
        "recommendation": _recommendation(scores["opportunity"], conf, bool(tickers), smart_money),
        "impact": {
            "short_term":  _impact_band(event, direction, "short"),
            "medium_term": _impact_band(event, direction, "medium"),
            "long_term":   _impact_band(event, direction, "long"),
        },
    })
    return article


def _impact_band(event: str, direction: str, horizon: str) -> str:
    """Coarse expected-move bands. Rules-based; refine later with realized vols."""
    if direction == "neutral":
        return "Flat / range-bound"
    sign = "+" if direction == "bullish" else "-"
    if event == "Earnings":
        return {"short": f"{sign}4-8%", "medium": f"{sign}2-5%", "long": f"{sign}0-3%"}[horizon]
    if event in {"M&A", "Regulatory", "Short Report"}:
        return {"short": f"{sign}10-25%", "medium": f"{sign}3-10%", "long": f"{sign}0-5%"}[horizon]
    if event == "Macro":
        return {"short": f"{sign}1-3% (broad)", "medium": f"{sign}2-6% (broad)", "long": f"{sign}5-15% (broad)"}[horizon]
    if event in {"Insider", "Institutional", "Smart Money"}:
        return {"short": f"{sign}2-6%", "medium": f"{sign}5-15%", "long": f"{sign}10-30%"}[horizon]
    if event == "Geopolitical":
        return {"short": f"{sign}1-4%", "medium": f"{sign}3-8%", "long": "Path-dependent"}[horizon]
    return {"short": f"{sign}1-3%", "medium": f"{sign}2-5%", "long": f"{sign}0-3%"}[horizon]


# ── Public API ────────────────────────────────────────────────────────────────

def fetch_market_news(limit: int = 30) -> List[dict]:
    """Back-compat: simple ranked feed used by the existing News page."""
    articles = _fetch_all_feeds()

    # de-dupe by title (different sources often syndicate the same story)
    seen, deduped = set(), []
    for a in articles:
        key = (a.get("title") or "").lower().strip()[:120]
        if not key or key in seen:
            continue
        seen.add(key)
        # Keep the original lightweight tag fields the old UI expects.
        text = f"{a.get('title','')} {a.get('summary','')}".lower()
        a["tags"] = sorted({
            label for pat, label, _ in EVENT_PATTERNS if re.search(pat, text)
        })
        a["strategy_relevance"] = len(a["tags"])
        deduped.append(a)

    deduped.sort(key=lambda x: (x["strategy_relevance"], x.get("published") or ""), reverse=True)
    return deduped[:limit]


# ── Persistent archive (powers day/week/month summaries) ─────────────────────
# Every intelligence pull appends new articles to a single JSON file. We keep a
# compact subset of fields (no full body) and prune to a rolling 90-day window
# so the file stays small. Dedupe is by article link.

_ARCHIVE_PATH = Path(__file__).resolve().parent.parent / "data" / "news_archive.json"
_ARCHIVE_LOCK = threading.Lock()
_ARCHIVE_RETENTION_DAYS = 90
_ARCHIVE_FIELDS = (
    "title", "link", "source", "published",
    "event_type", "sentiment", "sentiment_score",
    "tickers", "smart_money", "is_megacap",
    "confidence", "signal", "recommendation",
)


def _archive_load() -> list[dict]:
    if not _ARCHIVE_PATH.exists():
        return []
    try:
        with _ARCHIVE_PATH.open("r", encoding="utf-8") as f:
            return json.load(f) or []
    except Exception:
        return []


def _archive_save(records: list[dict]) -> None:
    try:
        _ARCHIVE_PATH.parent.mkdir(parents=True, exist_ok=True)
        with _ARCHIVE_PATH.open("w", encoding="utf-8") as f:
            json.dump(records, f, ensure_ascii=False)
    except Exception:
        pass


def _archive_upsert(enriched: list[dict]) -> None:
    """Merge a fresh pull into the archive, dedupe by link, prune to retention."""
    with _ARCHIVE_LOCK:
        existing = _archive_load()
        by_link: dict[str, dict] = {r["link"]: r for r in existing if r.get("link")}
        now_iso = datetime.now(timezone.utc).isoformat()
        for a in enriched:
            link = a.get("link")
            if not link:
                continue
            slim = {k: a.get(k) for k in _ARCHIVE_FIELDS}
            # Store an `archived_at` timestamp so we can window even when an
            # article has a missing/garbage `published` field.
            slim["archived_at"] = now_iso
            # Lower-tier `signal` payload: keep only what summaries need.
            sig = slim.get("signal") or {}
            slim["signal"] = {
                "opportunity": sig.get("opportunity"),
                "quality":     sig.get("quality"),
            }
            by_link[link] = slim

        # Prune old entries
        cutoff = datetime.now(timezone.utc) - timedelta(days=_ARCHIVE_RETENTION_DAYS)
        kept: list[dict] = []
        for r in by_link.values():
            ts_str = r.get("published") or r.get("archived_at") or ""
            try:
                ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
            except Exception:
                ts = datetime.now(timezone.utc)
            if ts >= cutoff:
                kept.append(r)

        _archive_save(kept)


def fetch_intelligence(
    limit: int = 25,
    min_confidence: int = 0,
    event_type: Optional[str] = None,
) -> dict:
    """Full intelligence payload — the headline endpoint for the new UI."""
    raw = _fetch_all_feeds()

    # de-dupe + enrich
    seen, enriched = set(), []
    for a in raw:
        key = (a.get("title") or "").lower().strip()[:120]
        if not key or key in seen:
            continue
        seen.add(key)
        enriched.append(_enrich(a))

    # Persist BEFORE filtering — the archive should reflect everything we saw,
    # not just what passes the user's current filter.
    _archive_upsert(enriched)

    # filters
    if event_type and event_type != "All":
        enriched = [a for a in enriched if a["event_type"] == event_type]
    if min_confidence:
        enriched = [a for a in enriched if a["confidence"] >= min_confidence]

    # Sort: smart money first (by entity boost), then by opportunity + confidence.
    enriched.sort(
        key=lambda a: (
            1 if a.get("smart_money", {}).get("detected") else 0,
            a.get("smart_money", {}).get("boost", 0),
            a["signal"]["opportunity"],
            a["confidence"],
            a.get("published") or "",
        ),
        reverse=True,
    )
    enriched = enriched[:limit]

    # Aggregations for the dashboard header
    by_event: dict[str, int] = {}
    by_sentiment = {"bullish": 0, "bearish": 0, "neutral": 0}
    ticker_hits: dict[str, int] = {}
    smart_money_articles: list[dict] = []
    entity_hits: dict[str, dict] = {}     # entity name → {category, count, direction}
    megacap_count = 0

    for a in enriched:
        by_event[a["event_type"]] = by_event.get(a["event_type"], 0) + 1
        by_sentiment[a["sentiment"]] = by_sentiment.get(a["sentiment"], 0) + 1
        for t in a["tickers"]:
            ticker_hits[t] = ticker_hits.get(t, 0) + 1
        if a.get("is_megacap"):
            megacap_count += 1
        sm = a.get("smart_money") or {}
        if sm.get("detected"):
            smart_money_articles.append(a)
            for ent in sm["entities"]:
                key = ent["name"]
                if key not in entity_hits:
                    entity_hits[key] = {"category": ent["category"], "count": 0, "buys": 0, "sells": 0}
                entity_hits[key]["count"] += 1
                if ent["direction"] == "buy":  entity_hits[key]["buys"]  += 1
                if ent["direction"] == "sell": entity_hits[key]["sells"] += 1

    top_tickers = sorted(ticker_hits.items(), key=lambda x: -x[1])[:10]
    top_entities = sorted(
        [{"name": k, **v} for k, v in entity_hits.items()],
        key=lambda e: -e["count"],
    )[:20]
    avg_conf    = int(sum(a["confidence"] for a in enriched) / len(enriched)) if enriched else 0
    market_tone = (
        "Risk-On"  if by_sentiment["bullish"] > by_sentiment["bearish"] * 1.3 else
        "Risk-Off" if by_sentiment["bearish"] > by_sentiment["bullish"] * 1.3 else
        "Mixed"
    )

    return {
        "generated_at":  datetime.now(timezone.utc).isoformat(),
        "articles":      enriched,
        "count":         len(enriched),
        "avg_confidence": avg_conf,
        "market_tone":    market_tone,
        "by_event":       by_event,
        "by_sentiment":   by_sentiment,
        "top_tickers":    [{"ticker": t, "mentions": n} for t, n in top_tickers],
        "event_types":    sorted({label for _, label, _ in EVENT_PATTERNS}) + ["Smart Money", "General"],
        "smart_money": {
            "count":        len(smart_money_articles),
            "top_entities": top_entities,
            "spotlight":    smart_money_articles,   # full list — UI paginates/expands
        },
        "megacap_count":  megacap_count,
    }


def fetch_stock_news(ticker: str, limit: int = 12) -> List[dict]:
    """Back-compat: simple per-ticker feed used elsewhere in the app."""
    items = _fetch_yahoo_ticker_news(ticker, limit=limit)
    return [
        {
            "title":     it["title"],
            "link":      it["link"],
            "publisher": it["source"],
            "published": it["published"],
            "thumbnail": "",
        }
        for it in items
    ]


def fetch_ticker_intelligence(ticker: str, limit: int = 15) -> dict:
    """Combine Yahoo Finance per-ticker news with Google News results, then enrich."""
    ticker = ticker.upper().strip()
    yahoo  = _fetch_yahoo_ticker_news(ticker, limit=limit)
    google = _fetch_google_news_for(f"{ticker} stock", limit=limit)

    seen, merged = set(), []
    for a in (yahoo + google):
        key = (a.get("title") or "").lower().strip()[:120]
        if not key or key in seen:
            continue
        seen.add(key)
        # Force-tag the requested ticker even if regex misses it (e.g. unicode dashes).
        enriched = _enrich(a)
        if ticker not in enriched["tickers"]:
            enriched["tickers"] = [ticker, *enriched["tickers"]]
        merged.append(enriched)

    merged.sort(
        key=lambda a: (a["signal"]["opportunity"], a["confidence"], a.get("published") or ""),
        reverse=True,
    )
    merged = merged[:limit]

    # ticker-level rollup
    bullish = sum(1 for a in merged if a["sentiment"] == "bullish")
    bearish = sum(1 for a in merged if a["sentiment"] == "bearish")
    avg_opp = int(sum(a["signal"]["opportunity"] for a in merged) / len(merged)) if merged else 0
    tone    = "bullish" if bullish > bearish * 1.3 else "bearish" if bearish > bullish * 1.3 else "mixed"

    return {
        "ticker":        ticker,
        "articles":      merged,
        "count":         len(merged),
        "bullish_count": bullish,
        "bearish_count": bearish,
        "tone":          tone,
        "avg_opportunity": avg_opp,
    }


# ── Bot integration helper ───────────────────────────────────────────────────

def get_news_score_for_ticker(ticker: str, direction: str = "long", limit: int = 12) -> dict:
    """Compress the per-ticker intelligence into a single 0-1 score and a
    short context dict the bot can store on the trade record.

    Returns:
        {
            "available":      bool,
            "score":          float (0-1),       # 0.5 = neutral / no info
            "tone":           str,                # bullish/bearish/mixed
            "article_count":  int,
            "bullish_count":  int,
            "bearish_count":  int,
            "avg_opportunity": int (0-100),
            "smart_money_buy":  int,              # SM article counts aligned w/ direction
            "smart_money_sell": int,
            "smart_money_entities": [str],        # canonical names mentioned
            "top_event_types":  [(event, count)], # most common event types
            "headline_top":   str | None,         # title of highest-opp article
            "reason":         str,                # one-line summary the bot can quote
        }
    """
    try:
        intel = fetch_ticker_intelligence(ticker, limit=limit)
    except Exception:
        return {"available": False, "score": 0.5, "reason": "news fetch failed"}

    arts = intel.get("articles") or []
    if not arts:
        return {"available": False, "score": 0.5, "reason": "no news available"}

    tone           = intel.get("tone", "mixed")
    avg_opp        = intel.get("avg_opportunity", 0)
    bullish_count  = intel.get("bullish_count", 0)
    bearish_count  = intel.get("bearish_count", 0)

    # Direction alignment
    direction = (direction or "long").lower()
    if direction == "long":
        if   tone == "bullish": dir_score = 0.85
        elif tone == "bearish": dir_score = 0.15
        else:                    dir_score = 0.50
    else:  # short
        if   tone == "bearish": dir_score = 0.85
        elif tone == "bullish": dir_score = 0.15
        else:                    dir_score = 0.50

    # Smart Money news alignment
    sm_buys = sm_sells = 0
    sm_entities: set[str] = set()
    event_counter: dict[str, int] = {}
    for a in arts:
        sm = a.get("smart_money") or {}
        if sm.get("detected"):
            d = sm.get("direction")
            if d == "buy":  sm_buys  += 1
            if d == "sell": sm_sells += 1
            for e in sm.get("entities") or []:
                sm_entities.add(e["name"])
        et = a.get("event_type", "General")
        event_counter[et] = event_counter.get(et, 0) + 1

    sm_bonus = 0.0
    if direction == "long":
        sm_bonus += 0.05 * sm_buys - 0.04 * sm_sells
    else:
        sm_bonus += 0.05 * sm_sells - 0.04 * sm_buys
    sm_bonus = max(-0.30, min(0.30, sm_bonus))

    opp_score = max(0.0, min(1.0, avg_opp / 100.0))

    # Final blend: 50% direction, 30% opp magnitude, 20% baseline + SM bonus
    score = (dir_score * 0.50) + (opp_score * 0.30) + 0.20 + sm_bonus
    score = max(0.0, min(1.0, score))

    top_event_types = sorted(event_counter.items(), key=lambda x: -x[1])[:3]
    headline_top = arts[0].get("title") if arts else None

    reason_bits = [
        f"News tone {tone}",
        f"{bullish_count}↑/{bearish_count}↓",
        f"avg_opp={avg_opp}",
    ]
    if sm_buys or sm_sells:
        reason_bits.append(f"SM news {sm_buys}B/{sm_sells}S")
    if sm_entities:
        reason_bits.append(f"entities: {', '.join(sorted(sm_entities)[:3])}")

    return {
        "available":        True,
        "score":            round(score, 4),
        "tone":             tone,
        "article_count":    intel.get("count", len(arts)),
        "bullish_count":    bullish_count,
        "bearish_count":    bearish_count,
        "avg_opportunity":  avg_opp,
        "smart_money_buy":  sm_buys,
        "smart_money_sell": sm_sells,
        "smart_money_entities": sorted(sm_entities),
        "top_event_types":  top_event_types,
        "headline_top":     headline_top,
        "reason":           " | ".join(reason_bits),
    }


# ── Day / Week / Month summary aggregator ────────────────────────────────────

_PERIOD_DAYS = {"day": 1, "week": 7, "month": 30}


def _parse_iso(s: str) -> Optional[datetime]:
    if not s:
        return None
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


def summarize(period: str = "day") -> dict:
    """Aggregate the archive over the requested window and return a rollup.

    Period:
      "day"   → last 24h
      "week"  → last 7d
      "month" → last 30d

    Pulls from the persistent archive (`backend/data/news_archive.json`) which
    is appended on every `fetch_intelligence` call. Coverage builds over time —
    a fresh install only has whatever the latest fetch surfaced.
    """
    period = period.lower()
    days = _PERIOD_DAYS.get(period, 1)
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=days)

    all_records = _archive_load()
    in_window: list[dict] = []
    for r in all_records:
        ts = _parse_iso(r.get("published")) or _parse_iso(r.get("archived_at"))
        if ts and ts >= cutoff:
            in_window.append(r)

    if not in_window:
        return {
            "period":         period,
            "window_days":    days,
            "window_from":    cutoff.isoformat(),
            "window_to":      now.isoformat(),
            "total_articles": 0,
            "smart_money_count": 0,
            "market_tone":    "No data",
            "avg_confidence": 0,
            "by_sentiment":   {"bullish": 0, "bearish": 0, "neutral": 0},
            "by_event":       [],
            "by_day":         [],
            "top_tickers":    [],
            "top_entities":   [],
            "top_signals":    [],
            "biggest_smart_money_moves": [],
            "archive_total":  len(all_records),
        }

    # Sentiment + event histograms
    by_sentiment = Counter(r.get("sentiment", "neutral") for r in in_window)
    by_event_cnt = Counter(r.get("event_type", "General") for r in in_window)

    # Per-day breakdown (always ordered oldest → newest for charting)
    by_day: dict[str, dict] = defaultdict(lambda: {"bull": 0, "bear": 0, "neut": 0, "sm": 0, "total": 0})
    for r in in_window:
        ts = _parse_iso(r.get("published")) or _parse_iso(r.get("archived_at")) or now
        d = ts.strftime("%Y-%m-%d")
        sent = r.get("sentiment", "neutral")
        by_day[d]["total"] += 1
        by_day[d]["bull"]  += int(sent == "bullish")
        by_day[d]["bear"]  += int(sent == "bearish")
        by_day[d]["neut"]  += int(sent == "neutral")
        if (r.get("smart_money") or {}).get("detected"):
            by_day[d]["sm"] += 1

    # Ticker mentions
    ticker_cnt: Counter[str] = Counter()
    for r in in_window:
        for t in (r.get("tickers") or []):
            ticker_cnt[t] += 1

    # Entity aggregation (per direction)
    entity_agg: dict[str, dict] = {}
    smart_money_records: list[dict] = []
    for r in in_window:
        sm = r.get("smart_money") or {}
        if not sm.get("detected"):
            continue
        smart_money_records.append(r)
        for e in sm.get("entities") or []:
            name = e["name"]
            if name not in entity_agg:
                entity_agg[name] = {"category": e["category"], "count": 0, "buys": 0, "sells": 0}
            entity_agg[name]["count"] += 1
            if e.get("direction") == "buy":  entity_agg[name]["buys"]  += 1
            if e.get("direction") == "sell": entity_agg[name]["sells"] += 1

    top_entities = sorted(
        [{"name": k, **v} for k, v in entity_agg.items()],
        key=lambda e: -e["count"],
    )[:15]

    # Top signals by opportunity (overall)
    def _opp(r: dict) -> int:
        return int(((r.get("signal") or {}).get("opportunity")) or 0)
    top_signals = sorted(in_window, key=_opp, reverse=True)[:8]

    # Biggest smart-money moves
    biggest_sm = sorted(smart_money_records, key=_opp, reverse=True)[:8]

    avg_conf = int(sum((r.get("confidence") or 0) for r in in_window) / len(in_window))

    tone = (
        "Risk-On"  if by_sentiment["bullish"] > by_sentiment["bearish"] * 1.3 else
        "Risk-Off" if by_sentiment["bearish"] > by_sentiment["bullish"] * 1.3 else
        "Mixed"
    )

    # Helper: trim a record for the response (drop big nested objects)
    def _slim(r: dict) -> dict:
        sm = r.get("smart_money") or {}
        return {
            "title":      r.get("title"),
            "link":       r.get("link"),
            "source":     r.get("source"),
            "published":  r.get("published"),
            "event_type": r.get("event_type"),
            "sentiment":  r.get("sentiment"),
            "tickers":    r.get("tickers") or [],
            "confidence": r.get("confidence"),
            "opportunity": _opp(r),
            "recommendation": r.get("recommendation"),
            "smart_money": {
                "detected":  sm.get("detected", False),
                "direction": sm.get("direction"),
                "entities":  [{"name": e["name"], "category": e["category"]} for e in (sm.get("entities") or [])],
                "headline":  sm.get("headline"),
            } if sm.get("detected") else None,
        }

    return {
        "period":              period,
        "window_days":         days,
        "window_from":         cutoff.isoformat(),
        "window_to":           now.isoformat(),
        "total_articles":      len(in_window),
        "smart_money_count":   len(smart_money_records),
        "market_tone":         tone,
        "avg_confidence":      avg_conf,
        "by_sentiment": {
            "bullish": by_sentiment.get("bullish", 0),
            "bearish": by_sentiment.get("bearish", 0),
            "neutral": by_sentiment.get("neutral", 0),
        },
        "by_event": [{"event": k, "count": v} for k, v in by_event_cnt.most_common(12)],
        "by_day": [
            {"date": d, **by_day[d]}
            for d in sorted(by_day.keys())
        ],
        "top_tickers":     [{"ticker": t, "mentions": n} for t, n in ticker_cnt.most_common(15)],
        "top_entities":    top_entities,
        "top_signals":     [_slim(r) for r in top_signals],
        "biggest_smart_money_moves": [_slim(r) for r in biggest_sm],
        "archive_total":   len(all_records),
    }
