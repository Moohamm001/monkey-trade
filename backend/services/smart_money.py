"""
Smart Money Score — Aggregated Whale Intelligence Engine.

Combines all six data sources into a single directional score (0–100)
and a ranked list of signals by conviction strength.

Scoring model:
  Base score: 50 (neutral)
  Each source contributes ±points based on signal strength.
  Final score is clamped to [0, 100].

  Source                  | Max Bull | Max Bear | Why weighted this way
  ----------------------- | -------- | -------- | ----------------------
  SEC Insider (Form 4)    |   +20    |   -15    | Cluster buy = highest conviction
  Activist Filing (13D/G) |   +20    |   -15    | New activist = hard catalyst
  Dark Pool               |   +15    |   -12    | Stealth accumulation signal
  Options Premium Flow    |   +12    |   -12    | Dollar-weighted smart money
  IV Skew                 |   +8     |   -10    | Fear vs greed in derivatives
  Unusual Options Activity|   +10    |   -10    | Fresh positioning (vol > OI)
  Congressional Trading   |   +10    |   -8     | Policy-informed signal
  COT (if relevant)       |   +12    |   -12    | Institutional futures positioning
  Short Interest          |   +5     |   -8     | Float suppression / squeeze setup

Score interpretation:
  80–100  EXTREME BULLISH  — Multiple institutional signals aligning. Rare. High conviction.
  65–79   BULLISH          — Smart money is positioning long. Favorable risk/reward.
  45–64   NEUTRAL          — Mixed or absent institutional signals.
  30–44   BEARISH          — Institutional indicators suggest selling pressure.
  0–29    EXTREME BEARISH  — Multiple signals warn of institutional distribution/exit.
"""
from __future__ import annotations

from typing import Any

from .sec_edgar       import get_insider_summary, get_activist_filings
from .dark_pool       import get_dark_pool_metrics
from .options_flow    import get_full_options_analysis
from .congress_trades import get_congress_trades
from .cot_report      import get_relevant_cot
from .institutional   import get_institutional_data


def _clamp(v: float, lo: float = 0, hi: float = 100) -> float:
    return max(lo, min(hi, v))


