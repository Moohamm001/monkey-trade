from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional, List
import json, time

from ..services import autonomous_bot, bot_model, storage
from ..services.cycle_detector import detect_cycle
from ..services.stock_data import get_price_history

router = APIRouter(prefix="/api/bot", tags=["bot"])


# ── streaming scan (SSE) ───────────────────────────────────────────────────────

@router.get("/run-stream")
def run_stream(
    mode: str = Query("full", enum=["full", "quick"]),
    max_trades: int = Query(3, ge=1, le=10),
):
    """
    Server-Sent Events stream: emits live scanner progress then final trade list.
    mode=full  → ~550 tickers (S&P 500 + ETFs + crypto + popular non-index)
    mode=quick → ~130 tickers (top-100 + ETFs + crypto)
    """
    def generate():
        lines: list[str] = []

        def emit(msg: str):
            lines.append(msg)
            return f"data: {json.dumps({'type': 'progress', 'msg': msg})}\n\n"

        try:
            m = bot_model.load_model()
            universe = autonomous_bot.UNIVERSE_MAP.get(mode, autonomous_bot.FULL_UNIVERSE)

            yield emit(
                f"🔍 Scan started | mode={mode} | universe={len(universe)} tickers "
                f"| threshold={m['min_score_threshold']:.2f} | max_trades={max_trades}"
            )

            # ── Stage 1: batch pre-filter ────────────────────────────────────
            yield emit(f"PRE-FILTER: checking {len(universe)} tickers for price/volume…")

            liquid = autonomous_bot._batch_prefilter(universe)
            yield emit(f"PRE-FILTER done: {len(liquid)} liquid | {len(universe)-len(liquid)} dropped")

            open_tickers = {
                t["ticker"] for t in autonomous_bot._load_store()["trades"]
                if t["status"] == "open"
            }

            # ── Stage 2: batch cycle detection ───────────────────────────────
            scan_id  = __import__("datetime").datetime.now().strftime("%Y%m%d_%H%M%S")
            scan_log = {
                "scan_id":       scan_id,
                "timestamp":     __import__("datetime").datetime.now().isoformat(),
                "mode":          mode,
                "universe_size": len(universe),
                "threshold":     m["min_score_threshold"],
                "results":       [],
            }

            yield emit(f"📡 Cycle-detecting {len(liquid)} tickers in batches of 50…")

            import yfinance as yf
            import pandas as pd
            candidates = []
            BATCH = 50

            for i in range(0, len(liquid), BATCH):
                chunk = liquid[i : i + BATCH]
                yield emit(f"  BATCH {i//BATCH + 1}/{(len(liquid)-1)//BATCH + 1} — {len(chunk)} tickers")

                try:
                    data = yf.download(
                        chunk, period="1y", progress=False,
                        auto_adjust=True, threads=True,
                    )
                except Exception as e:
                    yield emit(f"  ERR batch download: {str(e)[:60]}")
                    continue

                if data.empty:
                    continue

                is_multi = isinstance(data.columns, pd.MultiIndex)

                for ticker in chunk:
                    if ticker in open_tickers:
                        yield emit(f"  SKIP {ticker} — already in portfolio")
                        autonomous_bot._log_result(scan_log, ticker, "skip", reason="already open")
                        continue

                    try:
                        if is_multi:
                            lvl = data.columns.get_level_values(1)
                            if ticker not in lvl:
                                autonomous_bot._log_result(scan_log, ticker, "skip", reason="no data")
                                continue
                            df = data.xs(ticker, level=1, axis=1).dropna(how="all")
                        else:
                            df = data.dropna(how="all") if len(chunk) == 1 else None

                        if df is None or len(df) < 60:
                            autonomous_bot._log_result(scan_log, ticker, "skip", reason="<60 bars")
                            continue

                        cycle          = detect_cycle(df)
                        cycle["ticker"] = ticker

                        stage          = cycle.get("stage", "")
                        conf_raw       = cycle.get("confidence", 50)
                        # FIXED: detect_cycle returns 0-100; normalise to 0-1
                        confidence     = (conf_raw / 100.0) if conf_raw > 1 else float(conf_raw)

                        if stage == "distribution":
                            autonomous_bot._log_result(scan_log, ticker, "skip", stage=stage,
                                                       reason="distribution (no edge)")
                            yield emit(f"  SKIP {ticker:6s} [distribution] — no edge")
                            continue

                        signals   = autonomous_bot._extract_signals(cycle)
                        va        = cycle.get("volume_analysis") or {}
                        vol_ratio = va.get("volume_ratio", 1.0) if isinstance(va, dict) else 1.0

                        score, breakdown = bot_model.score_setup(stage, signals, confidence, vol_ratio)
                        passes = breakdown["passes"]

                        tl     = cycle.get("trade_levels", {})
                        entry  = tl.get("entry")
                        stop   = tl.get("stop_loss")
                        target = tl.get("target")

                        autonomous_bot._log_result(
                            scan_log, ticker,
                            "candidate" if passes else "below_threshold",
                            stage=stage, confidence=round(confidence, 3),
                            score=round(score, 4), signals=signals,
                            reason=None if passes else f"score {score:.3f} < {breakdown['threshold']:.3f}",
                            entry=round(entry, 2)  if entry  else None,
                            stop=round(stop, 2)    if stop   else None,
                            target=round(target,2) if target else None,
                        )

                        icon = "✓" if passes else "✗"
                        yield emit(
                            f"  {icon} {ticker:6s} [{stage:12s}] "
                            f"conf={confidence:.0%}  score={score:.3f}  "
                            + (", ".join(signals[:2]) if signals else "no signals")
                        )

                        if passes:
                            candidates.append({
                                "ticker": ticker, "stage": stage, "score": score,
                                "breakdown": breakdown, "signals": signals,
                                "confidence": confidence, "cycle": cycle,
                                "vol_ratio": vol_ratio,
                            })

                    except Exception as e:
                        autonomous_bot._log_result(scan_log, ticker, "error", reason=str(e)[:100])
                        yield emit(f"  ERR  {ticker} — {str(e)[:60]}")

            # ── Stage 3: Smart Money enrichment (top-N only) ─────────────────
            if candidates:
                yield emit(
                    f"🐋 SMS enrichment: fetching Smart Money Score for top "
                    f"{min(20, len(candidates))} candidates (parallel, ~6 APIs each)…"
                )
                candidates = autonomous_bot._enrich_with_smart_money(
                    candidates, scan_log, emit=None, max_sms=20
                )
                # Surface the re-scored top-3 in the live log
                for c in candidates[:3]:
                    sms = c.get("smart_money_score")
                    sms_str = f" 🐋SMS={sms:.0f}" if sms is not None else " SMS=n/a"
                    yield emit(
                        f"  ★ {c['ticker']:6s} [{c['stage']:12s}] "
                        f"score={c['score']:.3f}{sms_str}"
                    )

            # ── Finalise ──────────────────────────────────────────────────────
            candidates.sort(key=lambda c: c["score"], reverse=True)
            top = candidates[:max_trades]

            scan_log.update({
                "scanned":         len(liquid),
                "prefiltered_out": len(universe) - len(liquid),
                "candidates":      len(candidates),
                "logged":          len(top),
                "top_picks":       [
                    {"ticker": c["ticker"], "stage": c["stage"],
                     "score": round(c["score"], 4),
                     "smart_money_score": c.get("smart_money_score")}
                    for c in top
                ],
            })
            log_fname = autonomous_bot._save_scan_log(scan_log)

            yield emit(f"📊 {len(candidates)} candidates found | logging top {len(top)} | log → {log_fname}")

            logged = autonomous_bot.log_trades_autonomously(top)

            # Update model scan count
            m2 = bot_model.load_model()
            m2["total_scans"] = m2.get("total_scans", 0) + 1
            bot_model.save_model(m2)

            bot_model.append_activity({
                "event":         "scan_complete",
                "mode":          mode,
                "universe":      len(universe),
                "scanned":       len(liquid),
                "candidates":    len(candidates),
                "trades_logged": len(logged),
                "tickers":       [t["ticker"] for t in logged],
                "scores":        [t["bot_score"] for t in logged],
                "log_file":      log_fname,
                "note": (
                    f"mode={mode} | {len(liquid)}/{len(universe)} liquid | "
                    f"{len(candidates)} candidates | "
                    f"logged: {', '.join(t['ticker'] for t in logged)}"
                ),
            })

            yield f"data: {json.dumps({'type': 'done', 'trades': logged, 'total_candidates': len(candidates), 'log_file': log_fname})}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'msg': str(e)})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


