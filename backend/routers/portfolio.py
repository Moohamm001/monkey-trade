from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from ..services import portfolio as portfolio_svc

router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])


@router.get("/")
def get_portfolio():
    return portfolio_svc.get_summary()


@router.get("/equity-curve")
def equity_curve():
    p = portfolio_svc.load_portfolio()
    return p["equity_curve"]


@router.get("/positions")
def open_positions():
    p = portfolio_svc.load_portfolio()
    return list(p["open_positions"].values())


@router.get("/history")
def trade_history(limit: int = 50):
    p = portfolio_svc.load_portfolio()
    return p["trade_history"][:limit]


class ResetBody(BaseModel):
    balance: Optional[float] = 10000.0


@router.post("/reset")
def reset_portfolio(body: ResetBody):
    """Reset the virtual portfolio to a clean state."""
    from datetime import date
    p = {
        "initial_balance":  body.balance,
        "cash":             body.balance,
        "open_positions":   {},
        "equity_curve":     [{"date": str(date.today()), "equity": body.balance,
                              "cash": body.balance, "positions_value": 0.0}],
        "stats": {
            "total_trades": 0, "wins": 0, "losses": 0,
            "total_pnl_dollar": 0.0, "total_pnl_pct": 0.0,
            "best_trade_pct": None, "worst_trade_pct": None,
        },
        "trade_history": [],
    }
    portfolio_svc.save_portfolio(p)
    return {"ok": True, "balance": body.balance}
