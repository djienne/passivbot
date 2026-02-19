#!/usr/bin/env python3
"""
Passivbot Balance Calculator - Command Line Version (Hyperliquid)

Calculates the minimum required balance for a given passivbot configuration.

Usage:
    python calculate_required_balance.py --config configs/config_hype.json
    python calculate_required_balance.py --config configs/config_hype.json --buffer 0.2  # 20% buffer

The calculator uses the formula matching the real trading engine (src/passivbot.py):
    effective_min_cost = max(min_qty * price * contract_size, min_cost)
    wallet_exposure_per_position = total_wallet_exposure_limit / n_positions
    required_balance = effective_min_cost / (wallet_exposure_per_position * entry_initial_qty_pct)

Hyperliquid min_cost default (10.0) and multiplier (1.01) are applied to match live behavior.
"""

import argparse
import json
import sys
from pathlib import Path
from decimal import Decimal, ROUND_UP
from typing import Dict, List, Any

try:
    import ccxt
except ImportError:
    print("Error: ccxt library not installed")
    print("Install it with: pip install ccxt")
    sys.exit(1)


class BalanceCalculator:
    def __init__(self, config_path: str, buffer: float = 0.1):
        self.config_path = Path(config_path)
        self.config = self.load_config()
        self.exchange_id = "hyperliquid"
        self.buffer = buffer
        self.exchange = self.init_exchange()

    def load_config(self) -> Dict[str, Any]:
        """Load and parse the configuration file."""
        if not self.config_path.exists():
            print(f"Error: Config file not found: {self.config_path}")
            sys.exit(1)

        try:
            with open(self.config_path, 'r') as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            print(f"Error: Invalid JSON in config file: {e}")
            sys.exit(1)

    def init_exchange(self) -> ccxt.Exchange:
        """Initialize the ccxt exchange."""
        try:
            exchange_class = getattr(ccxt, self.exchange_id)
            exchange = exchange_class({
                'enableRateLimit': True,
                'options': {'defaultType': 'swap'}  # Use perpetual futures
            })
            return exchange
        except AttributeError:
            print(f"Error: Exchange '{self.exchange_id}' not found in ccxt")
            print(f"Available exchanges: {', '.join(ccxt.exchanges[:10])}...")
            sys.exit(1)

    def _apply_exchange_min_cost_default(self, min_cost) -> float:
        """Apply Hyperliquid min_cost default matching real trading code.

        When ccxt returns None for min_cost, default to 10.0.
        Then multiply by 1.01 (see src/exchanges/hyperliquid.py:70).
        """
        if min_cost is None:
            min_cost = 10.0
        min_cost = round(min_cost * 1.01, 2)
        return min_cost

    def get_approved_coins(self) -> Dict[str, List[str]]:
        """Get approved coins from config."""
        approved = self.config.get("live", {}).get("approved_coins", {})
        return {
            "long": approved.get("long", []),
            "short": approved.get("short", [])
        }

    def fetch_symbol_info(self, symbol: str) -> Dict[str, Any]:
        """Fetch symbol information from exchange."""
        try:
            # Normalize coin name: strip quote suffixes (e.g., HYPEUSDT -> HYPE)
            # Matches src/utils.py symbol_to_coin() logic
            coin = symbol
            if '/' not in coin:
                for suffix in ["USDT", "USDC", "BUSD", "USD", ":"]:
                    coin = coin.replace(suffix, "")
                symbol_formatted = f"{coin}/USDC:USDC"
            else:
                symbol_formatted = symbol

            # Load markets
            self.exchange.load_markets()

            # Get market info
            if symbol_formatted not in self.exchange.markets:
                # Try without :USDC suffix
                symbol_formatted = f"{coin}/USDC"
                if symbol_formatted not in self.exchange.markets:
                    return None

            market = self.exchange.markets[symbol_formatted]

            # Get current ticker price
            ticker = self.exchange.fetch_ticker(symbol_formatted)
            price = ticker['last']

            # Get minimum order cost and amount from exchange
            min_cost = market.get('limits', {}).get('cost', {}).get('min')
            min_amount = market.get('limits', {}).get('amount', {}).get('min')
            contract_size = market.get('contractSize', 1) or 1

            # Apply exchange-specific min_cost defaults (matching real trading code)
            min_cost = self._apply_exchange_min_cost_default(min_cost)

            # Calculate effective_min_cost matching real trading code:
            #   effective_min_cost = max(qty_to_cost(min_qty, price, c_mult), min_cost)
            # This uses max() of both constraints, not if/elif
            min_cost_from_qty = (min_amount * price * contract_size) if (min_amount and min_amount > 0 and price) else 0
            min_cost_flat = min_cost if (min_cost and min_cost > 0) else 0
            min_order_price = max(min_cost_from_qty, min_cost_flat)
            if min_order_price <= 0:
                min_order_price = 5.0  # fallback

            return {
                "symbol": symbol,
                "symbol_formatted": symbol_formatted,
                "price": price,
                "min_order_price": min_order_price,
                "min_cost": min_cost,
                "min_amount": min_amount,
                "contract_size": market.get('contractSize', 1),
                "max_leverage": market.get('limits', {}).get('leverage', {}).get('max', 10)
            }
        except Exception as e:
            print(f"Warning: Could not fetch info for {symbol}: {e}")
            return None

    def calculate_balance_for_coin(self, symbol: str, side: str, symbol_info: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate required balance for a specific coin and side."""
        bot_config = self.config.get("bot", {}).get(side, {})

        n_positions = bot_config.get("n_positions", 0)
        total_wallet_exposure_limit = bot_config.get("total_wallet_exposure_limit", 0)
        entry_initial_qty_pct = bot_config.get("entry_initial_qty_pct", 0.01)

        if n_positions == 0 or total_wallet_exposure_limit == 0:
            return None

        # Use Decimal for precise calculations
        twe = Decimal(str(total_wallet_exposure_limit))
        n_pos = Decimal(str(n_positions))
        entry_pct = Decimal(str(entry_initial_qty_pct))
        min_price = Decimal(str(symbol_info['min_order_price']))

        # Calculate wallet exposure per position
        we_per_position = twe / n_pos

        # Calculate required balance
        # Formula: min_order_price / (wallet_exposure_per_position * entry_initial_qty_pct)
        required_balance = min_price / (we_per_position * entry_pct)

        # Add buffer and round up to nearest 10
        balance_with_buffer = required_balance * Decimal(str(1 + self.buffer))
        recommended = (balance_with_buffer / Decimal('10')).quantize(Decimal('1'), rounding=ROUND_UP) * Decimal('10')

        return {
            "symbol": symbol,
            "side": side,
            "min_order_price": float(min_price),
            "current_price": symbol_info['price'],
            "total_wallet_exposure_limit": float(twe),
            "n_positions": int(n_pos),
            "entry_initial_qty_pct": float(entry_pct),
            "wallet_exposure_per_position": float(we_per_position),
            "required_balance": float(required_balance),
            "recommended_balance": int(recommended),
            "buffer_pct": self.buffer * 100
        }

    def calculate(self) -> List[Dict[str, Any]]:
        """Calculate required balance for all approved coins."""
        approved_coins = self.get_approved_coins()
        all_coins = set(approved_coins["long"] + approved_coins["short"])

        if not all_coins:
            print("Error: No approved coins found in config")
            sys.exit(1)

        results = []

        print(f"\nFetching coin information from {self.exchange_id}...")
        print(f"Approved coins: {', '.join(sorted(all_coins))}\n")

        for coin in sorted(all_coins):
            print(f"Fetching {coin}...", end=" ")
            symbol_info = self.fetch_symbol_info(coin)

            if not symbol_info:
                print("FAILED")
                continue

            print("OK")

            # Calculate for long side
            if coin in approved_coins["long"]:
                result = self.calculate_balance_for_coin(coin, "long", symbol_info)
                if result:
                    results.append(result)

            # Calculate for short side
            if coin in approved_coins["short"]:
                result = self.calculate_balance_for_coin(coin, "short", symbol_info)
                if result:
                    results.append(result)

        return results

    def print_results(self, results: List[Dict[str, Any]]):
        """Print calculation results in a formatted table."""
        if not results:
            print("\nNo results to display")
            return

        # Find the result with highest required balance
        highest = max(results, key=lambda x: x['required_balance'])

        print("\n" + "=" * 100)
        print("BALANCE CALCULATION RESULTS".center(100))
        print("=" * 100)
        print(f"\nConfig: {self.config_path.name}")
        print(f"Exchange: {self.exchange_id}")
        print(f"Buffer: {self.buffer * 100:.0f}%\n")

        # Print detailed calculation for highest requirement
        print("-" * 100)
        print(f"HIGHEST REQUIREMENT: {highest['symbol']} ({highest['side'].upper()} side)".center(100))
        print("-" * 100)
        print(f"  Current Price:                     ${highest['current_price']:.4f}")
        print(f"  Minimum Order Price:               ${highest['min_order_price']:.2f}")
        print(f"  Total Wallet Exposure Limit:       {highest['total_wallet_exposure_limit']:.2f}")
        print(f"  Number of Positions:               {highest['n_positions']}")
        print(f"  Entry Initial Qty %:               {highest['entry_initial_qty_pct']:.4f} ({highest['entry_initial_qty_pct']*100:.2f}%)")
        print(f"  Wallet Exposure per Position:      {highest['wallet_exposure_per_position']:.4f}")
        print()
        print(f"  Formula: min_order_price / (wallet_exposure_per_position x entry_initial_qty_pct)")
        print(f"  Calculation: {highest['min_order_price']:.2f} / ({highest['wallet_exposure_per_position']:.4f} x {highest['entry_initial_qty_pct']:.4f})")
        print(f"  = {highest['min_order_price']:.2f} / {highest['wallet_exposure_per_position'] * highest['entry_initial_qty_pct']:.6f}")
        print(f"  = ${highest['required_balance']:.2f}")
        print()
        print(f"  -> Required Balance (minimum):      ${highest['required_balance']:.2f}")
        print(f"  -> Recommended Balance (+{self.buffer*100:.0f}%):      ${highest['recommended_balance']:.0f} USDT")
        print("-" * 100)

        # Print summary table for all coins
        if len(results) > 1:
            print("\nALL COINS SUMMARY:")
            print("-" * 100)
            print(f"{'Symbol':<10} {'Side':<6} {'Price':<12} {'Min Order':<12} {'Required':<14} {'Recommended':<14}")
            print("-" * 100)

            for r in sorted(results, key=lambda x: x['required_balance'], reverse=True):
                print(f"{r['symbol']:<10} {r['side']:<6} ${r['current_price']:<11.4f} ${r['min_order_price']:<11.2f} ${r['required_balance']:<13.2f} ${r['recommended_balance']:<13.0f}")

            print("-" * 100)

        print("\n" + "=" * 100)
        print(f"FINAL RECOMMENDATION: Start with at least ${highest['recommended_balance']:.0f} USDT".center(100))
        print("=" * 100)
        print()
        print("Note: This calculation ensures you can place the initial entry order.")
        print("      Consider additional buffer for:")
        print("      - Grid entries (DCA)")
        print(f"      - Drawdown safety (backtest showed {self.config.get('analysis', {}).get('drawdown_worst', 0)*100:.1f}% max drawdown)")
        print("      - Multiple positions if n_positions > 1")
        print()


def main():
    parser = argparse.ArgumentParser(
        description="Calculate required balance for a passivbot configuration (Hyperliquid)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python calculate_required_balance.py --config configs/config_hype.json
  python calculate_required_balance.py --config configs/config_hype.json --buffer 0.2

The calculator will:
  1. Read your config file
  2. Fetch current market data from Hyperliquid
  3. Calculate minimum required balance
  4. Add a safety buffer (default 10%)
  5. Show detailed breakdown and recommendation
        """
    )

    parser.add_argument(
        "--config",
        "-c",
        required=True,
        help="Path to passivbot config file (e.g., configs/config_hype.json)"
    )

    parser.add_argument(
        "--buffer",
        "-b",
        type=float,
        default=0.1,
        help="Safety buffer percentage (default: 0.1 = 10%%)"
    )

    args = parser.parse_args()

    try:
        calculator = BalanceCalculator(
            config_path=args.config,
            buffer=args.buffer
        )

        results = calculator.calculate()
        calculator.print_results(results)

    except KeyboardInterrupt:
        print("\n\nCalculation interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
