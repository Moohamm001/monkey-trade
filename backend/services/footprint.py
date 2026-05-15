"""
Phase 1 — Footprint Chart & Volume Profile (VPVR).

Reads raw tick data from SQLite and reconstructs:
  • Footprint candles  — buy/sell qty at every price level + order imbalance flags
  • VPVR               — Point of Control (POC), Value Area High/Low, full profile
"""
from __future__ import annotations

from pathlib import Path

import aiosqlite
import pandas as pd

DB_PATH = Path("data/ticks.db")

IMBALANCE_RATIO = 3.0   # flag a level when one side ≥ 3× the other


# ── Data access ───────────────────────────────────────────────────────────────

async def get_ticks(symbol: str, minutes: int = 60) -> pd.DataFrame:
    """Return all trades for *symbol* in the last *minutes* minutes."""
    cutoff_ms = int(
        (pd.Timestamp.utcnow().timestamp() - minutes * 60) * 1000
    )
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM trades WHERE symbol=? AND timestamp>=? ORDER BY timestamp",
            (symbol.upper(), cutoff_ms),
        )
        rows = await cur.fetchall()

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame([dict(r) for r in rows])
    df["dt"]       = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
    df["buy_qty"]  = df["quantity"] * (1 - df["is_buyer_maker"])   # taker buy
    df["sell_qty"] = df["quantity"] * df["is_buyer_maker"]         # taker sell
    return df


async def get_orderbook_snapshot(symbol: str) -> dict:
    """Return the most recent order-book snapshot for *symbol*."""
    import json
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM orderbook_snapshots WHERE symbol=? ORDER BY timestamp DESC LIMIT 1",
            (symbol.upper(),),
        )
        row = await cur.fetchone()
    if not row:
        return {}
    return {
        "timestamp": row["timestamp"],
        "bids": json.loads(row["bids"]),
        "asks": json.loads(row["asks"]),
    }


# ── Footprint ─────────────────────────────────────────────────────────────────

def build_footprint(
    df: pd.DataFrame,
    candle_minutes: int = 5,
    tick_size: float = 1.0,
) -> list[dict]:
    """
    Group ticks into N-minute candles.
    For each candle, bucket trades by price level and compute:
      • buy_qty / sell_qty per level
      • volume delta (total aggressive buys − sells)
      • imbalance flag (one side ≥ 3× the other at a given level)
    """
    if df.empty:
        return []

    df = df.copy()
    df["price_level"] = (df["price"] / tick_size).round() * tick_size
    df["bar"]         = df["dt"].dt.floor(f"{candle_minutes}min")

    candles = []
    for bar_time, g in df.groupby("bar"):
        o = float(g["price"].iloc[0])
        h = float(g["price"].max())
        l = float(g["price"].min())
        c = float(g["price"].iloc[-1])
        total_vol = float(g["quantity"].sum())
        delta     = float(g["buy_qty"].sum() - g["sell_qty"].sum())

        levels = []
        for price_lvl, lg in g.groupby("price_level"):
            bq = float(lg["buy_qty"].sum())
            sq = float(lg["sell_qty"].sum())
            imbalance = (
                (sq > 0 and bq / sq >= IMBALANCE_RATIO) or
                (bq > 0 and sq / bq >= IMBALANCE_RATIO)
            )
            levels.append({
                "price":    price_lvl,
                "buy_qty":  round(bq, 4),
                "sell_qty": round(sq, 4),
                "delta":    round(bq - sq, 4),
                "imbalance": imbalance,
            })

        candles.append({
            "time":   bar_time.isoformat(),
            "open":   o, "high": h, "low": l, "close": c,
            "volume": round(total_vol, 4),
            "delta":  round(delta, 4),
            "levels": sorted(levels, key=lambda x: x["price"], reverse=True),
        })

    return candles


# ── VPVR ──────────────────────────────────────────────────────────────────────

def calc_vpvr(
    df: pd.DataFrame,
    tick_size: float = 1.0,
    value_area_pct: float = 0.70,
) -> dict:
    """
    Volume Profile Visible Range.

    Algorithm:
      1. Bin all traded quantity by price level.
      2. POC = price level with the highest total volume.
      3. Expand outward from POC (always adding the higher-volume adjacent bin)
         until the accumulated volume covers value_area_pct of total volume.
      4. The boundary bins at that point are Value Area High (VAH) and Low (VAL).
    """
    if df.empty:
        return {}

    df = df.copy()
    df["price_level"] = (df["price"] / tick_size).round() * tick_size
    profile = (
        df.groupby("price_level")["quantity"]
        .sum()
        .reset_index()
        .rename(columns={"price_level": "price", "quantity": "volume"})
        .sort_values("price")
        .reset_index(drop=True)
    )

    total_vol  = float(profile["volume"].sum())
    poc_idx    = int(profile["volume"].idxmax())
    poc        = float(profile.loc[poc_idx, "price"])
    target_vol = total_vol * value_area_pct

    accumulated = float(profile.loc[poc_idx, "volume"])
    above = poc_idx + 1
    below = poc_idx - 1
    max_i = len(profile) - 1

    while accumulated < target_vol:
        vol_above = float(profile.loc[above, "volume"]) if above <= max_i else 0.0
        vol_below = float(profile.loc[below, "volume"]) if below >= 0    else 0.0
        if vol_above == 0 and vol_below == 0:
            break
        if vol_above >= vol_below:
            accumulated += vol_above
            above += 1
        else:
            accumulated += vol_below
            below -= 1

    vah = float(profile.loc[min(above - 1, max_i), "price"])
    val = float(profile.loc[max(below + 1, 0),     "price"])

    return {
        "poc":              poc,
        "value_area_high":  vah,
        "value_area_low":   val,
        "total_volume":     round(total_vol, 4),
        "value_area_pct":   value_area_pct,
        "profile": [
            {"price": float(r["price"]), "volume": round(float(r["volume"]), 4)}
            for _, r in profile.iterrows()
        ],
    }
