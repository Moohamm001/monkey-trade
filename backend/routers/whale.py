from fastapi import APIRouter, HTTPException, Query

from ..services.smart_money    import get_whale_intelligence
from ..services.sec_edgar      import get_insider_summary, get_activist_filings
from ..services.dark_pool      import get_dark_pool_metrics
from ..services.options_flow   import get_full_options_analysis
from ..services.congress_trades import get_congress_trades
from ..services.cot_report     import get_cot_signal, INSTRUMENTS

router = APIRouter(prefix="/api/whale", tags=["whale"])


@router.get("/{ticker}")
def whale_intelligence(ticker: str):
    """Full whale intelligence package — all sources + smart money score."""
    try:
        return get_whale_intelligence(ticker.upper())
    except Exception as e:
        raise HTTPException(500, str(e))


@router.get("/{ticker}/score")
def whale_score(ticker: str):
    """Smart money score only (fast)."""
    try:
        data = get_whale_intelligence(ticker.upper())
        return {
            "ticker": ticker.upper(),
            "score":  data["score"],
            "rating": data["rating"],
            "rating_color": data["rating_color"],
            "summary": data["summary"],
            "signal_count": data["signal_count"],
        }
    except Exception as e:
        raise HTTPException(500, str(e))


@router.get("/{ticker}/insider")
def insider_data(ticker: str):
    """SEC Form 4 insider transactions + 13D/G activist filings."""
    try:
        return {
            "summary":   get_insider_summary(ticker.upper()),
            "activist":  get_activist_filings(ticker.upper()),
        }
    except Exception as e:
        raise HTTPException(500, str(e))


@router.get("/{ticker}/darkpool")
def dark_pool_data(ticker: str, days: int = Query(10, ge=3, le=30)):
    """FINRA dark pool / off-exchange volume metrics."""
    try:
        return get_dark_pool_metrics(ticker.upper(), lookback_days=days)
    except Exception as e:
        raise HTTPException(500, str(e))


@router.get("/{ticker}/options-flow")
def options_flow_data(ticker: str):
    """Enhanced multi-expiry options flow: unusual activity, expected move, IV skew, deep ITM calls."""
    try:
        return get_full_options_analysis(ticker.upper())
    except Exception as e:
        raise HTTPException(500, str(e))


@router.get("/{ticker}/congress")
def congress_data(ticker: str, days: int = Query(365, ge=30, le=730)):
    """Congressional stock trading disclosures (House + Senate)."""
    try:
        return get_congress_trades(ticker.upper(), lookback_days=days)
    except Exception as e:
        raise HTTPException(500, str(e))


@router.get("/cot/{instrument}")
def cot_data(instrument: str):
    """CFTC Commitment of Traders for a futures instrument."""
    inst = instrument.upper()
    if inst not in INSTRUMENTS:
        raise HTTPException(400, f"Unknown instrument. Available: {list(INSTRUMENTS.keys())}")
    try:
        return get_cot_signal(inst)
    except Exception as e:
        raise HTTPException(500, str(e))
