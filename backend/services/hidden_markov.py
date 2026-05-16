"""
Hidden Markov Model — Regime Detection (Jim Simons / Renaissance approach).

Leonard Baum, co-inventor of the Baum-Welch algorithm, joined Renaissance Technologies
in 1989. HMMs were central to Medallion's early edge because they model the market as
a *process with memory* — the regime today depends on the regime yesterday — which
K-Means completely ignores.

Mathematical foundation:
  Let S_t ∈ {0,1,2,3} be the hidden state (regime) at time t.
  Let O_t be the observed feature vector at time t.

  Model parameters λ = (π, A, B):
    π_i = P(S_0 = i)               — initial state probabilities
    A_ij = P(S_t = j | S_{t-1} = i) — transition matrix
    B_i(O_t) = N(O_t; μ_i, Σ_i)   — Gaussian emission probability

  Training (Baum-Welch / EM):
    E-step: Forward-backward algorithm to compute
      γ_t(i)  = P(S_t = i | O_{1:T}, λ)       — state occupancy
      ξ_t(i,j) = P(S_t=i, S_{t+1}=j | O_{1:T}) — transition occupancy
    M-step: Update π, A, μ_i, Σ_i to maximize expected log-likelihood.
    Repeat until convergence.

  Decoding (Viterbi):
    Find the most probable state sequence:
    S* = argmax_{S} P(S | O_{1:T}, λ)
    via dynamic programming in O(N²T).

States (4):
  Interpreted post-training by centroid characteristics:
  - Highest mean return + lowest vol  → Low-Vol Bull
  - Highest mean return, elevated vol → Momentum Bull
  - Mean return ≈ 0, elevated vol     → High-Vol / Distribution
  - Lowest mean return                → Bear / Markdown

Features:
  - Daily log return: r_t = ln(P_t / P_{t-1})
  - Normalized ATR: atr_t / P_t  (absolute volatility as fraction of price)
  - Log volume ratio: ln(V_t / EMA_20(V_t))  (unusual volume = institutional event)
"""
from __future__ import annotations

import warnings
import numpy as np
import pandas as pd

try:
    from hmmlearn.hmm import GaussianHMM
    HMM_AVAILABLE = True
except ImportError:
    HMM_AVAILABLE = False

from ta.volatility import AverageTrueRange
from ta.trend import EMAIndicator

N_STATES = 4
N_ITER   = 300
RANDOM_SEED = 42


# ── Feature construction ──────────────────────────────────────────────────────

def _build_features(df: pd.DataFrame) -> np.ndarray:
    close  = df["Close"]
    high   = df["High"]
    low    = df["Low"]
    volume = df["Volume"].replace(0, np.nan).ffill()

    log_return  = np.log(close / close.shift(1))
    atr         = AverageTrueRange(high, low, close, window=14).average_true_range()
    atr_pct     = atr / close
    ema20_vol   = EMAIndicator(volume, window=20).ema_indicator()
    log_vol_ratio = np.log((volume / ema20_vol.replace(0, np.nan)).clip(lower=1e-6))

    feat = pd.DataFrame({
        "log_return":    log_return,
        "atr_pct":       atr_pct,
        "log_vol_ratio": log_vol_ratio,
    }).dropna()

    return feat.values, feat.index


# ── State semantic labelling ──────────────────────────────────────────────────

def _label_states(means: np.ndarray) -> dict[int, dict]:
    """
    Map learned state indices to semantic regime labels.
    means[i] = [mean_log_return, mean_atr_pct, mean_log_vol_ratio] for state i.
    """
    ret_col = 0
    vol_col = 1

    sorted_by_ret = np.argsort(means[:, ret_col])
    bear_state     = int(sorted_by_ret[0])   # lowest mean return
    bull_fast      = int(sorted_by_ret[-1])  # highest mean return

    # Among remaining two, higher vol = distribution/panic
    remaining = [i for i in range(N_STATES) if i not in {bear_state, bull_fast}]
    vols = [(i, means[i, vol_col]) for i in remaining]
    vols_sorted = sorted(vols, key=lambda x: x[1], reverse=True)
    high_vol_state = vols_sorted[0][0]
    low_vol_bull   = vols_sorted[1][0]

    META = {
        bear_state:    {"label": "Bear",          "color": "#DC2626", "action": "Avoid longs. Short only if confirmed. Every bounce is a short-covering trap."},
        high_vol_state:{"label": "High Volatility","color": "#F59E0B", "action": "Reduce size 50%. Widen stops 2×. Institutions are distributing into volatility."},
        low_vol_bull:  {"label": "Accumulation",  "color": "#6366F1", "action": "Build positions slowly. Low volatility = stealth institutional buying. ATR-wide stops."},
        bull_fast:     {"label": "Markup",         "color": "#22C55E", "action": "Full size. Trail stops at SMA20. Momentum is institutional, not retail FOMO."},
    }
    return META