def get_whale_intelligence(ticker: str) -> dict:
    """
    Fetch all data sources in sequence and compute the Smart Money Score.
    Returns the full intelligence package for the frontend.
    """
    score     = 50.0
    signals   = []
    breakdown = {}

    # ── 1. SEC Insider Transactions (Form 4) ─────────────────────────────────
    try:
        insider = get_insider_summary(ticker)
        activist= get_activist_filings(ticker)

        if insider.get("cluster_buy"):
            delta = 20
            signals.append({
                "source": "SEC Form 4", "strength": "high",
                "direction": "bullish", "delta": delta,
                "title": f"Insider Cluster Buy — {insider['buys_30d']} executives bought in 30 days",
                "detail": insider["message"],
                "icon": "🏛",
            })
        elif insider.get("buys_30d", 0) > 0:
            delta = 10
            signals.append({
                "source": "SEC Form 4", "strength": "medium",
                "direction": "bullish", "delta": delta,
                "title": f"{insider['buys_30d']} Insider Purchase(s) — Last 30 Days",
                "detail": insider["message"],
                "icon": "🏛",
            })
        elif insider.get("cluster_sell"):
            delta = -15
            signals.append({
                "source": "SEC Form 4", "strength": "medium",
                "direction": "bearish", "delta": delta,
                "title": f"Insider Cluster Sell — {insider['sells_30d']} executives sold in 30 days",
                "detail": insider["message"],
                "icon": "🏛",
            })
        elif insider.get("sells_30d", 0) > 0:
            delta = -5
            signals.append({
                "source": "SEC Form 4", "strength": "low",
                "direction": "bearish", "delta": delta,
                "title": f"{insider['sells_30d']} Insider Sale(s) — Isolated (low weight)",
                "detail": insider["message"],
                "icon": "🏛",
            })
        else:
            delta = 0
        score += delta
        breakdown["insider"] = {"score_delta": delta, "signal": insider.get("signal", "neutral")}

        # Activist filings bonus
        activist_bullish = [a for a in activist if a.get("is_activist")]
        if activist_bullish:
            adelta = 20
            signals.append({
                "source": "SEC 13D/G", "strength": "high",
                "direction": "bullish", "delta": adelta,
                "title": f"Activist Investor Filed 13D — {activist_bullish[0]['filer']}",
                "detail": activist_bullish[0]["interpretation"],
                "icon": "⚡",
            })
            score += adelta
            breakdown["activist"] = {"score_delta": adelta, "filings": len(activist)}
        elif activist:
            adelta = 5
            signals.append({
                "source": "SEC 13D/G", "strength": "low",
                "direction": "bullish", "delta": adelta,
                "title": f"Passive 13G Filing — New >5% Institutional Holder",
                "detail": activist[0]["interpretation"],
                "icon": "📋",
            })
            score += adelta
            breakdown["activist"] = {"score_delta": adelta, "filings": len(activist)}

    except Exception as e:
        breakdown["insider"] = {"error": str(e)}

    # ── 2. Dark Pool ──────────────────────────────────────────────────────────
    try:
        dp = get_dark_pool_metrics(ticker)
        dp_signal = dp.get("signal", "neutral")
        if dp_signal == "bullish":
            dp_delta = 15 if dp.get("spike") else 10
        elif dp_signal == "bearish":
            dp_delta = -12
        else:
            dp_delta = 0
        if dp_delta != 0:
            signals.append({
                "source": "FINRA Dark Pool", "strength": "high" if abs(dp_delta) >= 12 else "medium",
                "direction": dp_signal, "delta": dp_delta,
                "title": (
                    f"Dark Pool Spike — {dp.get('latest_dark_pct')}% off-exchange" if dp.get("spike")
                    else f"Dark Pool {dp_signal.title()} — {dp.get('latest_dark_pct', '?')}% off-exchange"
                ),
                "detail": dp.get("message", ""),
                "icon": "🌑",
            })
        score += dp_delta
        breakdown["dark_pool"] = {"score_delta": dp_delta, "signal": dp_signal, "dark_pct": dp.get("latest_dark_pct")}
    except Exception as e:
        breakdown["dark_pool"] = {"error": str(e)}

    # ── 3. Options Flow ───────────────────────────────────────────────────────
    try:
        opt = get_full_options_analysis(ticker)
        flow_signal = opt.get("flow_signal", "neutral")

        # Premium flow
        if flow_signal == "bullish":
            opt_delta = 12
        elif flow_signal == "bearish":
            opt_delta = -12
        else:
            opt_delta = 0
        if opt_delta != 0:
            signals.append({
                "source": "Options Premium Flow", "strength": "medium",
                "direction": flow_signal, "delta": opt_delta,
                "title": f"Options Dollar Flow — {opt.get('call_premium_pct', 50):.0f}% Call-Dominated" if flow_signal == "bullish" else "Options Dollar Flow — Put-Heavy",
                "detail": opt.get("flow_message", ""),
                "icon": "💸",
            })
        score += opt_delta

        # IV Skew
        iv_sig = opt.get("iv_skew_signal", "neutral")
        if iv_sig == "bearish":
            iv_delta = -10
            signals.append({
                "source": "Options IV Skew", "strength": "medium",
                "direction": "bearish", "delta": iv_delta,
                "title": f"Negative IV Skew — Puts Premium vs Calls (skew: {opt.get('iv_skew')}%)",
                "detail": opt.get("iv_skew_msg", ""),
                "icon": "😨",
            })
        elif iv_sig == "bullish":
            iv_delta = 8
            signals.append({
                "source": "Options IV Skew", "strength": "medium",
                "direction": "bullish", "delta": iv_delta,
                "title": f"Positive IV Skew — Calls Premium vs Puts (skew: {opt.get('iv_skew')}%)",
                "detail": opt.get("iv_skew_msg", ""),
                "icon": "🚀",
            })
        else:
            iv_delta = 0
        score += iv_delta

        # Unusual activity
        unusual = opt.get("unusual_activity", [])
        bull_unusual = [u for u in unusual if u["is_bullish"]]
        bear_unusual = [u for u in unusual if not u["is_bullish"]]
        if len(bull_unusual) >= 3:
            u_delta = 10
            total_prem = sum(u["premium_usd"] for u in bull_unusual)
            signals.append({
                "source": "Unusual Options Activity", "strength": "high",
                "direction": "bullish", "delta": u_delta,
                "title": f"{len(bull_unusual)} Unusual Call Sweeps — ${_fmt(total_prem)} Total Premium",
                "detail": f"Volume exceeds open interest on {len(bull_unusual)} call contracts — fresh institutional positioning, not closing existing trades.",
                "icon": "🔥",
            })
            score += u_delta
        elif len(bear_unusual) >= 3:
            u_delta = -10
            total_prem = sum(u["premium_usd"] for u in bear_unusual)
            signals.append({
                "source": "Unusual Options Activity", "strength": "high",
                "direction": "bearish", "delta": u_delta,
                "title": f"{len(bear_unusual)} Unusual Put Sweeps — ${_fmt(total_prem)} Total Premium",
                "detail": f"Volume exceeds open interest on {len(bear_unusual)} put contracts — fresh downside protection being purchased.",
                "icon": "🔥",
            })
            score += u_delta

        breakdown["options"] = {
            "score_delta": opt_delta + iv_delta,
            "flow_signal": flow_signal,
            "iv_skew_signal": iv_sig,
            "unusual_count": len(unusual),
        }
    except Exception as e:
        breakdown["options"] = {"error": str(e)}

    # ── 4. Congressional Trading ──────────────────────────────────────────────
    try:
        cong = get_congress_trades(ticker, lookback_days=180)
        cong_signal = cong.get("signal", "neutral")
        if cong_signal == "bullish":
            cong_delta = 15 if cong.get("cluster_buy") else 7
        elif cong_signal == "bearish":
            cong_delta = -8
        else:
            cong_delta = 0
        if cong_delta != 0:
            signals.append({
                "source": "Congressional Trading", "strength": "high" if cong.get("cluster_buy") else "medium",
                "direction": cong_signal, "delta": cong_delta,
                "title": f"Congress {cong_signal.title()} — {cong.get('buys_90d', 0)} buys / {cong.get('sells_90d', 0)} sells (90d)",
                "detail": cong.get("message", ""),
                "icon": "🏛️",
            })
        score += cong_delta
        breakdown["congress"] = {"score_delta": cong_delta, "signal": cong_signal, "buys_90d": cong.get("buys_90d")}
    except Exception as e:
        breakdown["congress"] = {"error": str(e)}

    # ── 5. COT (if relevant futures exist) ────────────────────────────────────
    try:
        cots = get_relevant_cot(ticker)
        for cot in cots:
            cot_sig = cot.get("signal", "neutral")
            if cot_sig == "bullish":
                cot_delta = 12
            elif cot_sig == "bearish":
                cot_delta = -12
            else:
                cot_delta = 0
            if cot_delta != 0:
                signals.append({
                    "source": f"COT — {cot['instrument']}", "strength": "medium",
                    "direction": cot_sig, "delta": cot_delta,
                    "title": f"Institutions Net {'Long' if cot_delta > 0 else 'Short'} {cot['instrument']} Futures",
                    "detail": cot.get("message", ""),
                    "icon": "📊",
                })
            score += cot_delta
        breakdown["cot"] = {"instruments": [c["instrument"] for c in cots]}
    except Exception as e:
        breakdown["cot"] = {"error": str(e)}

    # ── 6. Short Interest ─────────────────────────────────────────────────────
    try:
        inst_data = get_institutional_data(ticker)
        si = inst_data.get("short_interest", {})
        si_signal = si.get("signal", "neutral")
        si_pct    = si.get("short_pct_float")
        si_change = si.get("change_vs_prior_month")

        if si_signal == "bearish":
            si_delta = -8
            signals.append({
                "source": "Short Interest", "strength": "medium",
                "direction": "bearish", "delta": si_delta,
                "title": f"High Short Interest — {si_pct}% of Float Shorted",
                "detail": si.get("message", ""),
                "icon": "🩳",
            })
        elif si_signal == "bullish" and si_pct is not None and si_pct > 5 and si_change is not None and si_change < -10:
            si_delta = 8   # shorts covering = potential squeeze fuel
            signals.append({
                "source": "Short Interest", "strength": "medium",
                "direction": "bullish", "delta": si_delta,
                "title": f"Short Squeeze Setup — {si_change}% Short Cover in 1 Month",
                "detail": f"Short interest dropping {abs(si_change):.1f}% MoM while float is {si_pct}% short — shorts are covering. Squeeze fuel present.",
                "icon": "💥",
            })
        else:
            si_delta = 0
        score += si_delta
        breakdown["short_interest"] = {"score_delta": si_delta, "signal": si_signal, "pct": si_pct}
    except Exception as e:
        breakdown["short_interest"] = {"error": str(e)}

    # ── Finalize ──────────────────────────────────────────────────────────────
    final_score = int(_clamp(score))
    signals.sort(key=lambda x: abs(x.get("delta", 0)), reverse=True)

    if final_score >= 80:
        rating = "EXTREME BULLISH"
        rating_color = "#16A34A"
        summary = (
            "Multiple institutional signals converging bullishly. Rare setup. "
            "Smart money across insiders, options, dark pools, and/or institutional positioning "
            "is aligned. Historically precedes significant upside moves."
        )
    elif final_score >= 65:
        rating = "BULLISH"
        rating_color = "#22C55E"
        summary = "Institutional indicators favor the bulls. Risk/reward skewed to the upside."
    elif final_score >= 45:
        rating = "NEUTRAL"
        rating_color = "#6366F1"
        summary = "Mixed or absent institutional signals. No strong directional edge from smart money data."
    elif final_score >= 30:
        rating = "BEARISH"
        rating_color = "#F59E0B"
        summary = "Institutional indicators suggest selling pressure or distribution."
    else:
        rating = "EXTREME BEARISH"
        rating_color = "#DC2626"
        summary = "Multiple signals warn of institutional exit or active shorting. High-risk long environment."

    return {
        "ticker":       ticker,
        "score":        final_score,
        "rating":       rating,
        "rating_color": rating_color,
        "summary":      summary,
        "signals":      signals,
        "breakdown":    breakdown,
        "signal_count": len(signals),
    }


def _fmt(v: float) -> str:
    if v >= 1e9: return f"{v/1e9:.1f}B"
    if v >= 1e6: return f"{v/1e6:.1f}M"
    if v >= 1e3: return f"{v/1e3:.0f}K"
    return str(int(v))
