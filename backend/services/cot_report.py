"""
CFTC Commitment of Traders (COT) Report Intelligence.

Source: CFTC Traders in Financial Futures (Disaggregated)
  https://publicreporting.cftc.gov/resource/jun7-fc8e.json  (Socrata API)

Why COT matters for stocks:
  The COT report shows how three trader types are positioned in futures:
    - Dealer/Intermediary (large banks, prime brokers) — commercial hedgers
    - Asset Manager / Institutional  — pension funds, mutual funds, endowments
    - Leveraged Funds  — hedge funds, CTAs (the "smart money speculators")
    - Other Reportables & Non-Reportables  — retail/smaller accounts

  For equity index futures (S&P 500, NASDAQ-100), the Asset Manager net position
  is the most directional signal — when large institutions are net long and
  increasing, the market has tailwind. When they are reducing longs while
  Leveraged Funds are shorting, major tops have historically formed.

Instruments tracked:
  E-MINI S&P 500  — correlates with SPY, AAPL, MSFT (market-wide)
  E-MINI NASDAQ-100 — correlates with QQQ, NVDA, TSLA, tech sector
  GOLD            — correlates with GLD, inflation trades
  CRUDE OIL       — correlates with XLE, energy sector, CL futures
  U.S. TREASURY   — bond market directional signal (inverse equity signal)

Signal interpretation:
  Asset Manager net long increasing week-over-week → institutional accumulation
  Leveraged Funds net short AND increasing       → hedge funds betting on decline
  Both Asset Manager and Leveraged Funds short   → rare extreme bearish setup
  Divergence (Asset Mgr long, Leveraged short)   → most common pre-squeeze setup
"""
from __future__ import annotations

from datetime import datetime, timedelta
from functools import lru_cache

import requests

_SESSION = requests.Session()
_SESSION.headers.update({"User-Agent": "MonkeyTrade research@monkeytrade.app"})

# Socrata endpoint — CFTC Traders in Financial Futures
_COT_URL = "https://publicreporting.cftc.gov/resource/jun7-fc8e.json"

# Map friendly names → CFTC market name substrings
INSTRUMENTS = {
    "SP500":   "E-MINI S&P 500",
    "NASDAQ":  "NASDAQ-100 MINI",
    "GOLD":    "GOLD",
    "OIL":     "CRUDE OIL",
    "BONDS":   "U.S. TREASURY BONDS",
    "VIX":     "VIX",
}

# Which tickers each instrument is relevant to
INSTRUMENT_RELEVANCE = {
    "SP500":  ["SPY", "IVV", "VOO", "AAPL", "MSFT", "AMZN", "GOOGL"],
    "NASDAQ": ["QQQ", "NVDA", "TSLA", "META", "NFLX", "AMD", "INTC"],
    "GOLD":   ["GLD", "GDX", "GDXJ", "NEM", "AEM", "AU"],
    "OIL":    ["XLE", "XOM", "CVX", "COP", "OXY", "SLB", "HAL"],
    "BONDS":  ["TLT", "IEF", "BND", "AGG", "HYG"],
    "VIX":    ["UVXY", "SVXY", "VXX"],
}


@lru_cache(maxsize=12)
def _fetch_cot(instrument_key: str, weeks: int = 8) -> list[dict]:
    """Fetch the last *weeks* weeks of COT data for *instrument_key*."""
    market_substr = INSTRUMENTS.get(instrument_key.upper())
    if not market_substr:
        return []

    since = (datetime.now() - timedelta(weeks=weeks + 2)).strftime("%Y-%m-%d")
    try:
        params = {
            "$where": (
                f"market_and_exchange_names like '%{market_substr}%' "
                f"AND report_date_as_yyyy_mm_dd >= '{since}'"
            ),
            "$order": "report_date_as_yyyy_mm_dd DESC",
            "$limit": str(weeks + 2),
        }
        r = _SESSION.get(_COT_URL, params=params, timeout=20)
        r.raise_for_status()
        return r.json()
    except Exception:
        return []


