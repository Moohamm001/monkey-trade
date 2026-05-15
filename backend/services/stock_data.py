import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Optional


def get_stock_info(ticker: str) -> dict:
    t = yf.Ticker(ticker)
    info = t.info
    return {
        "symbol": ticker.upper(),
        "name": info.get("longName", ticker),
        "sector": info.get("sector", "N/A"),
        "industry": info.get("industry", "N/A"),
        "market_cap": info.get("marketCap"),
        "pe_ratio": info.get("trailingPE"),
        "forward_pe": info.get("forwardPE"),
        "price": info.get("currentPrice") or info.get("regularMarketPrice"),
        "52w_high": info.get("fiftyTwoWeekHigh"),
        "52w_low": info.get("fiftyTwoWeekLow"),
        "avg_volume": info.get("averageVolume"),
        "dividend_yield": info.get("dividendYield"),
        "revenue_growth": info.get("revenueGrowth"),
        "earnings_growth": info.get("earningsGrowth"),
        "gross_margins": info.get("grossMargins"),
        "operating_margins": info.get("operatingMargins"),
        "net_margins": info.get("profitMargins"),
        "return_on_equity": info.get("returnOnEquity"),
        "debt_to_equity": info.get("debtToEquity"),
        "free_cashflow": info.get("freeCashflow"),
        "currency": info.get("currency", "USD"),
        "exchange": info.get("exchange", ""),
    }


def get_price_history(ticker: str, period: str = "1y", interval: str = "1d") -> pd.DataFrame:
    t = yf.Ticker(ticker)
    df = t.history(period=period, interval=interval)
    df.index = pd.to_datetime(df.index)
    df.index = df.index.tz_localize(None)
    return df


def get_financials(ticker: str) -> dict:
    t = yf.Ticker(ticker)
    result = {}

    try:
        inc = t.financials
        if not inc.empty:
            rows = {}
            for col in inc.columns[:4]:  # last 4 years
                year = str(col.year) if hasattr(col, "year") else str(col)
                rows[year] = {
                    "revenue": float(inc.loc["Total Revenue", col]) if "Total Revenue" in inc.index else None,
                    "gross_profit": float(inc.loc["Gross Profit", col]) if "Gross Profit" in inc.index else None,
                    "operating_income": float(inc.loc["Operating Income", col]) if "Operating Income" in inc.index else None,
                    "net_income": float(inc.loc["Net Income", col]) if "Net Income" in inc.index else None,
                }
            result["annual"] = rows
    except Exception:
        result["annual"] = {}

    try:
        qinc = t.quarterly_financials
        if not qinc.empty:
            rows = {}
            for col in qinc.columns[:4]:
                label = col.strftime("Q%q %Y") if hasattr(col, "strftime") else str(col)
                rows[label] = {
                    "revenue": float(qinc.loc["Total Revenue", col]) if "Total Revenue" in qinc.index else None,
                    "gross_profit": float(qinc.loc["Gross Profit", col]) if "Gross Profit" in qinc.index else None,
                    "operating_income": float(qinc.loc["Operating Income", col]) if "Operating Income" in qinc.index else None,
                    "net_income": float(qinc.loc["Net Income", col]) if "Net Income" in qinc.index else None,
                }
            result["quarterly"] = rows
    except Exception:
        result["quarterly"] = {}

    return result
