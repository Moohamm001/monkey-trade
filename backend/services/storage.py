"""
Safe JSON storage — atomic writes + per-path locks.

Why this exists:
  Multiple code paths read-modify-write the same JSON files:
    • SSE bot scan → portfolio.open_position()
    • Daily review → portfolio.close_position(), snapshot_equity()
    • Concurrent forwardtest CRUD → save_store()
    • Model updates during scoring + learning from closes

  Without locking, a `load → modify → save` sequence in one thread can be
  overwritten by another thread's save in between. Symptoms: cash balance
  silently desyncs from open positions, learned weights revert, closed
  trades reappear as open.

  Without atomic writes, a crash mid-`json.dump()` leaves a half-written
  file that fails to parse on next load — wiping the entire state.

This module provides both: per-file threading.Lock + write-to-tmp-then-replace.
"""
from __future__ import annotations

import json
import os
import threading
from contextlib import contextmanager
from typing import Any

# One lock per absolute path. Created lazily on first access.
_LOCKS: dict[str, threading.Lock] = {}
_LOCKS_GUARD = threading.Lock()


def _lock_for(path: str) -> threading.Lock:
    abspath = os.path.abspath(path)
    with _LOCKS_GUARD:
        if abspath not in _LOCKS:
            _LOCKS[abspath] = threading.Lock()
        return _LOCKS[abspath]


@contextmanager
def locked(path: str):
    """Hold the lock for `path` for the duration of the block."""
    lock = _lock_for(path)
    lock.acquire()
    try:
        yield
    finally:
        lock.release()


def atomic_write_json(path: str, data: Any, *, indent: int = 2) -> None:
    """
    Write JSON atomically: dump to <path>.tmp then os.replace() to final path.
    os.replace() is atomic on both POSIX and Windows for files on the same
    filesystem. A crash mid-write leaves the original file intact.
    """
    abspath = os.path.abspath(path)
    os.makedirs(os.path.dirname(abspath), exist_ok=True)
    tmp = abspath + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=indent, default=str)
        f.flush()
        try:
            os.fsync(f.fileno())   # force OS buffers to disk before rename
        except OSError:
            pass                    # fsync not available on some platforms
    os.replace(tmp, abspath)


def safe_load_json(path: str, default: Any) -> Any:
    """
    Load JSON, returning `default` if the file is missing OR unparseable
    (e.g. if a previous run was killed mid-write and atomic_write was not
    yet in use). Recovery is preferable to crash.
    """
    if not os.path.exists(path):
        return default
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return default


@contextmanager
def transaction(path: str, default: Any):
    """
    Locked read-modify-write transaction.

    Usage:
        with transaction(PATH, default={"items": []}) as data:
            data["items"].append(new_item)
        # data is auto-saved atomically on exit (if no exception)
    """
    lock = _lock_for(path)
    lock.acquire()
    try:
        data = safe_load_json(path, default)
        yield data
        atomic_write_json(path, data)
    finally:
        lock.release()