def get_cot_signal(instrument_key: str) -> dict:
    """
    Compute positioning signal for one COT instrument.
    Returns net positions, week-over-week change, and directional signal.
    """
    rows = _fetch_cot(instrument_key.upper())
    if not rows:
        return {
            "instrument": instrument_key,
            "signal": "neutral",
            "message": "COT data not available.",
            "weeks": [],
        }

    parsed = []
    for row in rows:
        try:
            parsed.append({
                "date": str(row.get("report_date_as_yyyy_mm_dd", ""))[:10],

                # Asset Manager (institutional — pension, mutual, endowment)
                "asset_mgr_long":  int(row.get("asset_mgr_long",  0) or 0),
                "asset_mgr_short": int(row.get("asset_mgr_short", 0) or 0),

                # Leveraged Funds (hedge funds, CTAs)
                "lev_long":        int(row.get("lev_money_long",  0) or 0),
                "lev_short":       int(row.get("lev_money_short", 0) or 0),

                # Dealer (prime brokers)
                "dealer_long":     int(row.get("dealer_long",  0) or 0),
                "dealer_short":    int(row.get("dealer_short", 0) or 0),

                "open_interest":   int(row.get("open_interest_all", 0) or 0),
            })
        except Exception:
            continue

    if not parsed:
        return {"instrument": instrument_key, "signal": "neutral", "message": "No parseable rows.", "weeks": []}

    parsed.sort(key=lambda x: x["date"])

    for p in parsed:
        p["asset_mgr_net"] = p["asset_mgr_long"] - p["asset_mgr_short"]
        p["lev_net"]       = p["lev_long"]        - p["lev_short"]
        p["dealer_net"]    = p["dealer_long"]      - p["dealer_short"]

    latest = parsed[-1]
    prev   = parsed[-2] if len(parsed) >= 2 else latest

    am_change  = latest["asset_mgr_net"] - prev["asset_mgr_net"]
    lev_change = latest["lev_net"]       - prev["lev_net"]

    # Signal logic
    am_net  = latest["asset_mgr_net"]
    lev_net = latest["lev_net"]

    if am_net > 0 and am_change > 0 and lev_net > 0:
        signal = "bullish"
        message = (
            f"Asset Managers are net long {am_net:,} contracts and ADDING ({am_change:+,} WoW). "
            f"Leveraged Funds also net long {lev_net:,}. "
            "Institutional and speculative money aligned bullish — strong tailwind for longs."
        )
    elif am_net > 0 and am_change > 0 and lev_net < 0:
        signal = "bullish"
        message = (
            f"Asset Managers net long {am_net:,} and increasing ({am_change:+,} WoW). "
            f"Leveraged Funds are net short {abs(lev_net):,} — set up for a short squeeze. "
            "This divergence (institutions accumulating while hedge funds short) is historically "
            "the strongest pre-squeeze COT pattern."
        )
    elif am_net < 0 and am_change < 0:
        signal = "bearish"
        message = (
            f"Asset Managers are net short {abs(am_net):,} contracts and increasing shorts ({am_change:+,} WoW). "
            "Institutional money is actively hedging or positioning for a decline. "
            "This is not retail — these are pension funds and endowments reducing equity risk."
        )
    elif am_net > 0 and am_change < 0:
        signal = "neutral"
        message = (
            f"Asset Managers remain net long {am_net:,} but REDUCING by {abs(am_change):,} WoW. "
            "Institutions are trimming exposure — not bearish yet, but the buying pressure is fading."
        )
    else:
        signal = "neutral"
        message = (
            f"Asset Managers net: {am_net:,}. Leveraged Funds net: {lev_net:,}. "
            "No extreme positioning. Market is balanced between institutional and speculative accounts."
        )

    return {
        "instrument":    instrument_key,
        "signal":        signal,
        "message":       message,
        "latest_date":   latest["date"],
        "asset_mgr_net": latest["asset_mgr_net"],
        "asset_mgr_chg": am_change,
        "lev_net":       latest["lev_net"],
        "lev_chg":       lev_change,
        "dealer_net":    latest["dealer_net"],
        "open_interest": latest["open_interest"],
        "weeks":         parsed[-8:],
    }


def get_relevant_cot(ticker: str) -> list[dict]:
    """Return COT signals for all instruments relevant to *ticker*."""
    ticker_up = ticker.upper()
    relevant  = []
    for inst, tickers in INSTRUMENT_RELEVANCE.items():
        if ticker_up in tickers:
            relevant.append(get_cot_signal(inst))
    if not relevant:
        # Always return SP500 for market context
        relevant.append(get_cot_signal("SP500"))
    return relevant
