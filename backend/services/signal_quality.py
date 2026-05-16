"""
Signal Quality Engine — Information Coefficient, Ljung-Box, Autocorrelation.

Renaissance's core discipline: every signal must be statistically validated
before capital is committed. A signal with no measurable IC is worthless noise.

─────────────────────────────────────────────────────────────────
1. Information Coefficient (IC)
─────────────────────────────────────────────────────────────────
  IC_t = Pearson correlation between signal at time t and forward return at t+n

  IC_t = cov(signal_t, return_{t+n}) / (σ_signal × σ_return)

  A single IC value is noisy. We compute it rolling and measure:
    Mean IC (IC̄)  — average predictive power
    IC Std (IC_σ) — consistency of the signal
    IR = IC̄ / IC_σ × √T — Information Ratio (annualised)

  Interpretation:
    IC̄  > 0.05  = weak but real edge
    IC̄  > 0.10  = strong edge (most quant funds aim for this)
    IC̄  > 0.20  = extraordinary (Renaissance levels)
    IR  > 0.5   = worth trading
    IR  > 1.0   = excellent (Sharpe > 1 likely)

  t-statistic:  t = IC̄ × √n / IC_σ
  p-value:      from t-distribution with df = n - 1
  Threshold:    |t| > 2.0  (p < 0.05) to use the signal

─────────────────────────────────────────────────────────────────
2. Ljung-Box Autocorrelation Test
─────────────────────────────────────────────────────────────────
  Tests whether returns are serially correlated (predictable).

  Q = n(n+2) Σ_{k=1}^{m} ρ_k² / (n-k)

  Where ρ_k = autocorrelation at lag k.
  Q ~ χ²(m) under H₀ of no autocorrelation.

  Significant Q → returns are predictable → signals have edge.
  Non-significant Q → returns are i.i.d. → market is efficient at this frequency.

─────────────────────────────────────────────────────────────────
3. Hurst Exponent
─────────────────────────────────────────────────────────────────
  Measures long-memory in a time series.

  H ≈ 0.5 → random walk (no memory)
  H > 0.5 → persistent (trending — momentum works)
  H < 0.5 → anti-persistent (mean-reverting — reversion works)

  Estimated via rescaled range (R/S) analysis:
    For each sub-period of length n:
      R(n) = max(cumsum_demeaned) - min(cumsum_demeaned)
      S(n) = std(demeaned_returns)
    E[R(n)/S(n)] = c × n^H
    H = slope of log(R/S) vs log(n)

─────────────────────────────────────────────────────────────────
4. Per-Signal IC Backtest
─────────────────────────────────────────────────────────────────
  For each of the 8 Wyckoff signals, compute the historical IC
  against 5-day, 10-day, and 20-day forward returns.
  This shows which signals actually predict future price and which are noise.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

try:
    from statsmodels.stats.diagnostic import acorr_ljungbox
    STATSMODELS_OK = True
except ImportError:
    STATSMODELS_OK = False

from ta.trend import ADXIndicator, MACD, SMAIndicator
from ta.momentum import RSIIndicator, StochasticOscillator
from ta.volatility import AverageTrueRange, BollingerBands
from ta.volume import OnBalanceVolumeIndicator


# ── Information Coefficient ───────────────────────────────────────────────────

def compute_ic(signal: pd.Series, forward_returns: pd.Series) -> dict:
    """
    Pearson IC between a signal series and forward returns.
    Both series must be aligned on the same index.
    """
    merged = pd.DataFrame({"signal": signal, "fwd": forward_returns}).dropna()
    n = len(merged)
    if n < 10:
        return {"ic": None, "t_stat": None, "p_value": None, "n": n, "significant": False}

    ic = float(merged["signal"].corr(merged["fwd"]))
    # t-statistic: t = IC × sqrt(n-2) / sqrt(1 - IC²)
    if abs(ic) >= 1.0:
        t_stat = float("inf")
        p_val  = 0.0
    else:
        t_stat = ic * np.sqrt(n - 2) / np.sqrt(1 - ic**2)
        p_val  = float(2 * stats.t.sf(abs(t_stat), df=n - 2))

    return {
        "ic":          round(ic, 4),
        "t_stat":      round(float(t_stat), 3),
        "p_value":     round(p_val, 5),
        "n":           n,
        "significant": bool(abs(t_stat) >= 2.0 and p_val < 0.05),
    }


def compute_rolling_ic(signal: pd.Series, forward_returns: pd.Series, window: int = 60) -> dict:
    """
    Rolling IC with Information Ratio.

    IC̄ = mean rolling IC
    IC_σ = std of rolling IC
    IR = IC̄ / IC_σ × √252  (annualised)
    """
    aligned = pd.DataFrame({"signal": signal, "fwd": forward_returns}).dropna()
    if len(aligned) < window + 5:
        return {"error": "Insufficient data for rolling IC"}

    rolling_ics = []
    for i in range(window, len(aligned)):
        chunk = aligned.iloc[i - window:i]
        ic = float(chunk["signal"].corr(chunk["fwd"]))
        rolling_ics.append(ic)

    ic_series = np.array(rolling_ics)
    ic_mean   = float(np.mean(ic_series))
    ic_std    = float(np.std(ic_series))
    ir        = ic_mean / max(ic_std, 1e-9) * np.sqrt(252)
    n         = len(ic_series)
    t_stat    = ic_mean * np.sqrt(n) / max(ic_std, 1e-9)
    p_val     = float(2 * stats.t.sf(abs(t_stat), df=n - 1))

    return {
        "ic_mean":     round(ic_mean, 4),
        "ic_std":      round(ic_std, 4),
        "ir":          round(ir, 3),
        "t_stat":      round(t_stat, 3),
        "p_value":     round(p_val, 5),
        "n_windows":   n,
        "significant": bool(abs(t_stat) >= 2.0 and p_val < 0.05),
        "grade": (
            "A" if abs(ic_mean) > 0.15 else
            "B" if abs(ic_mean) > 0.08 else
            "C" if abs(ic_mean) > 0.04 else
            "D"
        ),
    }


# ── Ljung-Box autocorrelation test ────────────────────────────────────────────

def ljung_box_test(returns: pd.Series, lags: int = 10) -> dict:
    """
    Q = n(n+2) Σ_{k=1}^{m} ρ_k² / (n-k)

    Tests whether returns are serially correlated at any of the first `lags` lags.
    """
    clean = returns.dropna()
    n     = len(clean)
    if n < lags + 5:
        return {"error": "Insufficient data"}

    # Compute autocorrelations manually
    autocorrs = {}
    for k in range(1, min(lags + 1, n // 2)):
        autocorrs[k] = float(clean.autocorr(lag=k))

    # Ljung-Box Q statistic
    Q = n * (n + 2) * sum(
        rho**2 / (n - k) for k, rho in autocorrs.items()
    )
    # p-value: χ² with degrees of freedom = lags
    p_val = float(1 - stats.chi2.cdf(Q, df=lags))

    predictable = bool(p_val < 0.05)

    # Dominant lag (highest |autocorr|)
    dominant_lag = max(autocorrs, key=lambda k: abs(autocorrs[k]))
    dominant_rho = autocorrs[dominant_lag]

    return {
        "Q_statistic":     round(Q, 4),
        "p_value":         round(p_val, 5),
        "lags_tested":     lags,
        "predictable":     predictable,
        "dominant_lag":    dominant_lag,
        "dominant_autocorr": round(dominant_rho, 4),
        "autocorrelations": {k: round(v, 4) for k, v in autocorrs.items()},
        "message": (
            f"Ljung-Box Q={Q:.2f}, p={p_val:.4f} — "
            f"{'returns are AUTOCORRELATED (predictable structure exists)' if predictable else 'returns appear random at this frequency'}"
        ),
    }


# ── Hurst Exponent ───────────────────────────────────────────────────────────

def hurst_exponent(prices: pd.Series) -> dict:
    """
    R/S analysis for long-memory estimation.

    E[R(n)/S(n)] ∝ n^H
    H estimated as slope of OLS(log(RS), log(n)).
    """
    p = prices.dropna().values
    n = len(p)
    if n < 20:
        return {"error": "Need at least 20 observations"}

    returns = np.diff(np.log(p))
    ns, rs_vals = [], []

    for sub_n in [8, 16, 32, 64, 128, 256]:
        if sub_n > len(returns) // 2:
            break
        chunks = len(returns) // sub_n
        rs_list = []
        for c in range(chunks):
            sub = returns[c * sub_n:(c + 1) * sub_n]
            mean_sub = np.mean(sub)
            demeaned  = sub - mean_sub
            cumsum    = np.cumsum(demeaned)
            R         = np.max(cumsum) - np.min(cumsum)
            S         = np.std(sub, ddof=1)
            if S > 0:
                rs_list.append(R / S)
        if rs_list:
            ns.append(np.log(sub_n))
            rs_vals.append(np.log(np.mean(rs_list)))

    if len(ns) < 3:
        return {"error": "Insufficient sub-periods for R/S analysis"}

    slope, intercept, r_val, _, _ = stats.linregress(ns, rs_vals)
    H = float(slope)
    r_sq = float(r_val**2)

    if H > 0.55:
        regime = "Trending (momentum)"
        implication = "Momentum strategies perform best — trend continuation is more likely than reversal."
    elif H < 0.45:
        regime = "Mean-Reverting"
        implication = "Mean-reversion strategies perform best — O-U z-score trades are valid."
    else:
        regime = "Random Walk"
        implication = "No strong directional memory — both momentum and mean-reversion have weak edge."

    return {
        "hurst":       round(H, 4),
        "r_squared":   round(r_sq, 4),
        "regime":      regime,
        "implication": implication,
        "message":     f"H={H:.3f} → {regime}. {implication}",
    }


# ── Per-signal IC backtest ────────────────────────────────────────────────────

def _compute_signal_series(df: pd.DataFrame) -> dict[str, pd.Series]:
    """
    Build a time series for each of the 8 Wyckoff signals.
    Values are the raw indicator (not binary), so IC can be computed as a correlation.
    """
    close = df["Close"]
    high  = df["High"]
    low   = df["Low"]
    vol   = df["Volume"]
    signals = {}

    # Signal 1: 60-day momentum (return)
    signals["60d Trend"] = close.pct_change(60)

    # Signal 2: MA alignment score — SMA20 vs SMA50 vs SMA200 spread
    sma20 = SMAIndicator(close, window=20).sma_indicator()
    sma50 = SMAIndicator(close, window=50).sma_indicator()
    sma200= SMAIndicator(close, window=200).sma_indicator()
    signals["MA Alignment"] = (sma20 - sma50) / close + (sma50 - sma200) / close

    # Signal 3: RSI (centered at 50 → positive = bullish)
    signals["RSI"] = RSIIndicator(close, window=14).rsi() - 50

    # Signal 4: MACD histogram
    m = MACD(close, window_slow=26, window_fast=12, window_sign=9)
    signals["MACD Histogram"] = m.macd_diff()

    # Signal 5: Bollinger Band position (where is price in the band?)
    bb = BollingerBands(close, window=20, window_dev=2)
    signals["BB Position"] = bb.bollinger_pband()  # 0=lower band, 1=upper band

    # Signal 6: OBV normalized slope
    obv = OnBalanceVolumeIndicator(close, vol).on_balance_volume()
    signals["OBV Slope"] = obv.pct_change(20)

    # Signal 7: Stochastic %K (centered)
    stoch = StochasticOscillator(high, low, close, window=14, smooth_window=3)
    signals["Stochastic"] = stoch.stoch() - 50

    # Signal 8: ADX (trend strength — not directional, so use MACD sign × ADX)
    adx = ADXIndicator(high, low, close, window=14).adx()
    macd_sign = np.sign(m.macd_diff().fillna(0))
    signals["ADX × Direction"] = adx * macd_sign

    return signals


def compute_signal_ic_table(df: pd.DataFrame, forward_periods: list[int] = [5, 10, 20]) -> dict:
    """
    For each of the 8 Wyckoff signals, compute IC against multiple forward return horizons.
    Returns a table of IC, t-stat, p-value, and significance grade.
    """
    if len(df) < 100:
        return {"error": "Need at least 100 bars for IC backtest"}

    signal_map = _compute_signal_series(df)
    returns = df["Close"].pct_change()

    results = {}
    for sig_name, sig_series in signal_map.items():
        results[sig_name] = {}
        for fwd in forward_periods:
            fwd_ret = returns.shift(-fwd).rolling(fwd).sum()
            ic_res  = compute_ic(sig_series, fwd_ret)
            results[sig_name][f"{fwd}d"] = ic_res

    # Summary: best horizon per signal
    summary = []
    for sig_name, horizons in results.items():
        best_horizon = max(horizons.items(), key=lambda x: abs(x[1].get("ic") or 0))
        best_ic_data = best_horizon[1]
        summary.append({
            "signal":     sig_name,
            "best_horizon": best_horizon[0],
            "ic":         best_ic_data.get("ic"),
            "t_stat":     best_ic_data.get("t_stat"),
            "p_value":    best_ic_data.get("p_value"),
            "significant":best_ic_data.get("significant"),
            "grade": (
                "A" if abs(best_ic_data.get("ic") or 0) > 0.12 else
                "B" if abs(best_ic_data.get("ic") or 0) > 0.07 else
                "C" if abs(best_ic_data.get("ic") or 0) > 0.03 else
                "D"
            ),
        })

    return {
        "ic_table":      results,
        "summary":       summary,
        "forward_periods": forward_periods,
        "interpretation": (
            "IC > 0.10 = strong edge (use full weight). "
            "IC 0.04–0.10 = real but weak edge (use half weight). "
            "IC < 0.04 = noise (p > 0.05 likely). "
            "Renaissance target: IC > 0.15, IR > 1.0."
        ),
    }


# ── Master quality report ─────────────────────────────────────────────────────

def get_full_signal_quality(df: pd.DataFrame) -> dict:
    """
    Complete signal quality report:
      1. Ljung-Box autocorrelation test on daily returns
      2. Hurst exponent
      3. IC table for all 8 Wyckoff signals
    """
    returns = df["Close"].pct_change().dropna()

    lb   = ljung_box_test(returns)
    hurst = hurst_exponent(df["Close"])
    ic   = compute_signal_ic_table(df)

    # Count significant signals
    sig_count = sum(
        1 for row in ic.get("summary", [])
        if row.get("significant")
    )

    return {
        "ljung_box":      lb,
        "hurst":          hurst,
        "signal_ic":      ic,
        "significant_signals": sig_count,
        "total_signals":  8,
        "market_efficiency_verdict": (
            "INEFFICIENT — multiple exploitable patterns detected"
            if lb.get("predictable") and sig_count >= 3
            else "SEMI-EFFICIENT — some patterns exist but edge is limited"
            if sig_count >= 1
            else "EFFICIENT at this frequency — signals are noise"
        ),
    }
