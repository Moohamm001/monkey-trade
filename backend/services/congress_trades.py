"""
Congressional Trading Disclosures Intelligence.

Sources (free, public S3 buckets maintained by open-source projects):
  House:  https://house-stock-watcher-data.s3-us-west-2.amazonaws.com/data/all_transactions.json
  Senate: https://senate-stock-watcher-data.s3-us-west-2.amazonaws.com/aggregate/all_transactions.json

Legal basis:
  STOCK Act (2012) requires all members of Congress to publicly disclose
  trades within 45 days of execution. Violations result in fines but
  enforcement is minimal — compliance is ~80% on time.

Why this matters for trading:
  Multiple academic studies (Ziobrowski et al. 2004, 2011) show that
  congressional portfolios significantly outperform the market. The information
  advantage is real: members sit on committees that regulate the industries
  they trade, receive classified intelligence briefings, and know about
  upcoming legislation before the market.

  Signal hierarchy:
    ★★★ Cluster buying by multiple members, same stock, <30 days apart
        → High-conviction intelligence-driven buy signal
    ★★  Single member purchase, relevant committee membership
        → Directional signal worth monitoring
    ★   Single member sale
        → Less meaningful (diversification, personal liquidity)

  Key committees to watch:
    - Armed Services → Defense stocks (LMT, RTX, NOC, BA)
    - Finance/Banking → Financial stocks (JPM, GS, BAC)
    - Technology → Big tech (AAPL, NVDA, MSFT, GOOGL)
    - Energy → Oil, utilities, clean energy
    - Health → Pharma, biotech, healthcare
"""
from __future__ import annotations

from datetime import datetime, timedelta
from functools import lru_cache
from typing import Optional

import requests

_SESSION = requests.Session()
_SESSION.headers.update({"User-Agent": "MonkeyTrade research@monkeytrade.app"})

_HOUSE_URL  = "https://house-stock-watcher-data.s3-us-west-2.amazonaws.com/data/all_transactions.json"
_SENATE_URL = "https://senate-stock-watcher-data.s3-us-west-2.amazonaws.com/aggregate/all_transactions.json"


@lru_cache(maxsize=2)
def _fetch_house(ttl_hash: int = None) -> list[dict]:  # ttl_hash changes daily to bust cache
    try:
        r = _SESSION.get(_HOUSE_URL, timeout=20)
        r.raise_for_status()
        return r.json()
    except Exception:
        return []


@lru_cache(maxsize=2)
def _fetch_senate(ttl_hash: int = None) -> list[dict]:
    try:
        r = _SESSION.get(_SENATE_URL, timeout=20)
        r.raise_for_status()
        return r.json()
    except Exception:
        return []


def _daily_ttl() -> int:
    """Cache buster that changes once per day."""
    return datetime.now().toordinal()


def get_congress_trades(ticker: str, lookback_days: int = 365) -> dict:
    """
    Return all congressional trades for *ticker* in the last *lookback_days* days.
    Combines House and Senate disclosures.
    """
    ticker_up = ticker.upper()
    cutoff    = datetime.now() - timedelta(days=lookback_days)
    trades    = []

    # ── House ────────────────────────────────────────────────────────────────
    for row in _fetch_house(_daily_ttl()):
        try:
            sym = str(row.get("ticker", "")).upper().strip()
            if sym != ticker_up:
                continue
            tx_date_str = str(row.get("transaction_date") or row.get("disclosure_date") or "")[:10]
            try:
                tx_date = datetime.strptime(tx_date_str, "%Y-%m-%d")
                if tx_date < cutoff:
                    continue
            except Exception:
                pass

            trade_type = str(row.get("type", "")).lower()
            trades.append({
                "chamber":     "House",
                "member":      str(row.get("representative", "")),
                "party":       str(row.get("party", "")),
                "state":       str(row.get("state", "")),
                "trade_date":  tx_date_str,
                "disclosure_date": str(row.get("disclosure_date", ""))[:10],
                "trade_type":  "buy" if "purchase" in trade_type else "sell" if "sale" in trade_type else trade_type,
                "amount":      str(row.get("amount", "")),
                "asset_description": str(row.get("asset_description", "")),
                "is_buy":      "purchase" in trade_type,
            })
        except Exception:
            continue

    # ── Senate ────────────────────────────────────────────────────────────────
    for row in _fetch_senate(_daily_ttl()):
        try:
            sym = str(row.get("ticker", "")).upper().strip()
            if sym != ticker_up:
                continue
            tx_date_str = str(row.get("transaction_date") or "")[:10]
            try:
                tx_date = datetime.strptime(tx_date_str, "%Y-%m-%d")
                if tx_date < cutoff:
                    continue
            except Exception:
                pass

            trade_type = str(row.get("type", "")).lower()
            trades.append({
                "chamber":     "Senate",
                "member":      str(row.get("senator", "")),
                "party":       str(row.get("party", "")),
                "state":       str(row.get("state", "")),
                "trade_date":  tx_date_str,
                "disclosure_date": tx_date_str,
                "trade_type":  "buy" if "purchase" in trade_type else "sell" if "sale" in trade_type else trade_type,
                "amount":      str(row.get("amount", "")),
                "asset_description": str(row.get("asset_description", "")),
                "is_buy":      "purchase" in trade_type,
            })
        except Exception:
            continue

    trades.sort(key=lambda x: x.get("trade_date", ""), reverse=True)

    buys_90d    = sum(1 for t in trades if t["is_buy"]  and _within_days(t["trade_date"], 90))
    sells_90d   = sum(1 for t in trades if not t["is_buy"] and _within_days(t["trade_date"], 90))
    cluster_buy = buys_90d >= 3

    if cluster_buy:
        signal = "bullish"
        message = (
            f"{buys_90d} members of Congress bought {ticker_up} in the last 90 days. "
            "Cluster congressional buying is a rare and powerful signal — these individuals "
            "have access to non-public policy information through committee work. "
            "Historically associated with upcoming favorable legislation or regulatory decisions."
        )
    elif buys_90d > 0:
        signal = "bullish"
        message = (
            f"{buys_90d} congressional purchase(s) in the last 90 days. "
            "Watch for additional buyers — cluster confirmation elevates the signal significantly."
        )
    elif sells_90d >= 3:
        signal = "bearish"
        message = (
            f"{sells_90d} members sold {ticker_up} in the last 90 days. "
            "Congressional cluster selling is uncommon for personal-liquidity reasons. "
            "May reflect advance knowledge of unfavorable regulatory or legislative action."
        )
    elif len(trades) == 0:
        signal = "neutral"
        message = f"No congressional trading in {ticker_up} in the last {lookback_days} days."
    else:
        signal = "neutral"
        message = f"Some congressional activity but no clear directional cluster (buys: {buys_90d}, sells: {sells_90d} in 90 days)."

    return {
        "signal":      signal,
        "message":     message,
        "buys_90d":    buys_90d,
        "sells_90d":   sells_90d,
        "cluster_buy": cluster_buy,
        "total_trades": len(trades),
        "trades":       trades[:20],
    }


def _within_days(date_str: str, days: int) -> bool:
    try:
        dt = datetime.strptime(date_str[:10], "%Y-%m-%d")
        return (datetime.now() - dt).days <= days
    except Exception:
        return False
