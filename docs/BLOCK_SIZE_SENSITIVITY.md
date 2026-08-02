# Block-size sensitivity policy

A moving-block bootstrap result depends on the declared block size. PeakFX must not select only the block size that produces the lowest drawdown.

## Required procedure

1. Declare the complete ascending block-size set before running the analysis.
2. Run the same number of simulations, initial balance, ruin threshold, and seed for every size.
3. Report every block-size result.
4. Use the largest P95 maximum drawdown as the conservative planning estimate.
5. Also retain the largest P99 drawdown, largest ruin probability, and lowest P05 terminal equity.

The default research declaration is `(5, 10, 20, 40)` trades. It is a governance default, not a claim that these sizes capture every market regime.

## Interpretation

A materially increasing P95 drawdown as block size increases indicates that local dependence and loss clustering matter. A stable result across sizes lowers sensitivity to this modeling choice, but does not prove future robustness.

This analysis does not replace chronological backtesting, cost stress, walk-forward testing, untouched out-of-sample evidence, or demo-forward validation.
