# Architecture J — Frozen Baseline Specification

## Identity
**Name:** Prior-Day Failed-Breakout Reversal

**Research hypothesis:** On EURUSD, when price breaks a completed prior UTC-day high or low during the European/US overlap but a completed M15 bar closes back inside that prior-day range, the failed breakout may mean-revert toward the prior-day midpoint.

This is distinct from Architecture C because the reference is the full prior UTC day rather than the Asian session, and distinct from Architecture H because no EMA/RSI statistical-deviation trigger is used.

## Market and clock
- Symbol: EURUSD only.
- Signal/execution timeframe: M15.
- Completed bars only.
- All rules in UTC.
- Eligible signal bars open from 07:00 through 15:45 UTC.
- Entry on first tradable tick of the next M15 bar.
- Force flat at or after 20:00 UTC.
- No weekend entries.
- Maximum one trade per UTC day.

## Prior-day reference
Use the most recent prior Monday-Friday UTC day with all 96 M15 bars available. Compute prior-day high, low, midpoint, and range. Invalid if any bar is missing or range <= 0.

## Excursion
Two frozen excursion thresholds:
- 0.05 × prior-day range beyond the prior-day extreme.
- 0.10 × prior-day range beyond the prior-day extreme.

## Reversal signal
Upside failed breakout requires:
1. signal bar high strictly above prior high + excursion threshold,
2. signal close strictly below prior-day high,
3. signal close below signal open.
Then sell.

Downside failed breakout is the inverse:
1. signal low strictly below prior low - excursion threshold,
2. signal close strictly above prior-day low,
3. signal close above signal open.
Then buy.

The first valid signal consumes the UTC day even if execution is skipped.

## Stop
- Short: signal-bar high + 0.10 × prior-day range.
- Long: signal-bar low - 0.10 × prior-day range.

## Exit styles
Two frozen exit styles:
- prior-day midpoint target;
- fixed 1.25R target.

Skip midpoint-target trades when midpoint is not on the profitable side of entry.

## Risk and safety
- Risk per trade: 0.25% of current equity.
- Maximum spread: 2.0 pips.
- No martingale, grid, averaging, pyramiding, trailing, or discretionary modification.
- Daily loss gate 1%, weekly loss gate 2%, tester DD gate 15%, demo/live breaker 5%.

## Frozen configurations
| ID | Excursion | Exit |
|---|---:|---|
| J01 | 0.05 × prior-day range | midpoint |
| J02 | 0.10 × prior-day range | midpoint |
| J03 | 0.05 × prior-day range | 1.25R |
| J04 | 0.10 × prior-day range | 1.25R |

## Development windows
- 2020-07-01 to 2021-06-30
- 2021-07-01 to 2022-06-30
- 2022-07-01 to 2023-06-30
- 2023-07-01 to 2024-06-30
- 2024-07-01 to 2025-06-30

## Frozen development gate
All required:
- pooled net profit > 0
- pooled PF >= 1.20
- pooled trades >= 100
- at least 4/5 annual windows profitable
- maximum consecutive losses <= 8
- worst equity DD <= 15%
- pooled recovery factor >= 1.25
- no safety/execution-integrity violation

Fewer than 100 pooled trades = Retire.

## Cost stress
Only after development pass: double observed spread cost, +0.3 pip adverse slippage entry, +0.3 pip adverse slippage exit, commission +25%. Required stressed PF >= 1.15 and positive stressed net.

## OOS
OOS remains locked through development, cost stress, and robustness. One final frozen candidate may open OOS once only after all prior gates pass. OOS failure means Retire.

## Decision states
Advance, Retire, Validated.

## Freeze rule
No strategy definition, threshold, target, stop, window, gate, or cost assumption may change after the first Architecture J result is viewed. If all four configurations fail, Architecture J is retired.
