# Architecture D — Retirement Record

## Decision
**RETIRE** — Early-Session Impulse Pullback Continuation (Architecture D)

## Artifact reviewed
GitHub Actions run: `31213338119`

The uploaded baseline artifact passed independent integrity verification:
- expected runs: 20
- observed runs: 20
- matrix complete: true
- verifier errors: none
- OOS remained locked

## Development result
All four frozen configurations produced zero trades in every one of the five annual development windows.

| Configuration | Pooled net profit | Pooled trades | Profit factor | Profitable windows |
|---|---:|---:|---:|---:|
| D01 | $0.00 | 0 | 0.00 | 0/5 |
| D02 | $0.00 | 0 | 0.00 | 0/5 |
| D03 | $0.00 | 0 | 0.00 | 0/5 |
| D04 | $0.00 | 0 | 0.00 | 0/5 |

Each report showed 100% real-tick history quality, so these are non-empty MT5 executions with no qualifying Architecture D trades, not missing backtests.

## Gate decision
The frozen development gate requires pooled trades >= 100 in addition to positive profit, PF >= 1.20, 4/5 profitable annual windows, recovery factor >= 1.25, drawdown and loss-streak constraints, and execution integrity.

Architecture D fails immediately on minimum evidence and all profitability gates. The frozen specification does not permit post-result threshold or signal changes. No cost stress, robustness, or OOS testing is permitted.

## Final state
**Architecture D: RETIRED**

Research must move to a genuinely orthogonal hypothesis rather than loosening D01-D04 after viewing these results.
