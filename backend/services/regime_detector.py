"""
Phase 2 — Market Regime Filter (K-Means Clustering).

Classifies the current market into one of three regimes:
  0 → Trending        (high ADX, directional price movement)
  1 → Mean-Reverting  (low ADX, oscillating price)
  2 → High Volatility (large ATR, no clear trend)

Why K-Means?
  A regime is a *latent* state — you cannot directly observe it, only infer it
  from indicator behaviour. K-Means clusters the feature space into three
  natural groups without requiring labelled training data, letting the
  historical data itself define what "trending" looks like for each instrument.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from ta.trend import ADXIndicator, SMAIndicator
from ta.volatility import AverageTrueRange

REGIME_META = {
    "Trending": {
        "color":  "#22C55E",
        "action": "Follow the trend — use breakout and momentum strategies. "
                  "Pullbacks to SMA20 are entries, not exits.",
    },
    "Mean-Reverting": {
        "color":  "#6366F1",
        "action": "Fade the extremes — buy range lows, sell range highs. "
                  "Tight stops; do not let winners run past the midpoint.",
    },
    "High Volatility": {
        "color":  "#EF4444",
        "action": "Reduce position size — widen stops or stay flat until "
                  "volatility compresses. Breakouts fail often in this regime.",
    },
}


def _build_features(df: pd.DataFrame) -> pd.DataFrame:
    close = df["Close"]
    high  = df["High"]
    low   = df["Low"]

    atr   = AverageTrueRange(high, low, close, window=14).average_true_range()
    adx   = ADXIndicator(high, low, close, window=14).adx()
    sma20 = SMAIndicator(close, window=20).sma_indicator()
    sma50 = SMAIndicator(close, window=50).sma_indicator()

    feat = pd.DataFrame({
        "atr_pct":   atr / close,
        "adx_norm":  adx / 100.0,
        "ma_spread": (sma20 - sma50) / close,
        "vol_20d":   close.pct_change().rolling(20).std(),
        "momentum":  close.pct_change(10),
    }).dropna()

    return feat


def _map_clusters_to_regimes(centroids: np.ndarray) -> dict[int, str]:
    """
    Assign semantic regime labels to cluster centroids by their characteristics.
    Feature column order: [atr_pct, adx_norm, ma_spread, vol_20d, momentum]
    Each cluster is assigned to exactly one regime — no overlaps.
    """
    adx_col = 1
    atr_col = 0
    vol_col = 3

    # Trending: highest ADX (directional strength)
    trending_cluster = int(np.argmax(centroids[:, adx_col]))

    # High Volatility: highest ATR+vol among remaining clusters
    combined = centroids[:, atr_col] + centroids[:, vol_col]
    combined_masked = combined.copy().astype(float)
    combined_masked[trending_cluster] = -np.inf
    high_vol_cluster = int(np.argmax(combined_masked))

    # Mean-Reverting: whatever is left
    mean_rev_cluster = next(
        i for i in range(3) if i not in {trending_cluster, high_vol_cluster}
    )

    return {
        trending_cluster:  "Trending",
        mean_rev_cluster:  "Mean-Reverting",
        high_vol_cluster:  "High Volatility",
    }


def detect_regime(df: pd.DataFrame) -> dict:
    """
    Run K-Means on the feature matrix and return the current regime,
    plus a 60-bar history for the frontend chart.
    """
    feat = _build_features(df)
    if len(feat) < 50:
        return {
            "regime": "Unknown", "color": "#A0AABF",
            "action": "Insufficient data", "confidence": 0, "history": [],
        }

    scaler = StandardScaler()
    X      = scaler.fit_transform(feat)

    km     = KMeans(n_clusters=3, random_state=42, n_init=10)
    labels = km.fit_predict(X)

    cluster_map    = _map_clusters_to_regimes(km.cluster_centers_)
    current_regime = cluster_map[int(labels[-1])]
    meta           = REGIME_META[current_regime]

    recent          = labels[-20:]
    current_cluster = int(labels[-1])
    confidence      = int(np.sum(recent == current_cluster) / len(recent) * 100)

    close_series = df["Close"].iloc[-len(labels):]
    dates        = df.index[-len(labels):]
    history = [
        {
            "date":   dt.strftime("%Y-%m-%d") if hasattr(dt, "strftime") else str(dt),
            "price":  round(float(price), 4),
            "regime": cluster_map[int(lbl)],
            "color":  REGIME_META[cluster_map[int(lbl)]]["color"],
        }
        for lbl, dt, price in zip(labels, dates, close_series.values)
    ]

    return {
        "regime":     current_regime,
        "color":      meta["color"],
        "action":     meta["action"],
        "confidence": confidence,
        "history":    history[-60:],
    }
