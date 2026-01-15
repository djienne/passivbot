use super::common::{
    calc_cropped_reentry_qty, calc_initial_entry_qty, calc_min_entry_qty, calc_reentry_price_bid,
    calc_reentry_qty,
};
use crate::constants::MAX_GRID_ITERATIONS;
use crate::types::{
    BotParams, ExchangeParams, Order, OrderType, Position, StateParams, TrailingPriceBundle,
};
use crate::utils::{
    calc_ema_price_bid, calc_new_psize_pprice, calc_wallet_exposure, interpolate, round_, round_dn,
};

pub fn calc_grid_entry_long(
    exchange_params: &ExchangeParams,
    state_params: &StateParams,
    bot_params: &BotParams,
    position: &Position,
    wallet_exposure_limit_cap: f64,
) -> Order {
    if bot_params.wallet_exposure_limit == 0.0 || state_params.balance <= 0.0 {
        return Order::default();
    }
    let initial_entry_price = calc_ema_price_bid(
        exchange_params.price_step,
        state_params.order_book.bid,
        state_params.ema_bands.lower,
        bot_params.entry_initial_ema_dist,
    );
    if initial_entry_price <= exchange_params.price_step {
        return Order::default();
    }
    let mut initial_entry_qty = calc_initial_entry_qty(
        exchange_params,
        bot_params,
        state_params.balance,
        initial_entry_price,
    );
    if position.size == 0.0 {
        return Order {
            qty: initial_entry_qty,
            price: initial_entry_price,
            order_type: OrderType::EntryInitialNormalLong,
        };
    } else if position.size < initial_entry_qty * 0.8 {
        return Order {
            qty: f64::max(
                calc_min_entry_qty(initial_entry_price, exchange_params),
                round_dn(initial_entry_qty - position.size, exchange_params.qty_step),
            ),
            price: initial_entry_price,
            order_type: OrderType::EntryInitialPartialLong,
        };
    } else if position.size < initial_entry_qty {
        initial_entry_qty = round_(position.size, exchange_params.qty_step)
            .max(calc_min_entry_qty(initial_entry_price, exchange_params));
    }
    let wallet_exposure = calc_wallet_exposure(
        exchange_params.c_mult,
        state_params.balance,
        position.size,
        position.price,
    );
    let effective_wallet_exposure_limit =
        f64::min(wallet_exposure_limit_cap, bot_params.wallet_exposure_limit);
    if wallet_exposure >= effective_wallet_exposure_limit * 0.999 {
        return Order::default();
    }

    // normal re-entry
    let reentry_price = calc_reentry_price_bid(
        position.price,
        wallet_exposure,
        state_params.order_book.bid,
        exchange_params,
        bot_params,
        state_params.grid_log_range,
        effective_wallet_exposure_limit,
    );
    if reentry_price <= 0.0 {
        return Order::default();
    }
    let reentry_qty = f64::max(
        calc_reentry_qty(
            reentry_price,
            state_params.balance,
            position.size,
            bot_params.entry_grid_double_down_factor,
            exchange_params,
            bot_params,
            effective_wallet_exposure_limit,
        ),
        initial_entry_qty,
    );
    let (wallet_exposure_if_filled, reentry_qty_cropped) = calc_cropped_reentry_qty(
        exchange_params,
        bot_params,
        position,
        wallet_exposure,
        state_params.balance,
        reentry_qty,
        reentry_price,
        effective_wallet_exposure_limit,
    );
    if reentry_qty_cropped < reentry_qty {
        return Order {
            qty: reentry_qty_cropped,
            price: reentry_price,
            order_type: OrderType::EntryGridCroppedLong,
        };
    }
    // preview next order to check if reentry qty is to be inflated
    let (psize_if_filled, pprice_if_filled) = calc_new_psize_pprice(
        position.size,
        position.price,
        reentry_qty,
        reentry_price,
        exchange_params.qty_step,
    );
    let next_reentry_price = calc_reentry_price_bid(
        pprice_if_filled,
        wallet_exposure_if_filled,
        state_params.order_book.bid,
        exchange_params,
        bot_params,
        state_params.grid_log_range,
        effective_wallet_exposure_limit,
    );
    let next_reentry_qty = f64::max(
        calc_reentry_qty(
            next_reentry_price,
            state_params.balance,
            psize_if_filled,
            bot_params.entry_grid_double_down_factor,
            exchange_params,
            bot_params,
            effective_wallet_exposure_limit,
        ),
        initial_entry_qty,
    );
    let (_next_wallet_exposure_if_filled, next_reentry_qty_cropped) = calc_cropped_reentry_qty(
        exchange_params,
        bot_params,
        &Position {
            size: psize_if_filled,
            price: pprice_if_filled,
        },
        wallet_exposure_if_filled,
        state_params.balance,
        next_reentry_qty,
        next_reentry_price,
        effective_wallet_exposure_limit,
    );
    let effective_double_down_factor = next_reentry_qty_cropped / psize_if_filled;
    if effective_double_down_factor < bot_params.entry_grid_double_down_factor * 0.25 {
        // next reentry too small. Inflate current reentry.
        let new_entry_qty = interpolate(
            effective_wallet_exposure_limit,
            &[wallet_exposure, wallet_exposure_if_filled],
            &[position.size, position.size + reentry_qty],
        ) - position.size;
        Order {
            qty: round_(new_entry_qty, exchange_params.qty_step),
            price: reentry_price,
            order_type: OrderType::EntryGridInflatedLong,
        }
    } else {
        Order {
            qty: reentry_qty,
            price: reentry_price,
            order_type: OrderType::EntryGridNormalLong,
        }
    }
}

