# Test 4 Repair-or-Retire Protocol

## Principle

Do not tune parameters until the backtest turns green. First determine whether the entry has measurable favorable excursion, whether exits are destroying that edge, or whether the signal should be retired.

## Current evidence

The latest milestone telemetry available for the v1.48 research run contains 1,078 completed trades, including 648 original losers.

At the +0.50R milestone:

- 287 original losers had previously reached +0.50R before finishing as losses.
- 287 / 648 = 44.29% of original losers.
- 195 original winners would have been converted to breakeven by a +0.50R breakeven rule.
- The +0.50R breakeven rule reduced headline loss but worsened profit factor and materially damaged the profitable long segment.

This does not pass a predeclared rule requiring more than 50% of losing trades to reach +0.50R. It also does not establish the separate retirement condition that at least 60% of losing trades never reach +0.25R, because the required +0.25R path statistic has not yet been verified.

## Required next gate

Before testing a lower target, time stop, or session restriction, produce a direction-split excursion table for losing trades:

- share reaching +0.25R;
- share reaching +0.50R;
- share reaching +0.75R;
- median and percentile MFE;
- median and percentile MAE;
- long and short results separately;
- results by year and session;
- results after realistic spread and slippage assumptions.

No repair hypothesis is promoted unless it survives these diagnostics.

## Conditional repair branch

Only when excursion evidence supports short-term entry alpha, test one modification at a time:

1. Fixed targets: 0.8R, 1.0R, 1.2R.
2. Time stops: exit after 4, 5, or 6 completed H1 bars.
3. Session candidates: evaluate UTC windows, including 07:00-16:00, without hard-coding a timezone assumption.
4. Cost stress: baseline cost, 1.5x spread, and 2x spread, plus explicit slippage.

Every candidate must be compared with the unchanged baseline over identical trades and dates. Promotion requires improvement in net expectancy, profit factor, drawdown, yearly breadth, and out-of-sample behavior. A smaller headline loss alone is insufficient.

## Retirement branch

Retire Test 4 when the verified data shows no useful favorable excursion, or when all repair candidates fail cost, stability, and out-of-sample gates.

Retirement means:

- freeze the final evidence;
- stop adding filters to the EMA pullback entry;
- do not optimize around the loss;
- begin a separate research program for a different mechanism.

Possible future mechanisms are volatility-compression breakout, session mean reversion, or higher-timeframe/multi-pair trend research. These are separate strategies and must not be blended into Test 4.

## Safety

- Research and demo only.
- No live trading.
- No merge to `main` before full parity and reconciliation.
- No profitability claim.
- No parameter is accepted because it merely turns one backtest positive.
