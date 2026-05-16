"""
Ornstein-Uhlenbeck Mean Reversion — Statistical Arbitrage Foundation.

Jim Simons' early Medallion signals were heavily mean-reversion based.
The O-U process is the continuous-time model for a mean-reverting price:

    dX_t = θ(μ - X_t)dt + σ dW_t

Where:
  θ  = speed of mean reversion (how fast price returns to μ)
  μ  = long-run equilibrium mean
  σ  = instantaneous volatility
  W_t = standard Brownian motion

Estimation (OLS on discrete differences):
  Regress ΔX_t = X_{t+1} - X_t  on  X_t:
    ΔX_t = a + b·X_t + ε_t

  Then:
    b = -θ·Δt  →  θ = -b  (daily, so Δt=1)
    a = θ·μ·Δt  →  μ = -a/b
    σ = std(ε)   (residual standard deviation)
    half_life = ln(2) / θ  (time for deviation to decay 50%)

Stationarity (ADF test):
  H₀: series has a unit root (random walk, non-stationary, no mean reversion)
  H₁: series is stationary (mean-reverting)
  Reject H₀ if p < 0.05 → mean reversion confirmed.

Z-score (entry signal):
  z_t = (X_t - μ_rolling) / σ_rolling
  |z| > 2.0 → price is 2σ from equilibrium → reversion trade setup
  z > 0  → price above mean → SHORT signal
  z < 0  → price below mean → LONG signal

Trading logic:
  Enter when |z| > entry_z (default 2.0)
  Exit  when |z| < exit_z  (default 0.5)
  Stop  when |z| > stop_z  (default 3.0) — thesis is wrong
"""
from __future__ import annotations

import numpy as np
import pandas as pd

try:
    from statsmodels.tsa.stattools import adfuller
    from statsmodels.regression.linear_model import OLS
    from statsmodels.tools import add_constant
    STATSMODELS_OK = True
except ImportError:
    STATSMODELS_OK = False


# ── Ornstein-Uhlenbeck parameter estimation ───────────────────────────────────

def fit_ou_process(prices: pd.Series) -> dict:
    """
    Fit O-U parameters to a price series via OLS on the lag-1 difference.

    Returns θ (speed), μ (mean), σ (vol), half_life (days), and fit quality.
    """
    if not STATSMODELS_OK:
        return {"error": "statsmodels not installed — run: pip install statsmodels"}
    if len(prices) < 20:
        return {"error": "Need at least 20 observations"}

    X      = prices.values[:-1]   # X_t
    delta  = np.diff(prices.values)  # X_{t+1} - X_t = ΔX_t

    # OLS: ΔX = a + b·X + ε
    X_with_const = add_constant(X)
    model  = OLS(delta, X_with_const).fit()
    a, b   = model.params[0], model.params[1]
    resids = model.resid

    # Guard: b must be negative for mean reversion
    if b >= 0:
        return {
            "mean_reverting": False,
            "message": f"b = {b:.4f} ≥ 0: series is trending or random walk, not mean-reverting",
            "theta": 0.0, "mu": float(prices.mean()), "sigma": float(prices.std()),
            "half_life_days": None,
        }

    theta     = float(-b)
    mu        = float(-a / b)
    sigma     = float(np.std(resids))
    half_life = float(np.log(2) / theta)

    # R² of the O-U fit
    r_squared = float(model.rsquared)

    return {
        "mean_reverting":  True,
        "theta":           round(theta, 6),
        "mu":              round(mu, 4),
        "sigma":           round(sigma, 6),
        "half_life_days":  round(half_life, 1),
        "r_squared":       round(r_squared, 4),
        "message": (
            f"Half-life {half_life:.1f} days — price deviations decay 50% in "
            f"{half_life:.1f} trading days. θ={theta:.4f}, μ={mu:.2f}, σ={sigma:.4f}."
        ),
    }


# ── ADF stationarity test ─────────────────────────────────────────────────────

def adf_test(prices: pd.Series) -> dict:
    """
    Augmented Dickey-Fuller test.

    H₀: unit root present (random walk — no mean reversion)
    H₁: stationary (mean-reverting)

    Test statistic: t = (ρ̂ - 1) / SE(ρ̂)
    Reject H₀ when t < critical value (or p < 0.05).
    """
    if not STATSMODELS_OK:
        return {"error": "statsmodels not installed"}
    if len(prices) < 20:
        return {"error": "Insufficient data"}

    result = adfuller(prices.dropna(), autolag="AIC")
    stat, pval, _, _, crit, _ = result

    stationary = bool(pval < 0.05)
    strength = (
        "Strong" if pval < 0.01
        else "Moderate" if pval < 0.05
        else "Weak" if pval < 0.10
        else "None"
    )

    return {
        "stationary":        stationary,
        "adf_statistic":     round(float(stat), 4),
        "p_value":           round(float(pval), 6),
        "critical_1pct":     round(float(crit["1%"]), 4),
        "critical_5pct":     round(float(crit["5%"]), 4),
        "critical_10pct":    round(float(crit["10%"]), 4),
        "mean_reversion_strength": strength,
        "message": (
            f"ADF p={pval:.4f} {'< 0.05 → STATIONARY: mean reversion confirmed' if stationary else '≥ 0.05 → UNIT ROOT: random walk, no mean reversion'}"
        ),
    }


