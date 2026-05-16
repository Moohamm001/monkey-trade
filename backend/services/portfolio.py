"""
Virtual $10,000 portfolio — automated capital allocation.

Every bot trade gets dollar-sized using quarter-Kelly, capped at 20% of
available cash.  Positions are opened/closed atomically so the cash balance
stays consistent.  An equity snapshot is appended once per daily-review run.

All state mutations go through storage.transaction() — a locked
read-modify-write with atomic disk write. Two threads opening positions
simultaneously can no longer race the cash balance out of sync.
"""
from __future__ import annotations

import os
from datetime import date, datetime
from typing import Optional

from . import storage

PORTFOLIO_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "portfolio.json")

MAX_POSITION_PCT  = 0.20   # never more than 20 % of cash per trade
MIN_TRADE_DOLLAR  = 100.0  # don't bother with tiny positions
MAX_OPEN_POSITIONS = 6


# ── persistence ───────────────────────────────────────────────────────────────

def _default_portfolio() -> dict:
    return {
        "initial_balance":  10000.0,
        "cash":             10000.0,
        "open_positions":   {},
        "equity_curve":     [{"date": str(date.today()), "equity": 10000.0,
                              "cash": 10000.0, "positions_value": 0.0}],
        "stats": {
            "total_trades": 0, "wins": 0, "losses": 0,
            "total_pnl_dollar": 0.0, "total_pnl_pct": 0.0,
            "best_trade_pct": None, "worst_trade_pct": None,
        },
        "trade_history": [],
    }


def load_portfolio() -> dict:
    """Read-only snapshot. Use storage.transaction() for mutations."""
    p = storage.safe_load_json(PORTFOLIO_PATH, None)
    if p is None:
        p = _default_portfolio()
        storage.atomic_write_json(PORTFOLIO_PATH, p)
    return p


def save_portfolio(p: dict):
    """Direct save with lock (for one-shot resets / external overrides)."""
    with storage.locked(PORTFOLIO_PATH):
        storage.atomic_write_json(PORTFOLIO_PATH, p)


# ── position management ───────────────────────────────────────────────────────

def open_position(
    trade_id: str,
    ticker: str,
    entry_price: float,
    stage: str,
    direction: str,
    kelly_frac: float,
) -> Optional[dict]:
    """
    Allocate capital for a new bot trade.
    Returns the position dict, or None if the portfolio can't accept the trade
    (insufficient cash, too many open positions).

    Cash decrement + position record are committed atomically.
    """
    with storage.transaction(PORTFOLIO_PATH, _default_portfolio()) as p:
        if len(p["open_positions"]) >= MAX_OPEN_POSITIONS:
            return None

        cash = p["cash"]
        alloc_pct = min(kelly_frac, MAX_POSITION_PCT)
        position_dollar = cash * alloc_pct

        if position_dollar < MIN_TRADE_DOLLAR:
            # Try a flat minimum if there's enough cash
            if cash >= MIN_TRADE_DOLLAR:
                position_dollar = MIN_TRADE_DOLLAR
            else:
                return None  # portfolio exhausted

        position_dollar = round(position_dollar, 2)
        shares = round(position_dollar / entry_price, 6)  # fractional shares

        position = {
            "trade_id":       trade_id,
            "ticker":         ticker,
            "stage":          stage,
            "direction":      direction,
            "entry_price":    round(entry_price, 4),
            "shares":         shares,
            "cost_basis":     position_dollar,
            "opened_at":      datetime.now().isoformat(),
        }

        p["open_positions"][trade_id] = position
        p["cash"] = round(cash - position_dollar, 2)
        return position