# ── background (non-streaming) scan ──────────────────────────────────────────

class RunBody(BaseModel):
    mode: str = "full"          # "full" | "quick"
    tickers: Optional[List[str]] = None
    max_trades: int = 3


@router.post("/run")
def run_scan(body: RunBody, background_tasks: BackgroundTasks):
    def _run():
        log_lines = []
        try:
            top = autonomous_bot.scan_universe(
                mode=body.mode,
                tickers=body.tickers,
                max_trades=body.max_trades,
                emit=lambda msg: log_lines.append(msg),
            )
            autonomous_bot.log_trades_autonomously(top)
        except Exception as e:
            bot_model.append_activity({"event": "error", "note": str(e)})

    background_tasks.add_task(_run)
    return {
        "status":  "scan started",
        "mode":    body.mode,
        "message": "Bot is scanning. Check /api/bot/activity for progress and /api/bot/scanlogs for detailed results.",
    }


# ── daily review ──────────────────────────────────────────────────────────────

@router.post("/daily-review")
def daily_review():
    """
    Refresh ALL open trades (manual + bot), auto-close stop/target hits,
    update the learning model from every outcome.
    """
    return autonomous_bot.daily_review()


# ── model ─────────────────────────────────────────────────────────────────────

@router.get("/model")
def get_model():
    return bot_model.get_model_summary()


