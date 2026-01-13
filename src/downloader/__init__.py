"""
Downloader package.

Re-exports the public API for backward compatibility.
"""
# Re-export ccxt for tests that access downloader.ccxt
import ccxt.async_support as ccxt

from .warmup import (
    compute_backtest_warmup_minutes,
    compute_per_coin_warmup_minutes,
)

from .main import (
    # Data I/O functions
    dump_ohlcv_data,
    load_ohlcv_data,
    ensure_millis,
    get_days_in_between,
    deduplicate_rows,
    fill_gaps_in_ohlcvs,
    attempt_gap_fix_ohlcvs,
    # Orchestration functions
    prepare_hlcvs,
    prepare_hlcvs_combined,
    compute_exchange_volume_ratios,
    # OHLCVManager class
    OHLCVManager,
)

# Re-export from utils for backward compatibility
# (some code imports these from downloader instead of utils)
from utils import (
    coin_to_symbol,
    load_markets,
    utc_ms,
    normalize_exchange_name,
)

__all__ = [
    # CCXT module
    "ccxt",
    # Warmup functions
    "compute_backtest_warmup_minutes",
    "compute_per_coin_warmup_minutes",
    # Data I/O
    "dump_ohlcv_data",
    "load_ohlcv_data",
    "ensure_millis",
    "get_days_in_between",
    "deduplicate_rows",
    "fill_gaps_in_ohlcvs",
    "attempt_gap_fix_ohlcvs",
    # Orchestration
    "prepare_hlcvs",
    "prepare_hlcvs_combined",
    "compute_exchange_volume_ratios",
    # Class
    "OHLCVManager",
    # Backward compatibility re-exports from utils
    "coin_to_symbol",
    "load_markets",
    "utc_ms",
    "normalize_exchange_name",
]
