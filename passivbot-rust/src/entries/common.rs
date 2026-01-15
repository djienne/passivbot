use crate::types::{BotParams, ExchangeParams, Position};
use crate::utils::{calc_wallet_exposure_if_filled, cost_to_qty, interpolate, round_, round_up};

pub fn calc_initial_entry_qty(
    exchange_params: &ExchangeParams,
    bot_params: &BotParams,
    balance: f64,
    entry_price: f64,
) -> f64 {
    f64::max(
        calc_min_entry_qty(entry_price, exchange_params),
        round_(
            cost_to_qty(
                balance * bot_params.wallet_exposure_limit * bot_params.entry_initial_qty_pct,
                entry_price,
                exchange_params.c_mult,
            ),
            exchange_params.qty_step,
        ),
    )
}

pub fn calc_min_entry_qty(entry_price: f64, exchange_params: &ExchangeParams) -> f64 {
    f64::max(
        exchange_params.min_qty,
        round_up(
            cost_to_qty(
                exchange_params.min_cost,
                entry_price,
                exchange_params.c_mult,
            ),
            exchange_params.qty_step,
        ),
    )
}

pub fn calc_cropped_reentry_qty(
    exchange_params: &ExchangeParams,
    bot_params: &BotParams,
    position: &Position,
    wallet_exposure: f64,
    balance: f64,
    entry_qty: f64,
    entry_price: f64,
    wallet_exposure_limit_cap: f64,
) -> (f64, f64) {
    let effective_wallet_exposure_limit =
        f64::min(wallet_exposure_limit_cap, bot_params.wallet_exposure_limit);
    let position_size_abs = position.size.abs();
    let entry_qty_abs = entry_qty.abs();
    let wallet_exposure_if_filled = calc_wallet_exposure_if_filled(
        balance,
        position_size_abs,
        position.price,
        entry_qty_abs,
        entry_price,
        exchange_params,
    );
    let min_entry_qty = calc_min_entry_qty(entry_price, exchange_params);
    if wallet_exposure_if_filled > effective_wallet_exposure_limit * 1.01 {
        // reentry too big. Crop current reentry qty.
        let entry_qty_abs = interpolate(
            effective_wallet_exposure_limit,
            &[wallet_exposure, wallet_exposure_if_filled],
            &[position_size_abs, position_size_abs + entry_qty_abs],
        ) - position_size_abs;
        (
            wallet_exposure_if_filled,
            f64::max(
                round_(entry_qty_abs, exchange_params.qty_step),
                min_entry_qty,
            ),
        )
    } else {
        (
            wallet_exposure_if_filled,
            f64::max(entry_qty_abs, min_entry_qty),
        )
    }
}

pub fn calc_reentry_qty(
    entry_price: f64,
    balance: f64,
    position_size: f64,
    double_down_factor: f64,
    exchange_params: &ExchangeParams,
    bot_params: &BotParams,
    wallet_exposure_limit_cap: f64,
) -> f64 {
    let effective_wallet_exposure_limit =
        f64::min(wallet_exposure_limit_cap, bot_params.wallet_exposure_limit);
    f64::max(
        calc_min_entry_qty(entry_price, exchange_params),
        round_(
            f64::max(
                position_size.abs() * double_down_factor,
                cost_to_qty(balance, entry_price, exchange_params.c_mult)
                    * effective_wallet_exposure_limit
                    * bot_params.entry_initial_qty_pct,
            ),
            exchange_params.qty_step,
        ),
    )
}

pub fn calc_reentry_price_bid(
    position_price: f64,
    wallet_exposure: f64,
    order_book_bid: f64,
    exchange_params: &ExchangeParams,
    bot_params: &BotParams,
    grid_log_range: f64,
    wallet_exposure_limit_cap: f64,
) -> f64 {
    use crate::utils::round_dn;
    let effective_wallet_exposure_limit =
        f64::min(wallet_exposure_limit_cap, bot_params.wallet_exposure_limit);
    let we_multiplier = if effective_wallet_exposure_limit > 0.0 {
        (wallet_exposure / effective_wallet_exposure_limit)
            * bot_params.entry_grid_spacing_we_weight
    } else {
        0.0
    };
    let log_multiplier = grid_log_range * bot_params.entry_grid_spacing_log_weight;
    let spacing_multiplier = 1.0 + we_multiplier + log_multiplier;
    let reentry_price = f64::min(
        round_dn(
            position_price
                * (1.0 - bot_params.entry_grid_spacing_pct * spacing_multiplier.max(0.0)),
            exchange_params.price_step,
        ),
        order_book_bid,
    );
    if reentry_price <= exchange_params.price_step {
        0.0
    } else {
        reentry_price
    }
}

pub fn calc_reentry_price_ask(
    position_price: f64,
    wallet_exposure: f64,
    order_book_ask: f64,
    exchange_params: &ExchangeParams,
    bot_params: &BotParams,
    grid_log_range: f64,
    wallet_exposure_limit_cap: f64,
) -> f64 {
    let effective_wallet_exposure_limit =
        f64::min(wallet_exposure_limit_cap, bot_params.wallet_exposure_limit);
    let we_multiplier = if effective_wallet_exposure_limit > 0.0 {
        (wallet_exposure / effective_wallet_exposure_limit)
            * bot_params.entry_grid_spacing_we_weight
    } else {
        0.0
    };
    let log_multiplier = grid_log_range * bot_params.entry_grid_spacing_log_weight;
    let spacing_multiplier = 1.0 + we_multiplier + log_multiplier;
    let reentry_price = f64::max(
        round_up(
            position_price
                * (1.0 + bot_params.entry_grid_spacing_pct * spacing_multiplier.max(0.0)),
            exchange_params.price_step,
        ),
        order_book_ask,
    );
    if reentry_price <= exchange_params.price_step {
        0.0
    } else {
        reentry_price
    }
}
