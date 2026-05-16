"""
Dark Pool & Off-Exchange Volume Intelligence (FINRA ATS Data).

Source: FINRA Equity Short Interest / Short Sale Volume
  https://cdn.finra.org/equity/regsho/daily/CNMSshvol{YYYYMMDD}.txt

Why dark pools matter:
  ~35-45% of all US equity volume trades off-exchange (dark pools, ATSs, internalizers).
  Retail orders are almost never routed to dark pools — they lack the size.
  When dark pool volume for a stock spikes above its baseline, it means institutions
  are executing large blocks away from lit exchanges to avoid revealing their intent.

  FINRA's Reg SHO short-sale volume data is the best free proxy:
  Most dark pool trades are reported as "short" for regulatory tracking purposes
  even when they represent actual equity purchases (the counterparty hedges with
  a short, but the economic effect is a purchase). High short-volume % with stable
  or rising price = institutional accumulation in the dark.

Reading the signal:
  Dark pool % > 50% + price flat/rising  = stealth accumulation
  Dark pool % > 50% + price falling      = distribution (or genuine shorts)
  Dark pool % < 25%                      = low institutional interest
  Dark pool % spiking vs 10-day avg      = sudden institutional activity

FINRA file format (pipe-delimited):
  Date|Symbol|ShortVolume|ShortExemptVolume|TotalVolume|Market
"""
from __future__ import annotations

import io
from datetime import date, datetime, timedelta
from functools import lru_cache
from typing import Optional

import pandas as pd
import requests

_SESSION = requests.Session()
_SESSION.headers.update({"User-Agent": "MonkeyTrade research@monkeytrade.app"})

_BASE_URL = "https://cdn.finra.org/equity/regsho/daily/CNMSshvol{date}.txt"


def _trading_days_back(n: int) -> list[date]:
    """Return the last *n* trading dates (Mon-Fri), excluding today."""
    days  = []
    check = datetime.now().date() - timedelta(days=1)
    while len(days) < n:
        if check.weekday() < 5:  # Mon=0 … Fri=4
            days.append(check)
        check -= timedelta(days=1)
    return days


@lru_cache(maxsize=10)
def _fetch_finra_day(day: date) -> Optional[pd.DataFrame]:
    """Download and parse one day of FINRA short-sale volume data."""
    url = _BASE_URL.format(date=day.strftime("%Y%m%d"))
    try:
        r = _SESSION.get(url, timeout=15)
        if r.status_code != 200:
            return None
        text = r.text
        # Strip trailing summary lines (start with "Date|")
        lines = [l for l in text.strip().split("\n") if "|" in l]
        df = pd.read_csv(io.StringIO("\n".join(lines)), sep="|")
        df.columns = [c.strip() for c in df.columns]
        return df
    except Exception:
        return None


def get_dark_pool_metrics(ticker: str, lookback_days: int = 10) -> dict:
    """
    Calculate dark pool / off-exchange metrics for *ticker* over the last
    *lookback_days* trading sessions.

    Returns:
      daily        — list of {date, short_volume, total_volume, dark_pct}
      avg_dark_pct — 10-day average dark pool percentage
      latest_dark_pct — most recent session
      spike        — True if latest > avg × 1.5 (sudden institutional activity)
      trend        — "increasing" | "decreasing" | "stable"
      signal       — "bullish" | "bearish" | "neutral"
      message      — plain-language interpretation
    """
    ticker = ticker.upper()
    days   = _trading_days_back(lookback_days + 2)  # buffer for missing files
    rows   = []

    for day in days:
        df = _fetch_finra_day(day)
        if df is None:
            continue
        match = df[df["Symbol"].str.upper() == ticker]
        if match.empty:
            continue
        row = match.iloc[0]
        try:
            short_vol = int(row.get("ShortVolume", 0))
            total_vol = int(row.get("TotalVolume", 1))
            dark_pct  = round(short_vol / total_vol * 100, 2) if total_vol > 0 else 0
            rows.append({
                "date":         day.strftime("%Y-%m-%d"),
                "short_volume": short_vol,
                "total_volume": total_vol,
                "dark_pct":     dark_pct,
            })
        except Exception:
            continue
        if len(rows) >= lookback_days:
            break

    if not rows:
        return {
            "daily":            [],
            "avg_dark_pct":     None,
            "latest_dark_pct":  None,
            "spike":            False,
            "trend":            "unknown",
            "signal":           "neutral",
            "message":          "No FINRA dark pool data available for this ticker.",
        }

    rows_sorted      = sorted(rows, key=lambda x: x["date"])
    avg_dark         = round(sum(r["dark_pct"] for r in rows_sorted) / len(rows_sorted), 2)
    latest_dark      = rows_sorted[-1]["dark_pct"]
    spike            = latest_dark > avg_dark * 1.5 and latest_dark > 40

    # Trend: compare first half vs second half average
    half    = max(1, len(rows_sorted) // 2)
    first_h = sum(r["dark_pct"] for r in rows_sorted[:half]) / half
    second_h= sum(r["dark_pct"] for r in rows_sorted[half:]) / max(1, len(rows_sorted) - half)
    if second_h > first_h * 1.1:
        trend = "increasing"
    elif second_h < first_h * 0.9:
        trend = "decreasing"
    else:
        trend = "stable"

    # Signal
    if latest_dark > 50 and trend == "increasing":
        signal  = "bullish"
        message = (
            f"Dark pool volume is {latest_dark:.1f}% of total (10-day avg: {avg_dark:.1f}%) "
            "and rising. Institutions are executing large blocks off-exchange at an accelerating rate. "
            "High dark pool % with stable/rising price = stealth accumulation. "
            "They are hiding their buy orders from the lit market to prevent price impact."
        )
    elif latest_dark > 50 and trend == "stable":
        signal  = "bullish"
        message = (
            f"Dark pool volume is consistently high at {latest_dark:.1f}% (10-day avg: {avg_dark:.1f}%). "
            "Sustained institutional off-exchange activity. Large players are accumulating without "
            "moving the tape — classic quiet accumulation before a breakout."
        )
    elif spike:
        signal  = "bullish"
        message = (
            f"Dark pool volume spiked to {latest_dark:.1f}% vs {avg_dark:.1f}% average — "
            f"{latest_dark/avg_dark:.1f}× the baseline. A sudden surge in off-exchange activity "
            "usually precedes a directional move within 1–3 sessions."
        )
    elif latest_dark < 25:
        signal  = "neutral"
        message = (
            f"Dark pool activity is low at {latest_dark:.1f}%. Institutional interest is limited. "
            "Most volume is retail-driven through lit exchanges. "
            "Without institutional participation, sustainable trends are unlikely."
        )
    elif trend == "decreasing":
        signal  = "bearish"
        message = (
            f"Dark pool volume is declining ({latest_dark:.1f}%, down from {avg_dark:.1f}% avg). "
            "Institutions are withdrawing — they are no longer accumulating in the dark. "
            "Watch for price weakness as the institutional bid disappears."
        )
    else:
        signal  = "neutral"
        message = (
            f"Dark pool volume at {latest_dark:.1f}% (10-day avg: {avg_dark:.1f}%). "
            "Normal off-exchange activity — no unusual institutional positioning detected."
        )

    return {
        "daily":            rows_sorted,
        "avg_dark_pct":     avg_dark,
        "latest_dark_pct":  latest_dark,
        "spike":            spike,
        "trend":            trend,
        "signal":           signal,
        "message":          message,
    }
