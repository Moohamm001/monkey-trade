"""
Autonomous Forward-Test Bot.

Full lifecycle:
  1. _batch_prefilter()    → download 5d data for all tickers, drop penny stocks / illiquid
  2. _batch_cycle_scan()   → download 1y data for filtered candidates, run detect_cycle
  3. score_setup()         → Bayesian model score for each passing candidate
  4. log_trades()          → write top-N to forwardtest_data.json
  5. daily_review()        → refresh ALL open trades, auto-close hits, update model
  6. update_from_trade()   → EMA weight update for every closed trade (manual or bot)

Bug fixed: detect_cycle() returns confidence in [0, 100]. We normalise to [0, 1]
           before passing to score_setup() which expects a probability.
"""
from __future__ import annotations

import json
import os
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime
from typing import Generator, Optional

import pandas as pd
import yfinance as yf

from . import bot_model
from . import portfolio as portfolio_svc
from . import storage
from .cycle_detector import detect_cycle
from .screener import SP500_TICKERS, TOP100_TICKERS

# Smart Money Score is heavy (6 external APIs per ticker). Imported lazily
# in _enrich_with_smart_money so a missing/slow source can't kill a scan.
try:
    from .smart_money import get_whale_intelligence
    _HAS_SMART_MONEY = True
except Exception:
    _HAS_SMART_MONEY = False

# ── paths ─────────────────────────────────────────────────────────────────────

STORE        = os.path.join(os.path.dirname(__file__), "..", "forwardtest_data.json")
SCAN_LOG_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "scan_logs")
os.makedirs(SCAN_LOG_DIR, exist_ok=True)

# ── universe ──────────────────────────────────────────────────────────────────

# Beyond S&P 500: ETFs, crypto, popular non-index names
EXTRA_UNIVERSE = [
    # Broad market ETFs
    "SPY", "QQQ", "IWM", "DIA", "VTI", "VOO",
    # Sector ETFs
    "XLK", "XLF", "XLV", "XLE", "XLI", "XLY", "XLP", "XLU", "XLB", "XLRE", "XLC",
    # Bonds / Commodities
    "TLT", "IEF", "HYG", "GLD", "SLV", "USO", "UNG", "PDBC",
    # Volatility
    "UVXY", "SQQQ", "TQQQ",
    # Crypto (Yahoo Finance)
    "BTC-USD", "ETH-USD", "SOL-USD", "ADA-USD", "AVAX-USD", "DOGE-USD",
    # High-profile outside S&P 500
    "PLTR", "RBLX", "SNAP", "DKNG", "HOOD", "COIN", "MSTR", "SMCI",
    "ARM", "RIVN", "LCID", "NIO", "XPEV", "LI",
    # International ADRs
    "BABA", "BIDU", "JD", "PDD", "TSM", "ASML", "SAP", "NVO", "SHOP",
    # Mid-cap momentum names
    "CELH", "AXON", "FICO", "DECK", "LNTH", "NTRA", "MTSI", "SAIA",
    "IDCC", "KRTX", "PTCT", "EXLS", "SPSC", "TMDX", "MELI",
]

# Deduplicated master universe
FULL_UNIVERSE  = list(dict.fromkeys(SP500_TICKERS + EXTRA_UNIVERSE))   # ~550 tickers
QUICK_UNIVERSE = list(dict.fromkeys(TOP100_TICKERS + EXTRA_UNIVERSE[:30]))  # ~130 tickers

UNIVERSE_MAP = {
    "full":  FULL_UNIVERSE,
    "quick": QUICK_UNIVERSE,
}


# ── persistence ───────────────────────────────────────────────────────────────

def _load_store() -> dict:
    return storage.safe_load_json(STORE, {"trades": []})


def _save_store(data: dict):
    with storage.locked(STORE):
        storage.atomic_write_json(STORE, data)


def _save_scan_log(log: dict):
    fname = log["scan_id"] + ".json"
    path  = os.path.join(SCAN_LOG_DIR, fname)
    # Scan log filenames are timestamped per scan, so no cross-writer race —
    # atomic write protects against partial writes if the process is killed.
    storage.atomic_write_json(path, log)
    return fname


