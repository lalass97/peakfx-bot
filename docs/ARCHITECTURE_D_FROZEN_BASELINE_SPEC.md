# Architecture D — Frozen Baseline Specification

## Identity
**Name:** Early-Session Impulse Pullback Continuation (Architecture D)

**Research hypothesis:** On EURUSD, a statistically large and directionally efficient early-European H1 impulse may retain positive continuation expectancy after a completed intraday pullback and resumption bar.

Architecture D is orthogonal to Architecture B and C. It does not use multi-day volatility compression, compression boxes, breakout-after-compression logic, Asian-range exhaustion fades, or mean-reversion entries.

This is a price/time hypothesis only. It does not claim centralized order flow, institutional positioning, DOM, or options-flow observation.

## Market and clock
- Symbol: EURUSD only.
- Signal/execution timeframe: H1.
- Signal evaluation: completed H1 bars only.
- All session rules are defined in UTC.
- Runner artifacts must record the broker-server to UTC conversion used by the EA.
- Early-European impulse window: four completed H1 bars opening at 06:00, 07:00, 08:00, and 09:00 UTC.
- Pullback/resumption signal window: completed H1 bars opening from 10:00 through 14:00 UTC.
- Entry: first tradable tick of the H1 bar immediately following an eligible completed signal.
- Force flat: at or after 20:00 UTC on the same trading day.
- No weekend entries. No new entry on Friday after 15:00 UTC.

## Impulse definition
For each eligible UTC trading day:
1. Impulse open = open of the 06:00 UTC H1 bar.
2. Impulse close = close of the 09:00 UTC H1 bar.
3. Impulse high = highest high of the four bars.
4. Impulse low = lowest low of the four bars.
5. Impulse range = impulse high - impulse low.
6. Directional displacement = absolute value of impulse close - impulse open.
7. Directional efficiency = directional displacement / impulse range.
8. The day is invalid if any of the four H1 bars is unavailable, if impulse range <= 0, or if directional displacement <= 0.

Bullish impulse: impulse close > impulse open.
Bearish impulse: impulse close < impulse open.

A valid directional impulse requires efficiency >= 0.60.

## Recent range reference
- Use the previous 20 completed eligible trading days before the current day.
- For each prior day, calculate the same 06:00–09:59 UTC four-bar impulse range.
- Median impulse range = arithmetic median of those 20 valid prior impulse ranges.
- Current day is invalid if fewer than 20 prior valid impulse ranges are available.
- The current day's range is not included in its own reference distribution.

## Impulse-strength thresholds
Two predeclared thresholds are tested:
- 1.00 × median prior impulse range.
- 1.25 × median prior impulse range.

A valid impulse requires current impulse range >= the configured threshold × median prior impulse range, in addition to the 0.60 directional-efficiency requirement.

## Pullback depth
Two predeclared pullback levels are tested:
- 38.2% retracement of the impulse directional displacement.
- 50.0% retracement of the impulse directional displacement.

For a bullish impulse:
- pullback level = impulse close - configured retracement × (impulse close - impulse open).

For a bearish impulse:
- pullback level = impulse close + configured retracement × (impulse open - impulse close).

## Resumption signal
The first completed H1 bar in the signal window that satisfies the frozen conditions consumes the day.

Bullish resumption signal requires all of:
1. Valid bullish impulse.
2. Signal-bar low <= configured bullish pullback level.
3. Signal-bar close > signal-bar open.
4. Signal-bar close > impulse midpoint, where impulse midpoint = (impulse open + impulse close) / 2.

Bearish resumption signal is the exact inverse:
1. Valid bearish impulse.
2. Signal-bar high >= configured bearish pullback level.
3. Signal-bar close < signal-bar open.
4. Signal-bar close < impulse midpoint.

Maximum one Architecture D trade per UTC day regardless of direction. No re-entry.

## Entry
- Bullish resumption -> buy at first tradable tick of next H1 bar.
- Bearish resumption -> sell at first tradable tick of next H1 bar.
- Skip entry if spread exceeds 2.0 pips.
- Maximum one open position.

## Stop loss
The initial stop is fixed from information known at signal completion:
- Long: signal-bar low - 0.15 × median prior impulse range.
- Short: signal-bar high + 0.15 × median prior impulse range.

No trailing stop, break-even move, averaging, grid, martingale, recovery sizing, or discretionary stop modification is permitted.

## Take profit
All four baseline configurations use one fixed exit shape to isolate the two research questions of impulse strength and pullback depth.

- Take profit = 1.50R, where R is the absolute entry-to-initial-stop distance.
- Exit at SL, TP, or the 20:00 UTC force-flat rule, whichever occurs first.

## Position sizing and safety
- Risk per trade: 0.25% of current equity.
- Daily loss limit: 1.0% of start-of-day equity.
- Weekly loss limit: 2.0% of start-of-week equity.
- Tester maximum equity drawdown gate: 15%.
- Live/demo circuit breaker: halt at 5% peak-to-valley drawdown until manual review.
- Position size must respect broker minimum, maximum, and volume step.
- Skip when the required stop or target violates broker stop-distance rules.

## Four frozen configurations
| ID | Impulse-range threshold | Pullback depth | Target | Stop buffer |
|---|---:|---:|---:|---:|
| D01 | 1.00 × median range | 38.2% | 1.50R | 0.15 × median range |
| D02 | 1.25 × median range | 38.2% | 1.50R | 0.15 × median range |
| D03 | 1.00 × median range | 50.0% | 1.50R | 0.15 × median range |
| D04 | 1.25 × median range | 50.0% | 1.50R | 0.15 × median range |

These four configurations are the complete Architecture D baseline matrix. No additional thresholds, pullback values, stop variants, signal windows, efficiency thresholds, targets, or entry definitions may be introduced after the first result is viewed.

## Development windows
Use the same five fixed annual development windows:
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
Apply one exact stress model only to a configuration that passes development:
- double observed spread cost
- add 0.3 pip adverse slippage on entry
- add 0.3 pip adverse slippage on exit
- increase commission by 25%

Required stressed PF >= 1.15 and stressed net profit > 0.

## Robustness
OOS remains locked. Robustness must include:
- consistency across the four frozen configurations; no new parameter values may be created
- annual stability
- cost stress
- source, binary, set-file, and specification hash verification

## Locked OOS
A final frozen candidate may open locked OOS once only after clearing development, cost stress, and robustness.

OOS gate:
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
This specification is frozen before the first Architecture D backtest. After the first result is viewed, no strategy definition, configuration, gate, development window, or cost assumption in this document may be changed. If all four configurations fail, Architecture D is retired and research moves to a genuinely orthogonal hypothesis.
