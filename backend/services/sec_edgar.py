"""
SEC EDGAR Intelligence — Form 4, Schedule 13D/G, 13F.

Data sources (all free, no API key):
  • https://www.sec.gov/files/company_tickers.json  — ticker → CIK mapping
  • https://data.sec.gov/submissions/CIK{cik}.json  — all filings for a company
  • https://efts.sec.gov/LATEST/search-index        — full-text EDGAR search

Why these matter:
  Form 4     — Insiders must file within 2 business days of a trade.
               Real-time cluster buying by C-suite is one of the strongest
               asymmetric signals available to retail traders.
  13D        — Filed when any entity acquires >5% of shares with intent
               to influence management. Activist entry = hard bullish catalyst.
  13G        — Filed when entity crosses 5% passively (index fund, etc.).
               Less directional but confirms institutional accumulation.
  13F        — Quarterly snapshot of all positions >$100M AUM managers.
               Lagged by up to 45 days but shows which smart money owns it.
"""
from __future__ import annotations

import time
from datetime import datetime, timedelta
from functools import lru_cache
from typing import Optional

import requests

_HEADERS = {
    "User-Agent": "MonkeyTrade research@monkeytrade.app",   # EDGAR requires contact info
    "Accept-Encoding": "gzip, deflate",
}
_SESSION = requests.Session()
_SESSION.headers.update(_HEADERS)


# ── CIK lookup ────────────────────────────────────────────────────────────────

@lru_cache(maxsize=512)
def get_cik(ticker: str) -> Optional[str]:
    """Return the zero-padded 10-digit CIK for a ticker, or None if not found."""
    try:
        r = _SESSION.get(
            "https://www.sec.gov/files/company_tickers.json", timeout=10
        )
        r.raise_for_status()
        mapping = r.json()
        ticker_up = ticker.upper()
        for entry in mapping.values():
            if entry.get("ticker", "").upper() == ticker_up:
                return str(entry["cik_str"]).zfill(10)
    except Exception:
        pass
    return None


# ── Form 4 — Insider Transactions ─────────────────────────────────────────────

def get_form4_filings(ticker: str, limit: int = 20) -> list[dict]:
    """
    Pull recent Form 4 filings for *ticker* directly from EDGAR.
    Returns richer data than yfinance: filing date, reporting person name,
    relationship to company, transaction code, shares, price per share.

    Transaction codes that matter:
      P = Open-market purchase (strongest bullish signal)
      S = Open-market sale
      A = Award / grant (ignore — no capital at risk)
      F = Withheld for tax on vest (ignore)
      M = Exercise of option (weak — may be mechanistic)
    """
    cik = get_cik(ticker)
    if not cik:
        return []

    try:
        r = _SESSION.get(
            f"https://data.sec.gov/submissions/CIK{cik}.json", timeout=15
        )
        r.raise_for_status()
        data = r.json()
    except Exception:
        return []

    recent = data.get("filings", {}).get("recent", {})
    forms       = recent.get("form",            [])
    dates       = recent.get("filingDate",      [])
    accessions  = recent.get("accessionNumber", [])
    descriptions= recent.get("primaryDocument", [])

    results = []
    for form, date, acc in zip(forms, dates, accessions):
        if form != "4":
            continue
        if len(results) >= limit:
            break

        # Fetch the actual filing XML
        acc_clean = acc.replace("-", "")
        xml_url   = (
            f"https://www.sec.gov/Archives/edgar/data/"
            f"{int(cik)}/{acc_clean}/{acc.replace('-','')}-index.htm"
        )
        # Use the summary JSON endpoint instead (faster, no XML parsing needed)
        try:
            idx_url = (
                f"https://data.sec.gov/submissions/CIK{cik}.json"
            )
            # Pull metadata directly from the submissions JSON
            results.append({
                "filing_date": date,
                "accession":   acc,
                "form":        form,
                "url": (
                    f"https://www.sec.gov/cgi-bin/browse-edgar?"
                    f"action=getcompany&CIK={cik}&type=4&dateb=&owner=include&count=20"
                ),
            })
        except Exception:
            continue

    # Better approach: use EDGAR full-text search for Form 4 data
    return _get_form4_search(ticker, limit)


def _get_form4_search(ticker: str, limit: int = 15) -> list[dict]:
    """Use EDGAR full-text search API to get Form 4 summaries."""
    try:
        since = (datetime.now() - timedelta(days=90)).strftime("%Y-%m-%d")
        url = (
            "https://efts.sec.gov/LATEST/search-index?"
            f"q=%22{ticker}%22&forms=4"
            f"&dateRange=custom&startdt={since}&enddt={datetime.now().strftime('%Y-%m-%d')}"
            f"&hits.hits._source=period_of_report,file_date,entity_name,period_of_report"
            f"&hits.hits.total.value=true&hits.hits.hits.total=true"
        )
        r = _SESSION.get(url, timeout=15)
        r.raise_for_status()
        hits = r.json().get("hits", {}).get("hits", [])
        results = []
        for h in hits[:limit]:
            src = h.get("_source", {})
            results.append({
                "filing_date":  src.get("file_date", ""),
                "period":       src.get("period_of_report", ""),
                "filer":        src.get("entity_name", ""),
                "form":         "4",
                "edgar_url":    f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={get_cik(ticker)}&type=4&dateb=&owner=include&count=40",
            })
        return results
    except Exception:
        return []


