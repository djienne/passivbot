"""
Type definitions and constants for the CandlestickManager.
"""
from dataclasses import dataclass
import numpy as np
import portalocker  # type: ignore

# Time constants
ONE_MIN_MS = 60_000

# Lock configuration
_LOCK_TIMEOUT_SECONDS = 10.0
_LOCK_STALE_SECONDS = 180.0
_LOCK_BACKOFF_INITIAL = 0.1
_LOCK_BACKOFF_MAX = 2.0


@dataclass
class _LockRecord:
    """Record for tracking held locks with reentrant counting."""
    lock: portalocker.Lock
    count: int
    acquired_at: float


# Structured array dtype for OHLCV candles
CANDLE_DTYPE = np.dtype(
    [
        ("ts", "int64"),      # Timestamp in milliseconds
        ("o", "float32"),     # Open price
        ("h", "float32"),     # High price
        ("l", "float32"),     # Low price
        ("c", "float32"),     # Close price
        ("bv", "float32"),    # Base volume
    ]
)

# Structured array dtype for EMA series
EMA_SERIES_DTYPE = np.dtype(
    [
        ("ts", "int64"),      # Timestamp in milliseconds
        ("ema", "float32"),   # EMA value
    ]
)
