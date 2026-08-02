# Sequence-risk qualification gate

PeakFX must not receive a green research decision solely because its chronological backtest or individual-trade permutation drawdown appears acceptable. A predeclared block-size sensitivity sweep must also pass explicit sequence-risk limits.

## Default gates

- Conservative P95 maximum drawdown: no greater than 20%.
- Conservative P99 maximum drawdown: no greater than 30%.
- Largest P95-to-historical drawdown ratio: no greater than 1.50x.
- Maximum ruin-threshold breach probability: no greater than 5%.
- Lowest P05 terminal equity: at least 80% of initial balance.
- Evidence must include at least four predeclared block sizes.

Threshold equality passes. Any measured breach is red. A run with no breach but insufficient block-size evidence is inconclusive, never green.

These are governance defaults for research triage, not universal statistical constants and not a profitability claim. They must be reviewed alongside cost stress, walk-forward testing, untouched out-of-sample evidence, open-equity risk, and demo-forward execution.
