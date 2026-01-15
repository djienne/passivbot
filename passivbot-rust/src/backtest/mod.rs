pub mod types;
mod ema;
mod fills;
mod orders;

pub use ema::{calc_ema_alphas, calc_warmup_bars};
pub use types::{EmaAlphas, Alphas, EMAs, HourBucket, EffectiveNPositions, OpenOrders, OpenOrderBundle, Actives, TrailingPrices, TrailingEnabled, TradingEnabled};

use crate::constants::{CLOSE, HIGH, LOW, LONG, SHORT, SPOT_TRADING_FEE_FACTOR, VOLUME};
use crate::types::{
    BacktestParams, Balance, BotParams, BotParamsPair, Equities, ExchangeParams, Fill,
    OrderBook, Positions, StateParams, TrailingPriceBundle,
};
use crate::utils::{
    calc_pnl_long, calc_pnl_short, calc_wallet_exposure, hysteresis_rounding,
};
use ndarray::{ArrayView1, ArrayView3};
use std::cmp::Ordering;
use std::collections::{HashMap, HashSet};

pub struct Backtest<'a> {
    pub hlcvs: &'a ArrayView3<'a, f64>,
    pub btc_usd_prices: &'a ArrayView1<'a, f64>,
    pub bot_params_master: BotParamsPair,
    pub bot_params: Vec<BotParamsPair>,
    pub bot_params_original: Vec<BotParamsPair>,
    pub effective_n_positions: EffectiveNPositions,
    pub exchange_params_list: Vec<ExchangeParams>,
    pub backtest_params: BacktestParams,
    pub balance: Balance,
    pub n_coins: usize,
    pub ema_alphas: Vec<EmaAlphas>,
    pub emas: Vec<EMAs>,
    pub coin_first_valid_idx: Vec<usize>,
    pub coin_last_valid_idx: Vec<usize>,
    pub coin_trade_start_idx: Vec<usize>,
    pub trade_activation_logged: Vec<bool>,
    pub first_timestamp_ms: u64,
    pub last_hour_boundary_ms: u64,
    pub latest_hour: Vec<HourBucket>,
    pub warmup_bars: usize,
    pub positions: Positions,
    pub open_orders: OpenOrders,
    pub trailing_prices: TrailingPrices,
    pub actives: Actives,
    pub pnl_cumsum_running: f64,
    pub pnl_cumsum_max: f64,
    pub fills: Vec<Fill>,
    pub trading_enabled: TradingEnabled,
    pub trailing_enabled: Vec<TrailingEnabled>,
    pub any_trailing_long: bool,
    pub any_trailing_short: bool,
    pub equities: Equities,
    pub last_valid_timestamps: HashMap<usize, usize>,
    pub first_valid_timestamps: HashMap<usize, usize>,
    pub did_fill_long: HashSet<usize>,
    pub did_fill_short: HashSet<usize>,
    pub n_eligible_long: usize,
    pub n_eligible_short: usize,
    pub total_wallet_exposures: Vec<f64>,
}

