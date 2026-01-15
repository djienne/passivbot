# Passivbot Windows Installation Guide

This guide explains how to install Passivbot on Windows to run backtests and download data.

## Prerequisites

- **Python 3.10** (required - versions 3.9-3.12 are supported, but **Python 3.13+ is NOT supported** due to numba compatibility)
- **Rust toolchain** (for building the passivbot-rust module)
- **Git** (optional, for cloning the repository)

## Step-by-Step Installation

### 1. Install Python 3.10

Download and install Python 3.10 from [python.org](https://www.python.org/downloads/release/python-31011/).

Make sure to check "Add Python to PATH" during installation.

Verify installation:
```bash
python --version
# Should show Python 3.10.x
```

If you have multiple Python versions, you may need to use the full path (e.g., `C:\Python310\python.exe`).

### 2. Install Rust

Download and run the Rust installer from [rustup.rs](https://rustup.rs/).

Follow the prompts to install the default toolchain.

Verify installation:
```bash
rustc --version
cargo --version
```

### 3. Clone or Download Passivbot

```bash
git clone https://github.com/djienne/passivbot.git
cd passivbot
```

Or download and extract the ZIP from GitHub.

> Note: This is the Windows-optimized fork. The original upstream project is at https://github.com/enarjord/passivbot

### 4. Create Virtual Environment

Create a virtual environment using Python 3.10:

```bash
# Windows Command Prompt
C:\Python310\python.exe -m venv .venv

# Or if Python 3.10 is in PATH
python -m venv .venv
```

### 5. Activate Virtual Environment

```bash
# Windows Command Prompt
.venv\Scripts\activate

# Git Bash / MSYS2
source .venv/Scripts/activate

# PowerShell
.venv\Scripts\Activate.ps1
```

### 6. Install Python Dependencies

```bash
pip install -r requirements.txt -r requirements-rust.txt
```

### 7. Build the Rust Extension

```bash
maturin develop --release -m passivbot-rust/Cargo.toml
```

This compiles the Rust backtesting engine and installs it in your virtual environment.

### 8. Fix DNS Issues (Important!)

On Windows, the `aiodns` package (auto-installed as a dependency of `ccxt`) can cause DNS resolution failures with errors like:

```
aiodns.error.DNSError: (11, 'Could not contact DNS servers')
```

This happens because `aiodns` uses the c-ares library which doesn't integrate well with Windows DNS configuration.

**Solution:** Uninstall `aiodns` to fall back to Python's built-in asyncio DNS resolver:

```bash
pip uninstall aiodns -y
```

This is safe to do - aiohttp and ccxt will automatically use the standard DNS resolver instead, which works correctly on Windows.

## Running Backtests

After installation, you can run backtests:

```bash
# Make sure virtual environment is activated
.venv\Scripts\activate

# Run backtest with a config file
python src/backtest.py configs/your_config.json
```

## Downloading Historical Data

The backtest script automatically downloads historical data when needed. Data is cached in:
- `historical_data/ohlcvs_<exchange>/` - OHLCV candlestick data
- `caches/` - Market info and metadata

## Common Issues

### "No module named 'numpy'" or similar import errors
Make sure you activated the virtual environment before running commands.

### "Cannot install on Python version 3.14; only versions >=3.9,<3.13 are supported"
You need Python 3.10-3.12. Install an older Python version and recreate the virtual environment.

### DNS errors when connecting to exchanges
Uninstall `aiodns`:
```bash
pip uninstall aiodns -y
```

### Rust compilation errors
1. Make sure Rust is installed: `rustc --version`
2. Update Rust: `rustup update`
3. Install Visual Studio Build Tools if prompted

### "maturin: command not found"
Use `python -m maturin` instead of `maturin`, or make sure the Scripts folder is in PATH.

## Quick Start Summary

```bash
# One-liner for Git Bash (after prerequisites installed)
C:\Python310\python.exe -m venv .venv && source .venv/Scripts/activate && pip install -r requirements.txt -r requirements-rust.txt && pip uninstall aiodns -y && maturin develop --release -m passivbot-rust/Cargo.toml
```

After this, you can run:
```bash
source .venv/Scripts/activate
python src/backtest.py configs/your_config.json
```
