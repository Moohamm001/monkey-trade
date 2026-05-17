"""
Bot learning model — Bayesian update of stage win rates and signal weights.

After every closed paper trade, the model updates its beliefs:
  new_weight = old_weight * (1 - alpha_eff) + outcome * alpha_eff

The classic EMA update gave every signal in a winning setup the same alpha,
which "launders credit" — weak signals that happened to fire alongside a
strong one got rewarded equally for the win. Over hundreds of trades the
signal_weights drift toward noise.

Fix: each signal's effective alpha is proportional to its share of the total
signal weight in that setup. A signal contributing 30% of the conviction
gets 30% of the credit/blame. Capped at 1.5×alpha to keep updates bounded.

All file I/O is atomic + per-path-locked via storage.transaction() so
concurrent scans and reviews cannot corrupt model state.
"""
from __future__ import annotations

import os
from datetime import datetime
from typing import Optional

from . import storage

MODEL_PATH    = os.path.join(os.path.dirname(__file__), "..", "data", "bot_model.json")
ACTIVITY_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "bot_activity.json")


# ── I/O ───────────────────────────────────────────────────────────────────────

def load_model() -> dict:
    """Read-only snapshot of the model. Use storage.transaction() for mutations."""
    m = storage.safe_load_json(MODEL_PATH, None)
    if m is None:
        raise FileNotFoundError(f"Model file missing: {MODEL_PATH}")
    return m


def save_model(m: dict):
    """Direct save with lock. Sets last_updated."""
    m["last_updated"] = datetime.now().strftime("%Y-%m-%d")
    with storage.locked(MODEL_PATH):
        storage.atomic_write_json(MODEL_PATH, m)


def load_activity() -> dict:
    return storage.safe_load_json(ACTIVITY_PATH, {"entries": []})


def save_activity(a: dict):
    with storage.locked(ACTIVITY_PATH):
        storage.atomic_write_json(ACTIVITY_PATH, a)


def append_activity(entry: dict):
    with storage.transaction(ACTIVITY_PATH, {"entries": []}) as a:
        a["entries"].insert(0, {**entry, "timestamp": datetime.now().isoformat()})
        a["entries"] = a["entries"][:200]   # keep last 200 entries


# ── Update rule ───────────────────────────────────────────────────────────────

def update_from_trade(trade: dict):
    """
    Called when a paper trade closes. Updates stage prior and signal weights.

    Signal updates are weighted by each signal's share of total signal weight
    in that setup, so high-conviction signals receive proportionally more
    credit/blame than incidental ones.
    """
    outcome = 1.0 if trade["status"] == "closed_win" else 0.0
    stage = trade.get("stage")

    with storage.transaction(MODEL_PATH, None) as m:
        if m is None:
            raise FileNotFoundError(f"Model file missing: {MODEL_PATH}")

        alpha = m.get("alpha", 0.15)

        # ── Stage prior: flat EMA update ─────────────────────────────────────
        if stage and stage in m["stage_priors"]:
            sp = m["stage_priors"][stage]
            sp["win_rate"] = round(sp["win_rate"] * (1 - alpha) + outcome * alpha, 4)
            sp["n"] += 1

        # ── Signal weights: WEIGHTED update by share of conviction ───────────
        trade_signals = [s for s in trade.get("signals", []) if s in m["signal_weights"]]
        if trade_signals:
            current_weights = [m["signal_weights"][s]["weight"] for s in trade_signals]
            total_w = sum(current_weights) or float(len(trade_signals))
            n_sigs = len(trade_signals)

            for sig, w_now in zip(trade_signals, current_weights):
                share     = w_now / total_w
                # Multiply by n_sigs so average signal still moves ~alpha,
                # but high-share signals get proportionally more.
                eff_alpha = min(alpha * share * n_sigs, alpha * 1.5)
                sw = m["signal_weights"][sig]
                sw["weight"] = round(sw["weight"] * (1 - eff_alpha) + outcome * eff_alpha, 4)
                sw["n"] += 1

        # ── News event-type weights: flat EMA update per detected event ──────
        # The bot remembers which news event types (Earnings / M&A / Smart Money
        # / Macro / Insider …) correlated with winning trades so it can nudge
        # future news scores up or down on the right kinds of catalysts.
        if "news_event_weights" not in m:
            m["news_event_weights"] = {}
        news_ctx     = trade.get("news_context") or {}
        event_types  = [et for et, _ in (news_ctx.get("top_event_types") or [])]
        for et in event_types:
            ew = m["news_event_weights"].setdefault(et, {"weight": 0.50, "n": 0})
            ew["weight"] = round(ew["weight"] * (1 - alpha) + outcome * alpha, 4)
            ew["n"]      = ew.get("n", 0) + 1

        m["trades_learned_from"] += 1

        perf_entry = {
            "date":    trade.get("exit_date", datetime.now().strftime("%Y-%m-%d")),
            "ticker":  trade["ticker"],
            "stage":   stage,
            "outcome": "win" if outcome == 1 else "loss",
            "pnl_pct": trade.get("pnl_pct", 0),
        }
        m["performance_log"].append(perf_entry)
        m["performance_log"] = m["performance_log"][-100:]   # keep last 100

        # Auto-adapt threshold: tighten if losing streak, loosen if winning
        recent = m["performance_log"][-10:]
        if len(recent) >= 5:
            recent_wr = sum(1 for r in recent if r["outcome"] == "win") / len(recent)
            if recent_wr < 0.40:
                m["min_score_threshold"] = min(0.70, round(m["min_score_threshold"] + 0.02, 3))
            elif recent_wr > 0.65:
                m["min_score_threshold"] = max(0.45, round(m["min_score_threshold"] - 0.01, 3))

        m["last_updated"] = datetime.now().strftime("%Y-%m-%d")
        # snapshot for activity log
        new_wr  = m["stage_priors"].get(stage, {}).get("win_rate", "?")
        new_thr = m["min_score_threshold"]

    # Activity log (outside the model transaction, separate file/lock)
    append_activity({
        "event":   "learned",
        "ticker":  trade["ticker"],
        "outcome": "win" if outcome == 1 else "loss",
        "pnl_pct": trade.get("pnl_pct"),
        "stage":   stage,
        "signals": trade.get("signals", []),
        "note": (
            f"Updated stage '{stage}' win_rate → {new_wr}. "
            f"Threshold now {new_thr}."
        ),
    })


