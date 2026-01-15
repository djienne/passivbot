use super::types::OpenOrders;
use super::Backtest;
use crate::closes::{calc_closes_long, calc_closes_short, calc_next_close_long, calc_next_close_short};
use crate::constants::{CLOSE, HIGH, LOW, LONG, NO_POS, SHORT};
use crate::entries::{calc_entries_long, calc_entries_short, calc_min_entry_qty, calc_next_entry_long, calc_next_entry_short};
use crate::types::{Order, OrderType, Position};
use crate::utils::{
    calc_auto_unstuck_allowance, calc_pnl_long, calc_pnl_short, calc_pprice_diff_int,
    calc_wallet_exposure, cost_to_qty, round_, round_dn, round_up,
};

impl<'a> Backtest<'a> {
    pub fn update_open_orders_long_single(&mut self, k: usize, idx: usize) {
        if !self.coin_is_valid_at(idx, k) {
            return;
        }
        let state_params = self.create_state_params(k, idx, LONG);
        let position = self
            .positions
            .long
            .get(&idx)
            .cloned()
            .unwrap_or(Position::default());

        // check if coin is delisted; if so, close pos as unstuck close
        if self.positions.long.contains_key(&idx) {
            if let Some(&delist_timestamp) = self.last_valid_timestamps.get(&idx) {
                if k >= delist_timestamp {
                    self.open_orders.long.entry(idx).or_default().closes = vec![Order {
                        qty: -self.positions.long[&idx].size,
                        price: round_(
                            f64::min(
                                self.hlcvs[[k, idx, HIGH]]
                                    - self.exchange_params_list[idx].price_step,
                                self.positions.long[&idx].price,
                            ),
                            self.exchange_params_list[idx].price_step,
                        ),
                        order_type: OrderType::CloseUnstuckLong,
                    }];
                    self.open_orders
                        .long
                        .entry(idx)
                        .or_default()
                        .entries
                        .clear();
                    return;
                }
            }
        }

        let next_entry_order = calc_next_entry_long(
            &self.exchange_params_list[idx],
            &state_params,
            self.bp(idx, LONG),
            &position,
            &self.trailing_prices.long[&idx],
        );
        // peek next candle to see if order will fill
        if self.order_filled(k + 1, idx, &next_entry_order) {
            self.open_orders.long.entry(idx).or_default().entries = calc_entries_long(
                &self.exchange_params_list[idx],
                &state_params,
                self.bp(idx, LONG),
                &position,
                &self.trailing_prices.long[&idx],
            );
        } else {
            self.open_orders.long.entry(idx).or_default().entries = [next_entry_order].to_vec();
        }
        let next_close_order = calc_next_close_long(
            &self.exchange_params_list[idx],
            &state_params,
            self.bp(idx, LONG),
            &position,
            &self.trailing_prices.long[&idx],
        );
        // peek next candle to see if order will fill
        if self.order_filled(k + 1, idx, &next_close_order) {
            // calc all orders
            self.open_orders.long.entry(idx).or_default().closes = calc_closes_long(
                &self.exchange_params_list[idx],
                &state_params,
                self.bp(idx, LONG),
                &position,
                &self.trailing_prices.long[&idx],
            );
        } else {
            self.open_orders.long.entry(idx).or_default().closes = [next_close_order].to_vec();
        }
    }

    pub fn update_open_orders_short_single(&mut self, k: usize, idx: usize) {
        if !self.coin_is_valid_at(idx, k) {
            return;
        }
        let state_params = self.create_state_params(k, idx, SHORT);
        let position = self
            .positions
            .short
            .get(&idx)
            .cloned()
            .unwrap_or(Position::default());

        // check if coin is delisted; if so, close pos as unstuck close
        if self.positions.short.contains_key(&idx) {
            if let Some(&delist_timestamp) = self.last_valid_timestamps.get(&idx) {
                if k >= delist_timestamp {
                    self.open_orders.short.entry(idx).or_default().closes = vec![Order {
                        qty: self.positions.short[&idx].size.abs(),
                        price: round_(
                            f64::max(
                                self.hlcvs[[k, idx, LOW]]
                                    + self.exchange_params_list[idx].price_step,
                                self.positions.short[&idx].price,
                            ),
                            self.exchange_params_list[idx].price_step,
                        ),
                        order_type: OrderType::CloseUnstuckShort,
                    }];
                    self.open_orders
                        .short
                        .entry(idx)
                        .or_default()
                        .entries
                        .clear();
                    return;
                }
            }
        }
        let next_entry_order = calc_next_entry_short(
            &self.exchange_params_list[idx],
            &state_params,
            self.bp(idx, SHORT),
            &position,
            &self.trailing_prices.short[&idx],
        );
        // peek next candle to see if order will fill
        if self.order_filled(k + 1, idx, &next_entry_order) {
            self.open_orders.short.entry(idx).or_default().entries = calc_entries_short(
                &self.exchange_params_list[idx],
                &state_params,
                self.bp(idx, SHORT),
                &position,
                &self.trailing_prices.short[&idx],
            );
        } else {
            self.open_orders.short.entry(idx).or_default().entries = [next_entry_order].to_vec();
        }

        let next_close_order = calc_next_close_short(
            &self.exchange_params_list[idx],
            &state_params,
            self.bp(idx, SHORT),
            &position,
            &self.trailing_prices.short[&idx],
        );
        // peek next candle to see if order will fill
        if self.order_filled(k + 1, idx, &next_close_order) {
            self.open_orders.short.entry(idx).or_default().closes = calc_closes_short(
                &self.exchange_params_list[idx],
                &state_params,
                self.bp(idx, SHORT),
                &position,
                &self.trailing_prices.short[&idx],
            );
        } else {
            self.open_orders.short.entry(idx).or_default().closes = [next_close_order].to_vec()
        }
    }