def list_scan_logs() -> list[str]:
    files = sorted(
        [f for f in os.listdir(SCAN_LOG_DIR) if f.endswith(".json")],
        reverse=True,
    )
    return files


def load_scan_log(filename: str) -> dict:
    path = os.path.join(SCAN_LOG_DIR, filename)
    with open(path) as f:
        return json.load(f)


# ── live price ────────────────────────────────────────────────────────────────

def _live_price(ticker: str) -> Optional[float]:
    try:
        return round(float(yf.Ticker(ticker).fast_info.last_price), 4)
    except Exception:
        return None


# ── signal extraction ─────────────────────────────────────────────────────────

def _extract_signals(cycle: dict) -> list[str]:
    """Convert cycle detector output into short label strings for the model."""
    labels: list[str] = []
    ind     = cycle.get("indicators", {})
    signals = cycle.get("signals",    [])

    rsi = ind.get("rsi")
    if rsi is not None:
        if rsi < 30:
            labels.append("RSI oversold")
        elif rsi > 70:
            labels.append("RSI overbought")

    macd = ind.get("macd_diff")
    if macd is not None:
        labels.append("MACD cross bullish" if macd > 0 else "MACD cross bearish")

    sma20, sma50 = ind.get("sma20"), ind.get("sma50")
    if sma20 and sma50 and sma20 > sma50:
        labels.append("Price above SMA50")

    va = cycle.get("volume_analysis") or {}
    if isinstance(va, dict) and va.get("volume_ratio", 1) >= 1.8:
        labels.append("Volume surge")

    # Named techniques from cycle signal list
    for s in signals:
        tech = s.get("technique", "")
        if tech and tech not in labels and len(labels) < 6:
            labels.append(tech)

    return labels[:6]


# ── pre-filter (batch, fast) ──────────────────────────────────────────────────

def _batch_prefilter(
    tickers: list[str],
    min_price: float = 3.0,
    min_avg_volume: int = 150_000,
    emit: Optional[callable] = None,
) -> list[str]:
    """
    Batch download 5-day OHLCV for up to 100 tickers at once.
    Drops penny stocks and illiquid names to avoid wasting cycle-detect time.
    """
    kept:    list[str] = []
    dropped: list[str] = []
    BATCH = 100

    if emit:
        emit(f"PRE-FILTER: checking {len(tickers)} tickers (price≥${min_price}, vol≥{min_avg_volume:,})…")

    for i in range(0, len(tickers), BATCH):
        chunk = tickers[i : i + BATCH]
        try:
            data = yf.download(
                chunk, period="5d", progress=False,
                auto_adjust=True, threads=True,
            )
            if data.empty:
                kept.extend(chunk)
                continue

            is_multi = isinstance(data.columns, pd.MultiIndex)

            for ticker in chunk:
                try:
                    if is_multi:
                        lvl = data.columns.get_level_values(1)
                        if ticker not in lvl:
                            kept.append(ticker)
                            continue
                        close  = data["Close"][ticker].dropna()
                        volume = data["Volume"][ticker].dropna()
                    else:
                        close  = data["Close"].dropna()
                        volume = data["Volume"].dropna()

                    if len(close) == 0:
                        kept.append(ticker)
                        continue

                    price   = float(close.iloc[-1])
                    avg_vol = float(volume.mean())

                    if price >= min_price and avg_vol >= min_avg_volume:
                        kept.append(ticker)
                    else:
                        dropped.append(ticker)
                except Exception:
                    kept.append(ticker)   # keep on error — safer than dropping
        except Exception:
            kept.extend(chunk)

    if emit:
        emit(f"PRE-FILTER done: {len(kept)} passed, {len(dropped)} dropped (penny/illiquid)")

    return kept


# ── full cycle scan (batch, with logging) ─────────────────────────────────────

