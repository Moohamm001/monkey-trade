from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List
import os, uuid
from datetime import date, datetime

from ..services import storage

router = APIRouter(prefix="/api/forwardtest", tags=["forwardtest"])

STORE = os.path.join(os.path.dirname(__file__), "..", "forwardtest_data.json")


# ── persistence ────────────────────────────────────────────────────────────────
# All writes go through storage.transaction() — same lock key as autonomous_bot,
# so the forwardtest UI and the bot scanner can never clobber each other.

def _load() -> dict:
    return storage.safe_load_json(STORE, {"trades": []})


def _save(data: dict):
    with storage.locked(STORE):
        storage.atomic_write_json(STORE, data)


def _get_current_price(ticker: str) -> Optional[float]:
    try:
        import yfinance as yf
        t = yf.Ticker(ticker)
        info = t.fast_info
        return round(float(info.last_price), 4)
    except Exception:
        return None


def _enrich_trade(trade: dict) -> dict:
    """Attach live price, unrealized P&L, auto-close if stop/target hit."""
    if trade["status"] != "open":
        return trade

    price = _get_current_price(trade["ticker"])
    if price is None:
        return trade

    trade["current_price"] = price
    entry = trade["entry_price"]
    direction = trade.get("direction", "long")

    if direction == "long":
        raw_pct = (price - entry) / entry * 100
    else:
        raw_pct = (entry - price) / entry * 100

    trade["unrealized_pnl_pct"] = round(raw_pct, 2)
    trade["unrealized_pnl_dollar"] = round(
        raw_pct / 100 * entry * trade.get("shares", 1), 2
    )

    # Track max gain / max drawdown
    prev_max = trade.get("max_gain_pct", 0)
    prev_dd  = trade.get("max_drawdown_pct", 0)
    trade["max_gain_pct"]     = round(max(prev_max, raw_pct), 2)
    trade["max_drawdown_pct"] = round(min(prev_dd,  raw_pct), 2)

    # Days held
    try:
        entry_dt = datetime.strptime(trade["entry_date"][:10], "%Y-%m-%d").date()
        trade["days_held"] = (date.today() - entry_dt).days
    except Exception:
        trade["days_held"] = 0

    # Auto-close on stop or target
    sl = trade.get("stop_loss")
    tp = trade.get("target")

    if direction == "long":
        if sl and price <= sl:
            return _close_trade(trade, price, "stop_hit")
        if tp and price >= tp:
            return _close_trade(trade, price, "target_hit")
    else:
        if sl and price >= sl:
            return _close_trade(trade, price, "stop_hit")
        if tp and price <= tp:
            return _close_trade(trade, price, "target_hit")

    return trade


def _close_trade(trade: dict, exit_price: float, reason: str) -> dict:
    entry = trade["entry_price"]
    direction = trade.get("direction", "long")
    shares = trade.get("shares", 1)

    if direction == "long":
        pnl_pct = (exit_price - entry) / entry * 100
    else:
        pnl_pct = (entry - exit_price) / entry * 100

    trade["status"]      = "closed_win" if pnl_pct > 0 else "closed_loss"
    trade["exit_price"]  = round(exit_price, 4)
    trade["exit_date"]   = str(date.today())
    trade["exit_reason"] = reason
    trade["pnl_pct"]     = round(pnl_pct, 2)
    trade["pnl_dollar"]  = round(pnl_pct / 100 * entry * shares, 2)
    return trade


# ── models ─────────────────────────────────────────────────────────────────────

class TradeIn(BaseModel):
    ticker: str
    direction: str = "long"          # long | short
    entry_price: float
    shares: float = 1
    stop_loss: Optional[float] = None
    target: Optional[float] = None
    stage: Optional[str] = None      # accumulation | markup | distribution | markdown
    confidence: Optional[float] = None
    signals: Optional[List[str]] = []
    technique: Optional[str] = None
    notes: Optional[str] = ""


class CloseIn(BaseModel):
    exit_price: float
    exit_reason: str = "manual"      # manual | stop_hit | target_hit


class LessonIn(BaseModel):
    lesson: str
    rating: Optional[int] = None     # 1-5 self-rating of trade quality


# ── endpoints ──────────────────────────────────────────────────────────────────

@router.get("")
def list_trades():
    data = _load()
    enriched = [_enrich_trade(t) for t in data["trades"]]
    # Persist any auto-closes
    data["trades"] = enriched
    _save(data)
    return enriched