impl<'a> Backtest<'a> {
    pub fn new(
        hlcvs: &'a ArrayView3<'a, f64>,
        btc_usd_prices: &'a ArrayView1<'a, f64>,
        bot_params: Vec<BotParamsPair>,
        exchange_params_list: Vec<ExchangeParams>,
        backtest_params: &BacktestParams,
    ) -> Self {
        // Determine if BTC collateral is used
        let mut balance = Balance::default();
        balance.use_btc_collateral = btc_usd_prices.iter().any(|&p| p != 1.0);

        // Initialize balances
        if balance.use_btc_collateral {
            balance.btc = backtest_params.starting_balance / btc_usd_prices[0];
        } else {
            balance.usd = backtest_params.starting_balance;
        }
        balance.usd_total = backtest_params.starting_balance;
        balance.usd_total_rounded = balance.usd_total;

        let n_timesteps = hlcvs.shape()[0];
        let n_coins = hlcvs.shape()[1];
        let mut first_valid_idx = backtest_params.first_valid_indices.clone();
        if first_valid_idx.len() != n_coins {
            first_valid_idx = vec![0usize; n_coins];
        }
        let mut last_valid_idx = backtest_params.last_valid_indices.clone();
        if last_valid_idx.len() != n_coins {
            last_valid_idx = vec![n_timesteps.saturating_sub(1); n_coins];
        }
        let warmup_minutes = if backtest_params.warmup_minutes.len() == n_coins {
            backtest_params.warmup_minutes.clone()
        } else {
            vec![0usize; n_coins]
        };
        let mut trade_start_idx = if backtest_params.trade_start_indices.len() == n_coins {
            backtest_params.trade_start_indices.clone()
        } else {
            vec![0usize; n_coins]
        };
        let mut trade_activation_logged = vec![false; n_coins];

        for i in 0..n_coins {
            let mut first = first_valid_idx[i];
            if first >= n_timesteps {
                first = n_timesteps.saturating_sub(1);
            }
            let mut last = last_valid_idx[i];
            if last >= n_timesteps {
                last = n_timesteps.saturating_sub(1);
            }
            if last < first {
                last = first;
            }
            first_valid_idx[i] = first;
            last_valid_idx[i] = last;
            let warm = warmup_minutes.get(i).copied().unwrap_or(0);
            let mut trade_idx = first.saturating_add(warm);
            if trade_idx > last {
                trade_idx = last;
            }
            trade_start_idx[i] = trade_idx;

            debug_assert_eq!(
                trade_idx,
                first.saturating_add(warm).min(last),
                "trade start index mismatch for coin {}: expected {} but got {}",
                i,
                first.saturating_add(warm).min(last),
                trade_idx
            );
            trade_activation_logged[i] = false;
        }

        let initial_emas = (0..n_coins)
            .map(|i| {
                let start_idx = first_valid_idx
                    .get(i)
                    .copied()
                    .unwrap_or(0)
                    .min(n_timesteps.saturating_sub(1));
                let close_price = hlcvs[[start_idx, i, CLOSE]];
                let base_close = if close_price.is_finite() {
                    close_price
                } else {
                    0.0
                };
                let volume = hlcvs[[start_idx, i, VOLUME]];
                let base_volume = if volume.is_finite() {
                    volume.max(0.0)
                } else {
                    0.0
                };
                EMAs {
                    long: [base_close; 3],
                    long_num: [base_close; 3],
                    long_den: [1.0; 3],
                    short: [base_close; 3],
                    short_num: [base_close; 3],
                    short_den: [1.0; 3],
                    vol_long: base_volume,
                    vol_long_num: base_volume,
                    vol_long_den: 1.0,
                    vol_short: base_volume,
                    vol_short_num: base_volume,
                    vol_short_den: 1.0,
                    log_range_long: 0.0,
                    log_range_long_num: 0.0,
                    log_range_long_den: 1.0,
                    log_range_short: 0.0,
                    log_range_short_num: 0.0,
                    log_range_short_den: 1.0,
                    grid_log_range_long: 0.0,
                    grid_log_range_long_num: 0.0,
                    grid_log_range_long_den: 1.0,
                    grid_log_range_short: 0.0,
                    grid_log_range_short_num: 0.0,
                    grid_log_range_short_den: 1.0,
                }
            })
            .collect();
        let mut equities = Equities::default();
        equities.usd.push(backtest_params.starting_balance);
        equities.btc.push(balance.btc);

        // init bot params
        let mut bot_params_master = bot_params[0].clone();
        bot_params_master.long.n_positions = n_coins.min(bot_params_master.long.n_positions);
        bot_params_master.short.n_positions = n_coins.min(bot_params_master.short.n_positions);

        // Store original bot params to preserve dynamic WEL indicators
        let bot_params_original = bot_params.clone();

        let n_eligible_long = bot_params_master.long.n_positions.max(
            (n_coins as f64 * (1.0 - bot_params_master.long.filter_volume_drop_pct)).round()
                as usize,
        );
        let n_eligible_short = bot_params_master.short.n_positions.max(
            (n_coins as f64 * (1.0 - bot_params_master.short.filter_volume_drop_pct)).round()
                as usize,
        );
        let effective_n_positions = EffectiveNPositions {
            long: n_eligible_long,
            short: n_eligible_short,
        };

        // Calculate EMA alphas for each coin
        let ema_alphas: Vec<EmaAlphas> = bot_params.iter().map(|bp| calc_ema_alphas(bp)).collect();
        let mut warmup_bars = backtest_params.global_warmup_bars;
        if warmup_bars == 0 {
            warmup_bars = calc_warmup_bars(&bot_params);
        }

        let trailing_enabled: Vec<TrailingEnabled> = bot_params
            .iter()
            .map(|bp| TrailingEnabled {
                long: bp.long.close_trailing_grid_ratio != 0.0
                    || bp.long.entry_trailing_grid_ratio != 0.0,
                short: bp.short.close_trailing_grid_ratio != 0.0
                    || bp.short.entry_trailing_grid_ratio != 0.0,
            })
            .collect();
        let any_trailing_long = trailing_enabled.iter().any(|te| te.long);
        let any_trailing_short = trailing_enabled.iter().any(|te| te.short);

        Backtest {
            hlcvs,
            btc_usd_prices,
            bot_params_master: bot_params_master.clone(),
            bot_params: bot_params.clone(),
            bot_params_original,
            effective_n_positions,
            exchange_params_list,
            backtest_params: backtest_params.clone(),
            balance,
            n_coins,
            ema_alphas,
            emas: initial_emas,
            coin_first_valid_idx: first_valid_idx,
            coin_last_valid_idx: last_valid_idx,
            coin_trade_start_idx: trade_start_idx,
            trade_activation_logged,
            positions: Positions::default(),
            first_timestamp_ms: backtest_params.first_timestamp_ms,
            last_hour_boundary_ms: (backtest_params.first_timestamp_ms / 3_600_000) * 3_600_000,
            latest_hour: vec![HourBucket::default(); n_coins],
            warmup_bars,
            open_orders: OpenOrders::default(),
            trailing_prices: TrailingPrices::default(),
            actives: Actives::default(),
            pnl_cumsum_running: 0.0,
            pnl_cumsum_max: 0.0,
            fills: Vec::new(),
            trading_enabled: TradingEnabled {
                long: bot_params
                    .iter()
                    .any(|bp| bp.long.wallet_exposure_limit != 0.0)
                    && bot_params_master.long.n_positions > 0,
                short: bot_params
                    .iter()
                    .any(|bp| bp.short.wallet_exposure_limit != 0.0)
                    && bot_params_master.short.n_positions > 0,
            },
            trailing_enabled,
            any_trailing_long,
            any_trailing_short,
            equities,
            last_valid_timestamps: HashMap::new(),
            first_valid_timestamps: HashMap::new(),
            did_fill_long: HashSet::new(),
            did_fill_short: HashSet::new(),
            n_eligible_long,
            n_eligible_short,
            total_wallet_exposures: Vec::with_capacity(n_timesteps),
        }
    }

