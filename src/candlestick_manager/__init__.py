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
from .utils import (
    _floor_minute,
)
from .manager import (
    CandlestickManager,
)

__all__ = [
    "CandlestickManager",
    "CANDLE_DTYPE",
    "ONE_MIN_MS",
    "EMA_SERIES_DTYPE",
    "_floor_minute",
    "_LockRecord",
]
