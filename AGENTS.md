# Repository Guidelines

## Project Structure & Module Organization
- `src/`: core trading logic (`main.py`, `backtest.py`, `optimize.py`, exchange and tool modules).
- `configs/`: configuration templates (for example `template.json`) and strategy configs.
- `tests/`: pytest suite for core behavior and regression tests.
- `scripts/` and `notebooks/`: utilities, data prep, and exploratory analysis.
- `historical_data/` and `caches/`: generated data; avoid committing large artifacts here.
- `passivbot-rust/`: Rust extensions for backtesting/optimization; built with `maturin`.

## Build, Test, and Development Commands
- Create env: `python -m venv venv` then `.\venv\Scripts\Activate.ps1` (Windows) or `source venv/bin/activate` (Linux/macOS).
- Install deps: `pip install -r requirements.txt`.
- Run bot: `python src/main.py -u <account_from_api-keys.json>` or `python src/main.py path/to/config.json`.
- Backtest: `python src/backtest.py path/to/config.json`.
- Run tests: `pytest` or `pytest tests/` from the repository root.

## Coding Style & Naming Conventions
- Python 3.8+, 4-space indentation, max line length 140 (see `.prospector.yml`).
- Use `snake_case` for functions and variables, `PascalCase` for classes, and `UPPER_SNAKE_CASE` for constants.
- Keep modules cohesive; prefer small, reusable helpers in `src/utils.py` or `src/pure_funcs.py` over duplicating logic.
- Keep new code lint-clean with Prospector/pytest where available; mirror nearby patterns.

## Testing Guidelines
- Add or update tests in `tests/test_*.py` for any behavior change or bug fix.
- Name tests descriptively, e.g. `test_candlestick_manager_locking_handles_stale_lock`.
- Focus coverage on exchange integrations, candlestick management, configuration parsing, and unstucking safeguards.
- Ensure `pytest` passes locally before opening a PR.

## Commit & Pull Request Guidelines
- Use short, descriptive commit messages in present tense, e.g. `improve non-standard coin handling` or `add tests for config overrides`.
- Group related changes together; avoid mixing large refactors with functional changes.
- PRs should include: summary of changes, rationale, test commands run (`pytest`, backtests), and links to related issues or discussions. Screenshots/log snippets are helpful for behavior changes.

## Agent-Specific Instructions
- Prefer minimal, targeted diffs that respect existing structure and naming.
- Do not modify user data directories such as `historical_data/` or `caches/` except when explicitly requested.
- When extending functionality, follow patterns in nearby code and tests, and update tests alongside code changes.
