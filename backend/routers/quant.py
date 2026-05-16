"""
Quant Engine Router — Jim Simons / Renaissance Mathematics.

Endpoints:
  GET /api/quant/{ticker}/hmm          — Hidden Markov Model regime
  GET /api/quant/{ticker}/mean-revert  — Ornstein-Uhlenbeck + ADF + z-score
  GET /api/quant/{ticker}/kalman       — Kalman filter trend estimation
  GET /api/quant/{ticker}/signal-quality — IC table, Ljung-Box, Hurst exponent
  GET /api/quant/{ticker}/kelly        — Kelly criterion position sizing
  GET /api/quant/{ticker}/full         — All five models in one call
"""
from fastapi import APIRouter, HTTPException, Query
import yfinance as yf

from ..services.hidden_markov  import detect_hmm_regime
from ..services.mean_reversion import get_mean_reversion_analysis
from ..services.kalman_filter  import get_kalman_analysis
from ..services.signal_quality import get_full_signal_quality
from ..services.kelly          import get_kelly_analysis

router = APIRouter(prefix="/api/quant", tags=["quant"])


def _fetch(ticker: str, period: str = "2y") -> object:
    df = yf.download(ticker, period=period, auto_adjust=True, progress=False)
    if df is None or len(df) < 30:
        raise HTTPException(404, f"No data for {ticker}")
    df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]
    return df


@router.get("/{ticker}/hmm")
def hmm_regime(ticker: str, period: str = Query("2y", description="yfinance period string")):
    """4-state Hidden Markov Model regime detection with transition matrix."""
    try:
        df = _fetch(ticker.upper(), period)
        return detect_hmm_regime(df)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))


@router.get("/{ticker}/mean-revert")
def mean_reversion(
    ticker: str,
    period: str  = Query("2y"),
    window: int  = Query(20, ge=5, le=120, description="Rolling z-score window (days)"),
):
    """Ornstein-Uhlenbeck parameters, ADF stationarity test, and z-score signal."""
    try:
        df = _fetch(ticker.upper(), period)
        return get_mean_reversion_analysis(df, window=window)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))


@router.get("/{ticker}/kalman")
def kalman_trend(ticker: str, period: str = Query("1y")):
    """Kalman filter: smoothed price, trend velocity, and 1σ uncertainty band."""
    try:
        df = _fetch(ticker.upper(), period)
        return get_kalman_analysis(df)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))


@router.get("/{ticker}/signal-quality")
def signal_quality(ticker: str, period: str = Query("3y")):
    """IC table for all 8 Wyckoff signals, Ljung-Box autocorrelation, Hurst exponent."""
    try:
        df = _fetch(ticker.upper(), period)
        return get_full_signal_quality(df)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))


@router.get("/{ticker}/kelly")
def kelly_sizing(ticker: str, period: str = Query("3y")):
    """Kelly Criterion: continuous (Sharpe-based) + per-stage discrete Kelly backtest."""
    try:
        df = _fetch(ticker.upper(), period)
        return get_kelly_analysis(df)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))


@router.get("/{ticker}/full")
def full_quant(ticker: str, period: str = Query("3y")):
    """All five Jim Simons models in a single call (slower — fetches once, runs all)."""
    try:
        df      = _fetch(ticker.upper(), period)
        df_1y   = df.iloc[-252:]  # Kalman only needs 1y

        hmm   = detect_hmm_regime(df)
        mr    = get_mean_reversion_analysis(df)
        kf    = get_kalman_analysis(df_1y)
        sq    = get_full_signal_quality(df)
        kelly = get_kelly_analysis(df)

        return {
            "ticker":         ticker.upper(),
            "hmm":            hmm,
            "mean_reversion": mr,
            "kalman":         kf,
            "signal_quality": sq,
            "kelly":          kelly,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))