    pub fn run(&mut self) -> (Vec<Fill>, Equities) {
        let n_timesteps = self.hlcvs.shape()[0];
        for idx in 0..self.n_coins {
            self.trailing_prices
                .long
                .insert(idx, TrailingPriceBundle::default());
            self.trailing_prices
                .short
                .insert(idx, TrailingPriceBundle::default());
        }

        // --- register first & last valid candle for every coin ---
        for idx in 0..self.n_coins {
            if let Some((start, end)) = self.coin_valid_range(idx) {
                self.first_valid_timestamps.insert(idx, start);
                if end.saturating_add(1400) < n_timesteps {
                    // add only if delisted more than one day before last timestamp
                    self.last_valid_timestamps.insert(idx, end);
                }
            }
        }

        let warmup_bars = self.warmup_bars.max(1);
        let guard_timestamp_ms = self
            .backtest_params
            .requested_start_timestamp_ms
            .max(self.first_timestamp_ms);
        for k in 1..(n_timesteps - 1) {
            for idx in 0..self.n_coins {
                if !self.trade_activation_logged[idx] && self.coin_is_tradeable_at(idx, k) {
                    self.trade_activation_logged[idx] = true;
                }
                if k < self.coin_trade_start_idx[idx] && self.coin_is_valid_at(idx, k) {
                    debug_assert!(
                        !self.coin_is_tradeable_at(idx, k),
                        "coin {} flagged tradeable too early at k {} (trade_start {})",
                        idx,
                        k,
                        self.coin_trade_start_idx[idx]
                    );
                }
            }
            self.check_for_fills(k);
            self.update_emas(k);
            self.update_rounded_balance(k);
            self.update_trailing_prices(k);
            let current_ts = self.first_timestamp_ms + (k as u64) * 60_000u64;
            if k > warmup_bars && current_ts >= guard_timestamp_ms {
                self.update_n_positions_and_wallet_exposure_limits(k);
                self.update_open_orders_all(k);
            }
            self.update_equities(k);
            self.record_total_wallet_exposure();
        }
        (self.fills.clone(), self.equities.clone())
    }

