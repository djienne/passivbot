"""
DryRunMixin: paper trading simulation overlay.

Mix this in before any real exchange bot class to intercept all private
API calls.  Public endpoints (OHLCV, tickers, market metadata) continue
to use the real exchange so the bot's signal logic is exercised against
live data.

Usage (handled automatically by setup_bot when live.dry_run is true):
    DryRunBybitBot = type("DryRunBybitBot", (DryRunMixin, BybitBot), {})
    bot = DryRunBybitBot(config)
"""

import asyncio
import logging

from utils import utc_ms


class DryRunMixin:
    """Intercept every private exchange call for in-memory paper trading."""

    # ------------------------------------------------------------------ #
    #  Paper-state helpers                                                 #
    # ------------------------------------------------------------------ #

    def _ensure_dry_run_state(self):
        if getattr(self, "_dry_run_initialized", False):
            return
        from config_utils import get_optional_config_value

        raw = get_optional_config_value(self.config, "live.dry_run_wallet", 10000.0)
        try:
            self._dry_run_balance = float(raw) if raw is not None else 10000.0
        except (TypeError, ValueError):
            self._dry_run_balance = 10000.0
        # {(symbol, pside): {"size": float, "price": float}}
        self._dry_run_positions = {}
        self._dry_run_initialized = True
        logging.info(
            f"[DRY RUN] paper wallet initialised at {self._dry_run_balance} USDT"
        )

    # ------------------------------------------------------------------ #
    #  Overridden private endpoints                                        #
    # ------------------------------------------------------------------ #

    async def fetch_positions(self):
        """Return simulated positions and balance instead of querying exchange."""
        self._ensure_dry_run_state()
        positions = []
        now = utc_ms()
        for (symbol, pside), pos in self._dry_run_positions.items():
            if pos["size"] != 0.0:
                positions.append(
                    {
                        "symbol": symbol,
                        "position_side": pside,
                        "size": abs(pos["size"]),
                        "price": pos["price"],
                        "timestamp": now,
                    }
                )
        return positions, self._dry_run_balance

    async def fetch_open_orders(self, symbol=None):
        """All orders are immediately filled; there are never open orders."""
        return []

    async def execute_order(self, order: dict) -> dict:
        """Simulate an immediate fill at limit price and update paper state."""
        self._ensure_dry_run_state()

        symbol = order["symbol"]
        pside = order.get("position_side", "long")
        qty = abs(order.get("qty", order.get("amount", 0.0)))
        price = float(order["price"])
        reduce_only = order.get("reduce_only", False)
        c_mult = self.c_mults.get(symbol, 1.0) if hasattr(self, "c_mults") else 1.0

        key = (symbol, pside)

        if reduce_only:
            # Closing an existing position — realise PnL
            pos = self._dry_run_positions.get(key, {"size": 0.0, "price": 0.0})
            entry_price = pos["price"]
            if pside == "long":
                pnl = (price - entry_price) * qty * c_mult
            else:
                pnl = (entry_price - price) * qty * c_mult
            self._dry_run_balance += pnl
            new_size = max(0.0, pos["size"] - qty)
            if new_size == 0.0:
                self._dry_run_positions.pop(key, None)
            else:
                self._dry_run_positions[key] = {"size": new_size, "price": entry_price}
            logging.debug(
                f"[DRY RUN] close {pside} {symbol} qty={qty} @ {price}"
                f"  pnl={pnl:.4f}  balance={self._dry_run_balance:.2f}"
            )
        else:
            # Opening / adding to a position — update weighted average entry
            pos = self._dry_run_positions.get(key, {"size": 0.0, "price": 0.0})
            old_size = pos["size"]
            new_size = old_size + qty
            if new_size > 0:
                new_price = (pos["price"] * old_size + price * qty) / new_size
            else:
                new_price = price
            self._dry_run_positions[key] = {"size": new_size, "price": new_price}
            logging.debug(
                f"[DRY RUN] entry {pside} {symbol} qty={qty} @ {price}"
                f"  pos_size={new_size:.6f}  avg_price={new_price:.4f}"
            )

        return {
            "id": f"dry_run_{utc_ms()}",
            "symbol": symbol,
            "side": order.get("side", ""),
            "price": price,
            "amount": qty,
            "filled": qty,
            "remaining": 0.0,
            "status": "closed",
            "timestamp": utc_ms(),
        }

    async def execute_cancellation(self, order: dict) -> dict:
        """Simulate order cancellation (nothing to cancel in dry-run)."""
        return {"id": order.get("id", ""), "symbol": order.get("symbol", ""), "status": "canceled"}

    async def fetch_pnls(self, start_time=None, end_time=None, limit=None):
        """No historical fill records in dry-run mode."""
        return []

    async def init_pnls(self):
        """Skip fetching PnL history; start with an empty list."""
        self.pnls = []

    # ------------------------------------------------------------------ #
    #  Exchange config calls that would touch private endpoints            #
    # ------------------------------------------------------------------ #

    async def update_exchange_config(self):
        """Skip setting hedge mode / account type on the exchange."""
        pass

    async def update_exchange_config_by_symbols(self, symbols):
        """Skip setting per-symbol leverage / margin mode on the exchange."""
        pass

    async def determine_utc_offset(self, verbose=True):
        """Skip private fetch_balance() call; assume exchange is UTC."""
        self.utc_offset = 0
        if verbose:
            logging.info("[DRY RUN] assuming UTC offset = 0ms")

    async def watch_orders(self):
        """Idle loop replacing the private authenticated WS order stream."""
        while not self.stop_websocket:
            await asyncio.sleep(1.0)

    def did_create_order(self, executed) -> bool:
        """Accept any response that carries a non-None id (shadows exchange overrides)."""
        try:
            return "id" in executed and executed["id"] is not None
        except Exception:
            return False

    def did_cancel_order(self, executed, order=None) -> bool:
        """Accept any response that carries a non-None id (shadows exchange overrides)."""
        try:
            return "id" in executed and executed["id"] is not None
        except Exception:
            return False
