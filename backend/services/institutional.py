import yfinance as yf
import pandas as pd
from datetime import datetime


def get_institutional_data(ticker: str) -> dict:
    t = yf.Ticker(ticker)
    result = {}

    # ── Major holder percentages ─────────────────────────────────────────────
    try:
        mh = t.major_holders
        if mh is not None and not mh.empty:
            rows = mh.iloc[:, 0].tolist()
            labels = mh.iloc[:, 1].tolist()
            result["major_holders"] = [
                {"label": str(labels[i]), "value": str(rows[i])}
                for i in range(len(rows))
            ]
    except Exception:
        result["major_holders"] = []

    # ── Top institutional holders ────────────────────────────────────────────
    try:
        ih = t.institutional_holders
        if ih is not None and not ih.empty:
            holders = []
            for _, row in ih.head(10).iterrows():
                pct_held = row.get("pctHeld") or row.get("% Out")
                shares   = row.get("Shares") or row.get("shares")
                value    = row.get("Value") or row.get("value")
                date_rep = row.get("Date Reported") or row.get("dateReported")
                name     = row.get("Holder") or row.get("holder") or ""

                holders.append({
                    "name":        str(name),
                    "shares":      int(shares) if shares and not pd.isna(shares) else None,
                    "value":       int(value)  if value  and not pd.isna(value)  else None,
                    "pct_held":    round(float(pct_held) * 100, 2) if pct_held and not pd.isna(pct_held) else None,
                    "date_reported": str(date_rep)[:10] if date_rep else None,
                })
            result["institutional_holders"] = holders
        else:
            result["institutional_holders"] = []
    except Exception:
        result["institutional_holders"] = []

    # ── Insider transactions (recent buys/sells) ─────────────────────────────
    try:
        it = t.insider_transactions
        if it is not None and not it.empty:
            transactions = []
            for _, row in it.head(12).iterrows():
                date_s = row.get("Start Date") or row.get("startDate") or ""
                insider = row.get("Insider") or row.get("insider") or ""
                title   = row.get("Position") or row.get("position") or ""
                txn     = row.get("Transaction") or row.get("transaction") or ""
                shares  = row.get("Shares") or row.get("shares")
                value   = row.get("Value") or row.get("value")
                transactions.append({
                    "date":        str(date_s)[:10],
                    "insider":     str(insider),
                    "title":       str(title),
                    "transaction": str(txn),
                    "shares":      int(shares) if shares and not pd.isna(shares) else None,
                    "value":       int(value)  if value  and not pd.isna(value)  else None,
                    "is_buy":      "purchase" in str(txn).lower() or "buy" in str(txn).lower(),
                })
            result["insider_transactions"] = transactions
        else:
            result["insider_transactions"] = []
    except Exception:
        result["insider_transactions"] = []

    # ── Options put/call ratio (nearest expiry) ──────────────────────────────
    try:
        expirations = t.options
        if expirations:
            chain = t.option_chain(expirations[0])
            call_vol = float(chain.calls["volume"].fillna(0).sum())
            put_vol  = float(chain.puts["volume"].fillna(0).sum())
            call_oi  = float(chain.calls["openInterest"].fillna(0).sum())
            put_oi   = float(chain.puts["openInterest"].fillna(0).sum())
            pc_vol   = round(put_vol  / (call_vol + 1e-9), 2)
            pc_oi    = round(put_oi   / (call_oi  + 1e-9), 2)

            if pc_vol > 1.5:
                pc_signal = "bearish"
                pc_msg    = f"P/C ratio {pc_vol} — heavy put buying. Options market is hedging or betting on a decline. This is smart-money bearish positioning."
            elif pc_vol > 1.1:
                pc_signal = "neutral"
                pc_msg    = f"P/C ratio {pc_vol} — slightly elevated puts. Some defensive positioning but not extreme."
            elif pc_vol < 0.5:
                pc_signal = "bullish"
                pc_msg    = f"P/C ratio {pc_vol} — very low. Traders are buying calls aggressively. Bullish speculative flow, but watch for complacency."
            else:
                pc_signal = "bullish"
                pc_msg    = f"P/C ratio {pc_vol} — call-heavy. Options flow is bullish; market participants expect higher prices."

            result["options"] = {
                "expiry":          expirations[0],
                "call_volume":     int(call_vol),
                "put_volume":      int(put_vol),
                "call_oi":         int(call_oi),
                "put_oi":          int(put_oi),
                "put_call_vol":    pc_vol,
                "put_call_oi":     pc_oi,
                "signal":          pc_signal,
                "message":         pc_msg,
            }
        else:
            result["options"] = None
    except Exception:
        result["options"] = None

    # ── Short interest ───────────────────────────────────────────────────────
    try:
        info = t.info
        short_ratio   = info.get("shortRatio")         # days to cover
        short_pct     = info.get("shortPercentOfFloat")
        shares_short  = info.get("sharesShort")
        prev_short    = info.get("sharesShortPriorMonth")

        short_change  = None
        if shares_short and prev_short and prev_short > 0:
            short_change = round((shares_short - prev_short) / prev_short * 100, 1)

        if short_pct and short_pct > 0.20:
            short_signal = "bearish"
            short_msg    = f"Short interest is very high ({short_pct*100:.1f}% of float). Institutions are betting heavily against this stock. High short interest can also fuel a squeeze if price rises."
        elif short_pct and short_pct > 0.10:
            short_signal = "neutral"
            short_msg    = f"Moderate short interest ({short_pct*100:.1f}% of float). Some bearish positioning but not extreme."
        elif short_pct:
            short_signal = "bullish"
            short_msg    = f"Low short interest ({short_pct*100:.1f}% of float). Not many institutions betting against this stock."
        else:
            short_signal = "neutral"
            short_msg    = "Short interest data unavailable."

        result["short_interest"] = {
            "shares_short":   int(shares_short)  if shares_short  else None,
            "short_pct_float": round(float(short_pct) * 100, 2) if short_pct else None,
            "days_to_cover":   round(float(short_ratio), 1) if short_ratio else None,
            "change_vs_prior_month": short_change,
            "signal":          short_signal,
            "message":         short_msg,
        }
    except Exception:
        result["short_interest"] = {}

    return result