def _batch_cycle_scan(
    tickers: list[str],
    open_tickers: set[str],
    scan_log: dict,
    emit: Optional[callable] = None,
) -> list[dict]:
    """
    Batch download 1-year history for `tickers` and run detect_cycle on each.
    Logs every decision (pass / skip-reason / score) to scan_log.
    Returns list of candidate dicts that passed the score threshold.
    """
    candidates: list[dict] = []
    m          = bot_model.load_model()
    threshold  = m["min_score_threshold"]
    BATCH      = 50

    for i in range(0, len(tickers), BATCH):
        chunk = tickers[i : i + BATCH]

        if emit:
            emit(f"SCANNING batch {i//BATCH + 1}/{(len(tickers)-1)//BATCH + 1} ({len(chunk)} tickers)…")

        try:
            data = yf.download(
                chunk, period="1y", progress=False,
                auto_adjust=True, threads=True,
            )
        except Exception as e:
            for t in chunk:
                _log_result(scan_log, t, "error", reason=f"batch download failed: {str(e)[:80]}")
                if emit:
                    emit(f"  ERR  {t} — download failed")
            continue

        if data.empty:
            for t in chunk:
                _log_result(scan_log, t, "skip", reason="no data returned")
            continue

        is_multi = isinstance(data.columns, pd.MultiIndex)

        for ticker in chunk:
            # Already open — skip
            if ticker in open_tickers:
                _log_result(scan_log, ticker, "skip", reason="already open in portfolio")
                if emit:
                    emit(f"  SKIP {ticker} — already in portfolio")
                continue

            try:
                if is_multi:
                    lvl = data.columns.get_level_values(1)
                    if ticker not in lvl:
                        _log_result(scan_log, ticker, "skip", reason="no data in batch response")
                        continue
                    df = data.xs(ticker, level=1, axis=1).dropna(how="all")
                else:
                    df = data.dropna(how="all") if len(chunk) == 1 else None

                if df is None or len(df) < 60:
                    _log_result(scan_log, ticker, "skip", reason=f"only {len(df) if df is not None else 0} bars (need 60)")
                    if emit:
                        emit(f"  SKIP {ticker} — not enough history")
                    continue

                cycle      = detect_cycle(df)
                cycle["ticker"] = ticker

                stage           = cycle.get("stage", "")
                confidence_raw  = cycle.get("confidence", 50)
                # FIXED: detect_cycle returns 0–100; normalise to 0–1
                confidence      = (confidence_raw / 100.0) if confidence_raw > 1 else float(confidence_raw)

                if stage == "distribution":
                    _log_result(scan_log, ticker, "skip", stage=stage,
                                confidence=confidence, reason="distribution (no directional edge)")
                    if emit:
                        emit(f"  SKIP {ticker} [{stage}] conf={confidence:.0%} — no edge in distribution")
                    continue

                signals   = _extract_signals(cycle)
                va        = cycle.get("volume_analysis") or {}
                vol_ratio = va.get("volume_ratio", 1.0) if isinstance(va, dict) else 1.0

                score, breakdown = bot_model.score_setup(stage, signals, confidence, vol_ratio)
                passes           = breakdown["passes"]

                tl    = cycle.get("trade_levels", {})
                entry = _live_price(ticker) or tl.get("entry")
                stop  = tl.get("stop_loss")
                tgt   = tl.get("target")

                _log_result(
                    scan_log, ticker,
                    "candidate" if passes else "below_threshold",
                    stage=stage, confidence=round(confidence, 3),
                    score=round(score, 4), signals=signals,
                    reason=None if passes else f"score {score:.3f} < threshold {threshold:.3f}",
                    entry=round(entry, 2) if entry else None,
                    stop=round(stop, 2)  if stop  else None,
                    target=round(tgt, 2) if tgt   else None,
                )

                icon = "✓" if passes else "✗"
                if emit:
                    emit(
                        f"  {icon} {ticker:6s} [{stage:12s}] "
                        f"conf={confidence:.0%}  score={score:.3f}  "
                        + (f"signals={signals[:2]}" if signals else "no signals")
                    )

                if passes:
                    candidates.append({
                        "ticker":     ticker,
                        "stage":      stage,
                        "score":      score,
                        "breakdown":  breakdown,
                        "signals":    signals,
                        "confidence": confidence,
                        "cycle":      cycle,
                        "vol_ratio":  vol_ratio,
                    })

            except Exception as e:
                _log_result(scan_log, ticker, "error", reason=str(e)[:120])
                if emit:
                    emit(f"  ERR  {ticker} — {str(e)[:60]}")

    return candidates


def _log_result(log: dict, ticker: str, decision: str, **kwargs):
    log["results"].append({"ticker": ticker, "decision": decision, **kwargs})