pub fn calc_next_entry_long(
    exchange_params: &ExchangeParams,
    state_params: &StateParams,
    bot_params: &BotParams,
    position: &Position,
    trailing_price_bundle: &TrailingPriceBundle,
) -> Order {
    let base_wallet_exposure_limit = bot_params.wallet_exposure_limit;
    if base_wallet_exposure_limit == 0.0 || state_params.balance <= 0.0 {
        return Order::default();
    }
    if bot_params.entry_trailing_grid_ratio >= 1.0 || bot_params.entry_trailing_grid_ratio <= -1.0 {
        return calc_trailing_entry_long(
            exchange_params,
            state_params,
            bot_params,
            position,
            trailing_price_bundle,
            base_wallet_exposure_limit,
        );
    } else if bot_params.entry_trailing_grid_ratio == 0.0 {
        return calc_grid_entry_long(
            exchange_params,
            state_params,
            bot_params,
            position,
            base_wallet_exposure_limit,
        );
    }
    let wallet_exposure = calc_wallet_exposure(
        exchange_params.c_mult,
        state_params.balance,
        position.size,
        position.price,
    );
    let wallet_exposure_ratio = if base_wallet_exposure_limit > 0.0 {
        wallet_exposure / base_wallet_exposure_limit
    } else {
        0.0
    };
    if bot_params.entry_trailing_grid_ratio > 0.0 {
        // trailing first
        if wallet_exposure_ratio < bot_params.entry_trailing_grid_ratio {
            let wallet_exposure_limit_cap = if wallet_exposure == 0.0 {
                base_wallet_exposure_limit
            } else {
                (base_wallet_exposure_limit * bot_params.entry_trailing_grid_ratio * 1.01)
                    .min(base_wallet_exposure_limit)
            };
            calc_trailing_entry_long(
                exchange_params,
                state_params,
                bot_params,
                position,
                trailing_price_bundle,
                wallet_exposure_limit_cap,
            )
        } else {
            calc_grid_entry_long(
                exchange_params,
                state_params,
                bot_params,
                position,
                base_wallet_exposure_limit,
            )
        }
    } else {
        // grid first
        if wallet_exposure_ratio < 1.0 + bot_params.entry_trailing_grid_ratio {
            let wallet_exposure_limit_cap = if wallet_exposure == 0.0 {
                base_wallet_exposure_limit
            } else {
                (base_wallet_exposure_limit * (1.0 + bot_params.entry_trailing_grid_ratio) * 1.01)
                    .min(base_wallet_exposure_limit)
            };
            calc_grid_entry_long(
                exchange_params,
                state_params,
                bot_params,
                position,
                wallet_exposure_limit_cap,
            )
        } else {
            calc_trailing_entry_long(
                exchange_params,
                state_params,
                bot_params,
                position,
                trailing_price_bundle,
                base_wallet_exposure_limit,
            )
        }
    }
}

