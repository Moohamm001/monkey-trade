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
