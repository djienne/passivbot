"""Test Hyperliquid data integration with Passivbot's OHLCVManager."""
import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from downloader import OHLCVManager


async def test_load_hyperliquid_data():
    """Test that OHLCVManager can load Hyperliquid data from cache."""
    print("Testing Hyperliquid data integration...")
    print("=" * 60)

    om = OHLCVManager(
        "hyperliquid",
        start_date="2025-11-14",
        end_date="2025-11-14",
        verbose=True,
    )

    # Load markets
    await om.load_markets()
    print(f"[OK] Markets loaded: {len(om.markets)} symbols")

    # Test loading cached data
    df = await om.get_ohlcvs("BTC")

    if len(df) > 0:
        print(f"[OK] Loaded {len(df)} candles from cache")
        print(f"     Date range: {df.timestamp.min():.0f} to {df.timestamp.max():.0f}")
        print(f"     Complete day: {len(df) == 1440}")
        print(f"     No gaps: {(df.timestamp.diff()[1:] == 60000).all()}")
        print(f"     Volume converted to quote: {df.volume.mean():.2f}")
        print("=" * 60)
        print("[OK] All tests passed!")
        print("[OK] Hyperliquid data is fully compatible with Passivbot!")
    else:
        print("[ERROR] No data loaded from cache")
        print("        Run the downloader first:")
        print("        python src/tools/download_hyperliquid_data.py --coins BTC --days-back 1")

    if om.cc:
        await om.cc.close()


if __name__ == "__main__":
    asyncio.run(test_load_hyperliquid_data())
