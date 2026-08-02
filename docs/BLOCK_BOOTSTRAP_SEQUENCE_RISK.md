# Block-bootstrap sequence-risk analysis

This module complements individual-trade permutation by preserving short-range trade ordering inside sampled blocks.

## Method

- The chronological cost-inclusive trade vector is divided implicitly into circular moving blocks.
- Block starts are sampled with replacement.
- Trade order inside every sampled block is preserved.
- Each simulated path is truncated to the original trade count.
- Equity, maximum drawdown, terminal equity, and ruin frequency are calculated with vectorized NumPy matrices.

## Why it is stricter than individual permutation

Individual permutation destroys all serial dependence. Block bootstrap preserves local win/loss clustering and can therefore expose drawdown risk associated with short market regimes.

Because blocks are sampled with replacement, terminal equity can vary across runs. This is different from pure permutation, where every path contains every trade exactly once and terminal equity is fixed.

## Interpretation

The reported MDD ratio is:

`block-bootstrap P95 MDD / chronological historical MDD`

It is a governance diagnostic, not proof of future risk. A large ratio indicates that the observed chronology was favorable relative to the block-bootstrap model. A ratio near or below one does not prove robustness; longer regimes, changing costs, and unseen distributions can still dominate live results.

## Required sensitivity work

No single block size is authoritative. A qualified study should compare several predeclared block sizes, for example 5, 10, 20, and 40 trades, without selecting only the most favorable result. Capital planning should use the most credible adverse result alongside chronological, cost-stressed, walk-forward, out-of-sample, and demo-forward evidence.

This module does not modify the EA, execute MT5, optimize parameters, enable live trading, or claim profitability.
