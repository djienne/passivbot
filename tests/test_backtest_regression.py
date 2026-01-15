"""
Backtest regression tests to ensure refactoring does not alter results.

These tests verify that the backtest output remains identical after code changes.
Run with: pytest tests/test_backtest_regression.py -v
"""
import asyncio
import hashlib
import json
import os
import sys
from pathlib import Path

import pytest

# Ensure src is in path
ROOT_DIR = Path(__file__).parent.parent
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "baseline_hype_dio_bybit"
CONFIG_PATH = ROOT_DIR / "configs" / "hype_dio_bybit.json"


def load_expected_analysis():
    """Load the expected analysis results from the baseline fixture."""
    with open(FIXTURES_DIR / "expected_analysis.json", "r") as f:
        return json.load(f)


def load_expected_fills_hash():
    """Load the expected SHA256 hash of fills.csv from the baseline fixture."""
    with open(FIXTURES_DIR / "expected_fills_hash.txt", "r") as f:
        return f.read().strip()


@pytest.fixture(scope="module")
def backtest_results():
    """Run backtest and return results. Cached for the module."""
    # Import here to avoid issues if passivbot_rust isn't built
    from backtest import run_backtest, prepare_hlcvs_mss
    from config_utils import load_config, format_config, parse_overrides
    from utils import load_markets, format_approved_ignored_coins

    async def _run():
        config = load_config(str(CONFIG_PATH), verbose=False)
        config = format_config(config, verbose=False)

        # Load markets for each exchange
        backtest_exchanges = config["backtest"]["exchanges"]
        for exchange in backtest_exchanges:
            await load_markets(exchange)

        config = parse_overrides(config, verbose=False)
        await format_approved_ignored_coins(config, backtest_exchanges)

        # Initialize config keys as main() does
        config["backtest"]["cache_dir"] = {}
        config["backtest"]["coins"] = {}

        # Prepare HLCV data (combined mode as per config)
        exchange = "combined"
        coins, hlcvs, mss, results_path, cache_dir, btc_usd_prices, timestamps = (
            await prepare_hlcvs_mss(config, exchange)
        )
        config["backtest"]["coins"][exchange] = coins
        config["backtest"]["cache_dir"][exchange] = str(cache_dir)

        # Run backtest
        fills, equities, equities_btc, analysis = run_backtest(
            hlcvs, mss, config, exchange, btc_usd_prices, timestamps
        )

        return {
            "analysis": analysis,
            "fills": fills,
            "config": config,
        }

    return asyncio.run(_run())


class TestBacktestRegression:
    """Regression tests comparing current backtest output to baseline."""

    def test_gain_unchanged(self, backtest_results):
        """Test that gain matches baseline exactly."""
        expected = load_expected_analysis()
        actual = backtest_results["analysis"]

        assert abs(actual["gain"] - expected["gain"]) < 1e-10, (
            f"Gain changed: expected {expected['gain']}, got {actual['gain']}"
        )

    def test_sharpe_ratio_unchanged(self, backtest_results):
        """Test that sharpe_ratio matches baseline exactly."""
        expected = load_expected_analysis()
        actual = backtest_results["analysis"]

        assert abs(actual["sharpe_ratio"] - expected["sharpe_ratio"]) < 1e-10, (
            f"Sharpe ratio changed: expected {expected['sharpe_ratio']}, "
            f"got {actual['sharpe_ratio']}"
        )

    def test_drawdown_worst_unchanged(self, backtest_results):
        """Test that drawdown_worst matches baseline exactly."""
        expected = load_expected_analysis()
        actual = backtest_results["analysis"]

        assert abs(actual["drawdown_worst"] - expected["drawdown_worst"]) < 1e-10, (
            f"Drawdown worst changed: expected {expected['drawdown_worst']}, "
            f"got {actual['drawdown_worst']}"
        )

    def test_adg_w_unchanged(self, backtest_results):
        """Test that adg_w (weighted average daily gain) matches baseline."""
        expected = load_expected_analysis()
        actual = backtest_results["analysis"]

        assert abs(actual["adg_w"] - expected["adg_w"]) < 1e-10, (
            f"ADG_W changed: expected {expected['adg_w']}, got {actual['adg_w']}"
        )

    def test_loss_profit_ratio_unchanged(self, backtest_results):
        """Test that loss_profit_ratio matches baseline exactly."""
        expected = load_expected_analysis()
        actual = backtest_results["analysis"]

        assert abs(actual["loss_profit_ratio"] - expected["loss_profit_ratio"]) < 1e-10, (
            f"Loss/profit ratio changed: expected {expected['loss_profit_ratio']}, "
            f"got {actual['loss_profit_ratio']}"
        )

    def test_all_metrics_within_tolerance(self, backtest_results):
        """Test that all numeric metrics are within acceptable tolerance."""
        expected = load_expected_analysis()
        actual = backtest_results["analysis"]

        # Tolerance for floating-point comparison
        tolerance = 1e-9

        # Keys added by post_process that may not be in raw backtest output
        post_process_keys = {
            "loss_profit_ratio_long", "loss_profit_ratio_short", "pnl_ratio_long_short"
        }

        mismatches = []
        for key, expected_value in expected.items():
            if key in post_process_keys:
                continue  # Skip keys added by post-processing
            if key not in actual:
                mismatches.append(f"Missing key: {key}")
                continue

            actual_value = actual[key]

            if isinstance(expected_value, (int, float)):
                if abs(actual_value - expected_value) > tolerance:
                    mismatches.append(
                        f"{key}: expected {expected_value}, got {actual_value}, "
                        f"diff={abs(actual_value - expected_value)}"
                    )

        if mismatches:
            pytest.fail("Metrics changed:\n" + "\n".join(mismatches))


# Quick smoke test that doesn't need actual backtest
class TestBacktestRegressionSetup:
    """Tests to verify regression test infrastructure is set up correctly."""

    def test_baseline_fixture_exists(self):
        """Test that baseline fixture files exist."""
        assert FIXTURES_DIR.exists(), f"Fixtures dir missing: {FIXTURES_DIR}"
        assert (FIXTURES_DIR / "expected_analysis.json").exists()
        assert (FIXTURES_DIR / "expected_fills_hash.txt").exists()
        assert (FIXTURES_DIR / "config_snapshot.json").exists()

    def test_config_file_exists(self):
        """Test that the config file used for baseline exists."""
        assert CONFIG_PATH.exists(), f"Config file missing: {CONFIG_PATH}"

    def test_expected_analysis_has_required_keys(self):
        """Test that expected analysis has critical keys."""
        expected = load_expected_analysis()
        required_keys = [
            "gain", "sharpe_ratio", "drawdown_worst", "adg_w",
            "loss_profit_ratio", "calmar_ratio"
        ]
        for key in required_keys:
            assert key in expected, f"Missing required key: {key}"

    def test_expected_fills_hash_format(self):
        """Test that fills hash is valid SHA256 format."""
        hash_value = load_expected_fills_hash()
        assert len(hash_value) == 64, f"Invalid hash length: {len(hash_value)}"
        assert all(c in "0123456789abcdef" for c in hash_value), "Invalid hash chars"
