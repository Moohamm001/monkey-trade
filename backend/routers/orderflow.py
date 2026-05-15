from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from pydantic import BaseModel

from ..services.data_pipeline import DB_PATH, TickPipeline, init_db
from ..services.flow_classifier import build_features, predict_flow, train_classifier
from ..services.footprint import calc_vpvr, get_orderbook_snapshot, get_ticks, build_footprint
from ..services.regime_detector import detect_regime
from ..services.risk_manager import InstitutionalRiskManager
from ..services.stock_data import get_price_history
from ..services.trigger_engine import TriggerEngine

router = APIRouter(prefix="/api/orderflow", tags=["orderflow"])

# ── Singletons (in-memory; production: Redis / DB-backed) ────────────────────
_risk_manager: Optional[InstitutionalRiskManager] = None
_pipeline:     Optional[TickPipeline]             = None
_svm_pipeline                                     = None
_trigger_engine                                   = TriggerEngine()


# ─────────────────────────────────────────────────────────────────────────────
# Market Regime (K-Means)
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/regime/{ticker}")
def get_regime(
    ticker: str,
    period: str = Query("1y", enum=["6mo", "1y", "2y"]),
):
    try:
        df = get_price_history(ticker.upper(), period=period)
        if df.empty:
            raise HTTPException(404, "No price data found")
        return detect_regime(df)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))


# ─────────────────────────────────────────────────────────────────────────────
# Footprint Chart & VPVR  (requires active TickPipeline)
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/footprint/{symbol}")
async def get_footprint(
    symbol:         str,
    minutes:        int   = Query(60,  ge=5,   le=480),
    candle_minutes: int   = Query(5,   ge=1,   le=60),
    tick_size:      float = Query(1.0, gt=0.0),
):
    try:
        df = await get_ticks(symbol.upper(), minutes=minutes)
        if df.empty:
            return {
                "candles":   [],
                "vpvr":      {},
                "tick_count": 0,
                "message":   "No tick data — start the pipeline first: POST /api/orderflow/pipeline/start/{symbol}",
            }
        return {
            "candles":    build_footprint(df, candle_minutes=candle_minutes, tick_size=tick_size),
            "vpvr":       calc_vpvr(df, tick_size=tick_size),
            "orderbook":  await get_orderbook_snapshot(symbol.upper()),
            "tick_count": len(df),
        }
    except Exception as e:
        raise HTTPException(500, str(e))


@router.get("/vpvr/{symbol}")
async def get_vpvr(
    symbol:    str,
    minutes:   int   = Query(60, ge=5, le=480),
    tick_size: float = Query(1.0, gt=0.0),
):
    try:
        df = await get_ticks(symbol.upper(), minutes=minutes)
        if df.empty:
            return {"vpvr": {}, "message": "No tick data"}
        return calc_vpvr(df, tick_size=tick_size)
    except Exception as e:
        raise HTTPException(500, str(e))


# ─────────────────────────────────────────────────────────────────────────────
# SVM Flow Classifier
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/train-classifier/{symbol}")
async def train_flow_classifier(symbol: str):
    global _svm_pipeline
    try:
        df = await get_ticks(symbol.upper(), minutes=240)
        if df.empty:
            return {"status": "no_data", "error": "Start the pipeline first to collect tick data"}
        feat_df  = build_features(df)
        pipeline, metrics = train_classifier(feat_df)
        if pipeline:
            _svm_pipeline = pipeline
        return {"status": "trained" if pipeline else "failed", "metrics": metrics}
    except Exception as e:
        raise HTTPException(500, str(e))


class PredictRequest(BaseModel):
    vol_delta_norm: float
    avg_trade_size: float
    n_trades:       int
    close_vs_vwap:  float
    buy_ratio:      float

@router.post("/predict-flow")
def predict_current_flow(body: PredictRequest):
    if not _svm_pipeline:
        raise HTTPException(400, "No trained classifier — POST /train-classifier/{symbol} first")
    return predict_flow(_svm_pipeline, body.model_dump())