    pub fn update_n_positions_and_wallet_exposure_limits(&mut self, k: usize) {
        let eligible: Vec<usize> = (0..self.n_coins)
            .filter(|&idx| self.coin_is_tradeable_at(idx, k))
            .collect();

        if eligible.is_empty() {
            return;
        }

        self.effective_n_positions.long =
            self.bot_params_master.long.n_positions.min(eligible.len());
        self.effective_n_positions.short =
            self.bot_params_master.short.n_positions.min(eligible.len());

        if self.effective_n_positions.long == 0 && self.effective_n_positions.short == 0 {
            return;
        }

        let dyn_wel_long = if self.effective_n_positions.long > 0 {
            self.bot_params_master.long.total_wallet_exposure_limit
                / self.effective_n_positions.long as f64
        } else {
            0.0
        };
        let dyn_wel_short = if self.effective_n_positions.short > 0 {
            self.bot_params_master.short.total_wallet_exposure_limit
                / self.effective_n_positions.short as f64
        } else {
            0.0
        };

        for &idx in &eligible {
            if self.bot_params_original[idx].long.wallet_exposure_limit < 0.0 {
                self.bot_params[idx].long.wallet_exposure_limit = dyn_wel_long;
            }
            if self.bot_params_original[idx].short.wallet_exposure_limit < 0.0 {
                self.bot_params[idx].short.wallet_exposure_limit = dyn_wel_short;
            }
        }
    }

    #[inline(always)]
    pub fn update_rounded_balance(&mut self, k: usize) {
        if self.balance.use_btc_collateral {
            self.balance.usd_total = (self.balance.btc * self.btc_usd_prices[k]) + self.balance.usd;
            self.balance.btc_total = self.balance.usd_total / self.btc_usd_prices[k];

            self.balance.usd_total_rounded = hysteresis_rounding(
                self.balance.usd_total,
                self.balance.usd_total_rounded,
                0.02,
                0.5,
            );
        }
    }

    #[inline(always)]
    pub fn bp(&self, coin_idx: usize, pside: usize) -> &BotParams {
        match pside {
            0 => &self.bot_params[coin_idx].long,
            1 => &self.bot_params[coin_idx].short,
            _ => unreachable!("invalid pside"),
        }
    }

    #[inline(always)]
    pub fn coin_valid_range(&self, idx: usize) -> Option<(usize, usize)> {
        if idx >= self.coin_first_valid_idx.len() {
            return None;
        }
        let start = self.coin_first_valid_idx[idx];
        let end = self.coin_last_valid_idx[idx];
        if start > end {
            None
        } else {
            Some((start, end))
        }
    }

    #[inline(always)]
    pub fn coin_is_valid_at(&self, idx: usize, k: usize) -> bool {
        self.coin_valid_range(idx)
            .map(|(start, end)| k >= start && k <= end)
            .unwrap_or(false)
    }

    #[inline(always)]
    pub fn coin_is_tradeable_at(&self, idx: usize, k: usize) -> bool {
        if idx >= self.coin_trade_start_idx.len() {
            return false;
        }
        let trade_start = self.coin_trade_start_idx[idx];
        self.coin_is_valid_at(idx, k) && k >= trade_start
    }

    pub fn calc_preferred_coins(&mut self, pside: usize) -> Vec<usize> {
        let n_positions = match pside {
            LONG => self.effective_n_positions.long,
            SHORT => self.effective_n_positions.short,
            _ => panic!("Invalid pside"),
        };

        if self.n_coins <= n_positions {
            return (0..self.n_coins).collect();
        }
        let volume_filtered = self.filter_by_relative_volume(pside);
        self.rank_by_log_range(&volume_filtered, pside)
    }

    fn filter_by_relative_volume(&mut self, pside: usize) -> Vec<usize> {
        let mut volume_indices: Vec<(f64, usize)> = Vec::with_capacity(self.n_coins);
        for idx in 0..self.n_coins {
            let vol = match pside {
                LONG => self.emas[idx].vol_long,
                SHORT => self.emas[idx].vol_short,
                _ => panic!("Invalid pside"),
            };
            volume_indices.push((vol, idx));
        }
        volume_indices.sort_unstable_by(|a, b| b.0.partial_cmp(&a.0).unwrap_or(Ordering::Equal));
        let n_eligible = match pside {
            LONG => self.n_eligible_long,
            SHORT => self.n_eligible_short,
            _ => panic!("Invalid pside"),
        };
        volume_indices
            .into_iter()
            .take(n_eligible.min(self.n_coins))
            .map(|(_, idx)| idx)
            .collect()
    }