def close_position(trade_id: str, exit_price: float, outcome: str) -> Optional[dict]:
    """
    Close an open position, return cash, and record in trade_history.
    outcome: 'win' | 'loss' | 'neutral'
    Returns the closed position dict (with pnl fields), or None if not found.

    Cash credit + position removal + stats update are committed atomically.
    """
    with storage.transaction(PORTFOLIO_PATH, _default_portfolio()) as p:
        pos = p["open_positions"].pop(trade_id, None)
        if pos is None:
            return None

        entry_price  = pos["entry_price"]
        shares       = pos["shares"]
        cost_basis   = pos["cost_basis"]
        direction    = pos.get("direction", "long")

        exit_value = round(shares * exit_price, 2)

        if direction == "long":
            pnl_dollar = round(exit_value - cost_basis, 2)
        else:
            pnl_dollar = round(cost_basis - exit_value, 2)

        pnl_pct = round(pnl_dollar / cost_basis * 100, 2) if cost_basis else 0.0

        p["cash"] = round(p["cash"] + cost_basis + pnl_dollar, 2)

        stats = p["stats"]
        stats["total_trades"] += 1
        if outcome == "win":
            stats["wins"] += 1
        else:
            stats["losses"] += 1
        stats["total_pnl_dollar"] = round(stats["total_pnl_dollar"] + pnl_dollar, 2)
        initial = p["initial_balance"]
        equity  = _equity_from(p)
        stats["total_pnl_pct"] = round((equity - initial) / initial * 100, 2)
        if stats["best_trade_pct"] is None or pnl_pct > stats["best_trade_pct"]:
            stats["best_trade_pct"] = pnl_pct
        if stats["worst_trade_pct"] is None or pnl_pct < stats["worst_trade_pct"]:
            stats["worst_trade_pct"] = pnl_pct

        closed = {**pos, "exit_price": exit_price, "exit_value": exit_value,
                  "pnl_dollar": pnl_dollar, "pnl_pct": pnl_pct,
                  "outcome": outcome, "closed_at": datetime.now().isoformat()}
        p["trade_history"].insert(0, closed)

        return closed


# ── equity tracking ───────────────────────────────────────────────────────────

def _equity_from(p: dict) -> float:
    """Total equity from a portfolio dict already in hand."""
    positions_value = sum(
        pos["shares"] * pos["entry_price"]
        for pos in p["open_positions"].values()
    )
    return round(p["cash"] + positions_value, 2)


def get_equity(p: Optional[dict] = None) -> float:
    """Total equity = cash + market value of all open positions."""
    if p is None:
        p = load_portfolio()
    return _equity_from(p)


def snapshot_equity(live_prices: Optional[dict] = None):
    """
    Append today's equity snapshot to the curve.
    live_prices: {ticker: price} — if provided, use live prices for positions.
    Called once per daily_review.
    """
    live_prices = live_prices or {}

    with storage.transaction(PORTFOLIO_PATH, _default_portfolio()) as p:
        positions_value = 0.0
        for pos in p["open_positions"].values():
            price = live_prices.get(pos["ticker"], pos["entry_price"])
            positions_value += pos["shares"] * price

        equity = round(p["cash"] + positions_value, 2)
        today  = str(date.today())

        # Update today's entry if it already exists, else append
        curve = p["equity_curve"]
        if curve and curve[-1]["date"] == today:
            curve[-1] = {"date": today, "equity": equity,
                         "cash": p["cash"], "positions_value": round(positions_value, 2)}
        else:
            curve.append({"date": today, "equity": equity,
                          "cash": p["cash"], "positions_value": round(positions_value, 2)})

        return equity


def get_summary() -> dict:
    p = load_portfolio()
    equity = _equity_from(p)
    initial = p["initial_balance"]
    open_pos = [
        {
            "trade_id":   tid,
            "ticker":     pos["ticker"],
            "stage":      pos["stage"],
            "direction":  pos["direction"],
            "cost_basis": pos["cost_basis"],
            "shares":     pos["shares"],
            "entry_price": pos["entry_price"],
        }
        for tid, pos in p["open_positions"].items()
    ]
    return {
        "initial_balance":   initial,
        "cash":              p["cash"],
        "equity":            equity,
        "positions_value":   round(equity - p["cash"], 2),
        "total_return_pct":  round((equity - initial) / initial * 100, 2),
        "open_positions":    open_pos,
        "open_count":        len(open_pos),
        "equity_curve":      p["equity_curve"],
        "stats":             p["stats"],
        "recent_trades":     p["trade_history"][:20],
    }