    pub fn order_filled(&self, k: usize, idx: usize, order: &Order) -> bool {
        if !self.coin_is_tradeable_at(idx, k) {
            return false;
        }
        // check if filled in current candle (pass k+1 to check if will fill in next candle)
        if order.qty > 0.0 {
            self.hlcvs[[k, idx, LOW]] < order.price
        } else if order.qty < 0.0 {
            self.hlcvs[[k, idx, HIGH]] > order.price
        } else {
            false
        }
    }

    pub fn calc_unstucking_close(&mut self, k: usize) -> (usize, usize, Order) {
        let mut stuck_positions: Vec<(usize, usize, f64)> = Vec::new(); // (idx, pside, pprice_diff)

        // Calculate long unstuck allowance and check long positions
        let long_allowance = if self.bot_params_master.long.unstuck_loss_allowance_pct > 0.0 {
            calc_auto_unstuck_allowance(
                self.balance.usd_total_rounded,
                self.bot_params_master.long.unstuck_loss_allowance_pct
                    * self.bot_params_master.long.total_wallet_exposure_limit,
                self.pnl_cumsum_max,
                self.pnl_cumsum_running,
            )
        } else {
            0.0
        };

        if long_allowance > 0.0 {
            for (&idx, position) in &self.positions.long {
                if !self.coin_is_tradeable_at(idx, k) {
                    continue;
                }
                let wallet_exposure = calc_wallet_exposure(
                    self.exchange_params_list[idx].c_mult,
                    self.balance.usd_total_rounded,
                    position.size,
                    position.price,
                );

                if self.bp(idx, LONG).wallet_exposure_limit == 0.0
                    || wallet_exposure / self.bp(idx, LONG).wallet_exposure_limit
                        > self.bp(idx, LONG).unstuck_threshold
                {
                    let ema_bands = self.emas[idx].compute_bands(LONG);
                    let ema_price = round_up(
                        ema_bands.upper * (1.0 + self.bp(idx, LONG).unstuck_ema_dist),
                        self.exchange_params_list[idx].price_step,
                    );

                    let current_price = self.hlcvs[[k, idx, CLOSE]];
                    if current_price >= ema_price {
                        let pprice_diff = calc_pprice_diff_int(LONG, position.price, current_price);
                        stuck_positions.push((idx, LONG, pprice_diff));
                    }
                }
            }
        }

        // Calculate short unstuck allowance and check short positions
        let short_allowance = if self.bot_params_master.short.unstuck_loss_allowance_pct > 0.0 {
            calc_auto_unstuck_allowance(
                self.balance.usd_total_rounded,
                self.bot_params_master.short.unstuck_loss_allowance_pct
                    * self.bot_params_master.short.total_wallet_exposure_limit,
                self.pnl_cumsum_max,
                self.pnl_cumsum_running,
            )
        } else {
            0.0
        };

        if short_allowance > 0.0 {
            for (&idx, position) in &self.positions.short {
                if !self.coin_is_tradeable_at(idx, k) {
                    continue;
                }
                let wallet_exposure = calc_wallet_exposure(
                    self.exchange_params_list[idx].c_mult,
                    self.balance.usd_total_rounded,
                    position.size.abs(),
                    position.price,
                );

                if self.bp(idx, SHORT).wallet_exposure_limit == 0.0
                    || wallet_exposure / self.bp(idx, SHORT).wallet_exposure_limit
                        > self.bp(idx, SHORT).unstuck_threshold
                {
                    let ema_bands = self.emas[idx].compute_bands(SHORT);
                    let ema_price = round_dn(
                        ema_bands.lower * (1.0 - self.bp(idx, SHORT).unstuck_ema_dist),
                        self.exchange_params_list[idx].price_step,
                    );

                    let current_price = self.hlcvs[[k, idx, CLOSE]];
                    if current_price <= ema_price {
                        let pprice_diff =
                            calc_pprice_diff_int(SHORT, position.price, current_price);
                        stuck_positions.push((idx, SHORT, pprice_diff));
                    }
                }
            }
        }

        if stuck_positions.is_empty() {
            return (NO_POS, NO_POS, Order::default());
        }

        // Sort by pprice_diff, then by idx for deterministic ordering
        stuck_positions.sort_by(|(i1, _, d1), (i2, _, d2)| {
            match d1.partial_cmp(d2).unwrap_or(std::cmp::Ordering::Equal) {
                std::cmp::Ordering::Equal => i1.cmp(i2),
                other => other,
            }
        });

        // Process stuck positions
        for (idx, pside, _pprice_diff) in stuck_positions {
            let close_price = self.hlcvs[[k, idx, CLOSE]];

            if pside == LONG {
                let min_entry_qty =
                    calc_min_entry_qty(close_price, &self.exchange_params_list[idx]);
                let mut close_qty = -f64::min(
                    self.positions.long[&idx].size,
                    f64::max(
                        min_entry_qty,
                        round_dn(
                            cost_to_qty(
                                self.balance.usd_total_rounded
                                    * self.bp(idx, LONG).wallet_exposure_limit
                                    * self.bp(idx, LONG).unstuck_close_pct,
                                close_price,
                                self.exchange_params_list[idx].c_mult,
                            ),
                            self.exchange_params_list[idx].qty_step,
                        ),
                    ),
                );

                if close_qty != 0.0 {
                    let pnl_if_closed = calc_pnl_long(
                        self.positions.long[&idx].price,
                        close_price,
                        close_qty,
                        self.exchange_params_list[idx].c_mult,
                    );
                    let pnl_if_closed_abs = pnl_if_closed.abs();

                    if pnl_if_closed < 0.0 && pnl_if_closed_abs > long_allowance {
                        close_qty = -f64::min(
                            self.positions.long[&idx].size,
                            f64::max(
                                min_entry_qty,
                                round_dn(
                                    close_qty.abs() * (long_allowance / pnl_if_closed_abs),
                                    self.exchange_params_list[idx].qty_step,
                                ),
                            ),
                        );
                    }

                    return (
                        idx,
                        LONG,
                        Order {
                            qty: close_qty,
                            price: close_price,
                            order_type: OrderType::CloseUnstuckLong,
                        },
                    );
                }
            } else {
                // SHORT
                let min_entry_qty =
                    calc_min_entry_qty(close_price, &self.exchange_params_list[idx]);
                let mut close_qty = f64::min(
                    self.positions.short[&idx].size.abs(),
                    f64::max(
                        min_entry_qty,
                        round_dn(
                            cost_to_qty(
                                self.balance.usd_total_rounded
                                    * self.bp(idx, SHORT).wallet_exposure_limit
                                    * self.bp(idx, SHORT).unstuck_close_pct,
                                close_price,
                                self.exchange_params_list[idx].c_mult,
                            ),
                            self.exchange_params_list[idx].qty_step,
                        ),
                    ),
                );

                if close_qty != 0.0 {
                    let pnl_if_closed = calc_pnl_short(
                        self.positions.short[&idx].price,
                        close_price,
                        close_qty,
                        self.exchange_params_list[idx].c_mult,
                    );
                    let pnl_if_closed_abs = pnl_if_closed.abs();

                    if pnl_if_closed < 0.0 && pnl_if_closed_abs > short_allowance {
                        close_qty = f64::min(
                            self.positions.short[&idx].size.abs(),
                            f64::max(
                                min_entry_qty,
                                round_dn(
                                    close_qty * (short_allowance / pnl_if_closed_abs),
                                    self.exchange_params_list[idx].qty_step,
                                ),
                            ),
                        );
                    }

                    return (
                        idx,
                        SHORT,
                        Order {
                            qty: close_qty,
                            price: close_price,
                            order_type: OrderType::CloseUnstuckShort,
                        },
                    );
                }
            }
        }

        (NO_POS, NO_POS, Order::default())
    }

