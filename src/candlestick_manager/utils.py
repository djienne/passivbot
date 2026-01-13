"""
Utility functions for the CandlestickManager.
"""
from __future__ import annotations

import inspect
import logging
import re
import time
from typing import Optional

import numpy as np

from .types import ONE_MIN_MS, CANDLE_DTYPE


def get_caller_name(depth: int = 2, logger: Optional[logging.Logger] = None) -> str:
    """Return a more useful origin for debug logs.

    Heuristics:
    - Skip CandlestickManager frames and common wrappers ("one", "<listcomp>", asyncio internals)
    - Prefer frames from a Passivbot instance method if present (module contains "passivbot")
    - Otherwise return the first non-wrapper frame as module.Class.func or module.func
    """

    def frame_to_name(fr) -> str:
        try:
            func = getattr(fr.f_code, "co_name", "unknown")
            mod = fr.f_globals.get("__name__", None)
            cls = None
            if "self" in fr.f_locals and fr.f_locals["self"] is not None:
                cls = type(fr.f_locals["self"]).__name__
            elif "cls" in fr.f_locals and fr.f_locals["cls"] is not None:
                cls = getattr(fr.f_locals["cls"], "__name__", None)
            parts = []
            if isinstance(mod, str) and mod:
                parts.append(mod)
            if isinstance(cls, str) and cls:
                parts.append(cls)
            if isinstance(func, str) and func:
                parts.append(func)
            return ".".join(parts) if parts else "unknown"
        except Exception:
            return "unknown"

    frame = inspect.currentframe()
    target = frame
    fallback_name = "unknown"
    try:
        # Initial hop
        for _ in range(max(0, int(depth))):
            if target is None:
                break
            target = target.f_back  # type: ignore[attr-defined]
        if target is not None:
            fallback_name = frame_to_name(target)

        # Walk up to find a meaningful caller
        cur = target
        preferred: Optional[str] = None
        for _ in range(20):  # safety cap
            if cur is None:
                break
            try:
                slf = cur.f_locals.get("self") if hasattr(cur, "f_locals") else None
                is_cm = slf is not None and type(slf).__name__ == "CandlestickManager"
            except Exception:
                is_cm = False
            func = getattr(getattr(cur, "f_code", None), "co_name", "")
            mod = None
            try:
                mod = cur.f_globals.get("__name__")
            except Exception:
                mod = None

            # Skip common wrappers and asyncio internals
            skip_names = {
                "one",
                "<listcomp>",
                "<dictcomp>",
                "<lambda>",
                "_run",
                "gather",
                "create_task",
            }
            is_asyncio = isinstance(mod, str) and (
                mod.startswith("asyncio.") or mod == "asyncio.events"
            )
            if not is_cm and func not in skip_names and not is_asyncio:
                name = frame_to_name(cur)
                if isinstance(mod, str) and "passivbot" in mod and name and name != "unknown":
                    # Prefer first passivbot frame
                    preferred = name
                    break
                if name and name != "unknown" and preferred is None:
                    preferred = name
            cur = cur.f_back  # type: ignore[attr-defined]
    finally:
        try:
            del frame
        except Exception:
            pass
        try:
            del target  # type: ignore[name-defined]
        except Exception:
            pass
    return preferred or fallback_name


def _utc_now_ms() -> int:
    return int(time.time() * 1000)


def _floor_minute(ms: int) -> int:
    return (int(ms) // ONE_MIN_MS) * ONE_MIN_MS


def _ensure_dtype(a: np.ndarray) -> np.ndarray:
    if a.dtype != CANDLE_DTYPE:
        return a.astype(CANDLE_DTYPE, copy=False)
    return a


def _ts_index(a: np.ndarray) -> np.ndarray:
    """Return sorted ts column as plain int64 array."""
    if a.size == 0:
        return np.empty((0,), dtype=np.int64)
    return np.asarray(a["ts"], dtype=np.int64)


def _sanitize_symbol(symbol: str) -> str:
    return symbol.replace("/", "_")


def _tf_to_ms(s: Optional[str]) -> int:
    """Parse timeframe string like '1m','5m','1h','1d' to milliseconds.

    Falls back to ONE_MIN_MS on invalid input. Seconds are rounded down to minutes.
    """
    if not s:
        return ONE_MIN_MS
    try:
        st = s.strip().lower()
    except Exception:
        return ONE_MIN_MS

    m = re.fullmatch(r"(\d+)([smhd])", st)
    if not m:
        return ONE_MIN_MS
    n, unit = int(m.group(1)), m.group(2)
    if unit == "s":
        return max(ONE_MIN_MS, (n // 60) * ONE_MIN_MS)
    if unit == "m":
        return n * ONE_MIN_MS
    if unit == "h":
        return n * 60 * ONE_MIN_MS
    if unit == "d":
        return n * 1440 * ONE_MIN_MS
    return ONE_MIN_MS
