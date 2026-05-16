from fastapi import APIRouter, Query
from typing import Optional

from ..services.news import (
    fetch_market_news,
    fetch_intelligence,
    fetch_stock_news,
    fetch_ticker_intelligence,
)

router = APIRouter(prefix="/api/news", tags=["news"])


@router.get("")
def market_news(limit: int = Query(30, ge=5, le=60)):
    """Legacy simple feed — kept for back-compat with the old News page."""
    return fetch_market_news(limit=limit)


@router.get("/intelligence")
def intelligence(
    limit: int = Query(60, ge=5, le=200),
    min_confidence: int = Query(0, ge=0, le=100),
    event_type: Optional[str] = Query(None, description="Filter by event type, e.g. 'Earnings'"),
):
    """Full News & Market Impact Intelligence payload."""
    return fetch_intelligence(
        limit=limit,
        min_confidence=min_confidence,
        event_type=event_type,
    )


@router.get("/ticker/{ticker}")
def ticker_news(ticker: str, limit: int = Query(15, ge=5, le=40)):
    """Per-ticker enriched news (Yahoo + Google News + intelligence layer)."""
    return fetch_ticker_intelligence(ticker, limit=limit)


@router.get("/stock/{ticker}")
def stock_news(ticker: str, limit: int = Query(12, ge=5, le=30)):
    """Legacy lightweight per-ticker feed."""
    return fetch_stock_news(ticker, limit=limit)
