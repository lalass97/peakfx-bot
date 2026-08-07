# Architecture I — Frozen Baseline Specification

## Identity
**Name:** H1 Channel Trend Following (Architecture I)

**Research hypothesis:** EURUSD may exhibit persistent directional moves when a completed H1 close breaks a multi-bar price channel in the same direction as a higher-timeframe H4 trend filter.

Architecture I is intentionally different from prior PeakFX session, compression, pullback, and mean-reversion hypotheses. It has no fixed London/Asian session dependency, no compression phase, and no fade logic.

## Market and timeframes
- Symbol: EURUSD only.
- Signal/execution timeframe: H1.
- Trend filter timeframe: H4.
- Completed bars only.
- Entry: first tradable tick of the H1 bar after a valid completed signal.
- Maximum one open Architecture I position.
- No pyramiding, grid, martingale, averaging down, or recovery sizing.
- No new entry Friday after 18:00 UTC.
- Force flat before weekly close at or after Friday 20:00 UTC.

## H4 trend filter
Use completed H4 EMA(200).

For a long candidate, the most recently completed H4 close must be strictly above its EMA200.
For a short candidate, the most recently completed H4 close must be strictly below its EMA200.

No EMA slope or second moving average is used.

## H1 breakout channel
Two predeclared channel lengths are tested: 20 and 40 completed H1 bars.

For each completed H1 signal bar:
- Upper channel = highest high of the configured number of H1 bars immediately preceding the signal bar.
- Lower channel = lowest low of those preceding bars.
- The signal bar itself is excluded from channel construction.

Long signal requires:
1. H4 long trend filter passes.
2. Signal-bar close strictly above the upper channel.
3. Signal bar closes above its open.

Short signal is the exact inverse.

## Volatility and stop
Use completed H1 ATR(14) at signal completion.
Initial stop distance = 1.50 × H1 ATR(14).

- Long SL = entry - 1.50 ATR.
- Short SL = entry + 1.50 ATR.

Skip if ATR is unavailable/non-positive, stop is invalid, or broker stop-distance rules are violated.

## Exit styles
Two predeclared exits are tested.

### Fixed 2R
Take profit at 2.00R. Exit at SL, TP, or weekly force-flat.

### Opposite 10-bar channel
No fixed TP. Once in a long, exit when a completed H1 close is strictly below the lowest low of the 10 H1 bars immediately preceding that completed exit-signal bar. For a short, exit on the inverse highest-high condition. Weekly force-flat remains active.

No trailing ATR stop or break-even modification is allowed.

## Entry restrictions and safety
- Skip entry if spread > 2.0 pips.
- Risk per trade: 0.25% of current equity.
- Daily loss limit: 1.0% of start-of-day equity.
- Weekly loss limit: 2.0% of start-of-week equity.
- Tester maximum equity drawdown gate: 15%.
- Live/demo circuit breaker: 5% peak-to-valley drawdown pending manual review.
- Respect broker lot minimum, maximum, step, and stop-distance restrictions.

## Four frozen configurations
| ID | Entry channel | Exit style |
|---|---:|---|
| I01 | 20 H1 bars | Fixed 2.00R |
| I02 | 40 H1 bars | Fixed 2.00R |
| I03 | 20 H1 bars | Opposite 10-bar channel |
| I04 | 40 H1 bars | Opposite 10-bar channel |

These are the complete Architecture I configurations. No extra channel lengths, EMA lengths, ATR multiples, exit channels, time filters, or targets may be introduced after the first result is viewed.

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
Only after a development pass:
- double observed spread cost
- add 0.3 pip adverse slippage on entry
- add 0.3 pip adverse slippage on exit
- increase commission by 25%

Required stressed PF >= 1.15 and stressed net profit > 0.

## Robustness and OOS
OOS remains locked through development, cost stress, and robustness. Robustness uses only the frozen I01-I04 neighborhood, annual stability, cost stress, and source/binary/set/specification hash verification.

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
This specification is frozen before the first Architecture I backtest. After the first result is viewed, no strategy definition, configuration, development gate, cost assumption, or development window may be changed.
