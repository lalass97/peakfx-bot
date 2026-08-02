# Pullback Research Decision Log

## Purpose

This file prevents previously rejected ideas from being reintroduced without new evidence. It records decisions from the EUR/USD H1 Test 4 pullback research program.

## Frozen reference

- Strategy: Test 4 trend + pullback + trigger
- Risk: 0.25% equity per trade
- Stop: ATR(14) × 1.5
- Target: 1.5R
- Maximum two entries per day
- Research only; no live approval

Historical runs have varied slightly because later telemetry builds corrected fill/R accounting and one v1.48 run stopped before the requested end date. Comparisons must therefore use exact run scope and trade-level joins, not only headline totals.

## Rejected: ADX filter

Decision: reject.

Reason: it did not create a sufficiently strong and stable improvement over the baseline. It is not part of the accepted pullback strategy.

## Rejected: ADX plus EMA separation

Decision: reject.

Reason: the combined filter reduced opportunity and did not produce a robust improvement.

## Rejected: confirmation candle

Decision: reject.

Observed comparison:

- Baseline full-history result: approximately −$506.79, PF 0.97, 1,196 trades
- Confirmation version: approximately −$495.92, PF 0.95, 659 trades

The small headline loss reduction was accompanied by a lower profit factor and a large reduction in trades. It did not demonstrate a stronger edge.

## Rejected: trigger-age-two exclusion

Decision: reject.

Reason: broad historical analysis showed materially worse net performance when trigger-age-two setups were removed.

## Rejected: fixed EMA50-distance threshold

Decision: reject as a coded rule.

A threshold above roughly 2.5 ATR reduced historical loss in one analysis but removed too many trades and was not stable enough to justify implementation. This may remain a diagnostic feature, not an approved filter.

## Rejected: partial-profit exits

Decision: reject partial profit at 0.75R and 1.00R.

Reason: both reliably worsened the reconstructed outcome relative to holding the original 1.5R target.

## Rejected: breakeven after milestone

v1.48 directly recorded first milestone crossings and subsequent returns to entry, eliminating the path-order ambiguity in earlier MFE/MAE analysis.

Analyzed data scope:

- Intended: 2016-01-01 through 2025-07-31
- Actual last event: 2025-07-07
- Completed matched trades: 1,078
- Entries/exits: clean 1:1 joins
- Restart flags: zero
- Telemetry consistency violations: zero

Baseline from that dataset:

- Net: −$301.15
- Profit factor: 0.980
- Expected payoff: −$0.279
- Winners/losers: 430/648
- Maximum consecutive losses: 15

### Breakeven at +0.50R

Decision: reject.

- Net: −$240.75
- PF: 0.971
- Expected payoff: −$0.22
- Winners/losses/breakeven: 235/361/482
- Original losers saved: 287
- Original winners converted to breakeven: 195, about 45%
- Years improved: 5 of 10
- Long net fell from $351.62 to $107.87

Although the net loss became smaller, profit factor worsened, nearly half of original winners were destroyed, improvement lacked yearly breadth, and the rule weakened the profitable long segment.

### Breakeven at +0.75R

Decision: reject.

- Net: −$372.35
- PF: 0.966
- Expected payoff: −$0.35
- Original losers saved: 183
- Original winners converted: 129

Net, PF and expectancy all worsened.

### Breakeven at +1.00R

Decision: reject.

- Net: −$407.27
- PF: 0.968
- Expected payoff: −$0.38
- Original losers saved: 104
- Original winners converted: 77

Net, PF and expectancy all worsened.

## Current research direction

Do not create a universal exit-management Test 6. The next work is baseline consolidation and directional diagnosis:

1. Preserve the exact recovered Test 4 source.
2. Recover the exact v1.48 telemetry source without reconstructing it from memory.
3. Build an event-driven Python model that mirrors the pullback state machine.
4. Reconcile MT5 and Python trade by trade.
5. Analyze long and short components independently.
6. Test a long-only candidate only if the long edge is broad across years, robust to costs and not carried by isolated periods.

## Termination rule

If the long-only component fails broad stability, cost sensitivity and out-of-sample gates, stop development of this strategy rather than adding more filters to force profitability.