@router.post("/model/reset")
def reset_model():
    import os as _os
    src = _os.path.join(_os.path.dirname(__file__), "..", "data", "bot_model.json")
    initial = {
        "version": 1, "created_at": "2026-05-16", "last_updated": "2026-05-16",
        "trades_learned_from": 0, "total_scans": 0,
        "stage_priors": {
            "accumulation": {"win_rate": 0.55, "n": 0},
            "markup":       {"win_rate": 0.65, "n": 0},
            "distribution": {"win_rate": 0.40, "n": 0},
            "markdown":     {"win_rate": 0.30, "n": 0},
        },
        "signal_weights": {
            "RSI oversold":       {"weight": 0.60, "n": 0},
            "RSI overbought":     {"weight": 0.50, "n": 0},
            "MACD cross bullish": {"weight": 0.58, "n": 0},
            "MACD cross bearish": {"weight": 0.52, "n": 0},
            "Volume surge":       {"weight": 0.62, "n": 0},
            "SMA alignment":      {"weight": 0.55, "n": 0},
            "BB squeeze":         {"weight": 0.57, "n": 0},
            "Wyckoff spring":     {"weight": 0.68, "n": 0},
            "Stoch crossover":    {"weight": 0.53, "n": 0},
            "OBV trend":          {"weight": 0.54, "n": 0},
            "Price above SMA50":  {"weight": 0.59, "n": 0},
            "52W breakout":       {"weight": 0.63, "n": 0},
        },
        "min_score_threshold": 0.52,
        "max_trades_per_scan": 3,
        "kelly_fraction": "quarter",
        "alpha": 0.15,
        "performance_log": [],
        "session_notes": [],
    }
    with storage.locked(src):
        storage.atomic_write_json(src, initial)
    bot_model.append_activity({"event": "reset", "note": "Model reset to initial Wyckoff priors."})
    return {"ok": True}


# ── activity log ──────────────────────────────────────────────────────────────

@router.get("/activity")
def get_activity(limit: int = Query(100, ge=1, le=500)):
    a = bot_model.load_activity()
    return a["entries"][:limit]


# ── scan logs ─────────────────────────────────────────────────────────────────

@router.get("/scanlogs")
def list_scan_logs():
    """List all saved scan log filenames (most recent first)."""
    return autonomous_bot.list_scan_logs()


@router.get("/scanlogs/{filename}")
def get_scan_log(filename: str):
    """Return the full detail of a specific scan log."""
    try:
        return autonomous_bot.load_scan_log(filename)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Scan log not found")


# ── Reset endpoints ──────────────────────────────────────────────────────────
# Each clears a single piece of bot state. Full Reset chains them all in one
# call so the user can wipe everything without remembering the order.

@router.delete("/activity")
def clear_activity():
    """Empty the bot decision log (`bot_activity.json`)."""
    bot_model.save_activity({"entries": []})
    return {"ok": True, "cleared": "activity_log"}


@router.delete("/scanlogs")
def clear_scanlogs():
    """Delete every per-scan JSON file under `data/scan_logs/`."""
    import os as _os
    removed = 0
    for fname in autonomous_bot.list_scan_logs():
        path = _os.path.join(autonomous_bot.SCAN_LOG_DIR, fname)
        try:
            _os.remove(path)
            removed += 1
        except Exception:
            continue
    bot_model.append_activity({
        "event": "reset",
        "note":  f"Cleared {removed} scan log file(s).",
    })
    return {"ok": True, "cleared": "scan_logs", "removed": removed}


