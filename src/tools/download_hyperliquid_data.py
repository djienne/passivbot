"""
Hyperliquid Historical Data Downloader for Passivbot

Downloads OHLCV candle data from Hyperliquid API and stores it in Passivbot-compatible format.

Usage:
    # Download available data for specific coins
    python src/tools/download_hyperliquid_data.py --coins BTC ETH SOL --days-back 3

    # Daily update (get latest data)
    python src/tools/download_hyperliquid_data.py --update --config configs/template.json

    # Download specific date range
    python src/tools/download_hyperliquid_data.py --coins BTC --start-date 2025-01-10 --end-date 2025-01-15
"""

import argparse
import asyncio
import json
import logging
import os
import random
import sys
import traceback
from collections import deque
from datetime import datetime, timedelta
from pathlib import Path
from time import time
from typing import List, Dict, Optional

import aiohttp
import pandas as pd
import numpy as np
from tqdm import tqdm

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from config_utils import load_config
from pure_funcs import safe_filename
from utils import (
    make_get_filepath,
    utc_ms,
    ts_to_date,
    date_to_ts,
    coin_to_symbol,
)
from downloader import (
    dump_ohlcv_data,
    ensure_millis,
    get_days_in_between,
)

# Configure logging
logging.basicConfig(
    format="%(asctime)s %(levelname)-8s %(message)s",
    level=logging.INFO,
    datefmt="%Y-%m-%dT%H:%M:%S",
)


class RateLimiter:
    """
    Rate limiter with exponential backoff for Hyperliquid API.

    Hyperliquid rate limits:
    - 1200 weight per minute for all requests
    - candleSnapshot has additional weight per 60 items returned
    - Conservative limit: 30 requests/minute to account for response size
    """

    def __init__(
        self,
        max_requests_per_minute: int = 30,
        base_backoff: float = 2.0,
        max_backoff: float = 60.0,
    ):
        self.max_requests_per_minute = max_requests_per_minute
        self.base_backoff = base_backoff
        self.max_backoff = max_backoff
        self.request_timestamps = deque(maxlen=1000)

    async def check_rate_limit(self):
        """Check rate limit and sleep if necessary."""
        current_time = time()

        # Remove timestamps older than 60 seconds
        while self.request_timestamps and current_time - self.request_timestamps[0] > 60:
            self.request_timestamps.popleft()

        # Check if at limit
        if len(self.request_timestamps) >= self.max_requests_per_minute:
            sleep_time = 60 - (current_time - self.request_timestamps[0])
            if sleep_time > 0:
                logging.debug(
                    f"Rate limit reached ({len(self.request_timestamps)}/{self.max_requests_per_minute}), "
                    f"sleeping for {sleep_time:.2f} seconds"
                )
                await asyncio.sleep(sleep_time)

        # Record this request
        self.request_timestamps.append(time())

    def add_jitter(self, delay: float) -> float:
        """Add random jitter to avoid thundering herd problem."""
        jitter = random.uniform(0, delay * 0.1)  # Up to 10% jitter
        return delay + jitter

    async def handle_rate_limit_error(self, retry_count: int) -> float:
        """
        Calculate exponential backoff delay on rate limit errors.

        Args:
            retry_count: Current retry attempt (0-indexed)

        Returns:
            Delay in seconds
        """
        delay = min(
            self.base_backoff * (2 ** retry_count),
            self.max_backoff
        )
        delay = self.add_jitter(delay)
        logging.warning(
            f"Rate limit error (retry {retry_count + 1}), backing off for {delay:.2f} seconds"
        )
        await asyncio.sleep(delay)
        return delay