# ── Smart Money enrichment ────────────────────────────────────────────────────

def _fetch_sms(ticker: str) -> Optional[float]:
    """Return the Smart Money Score (0-100) for a ticker, or None if unavailable."""
    if not _HAS_SMART_MONEY:
        return None
    try:
        intel = get_whale_intelligence(ticker)
        sms = intel.get("score")
        return float(sms) if sms is not None else None
    except Exception:
        return None


def _enrich_with_smart_money(
    candidates: list[dict],
    scan_log: dict,
    emit: Optional[callable] = None,
    max_sms: int = 20,
    workers: int = 5,
) -> list[dict]:
    """
    For the top-N technical candidates (already passed the cycle threshold),
    fetch the Smart Money Score in parallel and re-score with institutional
    weighting added. Why cap at N: each SMS call makes ~6 external API
    requests; running it on every ticker in the universe would be cripplingly
    slow and abusive to the free endpoints.

    Re-scored candidates are returned sorted by their new combined score.
    Candidates that couldn't get an SMS keep their base technical score
    (so a temporary API outage degrades gracefully).
    """
    if not candidates or not _HAS_SMART_MONEY:
        return candidates

    # Take the top-N by current technical score for SMS enrichment.
    candidates.sort(key=lambda c: c["score"], reverse=True)
    enrich_set = candidates[:max_sms]

    if emit:
        emit(f"🐋 SMS enrichment: fetching Smart Money Score for top {len(enrich_set)} candidates "
             f"({workers} workers, ~6 external APIs each)…")

    sms_results: dict[str, Optional[float]] = {}
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(_fetch_sms, c["ticker"]): c["ticker"] for c in enrich_set}
        for fut in as_completed(futures):
            t = futures[fut]
            try:
                sms_results[t] = fut.result()
            except Exception:
                sms_results[t] = None

    enriched: list[dict] = []
    for c in enrich_set:
        sms = sms_results.get(c["ticker"])
        if sms is None:
            # Couldn't fetch — keep base score, mark explicitly
            c["smart_money_score"] = None
            enriched.append(c)
            continue

        new_score, new_breakdown = bot_model.score_setup(
            stage             = c["stage"],
            signals           = c["signals"],
            confidence        = c["confidence"],
            volume_ratio      = c.get("vol_ratio", 1.0),
            smart_money_score = sms,
        )
        c["score"]             = new_score
        c["breakdown"]         = new_breakdown
        c["smart_money_score"] = sms

        # Update scan log entry for visibility
        for r in scan_log["results"]:
            if r.get("ticker") == c["ticker"] and r.get("decision") in ("candidate", "below_threshold"):
                r["smart_money_score"] = round(sms, 1)
                r["score"]             = round(new_score, 4)
                r["decision"]          = "candidate" if new_breakdown["passes"] else "below_threshold_after_sms"
                if not new_breakdown["passes"]:
                    r["reason"] = f"score {new_score:.3f} < threshold after SMS (sms={sms:.0f})"

        if emit:
            verdict = "✓" if new_breakdown["passes"] else "✗"
            emit(f"  {verdict} {c['ticker']:6s} SMS={sms:5.1f} → new score {new_score:.3f}")

        enriched.append(c)

    # Keep only candidates still passing the threshold after SMS
    enriched = [c for c in enriched if c.get("smart_money_score") is None
                or c["breakdown"]["passes"]]

    # Also keep the tail (candidates we didn't enrich) — still useful as
    # fallback if all enriched candidates failed SMS or below threshold.
    tail = candidates[max_sms:]

    combined = enriched + tail
    combined.sort(key=lambda c: c["score"], reverse=True)
    return combined


# ── trade logging ─────────────────────────────────────────────────────────────

