use super::types::{update_adjusted_ema, EmaAlphas, Alphas};
use super::Backtest;
use crate::constants::{CLOSE, HIGH, LOW, VOLUME};
use crate::types::BotParamsPair;

pub fn calc_ema_alphas(bot_params_pair: &BotParamsPair) -> EmaAlphas {
    let mut ema_spans_long = [
        bot_params_pair.long.ema_span_0,
        bot_params_pair.long.ema_span_1,
        (bot_params_pair.long.ema_span_0 * bot_params_pair.long.ema_span_1).sqrt(),
    ];
    ema_spans_long.sort_by(|a, b| a.partial_cmp(b).unwrap());

    let mut ema_spans_short = [
        bot_params_pair.short.ema_span_0,
        bot_params_pair.short.ema_span_1,
        (bot_params_pair.short.ema_span_0 * bot_params_pair.short.ema_span_1).sqrt(),
    ];
    ema_spans_short.sort_by(|a, b| a.partial_cmp(b).unwrap());

    let ema_alphas_long = ema_spans_long.map(|x| 2.0 / (x + 1.0));
    let ema_alphas_short = ema_spans_short.map(|x| 2.0 / (x + 1.0));

    EmaAlphas {
        long: Alphas {
            alphas: ema_alphas_long,
        },
        short: Alphas {
            alphas: ema_alphas_short,
        },
        // EMA spans for the volume/log range filters (alphas precomputed from spans)
        vol_alpha_long: 2.0 / (bot_params_pair.long.filter_volume_ema_span as f64 + 1.0),
        vol_alpha_short: 2.0 / (bot_params_pair.short.filter_volume_ema_span as f64 + 1.0),
        log_range_alpha_long: 2.0 / (bot_params_pair.long.filter_log_range_ema_span as f64 + 1.0),
        log_range_alpha_short: 2.0 / (bot_params_pair.short.filter_log_range_ema_span as f64 + 1.0),
        grid_log_range_alpha_long: {
            let span = bot_params_pair.long.entry_grid_spacing_log_span_hours;
            if span > 0.0 {
                2.0 / (span + 1.0)
            } else {
                0.0
            }
        },
        grid_log_range_alpha_short: {
            let span = bot_params_pair.short.entry_grid_spacing_log_span_hours;
            if span > 0.0 {
                2.0 / (span + 1.0)
            } else {
                0.0
            }
        },
    }
}

pub fn calc_warmup_bars(bot_params: &[BotParamsPair]) -> usize {
    let mut max_span_minutes = 0.0f64;

    for pair in bot_params {
        let spans_long = [
            pair.long.ema_span_0,
            pair.long.ema_span_1,
            pair.long.filter_volume_ema_span as f64,
            pair.long.filter_log_range_ema_span as f64,
            pair.long.entry_grid_spacing_log_span_hours * 60.0,
        ];
        let spans_short = [
            pair.short.ema_span_0,
            pair.short.ema_span_1,
            pair.short.filter_volume_ema_span as f64,
            pair.short.filter_log_range_ema_span as f64,
            pair.short.entry_grid_spacing_log_span_hours * 60.0,
        ];
        for span in spans_long.iter().chain(spans_short.iter()) {
            if span.is_finite() {
                max_span_minutes = max_span_minutes.max(*span);
            }
        }
    }

    max_span_minutes.ceil() as usize
}

