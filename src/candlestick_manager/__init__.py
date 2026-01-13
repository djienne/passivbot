"""
CandlestickManager package.

Re-exports the public API for backward compatibility.
"""
from .types import (
    CANDLE_DTYPE,
    ONE_MIN_MS,
    EMA_SERIES_DTYPE,
    _LockRecord,
)
from .manager import (
    CandlestickManager,
    _floor_minute,
)

__all__ = [
    "CandlestickManager",
    "CANDLE_DTYPE",
    "ONE_MIN_MS",
    "EMA_SERIES_DTYPE",
    "_floor_minute",
    "_LockRecord",
]