def _build_reasoning(ticker, stage, score, breakdown, signals, confidence, cycle) -> str:
    ind  = cycle.get("indicators", {})
    rsi  = ind.get("rsi")
    macd = ind.get("macd_diff", 0)
    parts = [
        f"Bot selected {ticker} | {stage.upper()} stage | score={score:.3f} (thr={breakdown['threshold']:.3f}).",
        f"Stage prior={breakdown['stage_score']*100:.0f}% | Signal avg={breakdown['signal_score']*100:.0f}% | Confidence={confidence*100:.0f}%.",
    ]
    sms_raw = breakdown.get("smart_money_raw")
    if sms_raw is not None:
        parts.append(f"Smart Money Score={sms_raw:.0f}/100 (institutional alignment).")
    if signals:
        parts.append(f"Signals: {', '.join(signals)}.")
    if rsi:
        parts.append(f"RSI={rsi:.1f}, MACD_diff={macd:.4f}.")
    action = cycle.get("stage_info", {}).get("action", "")
    if action:
        parts.append(f"Wyckoff action: {action}.")
    return " ".join(parts)


def log_trades_autonomously(candidates: list[dict]) -> list[dict]:
    logged: list[dict] = []

    # Build the trade records first (with their own portfolio allocations).
    # Each open_position() call is independently locked & atomic.
    pending: list[dict] = []
    for c in candidates:
        cycle  = c["cycle"]
        tl     = cycle.get("trade_levels", {})
        ticker = c["ticker"]
        stage  = c["stage"]
        score  = c["score"]

        entry = _live_price(ticker) or tl.get("entry")
        if not entry:
            continue

        stop      = tl.get("stop_loss") or round(entry * 0.97, 4)
        target    = tl.get("target")    or round(entry * 1.06, 4)
        direction = "short" if stage == "markdown" else "long"

        kelly_frac = bot_model.get_kelly_size(stage)
        trade_id   = str(uuid.uuid4())[:8]

        # ── Portfolio allocation (real dollars, atomic + locked) ────────────
        position = portfolio_svc.open_position(
            trade_id    = trade_id,
            ticker      = ticker,
            entry_price = entry,
            stage       = stage,
            direction   = direction,
            kelly_frac  = kelly_frac,
        )
        if position is None:
            # Portfolio full or out of cash — skip this candidate
            continue

        reasoning = _build_reasoning(
            ticker, stage, score, c["breakdown"],
            c["signals"], c["confidence"], cycle,
        )

        pending.append({
            "id":                    trade_id,
            "ticker":                ticker,
            "direction":             direction,
            "entry_price":           round(entry, 4),
            "shares":                position["shares"],
            "cost_basis":            position["cost_basis"],
            "stop_loss":             round(stop,   4) if stop   else None,
            "target":                round(target, 4) if target else None,
            "stage":                 stage,
            "confidence":            round(c["confidence"], 4),
            "signals":               c["signals"],
            "technique":             f"Bot | score={score:.3f}",
            "notes":                 reasoning,
            "entry_date":            str(date.today()),
            "status":                "open",
            "source":                "bot",
            "bot_score":             round(score, 4),
            "smart_money_score":     c.get("smart_money_score"),
            "current_price":         entry,
            "unrealized_pnl_pct":    0.0,
            "unrealized_pnl_dollar": 0.0,
            "max_gain_pct":          0.0,
            "max_drawdown_pct":      0.0,
            "days_held":             0,
            "exit_price":            None,
            "exit_date":             None,
            "exit_reason":           None,
            "pnl_pct":               None,
            "pnl_dollar":            None,
            "lesson":                "",
            "rating":                None,
        })

    # Single locked transaction to commit all new trades to STORE
    if pending:
        with storage.transaction(STORE, {"trades": []}) as data:
            for trade in pending:
                data["trades"].insert(0, trade)
        logged.extend(pending)

    return logged


# ── main scan function ────────────────────────────────────────────────────────