class HyperliquidDownloader:
    """Download historical OHLCV data from Hyperliquid API."""

    API_URL = "https://api.hyperliquid.xyz/info"
    MAX_RETRIES = 5

    def __init__(
        self,
        output_dir: str = "historical_data/ohlcvs_hyperliquid",
        cache_dir: str = "caches/hyperliquid",
        rate_limiter: Optional[RateLimiter] = None,
        verbose: bool = True,
    ):
        self.output_dir = output_dir
        self.cache_dir = cache_dir
        self.rate_limiter = rate_limiter or RateLimiter()
        self.verbose = verbose
        self.session = None

    async def __aenter__(self):
        """Async context manager entry."""
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.session:
            await self.session.close()

    async def fetch_candles(
        self,
        coin: str,
        start_ts: int,
        end_ts: int,
        interval: str = "1m",
        retry_count: int = 0,
    ) -> List[Dict]:
        """
        Fetch candles from Hyperliquid API.

        Args:
            coin: Asset symbol (e.g., "BTC", "ETH")
            start_ts: Start timestamp in milliseconds
            end_ts: End timestamp in milliseconds
            interval: Candle interval (default: "1m")
            retry_count: Current retry attempt

        Returns:
            List of candle dictionaries
        """
        await self.rate_limiter.check_rate_limit()

        payload = {
            "type": "candleSnapshot",
            "req": {
                "coin": coin,
                "interval": interval,
                "startTime": int(start_ts),
                "endTime": int(end_ts),
            }
        }

        try:
            async with self.session.post(
                self.API_URL,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=aiohttp.ClientTimeout(total=30),
            ) as response:
                if response.status == 429:
                    # Rate limit hit
                    if retry_count < self.MAX_RETRIES:
                        await self.rate_limiter.handle_rate_limit_error(retry_count)
                        return await self.fetch_candles(
                            coin, start_ts, end_ts, interval, retry_count + 1
                        )
                    else:
                        logging.error(f"Max retries reached for {coin} on {ts_to_date(start_ts)}")
                        return []

                if response.status != 200:
                    error_text = await response.text()
                    logging.error(
                        f"API error for {coin}: status {response.status}, response: {error_text}"
                    )
                    return []

                data = await response.json()
                return data if isinstance(data, list) else []

        except asyncio.TimeoutError:
            logging.error(f"Timeout fetching {coin} for {ts_to_date(start_ts)}")
            if retry_count < self.MAX_RETRIES:
                await asyncio.sleep(self.rate_limiter.add_jitter(2))
                return await self.fetch_candles(
                    coin, start_ts, end_ts, interval, retry_count + 1
                )
            return []
        except Exception as e:
            logging.error(f"Error fetching {coin} for {ts_to_date(start_ts)}: {e}")
            traceback.print_exc()
            return []

    def convert_api_response_to_df(self, candles: List[Dict]) -> pd.DataFrame:
        """
        Convert Hyperliquid API response to Passivbot-compatible DataFrame.

        API response format:
        [{
            "t": 1704067200000,  # timestamp
            "o": "42000.0",      # open
            "c": "42050.0",      # close
            "h": "42100.0",      # high
            "l": "41990.0",      # low
            "v": "125.5",        # volume
            "n": 234,            # number of trades
            "i": "1m",           # interval
            "s": "BTC"           # symbol
        }]

        Returns DataFrame with columns: [timestamp, open, high, low, close, volume]
        """
        if not candles:
            return pd.DataFrame(columns=["timestamp", "open", "high", "low", "close", "volume"])

        df = pd.DataFrame([
            {
                "timestamp": float(c["t"]),
                "open": float(c["o"]),
                "high": float(c["h"]),
                "low": float(c["l"]),
                "close": float(c["c"]),
                "volume": float(c["v"]),
            }
            for c in candles
        ])

        # Ensure timestamps are in milliseconds
        df = ensure_millis(df)

        # Sort by timestamp
        df = df.sort_values("timestamp").reset_index(drop=True)

        return df

    async def fetch_candles_for_day(
        self,
        coin: str,
        day_str: str,
    ) -> Optional[pd.DataFrame]:
        """
        Fetch candles for a single day.

        Args:
            coin: Asset symbol (e.g., "BTC")
            day_str: Date string in format "YYYY-MM-DD"

        Returns:
            DataFrame with OHLCV data or None if failed
        """
        start_ts = int(date_to_ts(day_str))
        end_ts = start_ts + (24 * 60 * 60 * 1000)  # +1 day

        candles = await self.fetch_candles(coin, start_ts, end_ts)
        if not candles:
            return None

        df = self.convert_api_response_to_df(candles)

        # Filter to exact day range
        df = df[(df.timestamp >= start_ts) & (df.timestamp < end_ts)].reset_index(drop=True)

        return df if len(df) > 0 else None

    def validate_day_data(self, df: pd.DataFrame, coin: str, day_str: str) -> bool:
        """
        Validate that day data is complete and correct.

        Args:
            df: DataFrame with OHLCV data
            day_str: Date string

        Returns:
            True if valid, False otherwise
        """
        if df is None or len(df) == 0:
            logging.warning(f"{coin} {day_str}: No data returned")
            return False

        # Check for complete day (1440 minutes)
        if len(df) != 1440:
            logging.warning(
                f"{coin} {day_str}: Incomplete day ({len(df)}/1440 candles), skipping"
            )
            return False

        # Check for gaps (should be exactly 60000ms between candles)
        intervals = np.diff(df["timestamp"].values)
        if not (intervals == 60000).all():
            max_gap = int(intervals.max() / 60000)
            logging.warning(
                f"{coin} {day_str}: Gaps detected (max gap: {max_gap} minutes), skipping"
            )
            return False

        # Validate OHLC relationships
        invalid_ohlc = (
            (df["high"] < df["open"]) |
            (df["high"] < df["close"]) |
            (df["low"] > df["open"]) |
            (df["low"] > df["close"])
        )
        if invalid_ohlc.any():
            logging.warning(f"{coin} {day_str}: Invalid OHLC relationships detected")
            return False

        return True

    async def process_and_save_day(
        self,
        coin: str,
        day_str: str,
        force: bool = False,
    ) -> bool:
        """
        Fetch, validate, and save data for a single day.

        Args:
            coin: Asset symbol
            day_str: Date string "YYYY-MM-DD"
            force: If True, overwrite existing files

        Returns:
            True if successful, False otherwise
        """
        # Check if already exists
        dirpath = make_get_filepath(os.path.join(self.output_dir, coin, ""))
        fpath = os.path.join(dirpath, f"{day_str}.npy")

        if os.path.exists(fpath) and not force:
            logging.debug(f"{coin} {day_str}: Already exists, skipping")
            return True

        # Fetch data
        df = await self.fetch_candles_for_day(coin, day_str)

        # Validate
        if not self.validate_day_data(df, coin, day_str):
            return False

        # Save to disk
        try:
            dump_ohlcv_data(df, fpath)
            if self.verbose:
                logging.info(f"{coin} {day_str}: Saved {len(df)} candles to {fpath}")
            return True
        except Exception as e:
            logging.error(f"{coin} {day_str}: Error saving data: {e}")
            traceback.print_exc()
            return False

    async def download_coins(
        self,
        coins: List[str],
        start_date: str,
        end_date: str,
        force: bool = False,
    ) -> Dict[str, int]:
        """
        Download data for multiple coins and date range.

        Args:
            coins: List of coin symbols
            start_date: Start date "YYYY-MM-DD"
            end_date: End date "YYYY-MM-DD"
            force: Overwrite existing files

        Returns:
            Dictionary with coin -> number of days downloaded
        """
        days = get_days_in_between(start_date, end_date)

        logging.info(
            f"Downloading {len(coins)} coin(s) for {len(days)} day(s) "
            f"({start_date} to {end_date})"
        )

        results = {coin: 0 for coin in coins}

        # Process each coin
        for coin in coins:
            logging.info(f"Processing {coin}...")

            # Download days with progress bar
            for day in tqdm(days, desc=f"{coin}", unit="day"):
                success = await self.process_and_save_day(coin, day, force=force)
                if success:
                    results[coin] += 1

            logging.info(f"{coin}: Downloaded {results[coin]}/{len(days)} days")

        return results

    def load_first_timestamps(self) -> Dict[str, int]:
        """Load first timestamps cache."""
        fpath = os.path.join(self.cache_dir, "first_timestamps.json")
        if os.path.exists(fpath):
            try:
                return json.load(open(fpath))
            except Exception as e:
                logging.error(f"Error loading first_timestamps.json: {e}")
        return {}

    def save_first_timestamps(self, timestamps: Dict[str, int]):
        """Save first timestamps cache."""
        fpath = make_get_filepath(os.path.join(self.cache_dir, "first_timestamps.json"))
        try:
            json.dump(timestamps, open(fpath, "w"), indent=2, sort_keys=True)
            logging.info(f"Updated first_timestamps.json")
        except Exception as e:
            logging.error(f"Error saving first_timestamps.json: {e}")

    async def update_first_timestamps(self, coins: List[str]):
        """
        Update first timestamps for coins by fetching the oldest available data.

        Note: Hyperliquid only provides ~5000 candles, so this finds the earliest
        timestamp currently available via API.
        """
        first_timestamps = self.load_first_timestamps()
        updated = False

        for coin in coins:
            if coin in first_timestamps:
                continue

            # Fetch oldest available data (go back ~3.5 days)
            now_ms = int(utc_ms())
            lookback_ms = 5000 * 60 * 1000  # ~5000 1-minute candles
            start_ts = now_ms - lookback_ms

            candles = await self.fetch_candles(coin, start_ts, now_ms)
            if candles and len(candles) > 0:
                df = self.convert_api_response_to_df(candles)
                if len(df) > 0:
                    first_ts = int(df["timestamp"].min())
                    first_timestamps[coin] = first_ts
                    updated = True
                    logging.info(
                        f"{coin}: First timestamp {ts_to_date(first_ts)} ({first_ts})"
                    )

        if updated:
            self.save_first_timestamps(first_timestamps)