    fn rank_by_log_range(&self, candidates: &[usize], pside: usize) -> Vec<usize> {
        let mut log_ranges: Vec<(f64, usize)> = candidates
            .iter()
            .map(|&idx| {
                let lr = match pside {
                    LONG => self.emas[idx].log_range_long,
                    SHORT => self.emas[idx].log_range_short,
                    _ => 0.0,
                };
                (lr, idx)
            })
            .collect();

        log_ranges.sort_unstable_by(|a, b| b.0.partial_cmp(&a.0).unwrap_or(Ordering::Equal));
        log_ranges.into_iter().map(|(_, idx)| idx).collect()
    }

    pub fn create_state_params(&self, k: usize, idx: usize, pside: usize) -> StateParams {
        let mut close_price = self.hlcvs[[k, idx, CLOSE]];
        if !close_price.is_finite() {
            close_price = 0.0;
        }
        StateParams {
            balance: self.balance.usd_total_rounded,
            order_book: OrderBook {
                bid: close_price,
                ask: close_price,
            },
            ema_bands: self.emas[idx].compute_bands(pside),
            grid_log_range: match pside {
                LONG => self.emas[idx].grid_log_range_long,
                SHORT => self.emas[idx].grid_log_range_short,
                _ => 0.0,
            },
        }
    }

    pub fn update_balance(&mut self, k: usize, mut pnl: f64, fee_paid: f64) {
        if self.balance.use_btc_collateral {
            self.balance.usd += fee_paid;

            if pnl > 0.0 {
                if self.balance.usd < 0.0 {
                    let offset_amount = pnl.min(-self.balance.usd);
                    self.balance.usd += offset_amount;
                    pnl -= offset_amount;
                }
                if pnl > 0.0 {
                    let btc_to_add = pnl / self.btc_usd_prices[k];
                    self.balance.btc += btc_to_add * SPOT_TRADING_FEE_FACTOR;
                }
            } else if pnl < 0.0 {
                self.balance.usd += pnl;
            }

            self.balance.usd_total = (self.balance.btc * self.btc_usd_prices[k]) + self.balance.usd;
            self.balance.btc_total = self.balance.usd_total / self.btc_usd_prices[k];
        } else {
            self.balance.usd += pnl + fee_paid;

            self.balance.usd_total = self.balance.usd;
            self.balance.usd_total_rounded = self.balance.usd;
            self.balance.btc_total = 0.0;
        }
    }

    pub fn update_equities(&mut self, k: usize) {
        let mut equity_usd = self.balance.usd_total;
        let mut equity_btc = self.balance.btc_total;

        let mut long_keys: Vec<usize> = self.positions.long.keys().cloned().collect();
        long_keys.sort();
        for idx in long_keys {
            let position = &self.positions.long[&idx];
            if !self.coin_is_valid_at(idx, k) {
                continue;
            }
            let current_price = self.hlcvs[[k, idx, CLOSE]];
            if !current_price.is_finite() {
                continue;
            }
            let upnl = calc_pnl_long(
                position.price,
                current_price,
                position.size,
                self.exchange_params_list[idx].c_mult,
            );
            equity_usd += upnl;
            equity_btc += upnl / self.btc_usd_prices[k];
        }

        let mut short_keys: Vec<usize> = self.positions.short.keys().cloned().collect();
        short_keys.sort();
        for idx in short_keys {
            let position = &self.positions.short[&idx];
            if !self.coin_is_valid_at(idx, k) {
                continue;
            }
            let current_price = self.hlcvs[[k, idx, CLOSE]];
            if !current_price.is_finite() {
                continue;
            }
            let upnl = calc_pnl_short(
                position.price,
                current_price,
                position.size,
                self.exchange_params_list[idx].c_mult,
            );
            equity_usd += upnl;
            equity_btc += upnl / self.btc_usd_prices[k];
        }

        self.equities.usd.push(equity_usd);
        self.equities.btc.push(equity_btc);
    }

    pub fn record_total_wallet_exposure(&mut self) {
        let total_wallet_exposure = self.compute_total_wallet_exposure();
        self.total_wallet_exposures.push(total_wallet_exposure);
    }

