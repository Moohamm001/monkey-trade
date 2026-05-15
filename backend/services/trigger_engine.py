"""
Phase 3 — Trigger Engine (Asymmetric Execution).

A buy order is placed ONLY when ALL three conditions align simultaneously:
  1. Price is within 1% of the POC (Point of Control from VPVR)
  2. Footprint shows a positive Volume Delta (aggressive buyers > sellers)
  3. SVM classifier returns 1 (Institutional signal)

Stop loss is placed strictly BELOW the POC, creating an asymmetric R:R:
  • Entry near POC → institutions are defending this level
  • Stop below POC → if institutions leave, we leave with them
  • Target above VAH (Value Area High) → profit target at next supply zone

Why POC as anchor?
  The POC is where the most volume traded — it represents fair value consensus.
  Institutions accumulate around POC because it offers the best average fill
  price. A price returning to POC after a deviation is statistically likely
  to find support (or resistance in a short setup). Placing the stop below
  it means: "if the POC breaks on volume, the thesis is wrong — exit."
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class TriggerResult:
    should_buy:     bool
    entry_price:    Optional[float]
    stop_loss:      Optional[float]
    poc:            float
    conditions_met: dict
    reasons:        list[str]

    def to_dict(self) -> dict:
        return {
            "should_buy":     self.should_buy,
            "entry_price":    self.entry_price,
            "stop_loss":      self.stop_loss,
            "poc":            self.poc,
            "conditions_met": self.conditions_met,
            "reasons":        self.reasons,
        }


class TriggerEngine:
    POC_MAX_DEVIATION  = 0.01    # price must be within 1% of POC
    STOP_BUFFER        = 0.005   # stop placed 0.5% below POC

    def evaluate(
        self,
        current_price:  float,
        poc:            float,
        volume_delta:   float,
        svm_signal:     int   = 0,
        svm_confidence: float = 0.0,
    ) -> TriggerResult:
        conditions = {}
        reasons    = []

        # ── Condition 1 ── Price within 1% of POC ────────────────────────────
        deviation = abs(current_price - poc) / (poc + 1e-9)
        c1 = deviation <= self.POC_MAX_DEVIATION
        conditions["price_near_poc"] = {
            "met":       c1,
            "value":     round(deviation * 100, 3),
            "threshold": self.POC_MAX_DEVIATION * 100,
            "detail":    f"Price {current_price:.4f} is {deviation*100:.2f}% from POC {poc:.4f}",
        }
        reasons.append(
            f"{'✓' if c1 else '✗'} Price is {deviation*100:.2f}% from POC "
            f"(limit: {self.POC_MAX_DEVIATION*100:.0f}%)"
        )

        # ── Condition 2 ── Positive volume delta ─────────────────────────────
        c2 = volume_delta > 0
        conditions["positive_delta"] = {
            "met":    c2,
            "value":  round(volume_delta, 4),
            "detail": f"Volume delta {volume_delta:+.4f} — "
                      f"{'aggressive buyers dominate' if c2 else 'sellers dominate'}",
        }
        reasons.append(
            f"{'✓' if c2 else '✗'} Volume delta {volume_delta:+.4f} "
            f"({'buy-side dominant' if c2 else 'sell-side dominant'})"
        )

        # ── Condition 3 ── Institutional SVM signal ───────────────────────────
        c3 = svm_signal == 1
        conditions["institutional_signal"] = {
            "met":        c3,
            "signal":     svm_signal,
            "confidence": svm_confidence,
            "detail":     f"SVM: {'Institutional' if c3 else 'Retail'} "
                          f"({svm_confidence:.1f}% confidence)",
        }
        reasons.append(
            f"{'✓' if c3 else '✗'} SVM detects "
            f"{'institutional' if c3 else 'retail'} flow "
            f"({svm_confidence:.0f}% confidence)"
        )

        # ── Decision ─────────────────────────────────────────────────────────
        all_met = c1 and c2 and c3
        entry_price = None
        stop_loss   = None

        if all_met:
            entry_price = current_price
            stop_loss   = round(poc * (1 - self.STOP_BUFFER), 6)
            reasons.append(
                f"🟢 ALL CONDITIONS MET — Entry {entry_price:.4f} | "
                f"Stop below POC at {stop_loss:.4f}"
            )
        else:
            met = sum([c1, c2, c3])
            reasons.append(f"🔴 {met}/3 conditions met — no trade signal")

        return TriggerResult(
            should_buy     = all_met,
            entry_price    = entry_price,
            stop_loss      = stop_loss,
            poc            = poc,
            conditions_met = conditions,
            reasons        = reasons,
        )