    pub fn update_open_orders_all(&mut self, k: usize) {
        self.open_orders = OpenOrders::default();
        if self.trading_enabled.long {
            let mut active_long_indices: Vec<usize> = self.positions.long.keys().cloned().collect();
            if self.positions.long.len() != self.effective_n_positions.long {
                self.update_actives_long();
                active_long_indices = self.actives.long.iter().cloned().collect();
            }
            active_long_indices.sort();
            for &idx in &active_long_indices {
                if self.coin_is_tradeable_at(idx, k) {
                    self.update_open_orders_long_single(k, idx);
                }
            }
        }
        if self.trading_enabled.short {
            let mut active_short_indices: Vec<usize> =
                self.positions.short.keys().cloned().collect();
            if self.positions.short.len() != self.effective_n_positions.short {
                self.update_actives_short();
                active_short_indices = self.actives.short.iter().cloned().collect();
            }
            active_short_indices.sort();
            for &idx in &active_short_indices {
                if self.coin_is_tradeable_at(idx, k) {
                    self.update_open_orders_short_single(k, idx);
                }
            }
        }

        let (unstucking_idx, unstucking_pside, unstucking_close) = self.calc_unstucking_close(k);
        if unstucking_pside != NO_POS {
            match unstucking_pside {
                LONG => {
                    self.open_orders
                        .long
                        .entry(unstucking_idx)
                        .or_default()
                        .closes = vec![unstucking_close];
                }
                SHORT => {
                    self.open_orders
                        .short
                        .entry(unstucking_idx)
                        .or_default()
                        .closes = vec![unstucking_close];
                }
                _ => unreachable!(),
            }
        }
    }
}