# ── Scoring ───────────────────────────────────────────────────────────────────

def score_setup(
    stage: str,
    signals: list[str],
    confidence: float,
    volume_ratio: float = 1.0,
    smart_money_score: Optional[float] = None,
    news_score: Optional[float] = None,
    news_event_types: Optional[list[str]] = None,
) -> tuple[float, dict]:
    """
    Returns (score 0–1, breakdown dict).

    Weighting strategy (re-balances as more intelligence becomes available):

      Tier 1 — Wyckoff only:
        score = stage*0.35 + signal*0.30 + confidence*0.25 + volume*0.10

      Tier 2 — Wyckoff + Smart Money Score (whale tracker):
        score = stage*0.30 + signal*0.25 + confidence*0.20 + volume*0.05 + sms*0.20

      Tier 3 — Wyckoff + SMS + News Intelligence (every signal layer):
        score = stage*0.25 + signal*0.20 + confidence*0.20 + volume*0.05
                + sms*0.15 + news*0.15

    All intel scores are normalised to [0, 1]. News score combines:
    direction alignment with the trade, average opportunity score across recent
    articles, and a bonus/penalty for Smart-Money entities mentioned in the news
    (Buffett buy vs Burry short, etc.).

    Per-event-type learning: if news_event_types is given, the average learned
    weight per event ("Earnings", "M&A", "Smart Money", …) gently nudges the
    news component up or down.
    """
    m = load_model()

    stage_score = m["stage_priors"].get(stage, {}).get("win_rate", 0.50)

    sws = [m["signal_weights"].get(s, {}).get("weight", 0.50) for s in signals]
    signal_score = sum(sws) / len(sws) if sws else 0.50

    vol_score = min(1.0, volume_ratio / 2.5)   # normalise: 2.5× avg → 1.0

    # Optional: learned event-type weights nudge the news score (±0.10 cap)
    event_weights = m.get("news_event_weights", {})
    event_nudge = 0.0
    if news_event_types and event_weights:
        ews = [event_weights.get(et, {}).get("weight", 0.50) for et in news_event_types]
        if ews:
            avg_ew    = sum(ews) / len(ews)
            event_nudge = (avg_ew - 0.50) * 0.20    # ±0.10 max

    have_sms  = smart_money_score is not None
    have_news = news_score is not None

    if have_sms and have_news:
        sms_norm  = max(0.0, min(1.0, smart_money_score / 100.0))
        news_norm = max(0.0, min(1.0, news_score + event_nudge))
        score = (
            stage_score   * 0.25 +
            signal_score  * 0.20 +
            confidence    * 0.20 +
            vol_score     * 0.05 +
            sms_norm      * 0.15 +
            news_norm     * 0.15
        )
        breakdown = {
            "stage_score":   round(stage_score, 4),
            "signal_score":  round(signal_score, 4),
            "confidence":    round(confidence, 4),
            "vol_score":     round(vol_score, 4),
            "smart_money":   round(sms_norm, 4),
            "smart_money_raw": round(smart_money_score, 1),
            "news":          round(news_norm, 4),
            "news_raw":      round(news_score, 4),
            "event_nudge":   round(event_nudge, 4),
            "total":         round(score, 4),
            "threshold":     m["min_score_threshold"],
            "passes":        score >= m["min_score_threshold"],
            "weights":       {"stage": 0.25, "signal": 0.20, "confidence": 0.20,
                              "volume": 0.05, "smart_money": 0.15, "news": 0.15},
            "tier":          "wyckoff+sms+news",
        }
    elif have_sms:
        sms_norm = max(0.0, min(1.0, smart_money_score / 100.0))
        score = (
            stage_score   * 0.30 +
            signal_score  * 0.25 +
            confidence    * 0.20 +
            vol_score     * 0.05 +
            sms_norm      * 0.20
        )
        breakdown = {
            "stage_score":   round(stage_score, 4),
            "signal_score":  round(signal_score, 4),
            "confidence":    round(confidence, 4),
            "vol_score":     round(vol_score, 4),
            "smart_money":   round(sms_norm, 4),
            "smart_money_raw": round(smart_money_score, 1),
            "news":          None,
            "total":         round(score, 4),
            "threshold":     m["min_score_threshold"],
            "passes":        score >= m["min_score_threshold"],
            "weights":       {"stage": 0.30, "signal": 0.25, "confidence": 0.20,
                              "volume": 0.05, "smart_money": 0.20},
            "tier":          "wyckoff+sms",
        }
    elif have_news:
        news_norm = max(0.0, min(1.0, news_score + event_nudge))
        score = (
            stage_score   * 0.30 +
            signal_score  * 0.25 +
            confidence    * 0.20 +
            vol_score     * 0.05 +
            news_norm     * 0.20
        )
        breakdown = {
            "stage_score":   round(stage_score, 4),
            "signal_score":  round(signal_score, 4),
            "confidence":    round(confidence, 4),
            "vol_score":     round(vol_score, 4),
            "smart_money":   None,
            "news":          round(news_norm, 4),
            "news_raw":      round(news_score, 4),
            "event_nudge":   round(event_nudge, 4),
            "total":         round(score, 4),
            "threshold":     m["min_score_threshold"],
            "passes":        score >= m["min_score_threshold"],
            "weights":       {"stage": 0.30, "signal": 0.25, "confidence": 0.20,
                              "volume": 0.05, "news": 0.20},
            "tier":          "wyckoff+news",
        }
    else:
        score = (
            stage_score   * 0.35 +
            signal_score  * 0.30 +
            confidence    * 0.25 +
            vol_score     * 0.10
        )
        breakdown = {
            "stage_score":   round(stage_score, 4),
            "signal_score":  round(signal_score, 4),
            "confidence":    round(confidence, 4),
            "vol_score":     round(vol_score, 4),
            "smart_money":   None,
            "news":          None,
            "total":         round(score, 4),
            "threshold":     m["min_score_threshold"],
            "passes":        score >= m["min_score_threshold"],
            "weights":       {"stage": 0.35, "signal": 0.30, "confidence": 0.25, "volume": 0.10},
            "tier":          "wyckoff",
        }

    return round(score, 4), breakdown


def get_kelly_size(stage: str) -> float:
    """Return the recommended position fraction for a stage (quarter-Kelly style)."""
    m = load_model()
    wr = m["stage_priors"].get(stage, {}).get("win_rate", 0.50)
    # Assume avg win = 5%, avg loss = 3% (ATR-based stops)
    avg_win, avg_loss = 0.05, 0.03
    b = avg_win / avg_loss
    edge = wr * b - (1 - wr)
    full_kelly = max(0, edge / b)
    return round(full_kelly / 4, 4)   # quarter-Kelly for safety


def get_model_summary() -> dict:
    m = load_model()
    log = m.get("performance_log", [])
    recent = log[-20:]
    wins = sum(1 for r in recent if r["outcome"] == "win")
    total = len(recent)
    return {
        **m,
        "recent_win_rate": round(wins / total * 100, 1) if total else None,
        "recent_n": total,
    }
