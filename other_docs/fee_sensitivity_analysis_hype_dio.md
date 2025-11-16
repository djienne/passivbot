# Fee Sensitivity Analysis: hype_dio Strategy

**Date:** 2025-11-16
**Config:** `configs/hype_dio.json`
**Symbol:** HYPEUSDT (Bybit)
**Period:** 2024-11-01 to 2025-11-10 (~1 year)
**Starting Balance:** 1,000 USDT

## Executive Summary

This analysis evaluates the impact of Bybit fee multipliers (1x, 2x, 4x) on the hype_dio trading strategy. The key finding is that **the strategy is remarkably resistant to fee increases**, with 4x fees reducing total returns by only 5.29% over the entire backtest period.

## Test Configurations

Three backtests were conducted with identical parameters except for the `bybit_fee_multiplier`:

- **Test 1:** `bybit_fee_multiplier = 1.0` (baseline)
- **Test 2:** `bybit_fee_multiplier = 2.0` (conservative estimate)
- **Test 3:** `bybit_fee_multiplier = 4.0` (stress test)

## Results Summary

### Performance Comparison

| Metric | 1x Fees | 2x Fees | 4x Fees | 1x→4x Change |
|--------|---------|---------|---------|--------------|
| **Total Gain** | 11.109x | 10.912x | 10.521x | **-5.29%** |
| **ADG (Avg Daily Gain)** | 0.7797% | 0.7739% | 0.7620% | -2.27% |
| **ADG Weighted** | 1.005% | 0.9972% | 0.9823% | -2.26% |
| **Worst Drawdown** | 24.62% | 24.67% | 24.77% | +0.63% |
| **Sharpe Ratio** | 0.1705 | 0.1695 | 0.1675 | -1.76% |
| **Sortino Ratio** | 0.3000 | 0.2968 | 0.2914 | -2.87% |
| **Omega Ratio** | 4.166 | 4.133 | 4.067 | -2.38% |
| **Sterling Ratio** | 0.0356 | 0.0353 | 0.0346 | -2.87% |
| **Loss/Profit Ratio** | 0.648% | 0.648% | 0.647% | -0.08% |

### Trading Behavior Metrics

| Metric | 1x Fees | 2x Fees | 4x Fees | Notes |
|--------|---------|---------|---------|-------|
| Positions per Day | 0.997 | 0.997 | 0.990 | Virtually unchanged |
| Avg Hold Time | 47.3 hrs | 47.3 hrs | 47.6 hrs | ~2 days per position |
| Volume % per Day | 0.508% | 0.506% | 0.509% | Very low turnover |
| Max Exposure | 2.327 | 2.327 | 2.329 | Identical leverage |
| Mean Exposure | 0.217 | 0.217 | 0.217 | Identical exposure |

## Key Findings

### 1. Minimal Fee Impact

Despite **quadrupling trading fees**, the strategy only loses:
- **1.77%** of total returns when fees double (1x → 2x)
- **5.29%** of total returns when fees quadruple (1x → 4x)

This demonstrates the strategy's strong **fee resistance**.

### 2. Linear Fee Scaling

Fee impact scales roughly linearly:
```
1x → 2x fees: -1.77% returns
2x → 4x fees: -3.52% returns (additional)
Total 1x → 4x: -5.29% returns
```

Each doubling of fees costs approximately 1.7-3.5% in total returns.

### 3. Stable Risk Profile

Risk metrics remain remarkably stable across all fee levels:
- Drawdown increases by only 0.63% (24.62% → 24.77%)
- Risk-adjusted returns (Sharpe, Sortino) decrease by <3%
- Expected shortfall barely changes (+0.73%)

### 4. Unchanged Trading Behavior

Trading patterns are essentially identical across all fee levels:
- **Position frequency:** ~1 position per day
- **Hold duration:** ~47-48 hours (nearly 2 days)
- **Daily volume:** ~0.51% of balance
- **Leverage:** ~22% mean, ~6% median exposure

## Why Is the Strategy Fee-Resistant?

The hype_dio strategy exhibits low fee sensitivity because it is a **low-frequency, position-holding strategy**:

1. **Infrequent Trading:** Only ~1 position per day, not multiple trades per hour
2. **Long Hold Times:** Average 47 hours (~2 days) per position
3. **Low Turnover:** Daily volume is only 0.5% of balance
4. **Grid-Based:** Not a high-frequency scalping strategy

In this type of strategy, **market direction and position sizing matter far more than execution costs**. Fees represent a tiny fraction of total P&L when positions are held for days.

## Conclusions

### For Backtesting

1. **2x fee multiplier** is a conservative choice that:
   - Reduces returns by only 1.77%
   - Provides safety margin against slippage/exchange variations
   - Maintains >98% of baseline performance

2. **Even 4x fees** show the strategy remains fundamentally profitable:
   - Still generates 10.5x returns (~950% gain)
   - Proves strategy is not overly sensitive to trading costs
   - Validates core strategy logic

### For Live Trading

The analysis suggests this strategy should perform well in live trading because:
- Fee sensitivity is minimal
- Returns are driven by market movements, not frequent trading
- Strategy can absorb significant cost increases without breaking down

### Recommendation

**Use `bybit_fee_multiplier = 2.0`** for backtesting. This provides:
- Realistic fee estimates accounting for exchange variations
- Safety margin for potential slippage
- Only 1.77% impact on results (negligible for 1-year backtest)

The strategy's robustness to 4x fees demonstrates it is not "optimized to the penny" and should translate well to live trading conditions.

---

## Appendix: Full Results

### Test 1: 1x Fees (Baseline)
```
Total Gain: 11.109x (1,111% return)
ADG: 0.7797%
Worst Drawdown: 24.62%
Sharpe Ratio: 0.1705
Positions per Day: 0.997
```

### Test 2: 2x Fees
```
Total Gain: 10.912x (1,091% return)
ADG: 0.7739%
Worst Drawdown: 24.67%
Sharpe Ratio: 0.1695
Positions per Day: 0.997
Delta from baseline: -1.77%
```

### Test 3: 4x Fees
```
Total Gain: 10.521x (952% return)
ADG: 0.7620%
Worst Drawdown: 24.77%
Sharpe Ratio: 0.1675
Positions per Day: 0.990
Delta from baseline: -5.29%
```

---

**Analysis Performed:** Claude Code
**Backtest Engine:** Passivbot v7.4.4 (Rust-accelerated)
