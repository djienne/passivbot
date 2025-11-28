# Passivbot (Windows-Optimized Fork)

## Project Overview

Passivbot is a cryptocurrency trading bot designed for perpetual futures derivatives markets. It employs a grid-based, contrarian market-making strategy, providing liquidity by placing limit buy and sell orders. It does not use technical indicators or trend following; instead, it relies on a modified Martingale strategy to average down entry prices and exit on small rebounds.

This specific repository is a **Windows-optimized fork** of the original Passivbot, featuring:
*   Enhanced Rust extension handling for Windows (`.pyd`/`.dll`).
*   Native Hyperliquid API integration for efficient data fetching (`candleSnapshot`) and trading.
*   Pre-configured setups for Windows backtesting.

## Architecture

*   **Language:** Python (Main logic), Rust (Performance-critical components via `pyo3` and `maturin`).
*   **Core Logic:** `src/passivbot.py` and `src/main.py`.
*   **Backtesting Engine:** `passivbot-rust/` (Rust crate) handles CPU-intensive calculations for backtesting.
*   **Exchange Integration:** Uses `ccxt` for most exchanges and custom implementations for Hyperliquid.
*   **Data:** Historical data is stored in `historical_data/`.

## Key Files & Directories

*   **`src/`**: Source code for the Python bot.
    *   `main.py`: Entry point for live trading.
    *   `backtest.py`: Entry point for backtesting.
    *   `passivbot.py`: Core bot logic.
*   **`passivbot-rust/`**: Rust source code for the high-performance backtesting extension.
    *   `Cargo.toml`: Rust dependencies and configuration.
    *   `src/lib.rs`: Rust entry point.
*   **`configs/`**: JSON configuration files for trading strategies.
*   **`requirements.txt`**: Python dependencies.
*   **`docker-compose.yml`**: Docker configuration for live trading.
*   **`docker-compose_HL_data.yml`**: Docker configuration for automated Hyperliquid data collection.

## Setup & Installation (Windows)

1.  **Prerequisites:**
    *   Python 3.10
    *   Rust (via `rustup`)
    *   C++ Build Tools (often required for compiling Python extensions on Windows)

2.  **Environment Setup:**
    ```powershell
    # Create virtual environment
    py -3.10 -m venv venv
    .\venv\Scripts\Activate.ps1

    # Install Python dependencies
    pip install -r requirements.txt
    ```

3.  **Build Rust Extension:**
    ```powershell
    cd passivbot-rust
    maturin develop --release
    cd ..
    ```

## Common Commands

### Backtesting
Run a backtest using a specific configuration:
```powershell
python src/backtest.py configs/examples/btc_long.json --disable_plotting
```

Hyperliquid-specific backtest (fetches data automatically):
```powershell
python src/backtest.py configs/test_hyperliquid_btc_aggressive.json
```

### Live Trading
Start the bot with a configuration file:
```powershell
python src/main.py configs/your_config.json
```
*Note: Requires `api-keys.json` to be configured.*

### Data Management
Download Hyperliquid data manually:
```powershell
python src/tools/download_hyperliquid_data.py --coins BTC ETH SOL HYPE --days-back 3
```

## Development Conventions

*   **Hybrid Codebase:** Changes to core math or backtesting logic often require modifying the Rust code (`passivbot-rust/`) and rebuilding with `maturin develop --release`.
*   **Configuration:** Strategies are defined in JSON files within `configs/`.
*   **Logging:** The bot uses Python's `logging` module. Verbosity can be controlled via CLI arguments (`--debug-level`).
*   **Hyperliquid:** This fork treats Hyperliquid as a first-class citizen with specific optimizations for its API.

## Docker Support

*   **Live Bot:** `docker compose up -d` (uses `docker-compose.yml`)
*   **Data Downloader:** `docker compose -f docker-compose_HL_data.yml up -d` (Automated data fetching)
