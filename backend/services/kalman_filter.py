"""
Kalman Filter — Optimal State Estimation for Price Trends.

Jim Simons' background was in pattern recognition (NSA codebreaking, MIT Geometry).
The Kalman filter is the mathematically optimal linear estimator for separating
signal from noise in a dynamical system — directly applicable to price series.

State Space Model:
  State vector:  x_t = [level_t, velocity_t]   (price level and trend speed)
  Observation:   z_t = P_t                      (observed closing price)

  State Transition (assume constant velocity):
    x_t = F·x_{t-1} + w_t,    w_t ~ N(0, Q)
    F = [[1, 1],
         [0, 1]]

  Observation Model:
    z_t = H·x_t + v_t,         v_t ~ N(0, R)
    H = [1, 0]

  Kalman Recursion:
    Predict:
      x̂_t|t-1 = F·x̂_{t-1|t-1}                     (prior state estimate)
      P_t|t-1  = F·P_{t-1|t-1}·F' + Q              (prior covariance)

    Update:
      K_t = P_t|t-1·H' / (H·P_t|t-1·H' + R)       (Kalman gain)
      x̂_t|t = x̂_t|t-1 + K_t·(z_t - H·x̂_t|t-1)   (posterior estimate)
      P_t|t  = (I - K_t·H)·P_t|t-1                 (posterior covariance)

  The Kalman gain K_t balances model prediction vs observation:
    K → 1: trust the new observation fully
    K → 0: trust the model prediction fully

Noise calibration:
  R (observation noise): variance of the measurement error.
  Q (process noise):     how much the true state can change per step.
  Q/R ratio = responsiveness. High Q/R → fast-adapting filter (like EMA).
  Low Q/R  → smooth filter, slow to react (like SMA).

  We estimate R from a rolling window of price variance.
  We set Q as a fraction of R to control smoothness.

Output:
  - smoothed_price: the Kalman estimate of "true" price (noise removed)
  - trend_velocity: estimated rate of change per day (in price units)
  - trend_direction: BULLISH / BEARISH / FLAT based on velocity
  - uncertainty: sqrt(P_t[0,0]) — 1σ confidence interval around smoothed price
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def run_kalman_filter(
    prices: pd.Series,
    observation_noise: float | None = None,
    process_noise_ratio: float = 1e-3,
) -> dict:
    """
    Run the Kalman filter on a closing-price series.

    Args:
        prices:               pandas Series of closing prices
        observation_noise:    R — measurement variance (auto-estimated if None)
        process_noise_ratio:  Q = process_noise_ratio × R (controls smoothness)

    Returns dict with smoothed series, trend velocity, and signal.
    """
    p = prices.dropna().values.astype(float)
    n = len(p)
    if n < 10:
        return {"error": "Need at least 10 price observations"}

    # Estimate R from rolling variance of first 20 bars (or all if shorter)
    init_window = min(20, n)
    R = float(np.var(np.diff(p[:init_window]))) if observation_noise is None else observation_noise
    R = max(R, 1e-6)

    Q_level    = R * process_noise_ratio         # level uncertainty
    Q_velocity = R * process_noise_ratio * 0.01  # velocity changes slowly

    # State transition matrix F and observation matrix H
    F = np.array([[1.0, 1.0],
                  [0.0, 1.0]])
    H = np.array([[1.0, 0.0]])

    # Process noise covariance Q
    Q = np.array([[Q_level, 0.0],
                  [0.0, Q_velocity]])

    # Observation noise covariance
    R_mat = np.array([[R]])

    # Storage
    smoothed   = np.zeros(n)
    velocities = np.zeros(n)
    uncertainty= np.zeros(n)
    gains      = np.zeros(n)

    # Initialization: start at first observation, zero velocity
    x = np.array([p[0], 0.0])
    P = np.eye(2) * R

    for t in range(n):
        # ── Predict ──────────────────────────────────────────────────────────
        x_pred = F @ x
        P_pred = F @ P @ F.T + Q

        # ── Update ───────────────────────────────────────────────────────────
        S = H @ P_pred @ H.T + R_mat        # innovation covariance
        K = (P_pred @ H.T) / S[0, 0]        # Kalman gain (2×1 vector)

        innovation = p[t] - (H @ x_pred)[0]
        x = x_pred + K * innovation
        P = (np.eye(2) - np.outer(K, H)) @ P_pred

        smoothed[t]    = x[0]
        velocities[t]  = x[1]
        uncertainty[t] = np.sqrt(P[0, 0])
        gains[t]       = float(K[0])

    # ── Trend signal ─────────────────────────────────────────────────────────
    current_velocity = float(velocities[-1])
    current_price    = float(p[-1])
    smoothed_now     = float(smoothed[-1])
    sigma            = float(uncertainty[-1])

    # Annualised trend: velocity × 252 / current_price
    annualised_trend_pct = current_velocity * 252 / max(current_price, 1e-6) * 100

    if current_velocity > sigma * 0.1:
        direction = "BULLISH"
        direction_color = "#22C55E"
    elif current_velocity < -sigma * 0.1:
        direction = "BEARISH"
        direction_color = "#EF4444"
    else:
        direction = "FLAT"
        direction_color = "#6366F1"

    # Price vs smoothed: how far is current price from filtered estimate?
    price_vs_smooth_pct = (current_price - smoothed_now) / max(smoothed_now, 1e-6) * 100

    # Build history for charting
    dates = prices.dropna().index
    history = []
    for i in range(max(0, n - 60), n):
        dt = dates[i]
        history.append({
            "date":      dt.strftime("%Y-%m-%d") if hasattr(dt, "strftime") else str(dt),
            "price":     round(float(p[i]), 4),
            "smoothed":  round(float(smoothed[i]), 4),
            "velocity":  round(float(velocities[i]), 4),
            "upper_1sigma": round(float(smoothed[i] + uncertainty[i]), 4),
            "lower_1sigma": round(float(smoothed[i] - uncertainty[i]), 4),
        })

    # Velocity histogram for regime detection
    vel_mean  = float(np.mean(velocities))
    vel_std   = float(np.std(velocities))
    vel_zscore= (current_velocity - vel_mean) / max(vel_std, 1e-9)

    return {
        "smoothed_price":       round(smoothed_now, 4),
        "trend_velocity":       round(current_velocity, 6),
        "trend_velocity_annualized_pct": round(annualised_trend_pct, 2),
        "direction":            direction,
        "direction_color":      direction_color,
        "uncertainty_1sigma":   round(sigma, 4),
        "upper_band":           round(smoothed_now + sigma, 4),
        "lower_band":           round(smoothed_now - sigma, 4),
        "price_vs_smooth_pct":  round(price_vs_smooth_pct, 2),
        "velocity_zscore":      round(vel_zscore, 3),
        "noise_ratio_R":        round(R, 6),
        "process_noise_Q":      round(Q_level, 8),
        "history":              history,
        "message": (
            f"Kalman velocity: {current_velocity:+.4f}/day "
            f"({annualised_trend_pct:+.1f}%/yr annualised). "
            f"Smoothed price {smoothed_now:.2f} ± {sigma:.2f} (1σ). "
            f"Current price {'above' if price_vs_smooth_pct > 0 else 'below'} "
            f"Kalman estimate by {abs(price_vs_smooth_pct):.2f}%."
        ),
    }


def get_kalman_analysis(df: pd.DataFrame) -> dict:
    """Convenience wrapper: run Kalman on the Close column."""
    return run_kalman_filter(df["Close"])
