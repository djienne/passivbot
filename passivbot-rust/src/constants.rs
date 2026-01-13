// HLCV array indices
pub const HIGH: usize = 0;
pub const LOW: usize = 1;
pub const CLOSE: usize = 2;
pub const VOLUME: usize = 3;

// Position sides
pub const LONG: usize = 0;
pub const SHORT: usize = 1;
pub const NO_POS: usize = 2;

// Trading constants
/// Factor applied when converting realized PNL to BTC (accounts for ~0.1% spot trading fee)
pub const SPOT_TRADING_FEE_FACTOR: f64 = 0.999;

/// Maximum iterations for grid order calculations to prevent infinite loops
pub const MAX_GRID_ITERATIONS: usize = 500;
