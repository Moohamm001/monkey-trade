from fastapi import APIRouter
from pydantic import BaseModel
from typing import List, Optional
from ..services.screener import screen_stocks, SP500_TICKERS, TOP100_TICKERS

router = APIRouter(prefix="/api/screener", tags=["screener"])


class ScreenerFilters(BaseModel):
    tickers: Optional[List[str]] = None
    universe: Optional[str] = "top100"   # "top100" | "sp500" | "custom"
    min_revenue_growth: Optional[float] = None
    min_earnings_growth: Optional[float] = None
    max_pe: Optional[float] = None
    min_market_cap: Optional[float] = None
    min_net_margin: Optional[float] = None
    sectors: Optional[List[str]] = None
    cycle_stages: Optional[List[str]] = None


@router.post("/run")
def run_screener(filters: ScreenerFilters):
    if filters.tickers:
        tickers = filters.tickers
    elif filters.universe == "sp500":
        tickers = SP500_TICKERS
    else:
        tickers = TOP100_TICKERS

    return screen_stocks(tickers, filters.model_dump(exclude={"tickers", "universe"}))


@router.get("/universes")
def get_universes():
    return {
        "top100": {"label": "Top 100 US Stocks", "count": len(TOP100_TICKERS)},
        "sp500":  {"label": "S&P 500 (~500 stocks)", "count": len(SP500_TICKERS)},
        "custom": {"label": "Custom Tickers", "count": 0},
    }
