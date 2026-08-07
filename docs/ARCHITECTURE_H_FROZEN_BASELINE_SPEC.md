# Architecture H — Frozen Baseline Specification

## Identity
**Name:** H1 Statistical Deviation Reversion (Architecture H)

**Research hypothesis:** On EURUSD, a completed H1 bar that becomes unusually extended from a 20-period exponential mean while momentum is extreme may partially mean-revert during the same trading day after a completed rejection candle.

Architecture H is deliberately distinct from Architecture C. It does not use an Asian-session range, session-extension boundary, or Asian midpoint. The reference is a continuously updated H1 EMA/ATR state plus RSI.

## Market and clock
- Symbol: EURUSD only.
- Signal/execution timeframe: H1.
- Completed bars only.
- All session rules are UTC.
- Eligible signal bars open 07:00 through 17:00 UTC.
- Entry: first tradable tick of the next H1 bar.
- Force flat at or after 20:00 UTC.
- No weekend entries.
- Maximum one Architecture H trade per UTC day.

## Indicators
Calculated from completed H1 bars only:
- EMA(20), close.
- ATR(14).
- RSI(14), close.

The signal bar uses indicator values at shift 1.

## Statistical extension
Two predeclared extension thresholds are tested:
- 1.25 ATR from EMA20.
- 1.50 ATR from EMA20.

Upside extension requires signal close >= EMA20 + threshold × ATR14.
Downside extension requires signal close <= EMA20 - threshold × ATR14.

## Reversal signal
Short signal requires all:
1. Eligible UTC signal time.
2. Upside extension is satisfied.
3. RSI14 >= 70.
4. Signal close < signal open.

Long signal requires all:
1. Eligible UTC signal time.
2. Downside extension is satisfied.
3. RSI14 <= 30.
4. Signal close > signal open.

The first valid signal consumes the UTC day even if execution is skipped.

## Entry and spread
- Short after a valid upside-reversal signal.
- Long after a valid downside-reversal signal.
- Skip if spread exceeds 2.0 pips.
- One open position maximum.

## Stop loss
Stop uses only information known at signal completion:
- Short: signal high + 0.75 × ATR14.
- Long: signal low - 0.75 × ATR14.

No trailing stop, break-even, averaging, grid, martingale, pyramiding, or recovery sizing.

## Exit styles
Two predeclared exit styles are tested.

### EMA target
- Short TP = signal-time EMA20.
- Long TP = signal-time EMA20.
- Skip if EMA20 is not on the profitable side of entry.

### Fixed-R target
- TP = 1.00R from entry, where R is entry-to-initial-stop distance.

All positions also force-flat at or after 20:00 UTC.

## Safety
- Risk per trade: 0.25% of current equity.
- Daily loss limit: 1.0% of start-of-day equity.
- Weekly loss limit: 2.0% of start-of-week equity.
- Tester maximum equity drawdown gate: 15%.
- Live/demo circuit breaker: 5% peak-to-valley drawdown pending manual review.
- Respect broker lot and stop-distance rules.

## Four frozen configurations
| ID | Extension threshold | Exit |
|---|---:|---|
| H01 | 1.25 ATR | EMA20 |
| H02 | 1.50 ATR | EMA20 |
| H03 | 1.25 ATR | 1.00R |
| H04 | 1.50 ATR | 1.00R |

No additional thresholds, RSI levels, EMA lengths, ATR lengths, stop buffers, time windows, or exit variants may be introduced after the first result is viewed.

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
Apply only after a development pass:
- double observed spread cost
- add 0.3 pip adverse slippage on entry
- add 0.3 pip adverse slippage on exit
- increase commission by 25%

Required stressed PF >= 1.15 and stressed net profit > 0.

## Robustness and locked OOS
OOS remains locked through development, cost stress, and robustness. A final frozen candidate may open locked OOS once only after clearing all prior gates.

OOS gate:
- net profit > 0
- PF >= 1.20
- at least 50 trades
- maximum equity drawdown <= 15%
- recovery factor >= 1.25
- no safety violation

Failure at OOS means retirement.

## Decision states
Only: Advance, Retire, Validated.

## Freeze rule
This specification is frozen before the first Architecture H backtest. After the first result is viewed, no strategy definition, configuration, gate, development window, or cost assumption may be changed.