def scan_universe(
    mode: str = "full",
    tickers: Optional[list[str]] = None,
    max_trades: int = 3,
    emit: Optional[callable] = None,
) -> list[dict]:
    """
    Full two-stage scan:
      Stage 1 — batch pre-filter (price + volume)
      Stage 2 — batch cycle detection + model scoring

    Returns top-N candidates sorted by score.
    Saves a detailed scan log to data/scan_logs/.
    """
    universe   = tickers or UNIVERSE_MAP.get(mode, FULL_UNIVERSE)
    scan_id    = datetime.now().strftime("%Y%m%d_%H%M%S")
    m          = bot_model.load_model()

    scan_log: dict = {
        "scan_id":       scan_id,
        "timestamp":     datetime.now().isoformat(),
        "mode":          mode if not tickers else "custom",
        "universe_size": len(universe),
        "threshold":     m["min_score_threshold"],
        "results":       [],
    }

    if emit:
        emit(f"🔍 Bot scan started | universe={len(universe)} | threshold={m['min_score_threshold']:.2f} | mode={scan_log['mode']}")

    # ── Stage 1: pre-filter ───────────────────────────────────────────────────
    liquid = _batch_prefilter(universe, emit=emit)

    open_tickers = {t["ticker"] for t in _load_store()["trades"] if t["status"] == "open"}

    # ── Stage 2: cycle detection ──────────────────────────────────────────────
    if emit:
        emit(f"📡 Cycle-detecting {len(liquid)} liquid tickers…")

    candidates = _batch_cycle_scan(liquid, open_tickers, scan_log, emit=emit)

    # ── Stage 3: Smart Money enrichment (top-N candidates only) ───────────────
    # Re-scores top technical candidates with the 6-source institutional
    # intelligence (insiders, dark pool, options flow, IV skew, congress, COT).
    candidates = _enrich_with_smart_money(candidates, scan_log, emit=emit, max_sms=20)

    # ── Finalise ──────────────────────────────────────────────────────────────
    candidates.sort(key=lambda c: c["score"], reverse=True)
    top = candidates[:max_trades]

    scan_log.update({
        "scanned":    len(liquid),
        "prefiltered_out": len(universe) - len(liquid),
        "candidates": len(candidates),
        "logged":     len(top),
        "top_picks":  [
            {"ticker": c["ticker"], "stage": c["stage"],
             "score": round(c["score"], 4),
             "smart_money_score": c.get("smart_money_score")}
            for c in top
        ],
    })
    log_fname = _save_scan_log(scan_log)

    if emit:
        emit(f"📊 {len(candidates)} candidates | logging top {len(top)} | log saved → {log_fname}")
    for c in top:
        if emit:
            sms = c.get("smart_money_score")
            sms_str = f" SMS={sms:.0f}" if sms is not None else " SMS=n/a"
            emit(f"  🎯 {c['ticker']} [{c['stage']}] score={c['score']:.3f}{sms_str} "
                 f"signals={c['signals'][:3]}")

    # Update scan count
    m["total_scans"] = m.get("total_scans", 0) + 1
    bot_model.save_model(m)

    bot_model.append_activity({
        "event":         "scan_complete",
        "mode":          scan_log["mode"],
        "universe":      len(universe),
        "scanned":       len(liquid),
        "candidates":    len(candidates),
        "trades_logged": len(top),
        "tickers":       [c["ticker"] for c in top],
        "scores":        [round(c["score"], 4) for c in top],
        "log_file":      log_fname,
        "note": (
            f"Scanned {len(liquid)}/{len(universe)} liquid tickers. "
            f"Found {len(candidates)} candidates. Logged {len(top)}: "
            + ", ".join(f"{c['ticker']}({c['stage'][0].upper()})" for c in top)
        ),
    })

    return top


# ── daily review ─────────────────────────────────────────────────────────────

