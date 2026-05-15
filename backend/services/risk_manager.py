"""
Phase 3 — Enterprise Risk Management & Kill Switch.

InstitutionalRiskManager enforces two rules:
  1. Volatility-adjusted position sizing:
       Size = (Balance × Risk%) / (ATR × Multiplier)
     This ensures dollar risk per trade is constant regardless of how much
     a stock moves — a volatile asset gets a smaller position.

  2. Portfolio Kill Switch:
     Tracks daily unrealised PnL across all open positions.
     If total equity drops more than KILL_SWITCH_THRESHOLD below the
     daily opening balance, ALL positions are immediately liquidated and
     further order entry is blocked until reset_daily() is called.
"""
from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Position:
    symbol:        str
    entry_price:   float
    quantity:      float
    stop_loss:     float
    current_price: float = field(default=0.0)

    @property
    def unrealized_pnl(self) -> float:
        return (self.current_price - self.entry_price) * self.quantity

    @property
    def unrealized_pnl_pct(self) -> float:
        return (self.current_price - self.entry_price) / (self.entry_price + 1e-9)


class InstitutionalRiskManager:
    KILL_SWITCH_THRESHOLD = -0.05   # −5% daily drawdown triggers halt
    DEFAULT_RISK_PCT      = 0.01    # 1% of account per trade
    DEFAULT_ATR_MULT      = 2.0     # stop = ATR × this multiplier
    MAX_POSITION_PCT      = 0.20    # never exceed 20% of account in one symbol

    def __init__(self, account_balance: float):
        self.account_balance     = float(account_balance)
        self.daily_start_balance = float(account_balance)
        self.positions: dict[str, Position] = {}
        self._halted             = False
        self._halt_reason        = ""
        self._lock               = threading.Lock()
        self._liquidation_log: list[dict] = []

    # ── Position sizing ───────────────────────────────────────────────────────

    def calc_position_size(
        self,
        atr:             float,
        risk_pct:        Optional[float] = None,
        atr_multiplier:  Optional[float] = None,
    ) -> dict:
        """
        Returns the number of units to buy so that if the stop is hit,
        the account loses exactly risk_pct of its current balance.
        """
        if self._halted:
            return {"error": "Kill switch active — trading halted", "size": 0}

        r    = risk_pct      or self.DEFAULT_RISK_PCT
        mult = atr_multiplier or self.DEFAULT_ATR_MULT

        dollar_risk   = self.account_balance * r
        stop_distance = atr * mult
        size          = dollar_risk / (stop_distance + 1e-9)
        max_val       = self.account_balance * self.MAX_POSITION_PCT

        return {
            "size":           round(size, 6),
            "dollar_risk":    round(dollar_risk, 2),
            "stop_distance":  round(stop_distance, 4),
            "max_position_value": round(max_val, 2),
            "risk_pct":       r,
            "atr_multiplier": mult,
            "formula":        f"({self.account_balance:.2f} × {r}) / ({atr:.4f} × {mult}) = {size:.4f} units",
        }

    # ── Position management ───────────────────────────────────────────────────

    def add_position(self, symbol: str, entry: float, qty: float, stop: float) -> None:
        with self._lock:
            if self._halted:
                raise RuntimeError(f"Kill switch active: {self._halt_reason}")
            self.positions[symbol] = Position(
                symbol=symbol,
                entry_price=entry,
                quantity=qty,
                stop_loss=stop,
                current_price=entry,
            )

    def update_price(self, symbol: str, price: float) -> None:
        with self._lock:
            if symbol not in self.positions:
                return
            self.positions[symbol].current_price = price
            self._check_stop_loss(symbol)
            self._check_kill_switch()

    def close_position(self, symbol: str) -> dict:
        with self._lock:
            return self._liquidate(symbol, reason="Manual close")

    # ── Internal checks ───────────────────────────────────────────────────────

    def _check_stop_loss(self, symbol: str) -> None:
        pos = self.positions.get(symbol)
        if pos and pos.stop_loss > 0 and pos.current_price <= pos.stop_loss:
            self._liquidate(symbol, reason=f"Stop loss hit at {pos.current_price:.4f}")

    def _check_kill_switch(self) -> None:
        total_unrealized = sum(p.unrealized_pnl for p in self.positions.values())
        equity           = self.account_balance + total_unrealized
        daily_dd         = (equity - self.daily_start_balance) / (self.daily_start_balance + 1e-9)

        if daily_dd <= self.KILL_SWITCH_THRESHOLD:
            self._halt_reason = (
                f"Daily drawdown reached {daily_dd*100:.1f}% — "
                f"exceeded the {self.KILL_SWITCH_THRESHOLD*100:.0f}% kill-switch threshold. "
                "All positions liquidated. Call reset_daily() to resume."
            )
            self._halted = True
            for sym in list(self.positions.keys()):
                self._liquidate(sym, reason="Kill switch — forced liquidation")

    def _liquidate(self, symbol: str, reason: str = "") -> dict:
        pos = self.positions.pop(symbol, None)
        if not pos:
            return {}
        pnl                  = pos.unrealized_pnl
        self.account_balance += pnl
        record = {
            "symbol":  symbol,
            "entry":   pos.entry_price,
            "exit":    pos.current_price,
            "qty":     pos.quantity,
            "pnl":     round(pnl, 2),
            "reason":  reason,
        }
        self._liquidation_log.append(record)
        return record

    # ── Status & admin ────────────────────────────────────────────────────────

    def status(self) -> dict:
        with self._lock:
            total_unrealized = sum(p.unrealized_pnl for p in self.positions.values())
            equity           = self.account_balance + total_unrealized
            daily_dd         = (equity - self.daily_start_balance) / (self.daily_start_balance + 1e-9)

            return {
                "account_balance":  round(self.account_balance, 2),
                "equity":           round(equity, 2),
                "total_unrealized": round(total_unrealized, 2),
                "daily_drawdown":   round(daily_dd * 100, 2),
                "kill_switch_threshold": self.KILL_SWITCH_THRESHOLD * 100,
                "halted":           self._halted,
                "halt_reason":      self._halt_reason,
                "open_positions":   len(self.positions),
                "positions": [
                    {
                        "symbol":    p.symbol,
                        "entry":     p.entry_price,
                        "current":   p.current_price,
                        "qty":       p.quantity,
                        "stop_loss": p.stop_loss,
                        "pnl":       round(p.unrealized_pnl, 2),
                        "pnl_pct":   round(p.unrealized_pnl_pct * 100, 2),
                    }
                    for p in self.positions.values()
                ],
                "liquidation_log": self._liquidation_log[-10:],
            }

    def reset_daily(self) -> None:
        """Call at market open to reset the kill-switch and daily baseline."""
        with self._lock:
            total_unrealized         = sum(p.unrealized_pnl for p in self.positions.values())
            self.daily_start_balance = self.account_balance + total_unrealized
            self._halted             = False
            self._halt_reason        = ""