# ── Z-score signal ────────────────────────────────────────────────────────────

def compute_zscore(prices: pd.Series, window: int = 20) -> dict:
    """
    Rolling z-score: z_t = (X_t - μ_rolling) / σ_rolling

    The z-score measures how many standard deviations the current price
    is from its rolling equilibrium. This is the entry signal for
    mean-reversion trades.

    | z-score | Signal          | Interpretation                        |
    |---------|-----------------|---------------------------------------|
    | > +2.0  | SHORT setup     | Price 2σ above mean — expect reversion |
    | +0.5 to +2.0 | Approaching | Monitor                              |
    | -0.5 to +0.5 | Neutral     | At equilibrium — exit zone           |
    | < -2.0  | LONG setup      | Price 2σ below mean — expect reversion |
    | < -3.0  | Stop zone       | Thesis wrong — regime may have changed |
    """
    rolling_mean = prices.rolling(window).mean()
    rolling_std  = prices.rolling(window).std()
    zscore_series = (prices - rolling_mean) / rolling_std.replace(0, np.nan)

    current_z    = float(zscore_series.iloc[-1])
    current_price = float(prices.iloc[-1])
    mean_price   = float(rolling_mean.iloc[-1])
    std_price    = float(rolling_std.iloc[-1])

    # Expected dollar move to return to mean
    deviation_pct = (current_price - mean_price) / mean_price * 100

    if current_z > 3.0:
        signal, strength = "SHORT", "extreme"
    elif current_z > 2.0:
        signal, strength = "SHORT", "strong"
    elif current_z > 0.5:
        signal, strength = "WATCH SHORT", "weak"
    elif current_z < -3.0:
        signal, strength = "LONG", "extreme"
    elif current_z < -2.0:
        signal, strength = "LONG", "strong"
    elif current_z < -0.5:
        signal, strength = "WATCH LONG", "weak"
    else:
        signal, strength = "NEUTRAL", "none"

    # Build history (last 60 bars)
    history_z   = zscore_series.dropna().iloc[-60:]
    history_px  = prices.iloc[-len(history_z):]
    history = [
        {"date": (dt.strftime("%Y-%m-%d") if hasattr(dt, "strftime") else str(dt)),
         "z": round(float(z), 3), "price": round(float(p), 4)}
        for dt, z, p in zip(history_z.index, history_z.values, history_px.values)
    ]

    return {
        "current_z":       round(current_z, 3),
        "current_price":   round(current_price, 4),
        "rolling_mean":    round(mean_price, 4),
        "rolling_std":     round(std_price, 4),
        "deviation_pct":   round(deviation_pct, 2),
        "signal":          signal,
        "strength":        strength,
        "window":          window,
        "entry_threshold": 2.0,
        "exit_threshold":  0.5,
        "stop_threshold":  3.0,
        "history":         history,
        "message": (
            f"z={current_z:.2f} — price is {abs(deviation_pct):.1f}% "
            f"{'above' if deviation_pct > 0 else 'below'} the {window}-day rolling mean. "
            f"Signal: {signal} ({strength} conviction)."
        ),
    }


# ── Full mean-reversion analysis ──────────────────────────────────────────────

def get_mean_reversion_analysis(df: pd.DataFrame, window: int = 20) -> dict:
    """Full O-U analysis: ADF + parameter estimation + z-score signal."""
    close = df["Close"].dropna()

    adf   = adf_test(close)
    ou    = fit_ou_process(close)
    zs    = compute_zscore(close, window=window)

    # Overall tradeable signal
    is_tradeable = (
        adf.get("stationary", False)
        and ou.get("mean_reverting", False)
        and ou.get("half_life_days", 999) <= 30   # revert within a month
        and abs(zs["current_z"]) >= 1.5
    )

    return {
        "adf":           adf,
        "ou_params":     ou,
        "zscore":        zs,
        "tradeable":     is_tradeable,
        "summary": (
            f"{'✓ MEAN-REVERTING' if adf.get('stationary') else '✗ RANDOM WALK'} — "
            f"half-life {ou.get('half_life_days', '?')} days — "
            f"z-score {zs['current_z']:.2f} → {zs['signal']}"
        ),
    }
