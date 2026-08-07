# Architecture F — Frozen Baseline Specification

## Identity
**Name:** London Opening-Range Breakout (Architecture F)

**Research hypothesis:** On EURUSD, a completed two-hour London opening range may contain useful information about the day's early price discovery; a later completed M15 close outside that range may have positive expectancy in the breakout direction when traded once per UTC day.

Architecture F is distinct from Architecture B multi-day compression, Architecture C session-exhaustion mean reversion, Architecture D impulse-pullback continuation, and Architecture E prior-day follow-through. It uses only the same-day London opening range and a later same-day breakout.

## Market and clock
- Symbol: EURUSD only.
- Signal/execution timeframe: M15.
- Completed bars only.
- All session rules defined in UTC.
- Opening range: M15 bars opening 06:00 through 07:45 UTC (8 bars).
- Signal window: M15 bars opening 08:00 through 13:45 UTC.
- Entry: first tradable tick of the next M15 bar after a valid completed signal.
- Force flat at or after 20:00 UTC same day.
- No weekend entries.
- Maximum one Architecture F trade per UTC day.

## Opening range
For each eligible UTC day, compute:
- OR high = highest high of the eight completed M15 bars from 06:00 through 07:45 UTC.
- OR low = lowest low of those eight bars.
- OR width = OR high - OR low.

The day is invalid if any required bar is unavailable or OR width <= 0.

## Volatility reference
Compute M15 ATR(14) on completed bars. The ATR value used for the breakout buffer is the ATR(14) value of the final opening-range bar (07:45 UTC), known before signal evaluation begins.

## Breakout signal
Two predeclared breakout buffers are tested:
- 0.00 × stored M15 ATR(14)
- 0.10 × stored M15 ATR(14)

Long signal:
1. Eligible signal bar opens 08:00-13:45 UTC.
2. Signal close is strictly above OR high + configured buffer.
3. Signal close is above signal open.

Short signal is the exact inverse using OR low - configured buffer and a bearish signal bar.

The first valid signal consumes the day, even if execution is later skipped by spread, sizing, or broker stop-distance validation. No re-entry.

## Entry and spread
- Long -> buy at first tradable tick of next M15 bar.
- Short -> sell at first tradable tick of next M15 bar.
- Skip if spread exceeds 2.0 pips.
- Maximum one open position.

## Stop loss
- Long stop = OR low.
- Short stop = OR high.

Skip if the stop is not on the correct side of entry or violates broker minimum stop-distance rules.

No trailing stop, break-even move, averaging, grid, martingale, pyramiding, or recovery sizing.

## Targets
Two predeclared fixed-R targets are tested:
- 1.00R
- 1.50R

R is absolute entry-to-stop distance. Exit at SL, TP, or 20:00 UTC force-flat, whichever occurs first.

## Position sizing and safety
- Risk per trade: 0.25% current equity.
- Daily loss limit: 1.0% start-of-day equity.
- Weekly loss limit: 2.0% start-of-week equity.
- Tester maximum equity drawdown gate: 15%.
- Live/demo circuit breaker: halt at 5% peak-to-valley drawdown pending manual review.
- Position size must respect broker minimum, maximum, and step.

## Four frozen configurations
| ID | Breakout buffer | Target | Stop |
|---|---:|---:|---|
| F01 | 0.00 × ATR(14) | 1.00R | opposite opening-range boundary |
| F02 | 0.10 × ATR(14) | 1.00R | opposite opening-range boundary |
| F03 | 0.00 × ATR(14) | 1.50R | opposite opening-range boundary |
| F04 | 0.10 × ATR(14) | 1.50R | opposite opening-range boundary |

No additional buffer, time-window, stop, filter, or target variants may be introduced after the first result is viewed.

## Development windows
- 2020-07-01 to 2021-06-30
- 2021-07-01 to 2022-06-30
- 2022-07-01 to 2023-06-30
- 2023-07-01 to 2024-06-30
- 2024-07-01 to 2025-06-30

## Frozen development gate
A configuration advances only if every condition passes:
- pooled net profit > 0 after modeled costs
- pooled PF >= 1.20
- pooled trades >= 100
- at least 4 of 5 annual windows profitable
- maximum consecutive losses <= 8
- worst equity drawdown <= 15%
- pooled recovery factor >= 1.25
- no safety or execution-integrity violation

Fewer than 100 pooled trades is retirement for insufficient evidence.

## Cost stress
Only for a configuration that passes development:
- double observed spread cost
- add 0.3 pip adverse slippage on entry
- add 0.3 pip adverse slippage on exit
- increase commission by 25%

Required stressed PF >= 1.15 and stressed net profit > 0.

## Robustness and OOS
OOS stays locked through development, cost stress, and robustness. Robustness must include annual stability, neighborhood consistency across only F01-F04, and source/binary/set/specification hash verification.

A final frozen candidate may open locked OOS once. OOS gate:
- net profit > 0
- PF >= 1.20
- at least 50 trades
- maximum equity drawdown <= 15%
- recovery factor >= 1.25
- no safety violation

Failure at OOS means retirement. OOS may not be reused for redesign.

## Decision states
Only: Advance, Retire, Validated.

## Freeze rule
This specification is frozen before the first Architecture F backtest. After the first result is viewed, no strategy definition, configuration, gate, development window, or cost assumption may be changed. If all four configurations fail, Architecture F is retired and research moves to another genuinely different hypothesis.