# ── Main entry point ──────────────────────────────────────────────────────────

def detect_hmm_regime(df: pd.DataFrame) -> dict:
    """
    Fit a 4-state Gaussian HMM to the price/volume features and return:
      - current_state: semantic label for the most recent regime
      - state_probs:   P(S_T = i | O_{1:T}) for i in {0,1,2,3}
      - transition_matrix: A[i][j] = P(state j | state i)  (persistence on diagonal)
      - history: last 60 bars with state label and color
      - viterbi: full decoded sequence for charting
    """
    if not HMM_AVAILABLE:
        return {"error": "hmmlearn not installed — run: pip install hmmlearn"}

    features, feat_idx = _build_features(df)
    if len(features) < 60:
        return {"error": "Need at least 60 bars of data for HMM fitting"}

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        model = GaussianHMM(
            n_components   = N_STATES,
            covariance_type= "full",
            n_iter         = N_ITER,
            random_state   = RANDOM_SEED,
            tol            = 1e-4,
        )
        model.fit(features)

    # Viterbi decoding — most probable state sequence
    viterbi_states = model.predict(features)

    # Posterior probabilities at each step (forward-backward)
    posteriors = model.predict_proba(features)

    # Current state probabilities (last observation)
    current_probs = posteriors[-1]
    current_state_idx = int(np.argmax(current_probs))

    state_meta = _label_states(model.means_)

    # Transition matrix with persistence interpretation
    A = model.transmat_
    transition = []
    for i in range(N_STATES):
        row = []
        for j in range(N_STATES):
            row.append(round(float(A[i, j]), 4))
        transition.append(row)

    # State labels in matrix order
    state_labels = [state_meta[i]["label"] for i in range(N_STATES)]

    # Half-life of each state (expected duration before switching)
    # E[duration in state i] = 1 / (1 - A_ii)  (geometric distribution)
    durations = {
        state_meta[i]["label"]: round(1.0 / max(1 - float(A[i, i]), 1e-6), 1)
        for i in range(N_STATES)
    }

    # Current state probabilities as named dict
    current_prob_named = {
        state_meta[i]["label"]: round(float(current_probs[i]) * 100, 1)
        for i in range(N_STATES)
    }

    # History — align Viterbi states with dates
    dates      = df.index[-len(viterbi_states):]
    close_vals = df["Close"].iloc[-len(viterbi_states):]
    history = []
    for i, (dt, price, state_idx) in enumerate(zip(dates, close_vals.values, viterbi_states)):
        meta = state_meta[int(state_idx)]
        history.append({
            "date":   dt.strftime("%Y-%m-%d") if hasattr(dt, "strftime") else str(dt),
            "price":  round(float(price), 4),
            "state":  meta["label"],
            "color":  meta["color"],
            "prob":   round(float(posteriors[i, int(state_idx)]) * 100, 1),
        })

    current_meta = state_meta[current_state_idx]

    # Log-likelihood per observation (model quality metric)
    log_prob = model.score(features) / len(features)

    return {
        "current_state":        current_meta["label"],
        "current_color":        current_meta["color"],
        "action":               current_meta["action"],
        "state_probabilities":  current_prob_named,
        "confidence":           round(float(current_probs[current_state_idx]) * 100, 1),
        "transition_matrix":    transition,
        "state_labels":         state_labels,
        "expected_durations_days": durations,
        "log_likelihood_per_obs": round(log_prob, 4),
        "n_states":             N_STATES,
        "n_observations":       len(features),
        "history":              history[-60:],
    }
