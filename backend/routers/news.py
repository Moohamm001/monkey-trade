from fastapi import APIRouter, Query
from ..services.news import fetch_market_news

router = APIRouter(prefix="/api/news", tags=["news"])


@router.get("")
def market_news(limit: int = Query(30, ge=5, le=60)):
    return fetch_market_news(limit=limit)
