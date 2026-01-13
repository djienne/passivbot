"""
Utility functions for passivbot.

This module contains helper functions extracted from passivbot.py for
better organization and maintainability.
"""
from __future__ import annotations

import os
import sys
import inspect
import logging
import re
import asyncio
import signal
from typing import Optional

import passivbot_rust as pbr

# Optional imports for memory tracking
try:
    import psutil  # type: ignore
except Exception:
    psutil = None

try:
    import resource  # type: ignore
except Exception:
    resource = None


# Constants
DEFAULT_MAX_MEMORY_CANDLES_PER_SYMBOL = 20_000
ONE_MIN_MS = 60_000

# Regex patterns for order type ID parsing
# Match "...0xABCD..." anywhere (case-insensitive)
_TYPE_MARKER_RE = re.compile(r"0x([0-9a-fA-F]{4})", re.IGNORECASE)
# Leading pure-hex fallback: optional 0x then 4 hex at the very start
_LEADING_HEX4_RE = re.compile(r"^(?:0x)?([0-9a-fA-F]{4})", re.IGNORECASE)


def _get_process_rss_bytes() -> Optional[int]:
    """Return current process RSS in bytes or None if unavailable."""
    try:
        if psutil is not None:
            return int(psutil.Process(os.getpid()).memory_info().rss)
    except Exception:
        pass
    if resource is not None:
        try:
            usage = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
            if sys.platform.startswith("linux"):
                usage = int(usage) * 1024
            else:
                usage = int(usage)
            return int(usage)
        except Exception:
            pass
    return None


def custom_id_to_snake(custom_id) -> str:
    """Translate a broker custom id into the snake_case order type name."""
    try:
        return snake_of(try_decode_type_id_from_custom_id(custom_id))
    except Exception as e:
        logging.error(f"failed to convert custom_id {custom_id} to str order_type")
        return "unknown"


def try_decode_type_id_from_custom_id(custom_id: str) -> int | None:
    """Extract the 16-bit order type id encoded in a custom order id string."""
    # 1) Preferred: look for "...0x<4-hex>..." anywhere
    m = _TYPE_MARKER_RE.search(custom_id)
    if m:
        return int(m.group(1), 16)

    # 2) Fallback: if string is pure-hex style (no broker code), parse the leading 4
    m = _LEADING_HEX4_RE.match(custom_id)
    if m:
        return int(m.group(1), 16)

    return None


def order_type_id_to_hex4(type_id: int) -> str:
    """Return the four-hex-digit representation of an order type id."""
    return f"{type_id:04x}"


def type_token(type_id: int, with_marker: bool = True) -> str:
    """Return the printable order type marker, optionally prefixed with `0x`."""
    h4 = order_type_id_to_hex4(type_id)
    return ("0x" + h4) if with_marker else h4


def snake_of(type_id: int) -> str:
    """Map an order type id to its snake_case string representation."""
    try:
        return pbr.order_type_id_to_snake(type_id)
    except Exception:
        return "unknown"


def calc_pnl(position_side, entry_price, close_price, qty, inverse, c_mult):
    """Calculate trade PnL by delegating to the appropriate Rust helper."""
    try:
        if isinstance(position_side, str):
            if position_side == "long":
                return pbr.calc_pnl_long(entry_price, close_price, qty, c_mult)
            else:
                return pbr.calc_pnl_short(entry_price, close_price, qty, c_mult)
        else:
            # fallback: assume long
            return pbr.calc_pnl_long(entry_price, close_price, qty, c_mult)
    except Exception:
        # rethrow to preserve behavior
        raise


def signal_handler(sig, frame):
    """Handle SIGINT by signalling the running bot to stop gracefully."""
    print("\nReceived shutdown signal. Stopping bot...")
    bot = globals().get("bot")
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = None

    if bot is not None:
        bot.stop_signal_received = True
        if loop is not None:
            shutdown_task = getattr(bot, "_shutdown_task", None)
            if shutdown_task is None or shutdown_task.done():
                bot._shutdown_task = loop.create_task(bot.shutdown_gracefully())
            loop.call_soon_threadsafe(lambda: None)
    elif loop is not None:
        loop.call_soon_threadsafe(loop.stop)


def get_function_name():
    """Return the caller function name one frame above the current scope."""
    return inspect.currentframe().f_back.f_code.co_name


def get_caller_name():
    """Return the caller name two frames above the current scope."""
    return inspect.currentframe().f_back.f_back.f_code.co_name


def or_default(f, *args, default=None, **kwargs):
    """Execute `f` safely, returning `default` if an exception is raised."""
    try:
        return f(*args, **kwargs)
    except:
        return default


def orders_matching(o0, o1, tolerance_qty=0.01, tolerance_price=0.002):
    """Return True if two orders are equivalent within the supplied tolerances."""
    for k in ["symbol", "side", "position_side"]:
        if o0[k] != o1[k]:
            return False
    if tolerance_price:
        if abs(o0["price"] - o1["price"]) / o0["price"] > tolerance_price:
            return False
    else:
        if o0["price"] != o1["price"]:
            return False
    if tolerance_qty:
        if abs(o0["qty"] - o1["qty"]) / o0["qty"] > tolerance_qty:
            return False
    else:
        if o0["qty"] != o1["qty"]:
            return False
    return True


def order_has_match(order, orders, tolerance_qty=0.01, tolerance_price=0.002):
    """Return the first matching order in `orders` or False if none match."""
    for elm in orders:
        if orders_matching(order, elm, tolerance_qty, tolerance_price):
            return elm
    return False
