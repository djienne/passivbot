# passivbot_real_run — live HYPE bot (local operations)

**This directory trades live with real money.** `api-keys.json` is populated (gitignored) and
`docker-compose.yml` runs with `restart: unless-stopped`, so the bot comes back after a host
reboot. Treat every command here as affecting a running position.

This is a checkout of the Windows-optimised fork `git@github.com:djienne/passivbot.git`
(v7.4.4, based on [enarjord/passivbot](https://github.com/enarjord/passivbot)). For install,
strategy theory, backtesting and optimiser docs, go upstream — none of that is restated here.

## What actually runs

| | |
|---|---|
| compose service | `passivbot-hype-live` (`docker-compose.yml`) |
| container name | `passivbot-hype-live` |
| image | `passivbot:latest`, built from `Dockerfile_live` |
| command | `python src/main.py configs/config_hype.json` |
| config | `configs/config_hype.json` — long-only **HYPE**, api-keys user `hyperliquid_01` |
| limits | 0.1 CPU / 1500 MB, json-file logs capped at 5 x 20 MB |

The repo root is bind-mounted at `/app`, so editing a config on the host and restarting the
container is enough — no rebuild needed. `SKIP_RUST_COMPILE=true` is set because the Rust
extension is already built into the image.

Other configs in `configs/` (`hype_dio.json`, `hype_top.json`, `template.json`, …) are present
but **not** what the live service runs. To switch, edit the `command:` line in
`docker-compose.yml`.

## Operate

```powershell
docker compose up -d          # start / apply compose changes
docker compose restart        # restart after a config edit
docker compose logs -f        # follow logs
docker logs -f passivbot-hype-live
docker compose down           # stop the live bot
docker compose build          # rebuild the image (only after src/ or deps change)
```

## DNS / aiodns caveat (important)

The service uses `network_mode: bridge`. The default Docker bridge hands the container Docker
Desktop's VM resolver as its **only** nameserver. ccxt resolves through `aiodns` (c-ares),
which has no fallback path — the moment that single resolver stalls, ccxt raises
`ExchangeNotAvailable` and the trading cycle is lost. The compose file therefore pins public
resolvers and a short timeout:

```yaml
dns: [1.1.1.1, 8.8.8.8]
dns_opt: [timeout:2, attempts:3]
```

A stall now costs 2 s instead of a cycle. **Do not remove those `dns` / `dns_opt` blocks.**
The same explanation lives as comments at `docker-compose.yml:10-22`; keep both in sync.

## Hyperliquid data downloader (separate, optional)

`docker-compose_HL_data.yml` runs a cron container that keeps local 1m history topped up.
Hyperliquid only exposes ~3.5 days of 1m candles, so it must run regularly to accumulate
long-term data.

```powershell
docker compose -f docker-compose_HL_data.yml up -d
docker compose -f docker-compose_HL_data.yml ps
docker logs -f passivbot-hl-downloader
docker compose -f docker-compose_HL_data.yml down
```

- Container: `passivbot-hl-downloader` (image `passivbot-hl-downloader:latest`, `Dockerfile.hl_data`).
- Schedule: every 4 hours (`0 */4 * * *`), set up in `scripts/download_cron_entrypoint.sh:43`.
- Coins: 20 majors — AAVE ADA AVAX BCH BNB BTC DOGE DOT ETH HBAR HYPE LINK LTC SOL SUI TON
  TRX UNI XLM XRP (`scripts/download_cron_entrypoint.sh:35`, `--days-back 3`).
  Note the `COINS` variable at line 5 also lists ASTER, but the cron job at line 35 hardcodes
  its own 20-coin list — ASTER is only fetched by a manual `run_download` invocation.
- Output: `./historical_data/ohlcvs_hyperliquid/<COIN>/YYYY-MM-DD.npy` plus `./caches/`
  (both bind-mounted, both gitignored).
- This downloader is **not** required for the live bot and is often left stopped.

`docker-compose_HL_data_instructions.txt` is superseded by this section and kept only for
reference; `docker-compose_HL_data.yml.bak` is an older revision of the compose file.

## Also in this directory

- `BALANCE_GUIDE.md` — how Passivbot sizes positions and how much USDT this config needs.
- `calculate_required_balance.py` / `calculate_balance_simple.py` — the calculators that guide uses.
- `test_hyperliquid_integration.py` — smoke test for the fork's HL candle fetching.