pub fn calc_trailing_entry_long(
    exchange_params: &ExchangeParams,
    state_params: &StateParams,
    bot_params: &BotParams,
    position: &Position,
    trailing_price_bundle: &TrailingPriceBundle,
    wallet_exposure_limit_cap: f64,
) -> Order {
    let initial_entry_price = calc_ema_price_bid(
        exchange_params.price_step,
        state_params.order_book.bid,
        state_params.ema_bands.lower,
        bot_params.entry_initial_ema_dist,
    );
    if initial_entry_price <= exchange_params.price_step {
        return Order::default();
    }
    let mut initial_entry_qty = calc_initial_entry_qty(
        exchange_params,
        bot_params,
        state_params.balance,
        initial_entry_price,
    );
    if position.size == 0.0 {
        return Order {
            qty: initial_entry_qty,
            price: initial_entry_price,
            order_type: OrderType::EntryInitialNormalLong,
        };
    } else if position.size < initial_entry_qty * 0.8 {
        return Order {
            qty: f64::max(
                calc_min_entry_qty(initial_entry_price, exchange_params),
                round_dn(initial_entry_qty - position.size, exchange_params.qty_step),
            ),
            price: initial_entry_price,
            order_type: OrderType::EntryInitialPartialLong,
        };
    } else if position.size < initial_entry_qty {
        initial_entry_qty = round_(position.size, exchange_params.qty_step)
            .max(calc_min_entry_qty(initial_entry_price, exchange_params));
    }
    let wallet_exposure = calc_wallet_exposure(
        exchange_params.c_mult,
        state_params.balance,
        position.size,
        position.price,
    );
    let effective_wallet_exposure_limit =
        f64::min(wallet_exposure_limit_cap, bot_params.wallet_exposure_limit);
    if wallet_exposure > effective_wallet_exposure_limit * 0.999 {
        return Order::default();
    }
    let mut entry_triggered = false;
    let mut reentry_price = 0.0;
    if bot_params.entry_trailing_threshold_pct <= 0.0 {
        if bot_params.entry_trailing_retracement_pct > 0.0
            && trailing_price_bundle.max_since_min
                > trailing_price_bundle.min_since_open
                    * (1.0 + bot_params.entry_trailing_retracement_pct)
        {
            entry_triggered = true;
            reentry_price = state_params.order_book.bid;
        }
    } else {
        if bot_params.entry_trailing_retracement_pct <= 0.0 {
            entry_triggered = true;
            reentry_price = f64::min(
                state_params.order_book.bid,
                round_dn(
                    position.price * (1.0 - bot_params.entry_trailing_threshold_pct),
                    exchange_params.price_step,
                ),
            );
        } else {
            if trailing_price_bundle.min_since_open
                < position.price * (1.0 - bot_params.entry_trailing_threshold_pct)
                && trailing_price_bundle.max_since_min
                    > trailing_price_bundle.min_since_open
                        * (1.0 + bot_params.entry_trailing_retracement_pct)
            {
                entry_triggered = true;
                reentry_price = f64::min(
                    state_params.order_book.bid,
                    round_dn(
                        position.price
                            * (1.0 - bot_params.entry_trailing_threshold_pct
                                + bot_params.entry_trailing_retracement_pct),
                        exchange_params.price_step,
                    ),
                );
            }
        }
    }
    if !entry_triggered {
        return Order {
            qty: 0.0,
            price: 0.0,
            order_type: OrderType::EntryTrailingNormalLong,
        };
    }
    let reentry_qty = f64::max(
        calc_reentry_qty(
            reentry_price,
            state_params.balance,
            position.size,
            bot_params.entry_trailing_double_down_factor,
            exchange_params,
            bot_params,
            effective_wallet_exposure_limit,
        ),
        initial_entry_qty,
    );
    let (_wallet_exposure_if_filled, reentry_qty_cropped) = calc_cropped_reentry_qty(
        exchange_params,
        bot_params,
        position,
        wallet_exposure,
        state_params.balance,
        reentry_qty,
        reentry_price,
        effective_wallet_exposure_limit,
    );
    if reentry_qty_cropped < reentry_qty {
        Order {
            qty: reentry_qty_cropped,
            price: reentry_price,
            order_type: OrderType::EntryTrailingCroppedLong,
        }
    } else {
        Order {
            qty: reentry_qty,
            price: reentry_price,
            order_type: OrderType::EntryTrailingNormalLong,
        }
    }
}

pub fn calc_entries_long(
    exchange_params: &ExchangeParams,
    state_params: &StateParams,
    bot_params: &BotParams,
    position: &Position,
    trailing_price_bundle: &TrailingPriceBundle,
) -> Vec<Order> {
    let mut entries = Vec::<Order>::new();
    let mut psize = position.size;
    let mut pprice = position.price;
    let mut bid = state_params.order_book.bid;
    for _ in 0..MAX_GRID_ITERATIONS {
        let position_mod = Position {
            size: psize,
            price: pprice,
        };
        let mut state_params_mod = state_params.clone();
        state_params_mod.order_book.bid = bid;
        let entry = calc_next_entry_long(
            exchange_params,
            &state_params_mod,
            bot_params,
            &position_mod,
            trailing_price_bundle,
        );
        if entry.qty == 0.0 {
            break;
        }
        if !entries.is_empty() {
            if entry.order_type == OrderType::EntryTrailingNormalLong
                || entry.order_type == OrderType::EntryTrailingCroppedLong
            {
                break;
            }
            if entries[entries.len() - 1].price == entry.price {
                break;
            }
        }
        (psize, pprice) = calc_new_psize_pprice(
            psize,
            pprice,
            entry.qty,
            entry.price,
            exchange_params.qty_step,
        );
        bid = bid.min(entry.price);
        entries.push(entry);
    }
    entries
}
