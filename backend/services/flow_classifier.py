"""
Phase 2 — Institutional Flow Classifier (SVM).

Binary classification per 1-minute bar:
  1 = Institutional Accumulation / Distribution
  0 = Retail Flow

Features engineered from tick data:
  • vol_delta_norm   — normalised volume delta (buy aggression vs sell aggression)
  • avg_trade_size   — mean quantity per trade (institutions trade large)
  • n_trades         — trade count (institutions may be infrequent but large)
  • close_vs_vwap    — price closing relative to VWAP (directional intent)
  • buy_ratio        — fraction of volume from aggressive buyers

Labelling strategy (unsupervised bootstrap):
  Bars in the top N-th percentile of both avg_trade_size AND |vol_delta_norm|
  are labelled Institutional. This heuristic reflects the empirical observation
  that institutions trade large and with directional conviction.

Architecture note for scaling to Deep Learning (CNN / LSTM):
  The feature engineering step produces a (T × 5) matrix per session.
  Replacing the SVM with a 1-D CNN over a rolling 30-bar window captures
  sequential order-book dynamics without hand-crafted features.
  An LSTM layer after the CNN adds memory of prior bars (drift detection).
  The same sklearn Pipeline interface is preserved — swap `svm` step for
  a Keras wrapper (scikeras) to maintain the predict / predict_proba API.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.metrics import classification_report, confusion_matrix
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC

FEATURE_COLS = [
    "vol_delta_norm",
    "avg_trade_size",
    "n_trades",
    "close_vs_vwap",
    "buy_ratio",
]
INSTITUTIONAL_PERCENTILE = 75   # top-quartile bars get label=1


# ── Feature Engineering ───────────────────────────────────────────────────────

def build_features(df_ticks: pd.DataFrame) -> pd.DataFrame:
    """Aggregate raw ticks into 1-minute bars with institutional features."""
    if df_ticks.empty:
        return pd.DataFrame()

    df = df_ticks.copy()
    df["bar"] = df["dt"].dt.floor("1min")
    rows = []

    for bar_time, g in df.groupby("bar"):
        total_qty = float(g["quantity"].sum())
        buy_qty   = float(g["buy_qty"].sum())
        sell_qty  = float(g["sell_qty"].sum())
        n_trades  = len(g)
        avg_size  = total_qty / (n_trades + 1e-9)
        delta     = buy_qty - sell_qty
        delta_n   = delta / (total_qty + 1e-9)

        price_range = g["price"].max() - g["price"].min()
        vwap = float((g["price"] * g["quantity"]).sum()) / (total_qty + 1e-9)
        close_vs_v  = (float(g["price"].iloc[-1]) - vwap) / (price_range + 1e-9)

        rows.append({
            "bar":           bar_time,
            "vol_delta_norm": delta_n,
            "avg_trade_size": avg_size,
            "n_trades":       n_trades,
            "close_vs_vwap":  close_vs_v,
            "buy_ratio":      buy_qty / (total_qty + 1e-9),
        })

    return pd.DataFrame(rows).dropna()


def _auto_label(feat_df: pd.DataFrame) -> np.ndarray:
    size_t  = feat_df["avg_trade_size"].quantile(INSTITUTIONAL_PERCENTILE / 100)
    delta_t = feat_df["vol_delta_norm"].abs().quantile(INSTITUTIONAL_PERCENTILE / 100)
    labels  = (
        (feat_df["avg_trade_size"] >= size_t) |
        (feat_df["vol_delta_norm"].abs() >= delta_t)
    ).astype(int).values
    return labels


# ── Training ──────────────────────────────────────────────────────────────────

def train_classifier(feat_df: pd.DataFrame) -> tuple[Pipeline | None, dict]:
    """
    Train an RBF-SVM on auto-labelled 1-minute bar features.
    Returns (pipeline, metrics_dict).
    """
    if len(feat_df) < 30:
        return None, {"error": "Need at least 30 minutes of tick data to train"}

    X = feat_df[FEATURE_COLS].values
    y = _auto_label(feat_df)

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y if y.sum() > 1 else None
    )

    pipeline = Pipeline([
        ("scaler", StandardScaler()),
        ("svm",    SVC(kernel="rbf", C=1.0, gamma="scale", probability=True)),
    ])
    pipeline.fit(X_train, y_train)

    y_pred  = pipeline.predict(X_test)
    cm      = confusion_matrix(y_test, y_pred).tolist()
    report  = classification_report(
        y_test, y_pred,
        target_names=["Retail", "Institutional"],
        output_dict=True,
        zero_division=0,
    )

    return pipeline, {
        "confusion_matrix":             cm,
        "accuracy":                     round(float(report["accuracy"]), 4),
        "institutional_precision":      round(float(report["Institutional"]["precision"]), 4),
        "institutional_recall":         round(float(report["Institutional"]["recall"]), 4),
        "retail_precision":             round(float(report["Retail"]["precision"]), 4),
        "samples_trained":              int(len(X_train)),
        "samples_tested":               int(len(X_test)),
        "institutional_pct_in_dataset": round(float(y.mean()) * 100, 1),
    }


# ── Inference ─────────────────────────────────────────────────────────────────

def predict_flow(pipeline: Pipeline, latest: dict) -> dict:
    """
    Predict whether the latest 1-minute bar is institutional or retail.
    *latest* is a dict with the same keys as FEATURE_COLS.
    """
    X    = np.array([[latest.get(c, 0.0) for c in FEATURE_COLS]])
    pred = int(pipeline.predict(X)[0])
    prob = pipeline.predict_proba(X)[0]

    return {
        "signal":               pred,
        "label":                "Institutional" if pred == 1 else "Retail",
        "confidence":           round(float(max(prob)) * 100, 1),
        "prob_retail":          round(float(prob[0]) * 100, 1),
        "prob_institutional":   round(float(prob[1]) * 100, 1),
    }