@router.post("")
def log_trade(body: TradeIn):
    data = _load()
    trade = {
        "id":           str(uuid.uuid4())[:8],
        "ticker":       body.ticker.upper(),
        "direction":    body.direction,
        "entry_price":  body.entry_price,
        "shares":       body.shares,
        "stop_loss":    body.stop_loss,
        "target":       body.target,
        "stage":        body.stage,
        "confidence":   body.confidence,
        "signals":      body.signals or [],
        "technique":    body.technique,
        "notes":        body.notes or "",
        "entry_date":   str(date.today()),
        "status":       "open",
        "current_price":      None,
        "unrealized_pnl_pct": None,
        "unrealized_pnl_dollar": None,
        "max_gain_pct":    0.0,
        "max_drawdown_pct":0.0,
        "days_held":       0,
        "exit_price":  None,
        "exit_date":   None,
        "exit_reason": None,
        "pnl_pct":     None,
        "pnl_dollar":  None,
        "lesson":      "",
        "rating":      None,
    }
    data["trades"].insert(0, trade)
    _save(data)
    return trade


@router.patch("/{trade_id}/close")
def close_trade(trade_id: str, body: CloseIn):
    data = _load()
    for t in data["trades"]:
        if t["id"] == trade_id:
            if t["status"] != "open":
                raise HTTPException(status_code=400, detail="Trade already closed")
            _close_trade(t, body.exit_price, body.exit_reason)
            _save(data)
            return t
    raise HTTPException(status_code=404, detail="Trade not found")


@router.patch("/{trade_id}/lesson")
def add_lesson(trade_id: str, body: LessonIn):
    data = _load()
    for t in data["trades"]:
        if t["id"] == trade_id:
            t["lesson"] = body.lesson
            if body.rating is not None:
                t["rating"] = body.rating
            _save(data)
            return t
    raise HTTPException(status_code=404, detail="Trade not found")


@router.delete("/{trade_id}")
def delete_trade(trade_id: str):
    data = _load()
    before = len(data["trades"])
    data["trades"] = [t for t in data["trades"] if t["id"] != trade_id]
    if len(data["trades"]) == before:
        raise HTTPException(status_code=404, detail="Trade not found")
    _save(data)
    return {"ok": True}


@router.get("/stats")
def get_stats():
    data = _load()
    trades = data["trades"]
    closed = [t for t in trades if t["status"] in ("closed_win", "closed_loss")]
    open_  = [t for t in trades if t["status"] == "open"]

    wins   = [t for t in closed if t["status"] == "closed_win"]
    losses = [t for t in closed if t["status"] == "closed_loss"]

    win_rate = round(len(wins) / len(closed) * 100, 1) if closed else 0
    avg_win  = round(sum(t["pnl_pct"] for t in wins)   / len(wins),   2) if wins   else 0
    avg_loss = round(sum(t["pnl_pct"] for t in losses)  / len(losses), 2) if losses else 0
    expectancy = round((win_rate/100 * avg_win) + ((1 - win_rate/100) * avg_loss), 2)

    # Win rate by stage
    stage_stats = {}
    for t in closed:
        s = t.get("stage") or "unknown"
        stage_stats.setdefault(s, {"wins": 0, "total": 0})
        stage_stats[s]["total"] += 1
        if t["status"] == "closed_win":
            stage_stats[s]["wins"] += 1
    for s, v in stage_stats.items():
        v["win_rate"] = round(v["wins"] / v["total"] * 100, 1)

    # Exit reason breakdown
    reasons = {}
    for t in closed:
        r = t.get("exit_reason", "manual")
        reasons[r] = reasons.get(r, 0) + 1

    # Equity curve (cumulative P&L %)
    equity = []
    cum = 0.0
    for t in sorted(closed, key=lambda x: x.get("exit_date", "")):
        cum += t["pnl_pct"] or 0
        equity.append({"date": t["exit_date"], "ticker": t["ticker"], "cumulative_pnl": round(cum, 2)})

    # Streak
    streak = 0
    streak_type = None
    for t in reversed(closed):
        st = "win" if t["status"] == "closed_win" else "loss"
        if streak_type is None:
            streak_type = st
        if st == streak_type:
            streak += 1
        else:
            break

    return {
        "total_trades":  len(trades),
        "open_trades":   len(open_),
        "closed_trades": len(closed),
        "wins":          len(wins),
        "losses":        len(losses),
        "win_rate":      win_rate,
        "avg_win_pct":   avg_win,
        "avg_loss_pct":  avg_loss,
        "expectancy":    expectancy,
        "stage_stats":   stage_stats,
        "exit_reasons":  reasons,
        "equity_curve":  equity,
        "current_streak": {"count": streak, "type": streak_type},
        "total_pnl_pct": round(sum(t["pnl_pct"] or 0 for t in closed), 2),
    }
