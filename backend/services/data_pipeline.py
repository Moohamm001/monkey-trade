"""
Phase 1 — Real-time Tick & Order Book ingestion via Binance WebSockets.
Batches inserts into SQLite asynchronously to minimise latency.
"""
import asyncio
import json
import time
from pathlib import Path

import aiosqlite
import websockets

DB_PATH = Path("data/ticks.db")


async def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS trades (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol          TEXT    NOT NULL,
                timestamp       INTEGER NOT NULL,
                price           REAL    NOT NULL,
                quantity        REAL    NOT NULL,
                is_buyer_maker  INTEGER NOT NULL,
                trade_id        INTEGER
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS orderbook_snapshots (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol    TEXT    NOT NULL,
                timestamp INTEGER NOT NULL,
                bids      TEXT    NOT NULL,
                asks      TEXT    NOT NULL
            )
        """)
        await db.execute(
            "CREATE INDEX IF NOT EXISTS idx_trades_sym_ts ON trades(symbol, timestamp)"
        )
        await db.commit()


class TickPipeline:
    """
    Opens two Binance WebSocket streams per symbol:
      • aggTrade  — every matched trade (price, qty, buyer/seller aggressor)
      • depth5    — top-5 bid/ask ladder snapshot every 100 ms

    Trades are batched in memory and flushed to SQLite every BATCH_SIZE ticks
    to amortise write overhead without sacrificing data completeness.
    Order-book snapshots are written one-by-one (lower throughput, richer data).
    """

    BATCH_SIZE      = 100
    RECONNECT_DELAY = 3   # seconds before reconnect on error

    def __init__(self, symbol: str = "BTCUSDT"):
        self.symbol    = symbol.upper()
        self._batch:  list = []
        self._running = False

    # ── Internal helpers ──────────────────────────────────────────────────────

    async def _flush(self) -> None:
        if not self._batch:
            return
        async with aiosqlite.connect(DB_PATH) as db:
            await db.executemany(
                "INSERT INTO trades (symbol,timestamp,price,quantity,is_buyer_maker,trade_id) "
                "VALUES (?,?,?,?,?,?)",
                self._batch,
            )
            await db.commit()
        self._batch.clear()

    async def _trade_stream(self) -> None:
        url = f"wss://stream.binance.com:9443/ws/{self.symbol.lower()}@aggTrade"
        while self._running:
            try:
                async with websockets.connect(url, ping_interval=20) as ws:
                    async for raw in ws:
                        if not self._running:
                            break
                        d = json.loads(raw)
                        self._batch.append((
                            self.symbol,
                            d["T"],                     # trade time ms
                            float(d["p"]),              # price
                            float(d["q"]),              # quantity
                            1 if d["m"] else 0,         # 1 = seller was aggressor
                            d["a"],                     # agg trade id
                        ))
                        if len(self._batch) >= self.BATCH_SIZE:
                            await self._flush()
            except Exception as exc:
                print(f"[TickPipeline:{self.symbol}] trade stream error: {exc}. "
                      f"Reconnecting in {self.RECONNECT_DELAY}s…")
                await self._flush()
                await asyncio.sleep(self.RECONNECT_DELAY)

    async def _orderbook_stream(self) -> None:
        url = f"wss://stream.binance.com:9443/ws/{self.symbol.lower()}@depth5@100ms"
        while self._running:
            try:
                async with websockets.connect(url, ping_interval=20) as ws:
                    async for raw in ws:
                        if not self._running:
                            break
                        d = json.loads(raw)
                        async with aiosqlite.connect(DB_PATH) as db:
                            await db.execute(
                                "INSERT INTO orderbook_snapshots (symbol,timestamp,bids,asks) "
                                "VALUES (?,?,?,?)",
                                (
                                    self.symbol,
                                    int(time.time() * 1000),
                                    json.dumps(d.get("bids", [])),
                                    json.dumps(d.get("asks", [])),
                                ),
                            )
                            await db.commit()
            except Exception as exc:
                print(f"[TickPipeline:{self.symbol}] orderbook stream error: {exc}. "
                      f"Reconnecting in {self.RECONNECT_DELAY}s…")
                await asyncio.sleep(self.RECONNECT_DELAY)

    # ── Public API ────────────────────────────────────────────────────────────

    async def start(self) -> None:
        """Run both streams concurrently (call from a background task)."""
        self._running = True
        await init_db()
        await asyncio.gather(
            self._trade_stream(),
            self._orderbook_stream(),
        )

    def stop(self) -> None:
        self._running = False