impl<'a> Backtest<'a> {
    #[inline]
    pub fn update_emas(&mut self, k: usize) {
        // Compute/refresh latest 1h bucket on whole-hour boundaries
        let current_ts = self.first_timestamp_ms + (k as u64) * 60_000u64;
        let hour_boundary = (current_ts / 3_600_000u64) * 3_600_000u64;
        if hour_boundary > self.last_hour_boundary_ms {
            // window is from max(first_ts, last_boundary) to previous minute
            let window_start_ms = self.first_timestamp_ms.max(self.last_hour_boundary_ms);
            if current_ts > window_start_ms + 60_000 {
                let start_idx = ((window_start_ms - self.first_timestamp_ms) / 60_000u64) as usize;
                let end_idx = if k == 0 { 0usize } else { k - 1 };
                if end_idx >= start_idx {
                    for i in 0..self.n_coins {
                        if let Some((coin_start, coin_end)) = self.coin_valid_range(i) {
                            let start = start_idx.max(coin_start);
                            let end = end_idx.min(coin_end);
                            if start > end {
                                continue;
                            }
                            let mut h = f64::MIN;
                            let mut l = f64::MAX;
                            let mut seen = false;
                            for j in start..=end {
                                let high = self.hlcvs[[j, i, HIGH]];
                                let low = self.hlcvs[[j, i, LOW]];
                                let close = self.hlcvs[[j, i, CLOSE]];
                                if !(high.is_finite() && low.is_finite() && close.is_finite()) {
                                    continue;
                                }
                                if high > h {
                                    h = high;
                                }
                                if low < l {
                                    l = low;
                                }
                                seen = true;
                            }
                            if !seen {
                                continue;
                            }
                            self.latest_hour[i] = super::types::HourBucket {
                                high: h,
                                low: l,
                            };
                        }
                    }
                }
            }
            self.last_hour_boundary_ms = hour_boundary;

            // Update hourly log-range EMAs for grid spacing adjustments
            for i in 0..self.n_coins {
                if self.coin_valid_range(i).is_none() {
                    continue;
                }
                let bucket = &self.latest_hour[i];
                if bucket.high <= 0.0
                    || bucket.low <= 0.0
                    || !bucket.high.is_finite()
                    || !bucket.low.is_finite()
                {
                    continue;
                }
                let hour_log_range = (bucket.high / bucket.low).ln();
                let grid_alpha_long = self.ema_alphas[i].grid_log_range_alpha_long;
                let grid_alpha_short = self.ema_alphas[i].grid_log_range_alpha_short;
                let emas = &mut self.emas[i];
                if grid_alpha_long > 0.0 {
                    emas.grid_log_range_long = update_adjusted_ema(
                        hour_log_range,
                        grid_alpha_long,
                        &mut emas.grid_log_range_long_num,
                        &mut emas.grid_log_range_long_den,
                    );
                }
                if grid_alpha_short > 0.0 {
                    emas.grid_log_range_short = update_adjusted_ema(
                        hour_log_range,
                        grid_alpha_short,
                        &mut emas.grid_log_range_short_num,
                        &mut emas.grid_log_range_short_den,
                    );
                }
            }
        }
        for i in 0..self.n_coins {
            if !self.coin_is_valid_at(i, k) {
                continue;
            }
            let close_price = self.hlcvs[[k, i, CLOSE]];
            if !close_price.is_finite() {
                continue;
            }
            let vol_raw = self.hlcvs[[k, i, VOLUME]];
            let vol = if vol_raw.is_finite() {
                f64::max(0.0, vol_raw)
            } else {
                0.0
            };
            let high = self.hlcvs[[k, i, HIGH]];
            let low = self.hlcvs[[k, i, LOW]];
            if !high.is_finite() || !low.is_finite() {
                continue;
            }

            let long_alphas = &self.ema_alphas[i].long.alphas;
            let short_alphas = &self.ema_alphas[i].short.alphas;

            let emas = &mut self.emas[i];

            // price EMAs (3 levels)
            for z in 0..3 {
                emas.long[z] = update_adjusted_ema(
                    close_price,
                    long_alphas[z],
                    &mut emas.long_num[z],
                    &mut emas.long_den[z],
                );
                emas.short[z] = update_adjusted_ema(
                    close_price,
                    short_alphas[z],
                    &mut emas.short_num[z],
                    &mut emas.short_den[z],
                );
            }

            // volume EMAs (single value per pside)
            let vol_alpha_long = self.ema_alphas[i].vol_alpha_long;
            let vol_alpha_short = self.ema_alphas[i].vol_alpha_short;
            emas.vol_long = update_adjusted_ema(
                vol,
                vol_alpha_long,
                &mut emas.vol_long_num,
                &mut emas.vol_long_den,
            );
            emas.vol_short = update_adjusted_ema(
                vol,
                vol_alpha_short,
                &mut emas.vol_short_num,
                &mut emas.vol_short_den,
            );

            // log range metric: ln(high / low)
            let log_range = if high > 0.0 && low > 0.0 {
                (high / low).ln()
            } else {
                0.0
            };
            emas.log_range_long = update_adjusted_ema(
                log_range,
                self.ema_alphas[i].log_range_alpha_long,
                &mut emas.log_range_long_num,
                &mut emas.log_range_long_den,
            );
            emas.log_range_short = update_adjusted_ema(
                log_range,
                self.ema_alphas[i].log_range_alpha_short,
                &mut emas.log_range_short_num,
                &mut emas.log_range_short_den,
            );
        }
    }
}
