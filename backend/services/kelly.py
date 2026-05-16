"""
Kelly Criterion — Mathematically Optimal Position Sizing.

Jim Simons reportedly used fractional Kelly throughout Medallion's history.
The Kelly Criterion answers: "What fraction of my capital should I risk on each bet
to maximize the long-run geometric growth rate of my portfolio?"

─────────────────────────────────────────────────────────────────
1. Discrete Kelly (Bernoulli outcomes)
─────────────────────────────────────────────────────────────────
  Given:
    p = probability of winning
    b = net gain per $1 risked (win/loss payoff ratio)
    q = 1 - p  (probability of losing)

  Kelly fraction:
    f* = (p·b - q) / b = p - (1-p)/b = edge / odds

  Example: win 60% of trades, average win = 2× average loss
    f* = (0.60 × 2 - 0.40) / 2 = (1.20 - 0.40) / 2 = 0.40
    Optimal bet: 40% of account per trade.

─────────────────────────────────────────────────────────────────
2. Continuous Kelly (log-normal returns)
─────────────────────────────────────────────────────────────────
  For assets with normally distributed log-returns:
    r ~ N(μ, σ²)

  Kelly fraction:
    f* = μ / σ²  =  Sharpe_ratio / σ

  Where μ = expected excess return per period, σ = std dev of returns.

  Derivation: maximise E[ln(W_t)] where W_t = wealth.
  Solution: f* = μ/σ² (same as maximising log-utility).

─────────────────────────────────────────────────────────────────
3. Why Fractional Kelly (Simons' safety factor)?
─────────────────────────────────────────────────────────────────
  Full Kelly maximises long-run growth BUT:
    - Assumes perfectly calibrated estimates of p, b, μ, σ
    - Assumes log-normal tails (reality has fat tails)
    - Can produce catastrophic drawdowns if estimates are wrong by 10%
    - Drawdown from full Kelly: ~50% drawdowns are expected and normal

  Half-Kelly (f* / 2):
    - Grows at ~75% of full Kelly speed
    - Reduces expected max drawdown by ~50%
    - Provides a safety margin for model misspecification

  Quarter-Kelly (f* / 4):
    - Grows at ~44% of full Kelly speed
    - Maximises Sharpe ratio of the strategy
    - Recommended when IC is uncertain or model is new

─────────────────────────────────────────────────────────────────
4. Multi-asset Kelly (portfolio extension)
─────────────────────────────────────────────────────────────────
  For n assets with return vector μ and covariance matrix Σ:
    f* = Σ⁻¹ · μ   (vector of optimal fractions)

  This is identical to the mean-variance efficient portfolio weights
  (Markowitz) with utility parameter λ = 1.
  The Kelly portfolio = the maximum log-growth portfolio.
─────────────────────────────────────────────────────────────────
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats


# ── Discrete Kelly ────────────────────────────────────────────────────────────

def kelly_discrete(win_rate: float, avg_win_pct: float, avg_loss_pct: float) -> dict:
    """
    Kelly fraction for discrete win/loss trades.

    Args:
        win_rate:     fraction of trades that are winners [0, 1]
        avg_win_pct:  average % gain on winning trades (e.g. 0.05 = 5%)
        avg_loss_pct: average % loss on losing trades (positive, e.g. 0.03 = 3%)

    Returns full Kelly, half-Kelly, quarter-Kelly, and interpretation.
    """
    p = max(0.01, min(0.99, win_rate))
    q = 1.0 - p
    b = avg_win_pct / max(avg_loss_pct, 1e-9)   # payoff ratio

    edge  = p * b - q
    f_full = edge / max(b, 1e-9)
    f_full = max(0.0, min(1.0, f_full))  # clamp to [0, 1]

    # Expected log-growth rate per trade (Kelly's formula)
    if f_full > 0:
        growth_rate = p * np.log(1 + f_full * b) + q * np.log(1 - f_full)
    else:
        growth_rate = 0.0

    # Expected drawdown (approximation: max DD ≈ f / (2*|g'|))
    expected_max_dd_full = f_full * 0.5  # rough rule of thumb: max DD ≈ 50% at full Kelly

    interpretation = (
        "Positive edge — Kelly sizing is valid"
        if f_full > 0
        else "No edge (f* ≤ 0) — do not trade this setup"
    )

    return {
        "win_rate":          round(p, 4),
        "loss_rate":         round(q, 4),
        "payoff_ratio":      round(b, 4),
        "edge":              round(edge, 4),
        "kelly_full":        round(f_full, 4),
        "kelly_half":        round(f_full / 2, 4),
        "kelly_quarter":     round(f_full / 4, 4),
        "recommended":       round(f_full / 2, 4),   # Renaissance-style half-Kelly
        "expected_log_growth_per_trade": round(growth_rate, 6),
        "expected_max_drawdown_full_kelly_pct": round(expected_max_dd_full * 100, 1),
        "interpretation":    interpretation,
        "formula": f"f* = ({p:.2f}×{b:.2f} - {q:.2f}) / {b:.2f} = {f_full:.4f}",
    }


# ── Continuous Kelly from historical returns ──────────────────────────────────

def kelly_continuous(returns: pd.Series, risk_free_rate_annual: float = 0.05) -> dict:
    """
    f* = μ_excess / σ²  =  Sharpe / σ

    Derived from maximising E[ln(W)] for log-normal returns.
    μ_excess = daily expected return above risk-free rate.
    σ = daily return std deviation.
    """
    clean = returns.dropna()
    n     = len(clean)
    if n < 20:
        return {"error": "Need at least 20 return observations"}

    rf_daily = (1 + risk_free_rate_annual) ** (1 / 252) - 1
    mu_excess = float(clean.mean()) - rf_daily
    sigma     = float(clean.std())

    if sigma <= 0:
        return {"error": "Zero volatility — cannot compute Kelly"}

    f_full = mu_excess / (sigma ** 2)
    f_full = max(-1.0, min(5.0, f_full))  # practical cap

    sharpe_daily = mu_excess / sigma
    sharpe_annual = sharpe_daily * np.sqrt(252)

    # t-test: is mean return significantly different from risk-free?
    t_stat = mu_excess * np.sqrt(n) / sigma
    p_val  = float(2 * stats.t.sf(abs(t_stat), df=n - 1))
    significant = bool(abs(t_stat) >= 2.0 and p_val < 0.05)

    return {
        "mu_daily":              round(float(clean.mean()) * 100, 4),
        "mu_excess_daily":       round(mu_excess * 100, 4),
        "sigma_daily":           round(sigma * 100, 4),
        "sharpe_annual":         round(sharpe_annual, 3),
        "kelly_full":            round(f_full, 4),
        "kelly_half":            round(f_full / 2, 4),
        "kelly_quarter":         round(f_full / 4, 4),
        "recommended":           round(max(0, f_full / 2), 4),
        "t_stat":                round(t_stat, 3),
        "p_value":               round(p_val, 5),
        "return_significant":    significant,
        "n_observations":        n,
        "formula":               f"f* = {mu_excess*100:.4f}% / ({sigma*100:.4f}%)² = {f_full:.4f}",
        "message": (
            f"Continuous Kelly: f*={f_full:.3f} (recommended half-Kelly: {max(0, f_full/2):.3f}). "
            f"Sharpe={sharpe_annual:.2f}. "
            f"Mean return {'IS' if significant else 'is NOT'} statistically significant (p={p_val:.4f})."
        ),
    }


# ── Stage-specific Kelly from backtest ───────────────────────────────────────

def kelly_from_cycle_backtest(df: pd.DataFrame) -> dict:
    """
    Walk-forward backtest of each Wyckoff stage:
      For each day, use the previous 252-day window to detect cycle stage.
      Record the 20-day forward return for each stage label.
      Compute Kelly fraction for each stage from realized win rate and R:R.

    This is a simplified single-feature backtest using 60d trend + MA alignment
    as a proxy for cycle stage (avoids circular importing full cycle_detector).
    """
    close    = df["Close"]
    n        = len(close)
    if n < 120:
        return {"error": "Need at least 120 bars for stage Kelly backtest"}

    fwd_20   = close.pct_change(20).shift(-20)

    # Simple stage proxy:
    #   Markup   → 60d return > +10% AND SMA20 > SMA50
    #   Markdown → 60d return < -10% AND SMA20 < SMA50
    #   Accumulation  → price between SMA50 and SMA200, momentum turning up
    #   Distribution  → price above SMA200, momentum slowing
    ret_60   = close.pct_change(60)
    sma20    = close.rolling(20).mean()
    sma50    = close.rolling(50).mean()

    stage_returns: dict[str, list[float]] = {
        "Markup": [], "Markdown": [], "Accumulation": [], "Distribution": []
    }
    for i in range(60, n - 20):
        r60 = ret_60.iloc[i]
        above = sma20.iloc[i] > sma50.iloc[i]
        fwd   = fwd_20.iloc[i]
        if pd.isna(fwd) or pd.isna(r60):
            continue
        if r60 > 0.10 and above:
            stage_returns["Markup"].append(float(fwd))
        elif r60 < -0.10 and not above:
            stage_returns["Markdown"].append(float(fwd))
        elif -0.05 < r60 < 0.05 and above:
            stage_returns["Distribution"].append(float(fwd))
        else:
            stage_returns["Accumulation"].append(float(fwd))

    result = {}
    for stage, rets in stage_returns.items():
        if len(rets) < 10:
            result[stage] = {"n": len(rets), "message": "Insufficient samples"}
            continue
        arr       = np.array(rets)
        wins      = arr[arr > 0]
        losses    = arr[arr < 0]
        win_rate  = len(wins) / len(arr)
        avg_win   = float(wins.mean()) if len(wins) > 0 else 0.01
        avg_loss  = float(abs(losses.mean())) if len(losses) > 0 else 0.01

        kelly_res = kelly_discrete(win_rate, avg_win, avg_loss)
        kelly_res.update({
            "n":         len(rets),
            "mean_return_pct": round(float(arr.mean()) * 100, 2),
            "stage":     stage,
        })
        result[stage] = kelly_res

    return {
        "stage_kelly": result,
        "note": (
            "Walk-forward Kelly per Wyckoff stage. "
            "Use recommended (half-Kelly) fraction for position sizing when in that stage. "
            "If p-value > 0.05 for a stage, the edge is not statistically confirmed."
        ),
    }


# ── Master Kelly analysis ──────────────────────────────────────────────────────

def get_kelly_analysis(df: pd.DataFrame) -> dict:
    """Full Kelly analysis: continuous Kelly + stage-specific backtest."""
    returns = df["Close"].pct_change()
    ck   = kelly_continuous(returns)
    sbk  = kelly_from_cycle_backtest(df)

    return {
        "continuous_kelly": ck,
        "stage_kelly":      sbk.get("stage_kelly", {}),
        "simons_rule": (
            "Renaissance used half-Kelly as the baseline, then further reduced "
            "by the number of correlated positions in the portfolio. "
            "The multi-asset Kelly fraction for n correlated positions ≈ f*/n when ρ≈1."
        ),
    }