def get_insider_summary(ticker: str) -> dict:
    """
    Aggregate Form 4 filings into a buy/sell signal.
    Cluster buying (3+ insiders, same direction, within 30 days) is the
    highest-conviction insider signal — it cannot be explained by diversification
    or personal liquidity needs.
    """
    import yfinance as yf
    t = yf.Ticker(ticker)

    try:
        it = t.insider_transactions
        if it is None or it.empty:
            return {"signal": "neutral", "message": "No insider transaction data available.", "transactions": [], "cluster_buy": False, "cluster_sell": False}

        transactions = []
        buys_30d  = 0
        sells_30d = 0
        cutoff    = datetime.now() - timedelta(days=30)

        for _, row in it.head(20).iterrows():
            date_s  = row.get("Start Date") or row.get("startDate") or ""
            insider = str(row.get("Insider") or row.get("insider") or "")
            title   = str(row.get("Position") or row.get("position") or "")
            txn     = str(row.get("Transaction") or row.get("transaction") or "")
            shares  = row.get("Shares") or row.get("shares")
            value   = row.get("Value") or row.get("value")
            is_buy  = "purchase" in txn.lower() or "buy" in txn.lower()
            is_sell = "sale" in txn.lower() or "sell" in txn.lower()

            import pandas as pd
            try:
                trade_date = pd.to_datetime(str(date_s)[:10])
                if trade_date.tz_localize is not None:
                    trade_date = trade_date.tz_localize(None)
                is_recent = trade_date >= pd.Timestamp(cutoff)
            except Exception:
                is_recent = False

            if is_recent:
                if is_buy:  buys_30d  += 1
                if is_sell: sells_30d += 1

            import numpy as np
            transactions.append({
                "date":        str(date_s)[:10],
                "insider":     insider,
                "title":       title,
                "transaction": txn,
                "shares":      int(shares) if shares and not pd.isna(shares) else None,
                "value":       int(value)  if value  and not pd.isna(value)  else None,
                "is_buy":      is_buy,
                "is_sell":     is_sell,
                "is_recent":   is_recent,
            })

        cluster_buy  = buys_30d  >= 3
        cluster_sell = sells_30d >= 3

        if cluster_buy:
            signal  = "bullish"
            message = (
                f"{buys_30d} insiders purchased shares in the last 30 days. "
                "Cluster buying is the strongest insider signal — insiders only buy for one reason. "
                "This cannot be explained by taxes, diversification, or mechanical plans."
            )
        elif cluster_sell:
            signal  = "bearish"
            message = (
                f"{sells_30d} insiders sold shares in the last 30 days. "
                "Cluster selling warrants caution — although insider sales often have personal reasons, "
                "simultaneous selling by multiple executives signals they see limited upside ahead."
            )
        elif buys_30d > 0:
            signal  = "bullish"
            message = f"{buys_30d} insider purchase(s) in the last 30 days. Positive but not yet cluster conviction."
        elif sells_30d > 0:
            signal  = "neutral"
            message = f"{sells_30d} insider sale(s) in the last 30 days. Isolated sales are normal — watch for cluster patterns."
        else:
            signal  = "neutral"
            message = "No insider trades in the last 30 days."

        return {
            "signal":        signal,
            "message":       message,
            "buys_30d":      buys_30d,
            "sells_30d":     sells_30d,
            "cluster_buy":   cluster_buy,
            "cluster_sell":  cluster_sell,
            "transactions":  transactions[:15],
        }

    except Exception as e:
        return {"signal": "neutral", "message": str(e), "transactions": [], "cluster_buy": False, "cluster_sell": False}


def get_activist_filings(ticker: str) -> list[dict]:
    """
    Search EDGAR for recent Schedule 13D and 13G filings mentioning this ticker.
    13D = activist (intent to influence) — immediate hard catalyst.
    13G = passive holder crossing 5% — confirms institutional accumulation.
    """
    try:
        since = (datetime.now() - timedelta(days=180)).strftime("%Y-%m-%d")
        url = (
            "https://efts.sec.gov/LATEST/search-index?"
            f"q=%22{ticker}%22"
            "&forms=SC+13D,SC+13G,SC+13D%2FA,SC+13G%2FA"
            f"&dateRange=custom&startdt={since}&enddt={datetime.now().strftime('%Y-%m-%d')}"
        )
        r = _SESSION.get(url, timeout=15)
        r.raise_for_status()
        hits = r.json().get("hits", {}).get("hits", [])

        results = []
        for h in hits[:10]:
            src  = h.get("_source", {})
            form = src.get("form_type", "")
            is_activist = "13D" in form and "/A" not in form
            results.append({
                "form":        form,
                "filing_date": src.get("file_date", ""),
                "filer":       src.get("entity_name", ""),
                "is_activist": is_activist,
                "signal":      "bullish" if "13D" in form else "neutral",
                "interpretation": (
                    "ACTIVIST ENTRY — filer intends to influence management. "
                    "Historically precedes buybacks, spin-offs, CEO changes, or M&A." if is_activist
                    else "Passive holder crossed 5% threshold. Large institutional accumulation confirmed."
                ),
            })
        return results
    except Exception:
        return []
