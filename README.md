![Passivbot](docs/images/pbot_logo_full.svg)

# Trading bot running on Bybit, OKX, Bitget, GateIO, Binance, Kucoin and Hyperliquid

:warning: **Used at one's own risk** :warning:

v7.4.4

## Fork & Windows Optimizations

This repository is a Windows-optimised fork of [enarjord/passivbot](https://github.com/enarjord/passivbot) based on v7.4.4.  
It keeps behaviour compatible with upstream while improving:

- Rust extension handling on Windows (recognises `.pyd`/`.dll` builds from `maturin` and avoids unnecessary recompilations).
- Hyperliquid OHLCV fetching by calling the native `candleSnapshot` API and caching daily data under `historical_data/ohlcvs_hyperliquid`, with ready-made configs for Hyperliquid-focused backtesting.
- Example configs and defaults for Windows backtesting (see `configs/test_hyperliquid_btc_aggressive.json` for Hyperliquid and `configs/test_multi_btc_aggressive.json` for multi-exchange BTC).

## Overview

Passivbot is a cryptocurrency trading bot written in Python and Rust, intended to require minimal user intervention.  

It operates on perpetual futures derivatives markets, automatically creating and cancelling limit buy and sell orders on behalf of the user. It does not try to predict future price movements, it does not use technical indicators, nor does it follow trends. Rather, it is a contrarian market maker, providing resistance to price changes in both directions, thereby "serving the market" as a price stabilizer.  

Passivbot's behavior may be backtested on historical price data, using the included backtester whose CPU heavy functions are written in Rust for speed. Also included is an optimizer, which finds better configurations by iterating thousands of backtests with different candidates, converging on the optimal ones with an evolutionary algorithm.  

## Strategy

Inspired by the Martingale betting strategy, the robot will make a small initial entry and double down on its losing positions multiple times to bring the average entry price closer to current price action. The orders are placed in a grid, ready to absorb sudden price movements. After each re-entry, the robot quickly updates its closing orders at a set take-profit markup. This way, if there is even a minor market reversal, or "bounce", the position can be closed in profit, and it starts over.  

### Trailing Orders
In addition to grid-based entries and closes, Passivbot may be configured to utilize trailing entries and trailing closes.

For trailing entries, the bot waits for the price to move beyond a specified threshold and then retrace by a defined percentage before placing a re-entry order. Similarly, for trailing closes, the bot waits before placing its closing orders until after the price has moved favorably by a threshold percentage and then retraced by a specified percentage. This may result in the bot locking in profits more effectively by exiting positions when the market shows signs of reversing instead of at a fixed distance from average entry price.

Grid and trailing orders may be combined, such that the robot enters or closes a whole or a part of the position as grid orders and/or as trailing orders.

### Forager
The Forager feature dynamically chooses the most volatile markets on which to open positions. Volatility is defined as the mean of the normalized relative range for the most recent 1m candles, i.e. `mean((ohlcv.high - ohlcv.low) / ohlcv.close)`.

### Unstucking Mechanism
Passivbot manages underperforming, or "stuck", positions by realizing small losses over time. If multiple positions are stuck, the bot prioritizes positions with the smallest gap between the entry price and current market price for "unstucking". Losses are limited by ensuring that the account balance does not fall under a set percentage below the past peak balance.  

## Installation (Windows Only)

This fork is tuned for Windows. The steps below assume PowerShell on Windows 10/11.

### 1. Clone the Repository

Open PowerShell, then clone this Windows-optimised fork:

```powershell
git clone git@github.com:djienne/passivbot.git passivbot
cd passivbot
```

The original upstream project lives at: https://github.com/enarjord/passivbot.

### 2. Install Python 3.10 with Chocolatey

Run PowerShell **as Administrator**, `cd` into the `passivbot` directory, then:

1. Install Chocolatey (if not already installed) following https://chocolatey.org/install.  
2. Install Python 3.10.11 explicitly:

```powershell
choco install python --version=3.10.11 --allow-downgrade -y
```

Close and reopen PowerShell (non-admin is fine), then verify:

```powershell
py -3.10 --version
```

### 3. Create and Activate a 3.10 Virtual Environment

From the repository root:

```powershell
py -3.10 -m venv venv
.\venv\Scripts\Activate.ps1
```

You should see `(venv)` in your prompt.

### 4. Install Python Dependencies

With the venv active, install dependencies for this fork:

```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### 5. Install Rust and Build the Rust Extension

Passivbot uses Rust (via `maturin`) for high‑performance backtesting.

1. Install Rust using rustup (https://www.rust-lang.org/tools/install), then restart your terminal so `cargo` is on `PATH`.
2. Build the Rust extension inside the venv:

```powershell
cd passivbot-rust
maturin develop --release
cd ..
```

On Windows, this produces a `.pyd` in the venv; the fork’s startup logic recognises it and skips redundant recompiles.

### 6. Add API Keys

Copy the example file and fill in your keys (only needed for live trading; backtesting and optimisation do not require API credentials):

```powershell
Copy-Item api-keys.json.example api-keys.json
```

Edit `api-keys.json` with your exchange credentials.

### 7. Sanity Check: BTC Long Backtest

Run a multi‑year BTC futures backtest on Binance/Bybit to confirm everything is working:

```powershell
python .\src\backtest.py .\configs\examples\btc_long.json --disable_plotting
```

This uses the `configs/examples/btc_long.json` strategy (long‑only BTC grid/trailing system) and will download or reuse 1m OHLCV from Binance and Bybit, writing results under `backtests/`.

### 8. Hyperliquid BTC Backtest & Data Collection

To exercise the Hyperliquid integration and start accumulating local HL history:

```powershell
python .\src\backtest.py .\configs\test_hyperliquid_btc_aggressive.json
```

This runs an aggressive BTC strategy on Hyperliquid, fetching 1m candles via the native `candleSnapshot` API and caching them under `historical_data/ohlcvs_hyperliquid/BTC/`. Re‑running this command every few days will gradually build a longer local HL dataset within the exchange’s ~3.5‑day API window.

### Logging

Passivbot uses Python's logging module throughout the bot, backtester, and supporting tools.  
- Use `--debug-level {0-3}` (alias `--log-level`) on `src/main.py` or `src/backtest.py` to adjust verbosity at runtime: `0 = warnings only`, `1 = info`, `2 = debug`, `3 = trace`.  
- Persist a default by adding a top-level section to your config: `"logging": {"level": 2}`. The CLI flag always overrides the config value for that run.
- CandlestickManager and other subsystems inherit the chosen level so EMA warm-up, data fetching, and cache behaviour can be inspected consistently.

### Running Multiple Bots

Running several Passivbot instances against the same exchange on one machine is supported. Each process shares the same on-disk OHLCV cache, and the candlestick manager now uses short-lived, self-healing locks with automatic stale cleanup so that one stalled process cannot block the rest. No manual deletion of lock files is required; the bot removes stale locks on startup and logs whenever a lock acquisition times out.

## Hyperliquid Data & Backtesting (Windows Fork)

- Hyperliquid 1m candles are fetched via the native `candleSnapshot` API and cached as daily `.npy` files under `historical_data/ohlcvs_hyperliquid/<COIN>/YYYY-MM-DD.npy`.
- Backtests that include `hyperliquid` in `backtest.exchanges` (for example `configs/test_hyperliquid_btc_aggressive.json`) automatically download any missing Hyperliquid days before running.
- Hyperliquid only exposes ~3.5 days of 1m history; run either the Hyperliquid backtest or `python src/tools/download_hyperliquid_data.py --coins BTC ETH SOL HYPE --days-back 3` regularly (every 2–3 days) to accumulate long-term local history.

### Automated Hyperliquid Data Collection with Docker

For automated data collection, use the included Docker setup that runs the downloader every 4 hours:

```bash
# Start the automated downloader (runs in background)
docker compose -f docker-compose_HL_data.yml up -d

# View logs
docker logs -f passivbot-hl-downloader

# Stop the downloader
docker compose -f docker-compose_HL_data.yml down
```

The Docker scheduler downloads data for 20 major coins (AAVE, ADA, AVAX, BCH, BNB, BTC, DOGE, DOT, ETH, HBAR, HYPE, LINK, LTC, SOL, SUI, TON, TRX, UNI, XLM, XRP) every 4 hours, automatically accumulating historical data over time. Data is persisted in `./historical_data/` and `./caches/` directories.

**Requirements:** Docker and Docker Compose installed on your system.

### Running Live Bot with Docker

For live trading, you can run the bot in a Docker container:

```bash
# Build the Docker image
docker compose build

# Start the live bot (runs in background)
docker compose up -d

# View logs
docker logs -f passivbot-hype-live

# Stop the bot
docker compose down
```

The default configuration runs `configs/hype_dio.json` (not included in repository - you'll need to create your own config or use one from `configs/examples/`). To use a different config, edit the `command` line in `docker-compose.yml`.

**Requirements:**
- Docker and Docker Compose installed on your system
- Valid API keys configured in `api-keys.json` (the config specifies which exchange user to use)

## Jupyter Lab

Jupyter lab needs to be run in the same virtual environment as the bot. Activate venv (see installation instructions above, step 3), and launch Jupyter lab from the Passivbot root dir with:
```shell
python3 -m jupyter lab
```

## Requirements

- Python >= 3.8
- [requirements.txt](requirements.txt) dependencies

## Pre-optimized configurations

Coming soon...

See also https://pbconfigdb.scud.dedyn.io/

## Documentation:

For more detailed information about Passivbot, see documentation files here: [docs/](docs/)

## Support

[![Discord](https://img.shields.io/badge/Discord-7289DA?style=for-the-badge&logo=discord&logoColor=white)](https://discord.gg/QAF2H2UmzZ)

[![Telegram](https://img.shields.io/badge/Telegram-2CA5E0?style=for-the-badge&logo=telegram&logoColor=white)](https://t.me/passivbot_futures)

## Third Party Links, Referrals and Tip Jar

**Hyperliquid Reference Vault**
Passivbot's default template config running on a Hyperliquid Vault:  
https://app.hyperliquid.xyz/vaults/0x490af7d4a048a81db0f677517ed6373565b42349

**Passivbot GUI**
A graphical user interface for Passivbot:  
https://github.com/msei99/pbgui

**Referrals:**  
Signing up using these referrals is appreciated:  
https://accounts.binance.com/register?ref=TII4B07C  
https://partner.bybit.com/b/passivbot  
https://partner.bitget.com/bg/Y8FU1W  
https://www.okx.com/join/PASSIVBOT  
https://app.hyperliquid.xyz/join/PASSIVBOT  
https://www.kucoin.com/r/rf/CX8Q6DUF  

**Note on Binance**  
To support continued Passivbot development, please use a Binance account which  
1) was created after 2024-09-21 and  
2) either:  
  a) was created without a referral link, or  
  b) was created with referral ID: "TII4B07C".  
                                                                                      
Passivbot receives commissions from trades only for accounts meeting these criteria.  


**BuyMeACoffee:**  
https://www.buymeacoffee.com/enarjord  

**Donations:**  
If the robot is profitable, consider donating as showing gratitude for its development:  

- USDT or USDC Binance Smart Chain BEP20:  
0x4b7b5bf6bea228052b775c052843fde1c63ec530  
- USDT or USDC Arbitrum One:  
0x4b7b5bf6bea228052b775c052843fde1c63ec530  

Bitcoin (BTC) via Strike:  
enarjord@strike.me

## License
This is free and unencumbered software released into the public domain.

Anyone is free to copy, modify, publish, use, compile, sell, or
distribute this software, either in source code form or as a compiled
binary, for any purpose, commercial or non-commercial, and by any
means.

In jurisdictions that recognize copyright laws, the author or authors
of this software dedicate any and all copyright interest in the
software to the public domain. We make this dedication for the benefit
of the public at large and to the detriment of our heirs and
successors. We intend this dedication to be an overt act of
relinquishment in perpetuity of all present and future rights to this
software under copyright law.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
IN NO EVENT SHALL THE AUTHORS BE LIABLE FOR ANY CLAIM, DAMAGES OR
OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE,
ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
OTHER DEALINGS IN THE SOFTWARE.

For more information, please refer to <https://unlicense.org/>
