from fastapi import APIRouter, HTTPException, Query
from ..services.stock_data import get_stock_info, get_price_history, get_financials
from ..services.cycle_detector import detect_cycle
from ..services.news import fetch_stock_news
from ..services.institutional import get_institutional_data

router = APIRouter(prefix="/api/stock", tags=["stock"])


@router.get("/{ticker}/info")
def stock_info(ticker: str):
    try:
        return get_stock_info(ticker.upper())
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/{ticker}/cycle")
def stock_cycle(ticker: str, period: str = Query("1y", enum=["6mo", "1y", "2y", "5y"])):
    try:
        df = get_price_history(ticker.upper(), period=period)
        if df.empty:
            raise HTTPException(status_code=404, detail="No price data found")
        result = detect_cycle(df)
        # Add OHLCV for chart
        chart = df[["Open", "High", "Low", "Close", "Volume"]].tail(200)
        chart.index = chart.index.strftime("%Y-%m-%d")
        result["chart"] = chart.reset_index().rename(columns={"index": "date"}).to_dict(orient="records")
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{ticker}/financials")
def stock_financials(ticker: str):
    try:
        return get_financials(ticker.upper())
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{ticker}/news")
def stock_news(ticker: str, limit: int = Query(10, ge=1, le=30)):
    return fetch_stock_news(ticker.upper(), limit=limit)


@router.get("/{ticker}/institutional")
def institutional(ticker: str):
    try:
        return get_institutional_data(ticker.upper())
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
