mod common;
mod long;
mod short;

pub use common::{calc_min_entry_qty, calc_initial_entry_qty};
pub use long::{calc_entries_long, calc_grid_entry_long, calc_next_entry_long, calc_trailing_entry_long};
pub use short::{calc_entries_short, calc_grid_entry_short, calc_next_entry_short, calc_trailing_entry_short};
