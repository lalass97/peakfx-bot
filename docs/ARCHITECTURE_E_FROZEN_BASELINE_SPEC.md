# Architecture E — Frozen Baseline Specification

## Identity
**Name:** Prior-Day Directional Follow-Through (Architecture E)

**Research hypothesis:** On EURUSD, a completed UTC trading day with a large directional candle body relative to its full daily range may be followed by same-direction continuation when the next European session produces a completed M15 close beyond the prior UTC-day extreme.

Architecture E is intentionally different from Architecture B compression breakout, Architecture C session-exhaustion mean reversion, and Architecture D impulse-pullback continuation. It does not use a compression phase, Asian-range fade, or pullback-depth entry.

## Market and clock
- Symbol: EURUSD only.
- Signal/execution timeframe: M15.
- Signal evaluation: completed M15 bars only.
- All day and session rules are defined in UTC.
- Prior-day OHLC is reconstructed from completed M15 bars belonging to the prior valid UTC trading day.
- European signal window: completed M15 bars opening from 07:00 through 13:45 UTC.
- Entry: first tradable tick of the M15 bar immediately following a valid completed signal.
- Force flat: at or after 20:00 UTC on the same UTC trading day.
- No weekend entries.
- Maximum one Architecture E trade per UTC day.

## Prior UTC trading day
For the current eligible UTC day, locate the most recent earlier Monday-Friday UTC day for which all 96 M15 bars from 00:00 through 23:45 UTC are available.

For that prior day calculate:
- Open = open of the 00:00 UTC M15 bar.
- High = highest high of all 96 M15 bars.
- Low = lowest low of all 96 M15 bars.
- Close = close of the 23:45 UTC M15 bar.
- Range = High - Low.
- Body = abs(Close - Open).
- Body fraction = Body / Range.

The prior day is invalid if any of its 96 M15 bars is unavailable or Range <= 0.

## Directional qualification
Two predeclared body-fraction thresholds are tested:
- 0.55
- 0.65

Bullish prior day:
- Close > Open, and
- Body fraction >= configured threshold.

Bearish prior day:
- Close < Open, and
- Body fraction >= configured threshold.

Otherwise there is no setup for the current day.

## Continuation signal
A bullish continuation signal requires all of the following:
1. Prior day qualifies bullish.
2. Completed M15 signal bar opens within the frozen 07:00-13:45 UTC window.
3. Signal close is strictly above the prior UTC-day high.
4. Signal close is above signal open.

A bearish continuation signal is the exact inverse:
1. Prior day qualifies bearish.
2. Eligible M15 signal bar.
3. Signal close strictly below the prior UTC-day low.
4. Signal close below signal open.

The first valid signal consumes the UTC day even when execution is skipped because of spread, invalid sizing, or broker stop-distance restrictions. No re-entry is allowed.

## Entry
- Bullish signal -> buy on the first tradable tick of the next M15 bar.
- Bearish signal -> sell on the first tradable tick of the next M15 bar.
- Skip if spread exceeds 2.0 pips.
- One open position maximum.

## Stop loss
Stop is derived only from information known when the signal completes.

- Long: signal-bar low - 0.10 × prior UTC-day range.
- Short: signal-bar high + 0.10 × prior UTC-day range.

Skip the trade if the stop is not on the correct side of entry, required volume is invalid, or broker minimum stop-distance rules are violated.

No trailing stop, break-even move, averaging, grid, martingale, pyramiding, or recovery sizing is permitted.

## Target
Two predeclared fixed-R targets are tested:
- 1.00R
- 1.50R

R is the absolute entry-to-initial-stop distance. Exit at SL, TP, or the 20:00 UTC force-flat rule, whichever occurs first.

## Position sizing and safety
- Risk per trade: 0.25% of current equity.
- Daily loss limit: 1.0% of start-of-day equity.
- Weekly loss limit: 2.0% of start-of-week equity.
- Tester maximum equity drawdown gate: 15%.
- Live/demo circuit breaker: halt at 5% peak-to-valley drawdown pending manual review.
- Position size must respect broker minimum lot, maximum lot, and volume step.

## Four frozen configurations
| ID | Prior-day body fraction | Target | Stop basis |
|---|---:|---:|---|
| E01 | 0.55 | 1.00R | signal extreme + 0.10 × prior-day range |
| E02 | 0.65 | 1.00R | signal extreme + 0.10 × prior-day range |
| E03 | 0.55 | 1.50R | signal extreme + 0.10 × prior-day range |
| E04 | 0.65 | 1.50R | signal extreme + 0.10 × prior-day range |

These four configurations are the complete Architecture E baseline matrix. No additional body thresholds, signal windows, stop variants, trend filters, or targets may be introduced after the first result is viewed.

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
Apply only to a configuration that passes development:
- double observed spread cost
- add 0.3 pip adverse slippage on entry
- add 0.3 pip adverse slippage on exit
- increase commission by 25%

Required stressed PF >= 1.15 and stressed net profit > 0.

## Robustness and locked OOS
OOS remains locked through development, cost stress, and robustness. Robustness must include annual stability, neighborhood consistency across only E01-E04, source/binary/set/specification hash verification, and the frozen cost stress.

A final frozen candidate may open locked OOS once. OOS gate:
- net profit > 0
- PF >= 1.20
- at least 50 trades
- maximum equity drawdown <= 15%
- recovery factor >= 1.25
- no safety violation

Failure at OOS means retirement. OOS may not be reused for redesign.

## Decision states
Only these states are allowed:
- Advance
- Retire
- Validated

## Freeze rule
This specification is frozen before the first Architecture E result is viewed. No strategy definition, configuration, gate, development window, or cost assumption may be changed after that point. If all four configurations fail, Architecture E is retired and research moves to another genuinely different hypothesis.
