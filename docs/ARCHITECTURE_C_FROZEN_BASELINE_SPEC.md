# Architecture C — Frozen Baseline Specification

## Identity
**Name:** Session Exhaustion Mean Reversion (Architecture C)

**Research hypothesis:** On EURUSD, an unusually large European-session extension beyond a completed Asian-session range may mean-revert after a completed H1 rejection bar closes back inside that Asian range.

This is a price/time hypothesis only. It does not claim centralized order flow, DOM, options positioning, or institutional-flow observation.

## Market and clock
- Symbol: EURUSD only.
- Signal/execution timeframe: H1.
- Signal evaluation: completed H1 bars only.
- All session rules are defined in UTC.
- Runner artifacts must record the broker-server to UTC conversion used by the EA.
- Asian reference session: 00:00 through 06:59 UTC. It contains the seven completed H1 bars opening at 00:00, 01:00, 02:00, 03:00, 04:00, 05:00, and 06:00 UTC.
- European signal window: completed H1 signal bars opening from 07:00 through 14:00 UTC. Therefore the latest eligible signal completes at 15:00 UTC.
- Entry: first tradable tick of the H1 bar immediately following an eligible completed signal.
- Force flat: at or after 20:00 UTC on the same trading day.
- No weekend entries. No new entry on Friday after 15:00 UTC.

## Asian reference
For each eligible UTC trading day:
1. Asian high = highest high of the seven completed H1 Asian-session bars.
2. Asian low = lowest low of those seven bars.
3. Asian midpoint = (Asian high + Asian low) / 2.
4. Asian range = Asian high - Asian low.
5. The day is invalid if any of the seven H1 bars is unavailable or if range <= 0.

## Recent range reference
- Use the previous 20 completed eligible trading days before the current day.
- For each day, calculate the Asian range using the same 00:00–06:59 UTC definition.
- Median Asian range = arithmetic median of those 20 values.
- The current day is invalid if fewer than 20 prior valid Asian ranges are available.
- The current day's Asian range is not included in its own reference distribution.

## Exhaustion boundary
Two predeclared excursion thresholds are tested:
- 0.50 × median Asian range beyond the current Asian high/low.
- 0.75 × median Asian range beyond the current Asian high/low.

Upside exhaustion boundary = Asian high + threshold × median Asian range.
Downside exhaustion boundary = Asian low - threshold × median Asian range.

## Reversal signal
A completed H1 bar is an upside-reversal signal only when all are true:
1. Its opening time is within the frozen European signal window.
2. Its high is strictly above the upside exhaustion boundary.
3. Its close is strictly below the current day's Asian high.
4. Its close is below its open.

A downside-reversal signal is the exact inverse:
1. Eligible opening time.
2. Low strictly below the downside exhaustion boundary.
3. Close strictly above the current day's Asian low.
4. Close above its open.

The first valid signal of the day consumes the day. Maximum one Architecture C trade per UTC day, regardless of direction. No re-entry.

## Entry
- Upside reversal -> sell at the first tradable tick of the next H1 bar.
- Downside reversal -> buy at the first tradable tick of the next H1 bar.
- Entry is skipped if spread exceeds 2.0 pips.
- Maximum one open position.

## Stop loss
The initial stop is fixed from information known at signal completion:
- Short: signal-bar high + 0.25 × median Asian range.
- Long: signal-bar low - 0.25 × median Asian range.

No trailing stop, break-even move, averaging, grid, martingale, recovery sizing, or discretionary stop modification is permitted.

## Exit styles
Two predeclared exit styles are tested.

### Midpoint target
- Take profit at the current day's Asian midpoint.
- If the midpoint would not be on the profitable side of entry, skip the trade.
- Exit at SL, midpoint TP, or the 20:00 UTC force-flat rule, whichever occurs first.

### Fixed-R target
- Take profit at 1.50R, where R is the absolute entry-to-initial-stop distance.
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
| ID | Excursion threshold | Exit style | Stop basis |
|---|---:|---|---|
| C01 | 0.50 × median Asian range | Asian midpoint | signal extreme + 0.25 × median range |
| C02 | 0.75 × median Asian range | Asian midpoint | signal extreme + 0.25 × median range |
| C03 | 0.50 × median Asian range | 1.50R | signal extreme + 0.25 × median range |
| C04 | 0.75 × median Asian range | 1.50R | signal extreme + 0.25 × median range |

These four configurations are the complete Architecture C baseline matrix. No additional thresholds, stop variants, time windows, reversal definitions, or targets may be introduced after the first result is viewed.

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
- configuration-neighborhood consistency using only the four frozen configurations; no new parameter values may be created
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
This specification is frozen before the first Architecture C backtest. After the first result is viewed, no strategy definition, configuration, gate, development window, or cost assumption in this document may be changed. If all four configurations fail, Architecture C is retired and research moves to a genuinely orthogonal hypothesis.