# ─────────────────────────────────────────────────────────────────────────────
# Risk Manager
# ─────────────────────────────────────────────────────────────────────────────

class RiskInitBody(BaseModel):
    account_balance: float

@router.post("/risk/init")
def init_risk_manager(body: RiskInitBody):
    global _risk_manager
    _risk_manager = InstitutionalRiskManager(body.account_balance)
    return {"status": "initialized", "balance": body.account_balance}

@router.get("/risk/status")
def risk_status():
    if not _risk_manager:
        raise HTTPException(400, "Risk manager not initialized — POST /api/orderflow/risk/init first")
    return _risk_manager.status()

class SizeRequest(BaseModel):
    atr:            float
    risk_pct:       float = 0.01
    atr_multiplier: float = 2.0

@router.post("/risk/position-size")
def calc_position_size(body: SizeRequest):
    if not _risk_manager:
        raise HTTPException(400, "Risk manager not initialized")
    return _risk_manager.calc_position_size(body.atr, body.risk_pct, body.atr_multiplier)

class AddPositionBody(BaseModel):
    symbol:    str
    entry:     float
    quantity:  float
    stop_loss: float

@router.post("/risk/add-position")
def add_position(body: AddPositionBody):
    if not _risk_manager:
        raise HTTPException(400, "Risk manager not initialized")
    try:
        _risk_manager.add_position(body.symbol, body.entry, body.quantity, body.stop_loss)
        return {"status": "added", **body.model_dump()}
    except RuntimeError as e:
        raise HTTPException(400, str(e))

class UpdatePriceBody(BaseModel):
    symbol: str
    price:  float

@router.post("/risk/update-price")
def update_price(body: UpdatePriceBody):
    if not _risk_manager:
        raise HTTPException(400, "Risk manager not initialized")
    _risk_manager.update_price(body.symbol, body.price)
    return _risk_manager.status()

@router.post("/risk/reset-daily")
def reset_daily():
    if not _risk_manager:
        raise HTTPException(400, "Risk manager not initialized")
    _risk_manager.reset_daily()
    return {"status": "reset", **_risk_manager.status()}


# ─────────────────────────────────────────────────────────────────────────────
# Trigger Engine
# ─────────────────────────────────────────────────────────────────────────────

class TriggerRequest(BaseModel):
    current_price:  float
    poc:            float
    volume_delta:   float
    svm_signal:     int   = 0
    svm_confidence: float = 0.0

@router.post("/trigger/evaluate")
def evaluate_trigger(body: TriggerRequest):
    result = _trigger_engine.evaluate(
        current_price  = body.current_price,
        poc            = body.poc,
        volume_delta   = body.volume_delta,
        svm_signal     = body.svm_signal,
        svm_confidence = body.svm_confidence,
    )
    return result.to_dict()


# ─────────────────────────────────────────────────────────────────────────────
# Data Pipeline Control
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/pipeline/start/{symbol}")
async def start_pipeline(symbol: str, background_tasks: BackgroundTasks):
    global _pipeline
    await init_db()
    if _pipeline and _pipeline._running:
        return {"status": "already_running", "symbol": _pipeline.symbol}
    _pipeline = TickPipeline(symbol.upper())
    background_tasks.add_task(_pipeline.start)
    return {
        "status":  "started",
        "symbol":  symbol.upper(),
        "streams": ["aggTrade", "depth5@100ms"],
        "db_path": str(DB_PATH),
    }

@router.post("/pipeline/stop")
def stop_pipeline():
    global _pipeline
    if _pipeline:
        _pipeline.stop()
        return {"status": "stopped", "symbol": _pipeline.symbol}
    return {"status": "not_running"}

@router.get("/pipeline/status")
def pipeline_status():
    return {
        "running":     bool(_pipeline and _pipeline._running),
        "symbol":      _pipeline.symbol if _pipeline else None,
        "db_path":     str(DB_PATH),
        "db_exists":   DB_PATH.exists(),
        "svm_trained": _svm_pipeline is not None,
        "risk_initialized": _risk_manager is not None,
    }