@router.delete("/trades")
def clear_bot_trades(close_open: bool = Query(True, description="Force-close open bot trades at last known price")):
    """Remove bot-sourced trades from the forwardtest store. Manual trades are preserved.

    If `close_open=true` (default), any open bot trades are first force-closed
    at their last known price (so portfolio cash is returned). Otherwise they
    are deleted outright (cash stays locked — only use if you're also resetting
    the portfolio in the same flow).
    """
    from ..services import portfolio as portfolio_svc
    removed_open = 0
    removed_closed = 0

    with storage.transaction(autonomous_bot.STORE, {"trades": []}) as data:
        kept = []
        for t in data.get("trades", []):
            if t.get("source") != "bot":
                kept.append(t)
                continue
            if t.get("status") == "open":
                if close_open:
                    try:
                        price = t.get("current_price") or t.get("entry_price") or 0
                        portfolio_svc.close_position(
                            trade_id   = t["id"],
                            exit_price = price,
                            outcome    = "win" if (t.get("unrealized_pnl_pct") or 0) > 0 else "loss",
                        )
                    except Exception:
                        pass
                removed_open += 1
            else:
                removed_closed += 1
        data["trades"] = kept

    bot_model.append_activity({
        "event": "reset",
        "note":  f"Cleared {removed_open} open + {removed_closed} closed bot trade(s) "
                 f"({'force-closed in portfolio' if close_open else 'deleted outright'}).",
    })
    return {
        "ok":             True,
        "cleared":        "bot_trades",
        "removed_open":   removed_open,
        "removed_closed": removed_closed,
        "force_closed":   close_open,
    }


@router.post("/full-reset")
def full_reset(reset_portfolio: bool = Query(True, description="Also reset the $10k virtual portfolio")):
    """Nuclear option — wipe ALL bot state in one call.

    Order matters:
      1. Force-close + delete bot trades (returns cash to portfolio)
      2. Optionally reset portfolio to $10k baseline
      3. Reset learning model to initial Wyckoff priors
      4. Clear activity log
      5. Clear scan logs

    Manual forwardtest trades are preserved.
    """
    import os as _os
    from ..services import portfolio as portfolio_svc

    summary: dict = {}

    # 1. Bot trades (close-open so portfolio cash is reclaimed)
    summary["trades"] = clear_bot_trades(close_open=True)

    # 2. Portfolio reset (inline because the public reset lives in the
    # portfolio router, not the service module).
    if reset_portfolio:
        try:
            from datetime import date as _date
            balance = 10000.0
            portfolio_svc.save_portfolio({
                "initial_balance": balance,
                "cash":            balance,
                "open_positions":  {},
                "equity_curve":    [{
                    "date":            str(_date.today()),
                    "equity":          balance,
                    "cash":            balance,
                    "positions_value": 0.0,
                }],
                "stats": {
                    "total_trades":     0, "wins": 0, "losses": 0,
                    "total_pnl_dollar": 0.0, "total_pnl_pct": 0.0,
                    "best_trade_pct":   None, "worst_trade_pct": None,
                },
                "trade_history": [],
            })
            summary["portfolio"] = {"ok": True, "reset_to": balance}
        except Exception as e:
            summary["portfolio"] = {"ok": False, "error": str(e)[:160]}

    # 3. Learning model
    summary["model"] = reset_model()

    # 4. Activity log
    summary["activity"] = clear_activity()

    # 5. Scan logs (run last so the reset events from steps 1-4 don't end up
    # in a log that the next scan deletes anyway — but keeping last-clear
    # event in activity log)
    summary["scanlogs"] = clear_scanlogs()

    bot_model.append_activity({
        "event": "reset",
        "note":  "FULL RESET — bot trades, model, activity, scan logs"
                 + (" + portfolio" if reset_portfolio else "") + " wiped.",
    })
    return {"ok": True, "performed": summary}


@router.get("/scanlogs/latest/summary")
def latest_scan_summary():
    """Quick summary of the most recent scan log."""
    logs = autonomous_bot.list_scan_logs()
    if not logs:
        return {"message": "No scan logs yet"}
    log = autonomous_bot.load_scan_log(logs[0])
    results = log.get("results", [])
    decisions = {}
    for r in results:
        d = r.get("decision", "unknown")
        decisions[d] = decisions.get(d, 0) + 1
    return {
        "scan_id":      log.get("scan_id"),
        "timestamp":    log.get("timestamp"),
        "mode":         log.get("mode"),
        "universe":     log.get("universe_size"),
        "scanned":      log.get("scanned"),
        "candidates":   log.get("candidates"),
        "logged":       log.get("logged"),
        "top_picks":    log.get("top_picks", []),
        "decision_breakdown": decisions,
    }