    pub fn compute_total_wallet_exposure(&self) -> f64 {
        let mut total = 0.0;
        for (&idx, position) in &self.positions.long {
            if position.size != 0.0 {
                total += calc_wallet_exposure(
                    self.exchange_params_list[idx].c_mult,
                    self.balance.usd_total,
                    position.size.abs(),
                    position.price,
                );
            }
        }
        for (&idx, position) in &self.positions.short {
            if position.size != 0.0 {
                total += calc_wallet_exposure(
                    self.exchange_params_list[idx].c_mult,
                    self.balance.usd_total,
                    position.size.abs(),
                    position.price,
                );
            }
        }
        total
    }

    pub fn update_actives_long(&mut self) -> Vec<usize> {
        let n_positions = self.effective_n_positions.long;

        let mut current_positions: Vec<usize> = self.positions.long.keys().cloned().collect();
        current_positions.sort();
        let preferred_coins = if current_positions.len() < n_positions {
            self.calc_preferred_coins(LONG)
        } else {
            Vec::new()
        };

        let actives = &mut self.actives.long;
        actives.clear();

        for &idx in &current_positions {
            actives.insert(idx);
        }

        let mut actives_without_pos = Vec::new();
        for &idx in &preferred_coins {
            if actives.len() >= n_positions {
                break;
            }
            if actives.insert(idx) {
                actives_without_pos.push(idx);
            }
        }

        actives_without_pos
    }

    pub fn update_actives_short(&mut self) -> Vec<usize> {
        let n_positions = self.effective_n_positions.short;

        let mut current_positions: Vec<usize> = self.positions.short.keys().cloned().collect();
        current_positions.sort();

        let preferred_coins = if current_positions.len() < n_positions {
            self.calc_preferred_coins(SHORT)
        } else {
            Vec::new()
        };

        let actives = &mut self.actives.short;
        actives.clear();

        for &idx in &current_positions {
            actives.insert(idx);
        }

        let mut actives_without_pos = Vec::new();
        for &idx in &preferred_coins {
            if actives.len() >= n_positions {
                break;
            }
            if actives.insert(idx) {
                actives_without_pos.push(idx);
            }
        }

        actives_without_pos
    }

    pub fn update_trailing_prices(&mut self, k: usize) {
        // ----- LONG side -----
        if self.trading_enabled.long && self.any_trailing_long {
            for (&idx, _) in &self.positions.long {
                if !self.trailing_enabled[idx].long {
                    continue;
                }
                if !self.coin_is_valid_at(idx, k) {
                    continue;
                }
                let bundle = self.trailing_prices.long.entry(idx).or_default();
                if self.did_fill_long.contains(&idx) {
                    *bundle = TrailingPriceBundle::default();
                } else {
                    let low = self.hlcvs[[k, idx, LOW]];
                    let high = self.hlcvs[[k, idx, HIGH]];
                    let close = self.hlcvs[[k, idx, CLOSE]];

                    if low < bundle.min_since_open {
                        bundle.min_since_open = low;
                        bundle.max_since_min = close;
                    } else {
                        bundle.max_since_min = bundle.max_since_min.max(high);
                    }

                    if high > bundle.max_since_open {
                        bundle.max_since_open = high;
                        bundle.min_since_max = close;
                    } else {
                        bundle.min_since_max = bundle.min_since_max.min(low);
                    }
                }
            }
        }

        // ----- SHORT side -----
        if self.trading_enabled.short && self.any_trailing_short {
            for (&idx, _) in &self.positions.short {
                if !self.trailing_enabled[idx].short {
                    continue;
                }
                if !self.coin_is_valid_at(idx, k) {
                    continue;
                }
                let bundle = self.trailing_prices.short.entry(idx).or_default();
                if self.did_fill_short.contains(&idx) {
                    *bundle = TrailingPriceBundle::default();
                } else {
                    let low = self.hlcvs[[k, idx, LOW]];
                    let high = self.hlcvs[[k, idx, HIGH]];
                    let close = self.hlcvs[[k, idx, CLOSE]];

                    if low < bundle.min_since_open {
                        bundle.min_since_open = low;
                        bundle.max_since_min = close;
                    } else {
                        bundle.max_since_min = bundle.max_since_min.max(high);
                    }

                    if high > bundle.max_since_open {
                        bundle.max_since_open = high;
                        bundle.min_since_max = close;
                    } else {
                        bundle.min_since_max = bundle.min_since_max.min(low);
                    }
                }
            }
        }
    }
}