def daily_review() -> dict:
    """
    Run every day (or on demand):
    • Refreshes live prices for ALL open trades (manual + bot)
    • Auto-closes any that hit stop / target
    • For newly-closed trades, updates the learning model (regardless of source)
    • Writes auto-generated lessons to closed trades

    Learning from everything — not just bot trades — is intentional:
    the model should reflect what *actually* works in the portfolio.
    """
    closed_now  = []
    reviewed    = []
    open_live_prices: dict[str, float] = {}

    # Refresh + auto-close inside a single locked transaction so concurrent
    # manual edits in the forwardtest UI cannot clobber our updates.
    with storage.transaction(STORE, {"trades": []}) as data:
        # Cache model once — avoid 50+ file reads on a large open book
        model_snapshot = bot_model.load_model()

        for trade in data["trades"]:
            if trade["status"] != "open":
                continue

            price = _live_price(trade["ticker"])
            if not price:
                # Log the failure so it's visible — silent skip is the #1
                # way stop-losses get missed when Yahoo throttles us.
                bot_model.append_activity({
                    "event":  "price_fetch_failed",
                    "ticker": trade["ticker"],
                    "note":   f"Could not fetch live price for open trade {trade['id']} — stop/target check skipped today.",
                })
                continue

            entry     = trade["entry_price"]
            direction = trade.get("direction", "long")
            sl        = trade.get("stop_loss")
            tp        = trade.get("target")

            if direction == "long":
                pnl_pct    = (price - entry) / entry * 100
                hit_stop   = sl and price <= sl
                hit_target = tp and price >= tp
            else:
                pnl_pct    = (entry - price) / entry * 100
                hit_stop   = sl and price >= sl
                hit_target = tp and price <= tp

            trade["current_price"]           = price
            trade["unrealized_pnl_pct"]      = round(pnl_pct, 2)
            trade["unrealized_pnl_dollar"]   = round(pnl_pct / 100 * entry * trade.get("shares", 1), 2)
            trade["max_gain_pct"]            = round(max(trade.get("max_gain_pct",    0), pnl_pct), 2)
            trade["max_drawdown_pct"]        = round(min(trade.get("max_drawdown_pct", 0), pnl_pct), 2)

            try:
                ed = datetime.strptime(trade["entry_date"][:10], "%Y-%m-%d").date()
                trade["days_held"] = (date.today() - ed).days
            except Exception:
                pass

            reviewed.append(trade["ticker"])
            open_live_prices[trade["ticker"]] = price

            if hit_stop or hit_target:
                reason = "target_hit" if hit_target else "stop_hit"
                is_win = pnl_pct > 0
                trade["status"]      = "closed_win" if is_win else "closed_loss"
                trade["exit_price"]  = price
                trade["exit_date"]   = str(date.today())
                trade["exit_reason"] = reason
                trade["pnl_pct"]     = round(pnl_pct, 2)
                trade["pnl_dollar"]  = round(pnl_pct / 100 * entry * trade.get("shares", 1), 2)

                # Return capital to portfolio (bot trades only — manual trades have no portfolio position)
                if trade.get("source") == "bot":
                    portfolio_svc.close_position(
                        trade_id   = trade["id"],
                        exit_price = price,
                        outcome    = "win" if is_win else "loss",
                    )

                stage    = trade.get("stage", "")
                stage_wr = model_snapshot["stage_priors"].get(stage, {}).get("win_rate", 0.5)
                outcome  = "WIN" if is_win else "LOSS"
                source   = trade.get("source", "manual")

                trade["lesson"] = (
                    f"Auto-review {date.today()} [{source}]: {outcome} | "
                    f"{reason.replace('_',' ')} at ${price:.2f} | "
                    f"P&L {pnl_pct:+.2f}% over {trade.get('days_held','?')}d held. "
                    f"Stage '{stage}' model win-rate was {stage_wr*100:.0f}% at time of close. "
                    f"Signals active: {', '.join(trade.get('signals',[]) or ['none'])}."
                )

                closed_now.append(trade)

    # Run learning updates AFTER the STORE transaction releases its lock,
    # so the bot_model transaction can acquire its own lock without nesting.
    for trade in closed_now:
        bot_model.update_from_trade(trade)

    # Snapshot portfolio equity with today's live prices
    portfolio_svc.snapshot_equity(open_live_prices)

    wins   = sum(1 for t in closed_now if t["status"] == "closed_win")
    losses = len(closed_now) - wins

    summary = {
        "reviewed":      len(reviewed),
        "closed":        len(closed_now),
        "wins":          wins,
        "losses":        losses,
        "closed_detail": [
            {
                "id":          t["id"],
                "ticker":      t["ticker"],
                "source":      t.get("source", "manual"),
                "status":      t["status"],
                "pnl_pct":     t["pnl_pct"],
                "exit_reason": t["exit_reason"],
                "stage":       t.get("stage"),
                "signals":     t.get("signals", []),
                "lesson":      t["lesson"],
            }
            for t in closed_now
        ],
    }

    bot_model.append_activity({
        "event":    "daily_review",
        "reviewed": len(reviewed),
        "closed":   len(closed_now),
        "wins":     wins,
        "losses":   losses,
        "note": (
            f"Reviewed {len(reviewed)} open trades (all sources). "
            f"Closed {len(closed_now)}: {wins}W / {losses}L. Model updated."
        ),
    })

    return summary