async def main():
    parser = argparse.ArgumentParser(
        prog="download_hyperliquid_data",
        description="Download historical OHLCV data from Hyperliquid for Passivbot",
    )

    # Coin selection
    parser.add_argument(
        "--coins",
        type=str,
        nargs="+",
        help="List of coins to download (e.g., BTC ETH SOL)",
    )
    parser.add_argument(
        "--config",
        type=str,
        help="Path to Passivbot config (will use approved_coins from config)",
    )

    # Date range options
    parser.add_argument(
        "--start-date",
        type=str,
        help="Start date in YYYY-MM-DD format",
    )
    parser.add_argument(
        "--end-date",
        type=str,
        help="End date in YYYY-MM-DD format (default: today)",
    )
    parser.add_argument(
        "--days-back",
        type=int,
        default=3,
        help="Number of days to go back from today (default: 3, max practical: ~3)",
    )
    parser.add_argument(
        "--update",
        action="store_true",
        help="Update mode: download latest available data",
    )

    # Other options
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force re-download of existing files",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Verbose logging",
    )

    args = parser.parse_args()

    # Set logging level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Determine coin list
    coins = []
    if args.coins:
        coins = args.coins
    elif args.config:
        config = load_config(args.config)
        approved = config.get("live", {}).get("approved_coins", [])
        if isinstance(approved, dict):
            coins = list(set(approved.get("long", []) + approved.get("short", [])))
        elif isinstance(approved, list):
            coins = approved

    if not coins:
        logging.error("No coins specified. Use --coins or --config")
        return

    # Determine date range
    if args.update:
        # Update mode: get the most recent available data (~3 days)
        end_date = ts_to_date(utc_ms())[:10]
        start_date_ts = utc_ms() - (3 * 24 * 60 * 60 * 1000)
        start_date = ts_to_date(start_date_ts)[:10]
    elif args.start_date and args.end_date:
        start_date = args.start_date
        end_date = args.end_date
    elif args.start_date:
        start_date = args.start_date
        end_date = ts_to_date(utc_ms())[:10]
    else:
        # Default: go back N days
        end_date = ts_to_date(utc_ms())[:10]
        start_date_ts = utc_ms() - (args.days_back * 24 * 60 * 60 * 1000)
        start_date = ts_to_date(start_date_ts)[:10]

    # Warn if trying to go back too far
    days_diff = (date_to_ts(end_date) - date_to_ts(start_date)) / (24 * 60 * 60 * 1000)
    if days_diff > 3.5:
        logging.warning(
            f"⚠️  Date range is {days_diff:.1f} days, but Hyperliquid API only provides "
            f"~3.5 days of data. Older data may not be available."
        )

    logging.info(f"Coins: {', '.join(coins)}")
    logging.info(f"Date range: {start_date} to {end_date}")

    # Download data
    async with HyperliquidDownloader(verbose=args.verbose) as downloader:
        # Update first timestamps
        await downloader.update_first_timestamps(coins)

        # Download data
        results = await downloader.download_coins(
            coins, start_date, end_date, force=args.force
        )

        # Print summary
        logging.info("\n" + "="*60)
        logging.info("Download Summary:")
        logging.info("="*60)
        total_days = 0
        for coin, days_downloaded in results.items():
            logging.info(f"  {coin:6s}: {days_downloaded} days")
            total_days += days_downloaded
        logging.info("="*60)
        logging.info(f"  Total: {total_days} days across {len(coins)} coins")
        logging.info("="*60)

        logging.info(f"\n✅ Data saved to: historical_data/ohlcvs_hyperliquid/")
        logging.info(f"📊 You can now run backtests with this data!")


if __name__ == "__main__":
    asyncio.run(main())
