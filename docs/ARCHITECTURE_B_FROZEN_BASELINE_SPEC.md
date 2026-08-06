# Architecture B — Frozen Baseline Specification

## Identity
**Name:** Pre-Structure-Aligned Volatility Expansion (Architecture B)

**Research hypothesis:** A statistically unusual multi-day EUR/USD volatility compression may be followed by directional persistence when a completed H1 expansion closes outside the full compression box in the same direction as daily price structure that was already confirmed before compression began.

This is a price-and-volatility hypothesis only. It does not claim direct observation of institutional order flow, DOM, options positioning, or centralized transaction volume.

## Market and timeframes
- Symbol: EURUSD only
- Regime and structural timeframe: D1
- Signal and execution timeframe: H1
- Signal evaluation: completed bars only
- Entry: first tradable tick of the H1 bar immediately following a valid completed signal bar
- Maximum open positions: 1
- No pyramiding, hedging, averaging down, grid, martingale, or recovery sizing

## Daily compression regime
1. Compute D1 ATR(14) using completed daily bars.
2. For each completed D1 bar, compare its ATR(14) with the trailing 180 completed D1 ATR values available before that bar.
3. A daily bar qualifies as compressed when its ATR(14) is at or below the 25th percentile of that trailing 180-bar distribution.
4. A valid compression phase requires at least 5 consecutive qualifying completed D1 bars.
5. The phase includes every consecutive qualifying bar, capped at 15 completed D1 bars.
6. If compression continues beyond 15 bars, the setup is invalidated until a non-compressed D1 bar ends the phase and a new phase later forms.
7. Compression box high is the highest high of all bars in the valid phase. Compression box low is the lowest low of all bars in the valid phase.

## Pre-compression structure alignment
A confirmed D1 swing high is a completed daily bar whose high is greater than the highs of the two completed bars before it and the two completed bars after it. A confirmed swing low is defined inversely.

Only swing points fully confirmed before the first compression bar may be used.

- Bullish structure: the two most recent eligible confirmed swing highs are increasing and the two most recent eligible confirmed swing lows are increasing.
- Bearish structure: the two most recent eligible confirmed swing highs are decreasing and the two most recent eligible confirmed swing lows are decreasing.
- Otherwise: no directional alignment and no trade.

## Stored compression volatility
- Compute H1 ATR(14) using completed H1 bars.
- Store the arithmetic mean of all completed H1 ATR(14) values whose bars fall inside the valid compression phase.
- Exclude any H1 bar after the final compression day and exclude the eventual expansion bar.
- A setup is invalid if fewer than 72 completed H1 ATR observations are available.

## Expansion signal
A long signal requires all of the following:
1. Valid compression phase exists.
2. Bullish pre-compression structure is confirmed.
3. A completed H1 bar closes strictly above the compression box high.
4. That signal bar's true range is at least the configured expansion multiplier times the stored mean compression-phase H1 ATR(14).

A short signal uses the inverse conditions.

No new entry is permitted during the final 2 hours before the weekly market close or the first 2 hours after the weekly market open. UTC and broker-server conversions must be recorded in the run manifest.

## Entry and re-entry
- Enter on the first tradable tick of the next H1 bar.
- Entry is void if spread exceeds the fixed project spread cap.
- One trade maximum per compression box.
- After a stopped or timed-out trade, no re-entry into the same box is allowed.

## Position sizing and safety
- Risk per trade: 0.25% of current equity
- Daily loss limit: 1.0% of start-of-day equity
- Weekly loss limit: 2.0% of start-of-week equity
- Tester maximum equity drawdown gate: 15%
- Live/demo circuit breaker: halt at 5% peak-to-valley drawdown until manual review
- Position size must respect broker minimum lot, maximum lot, and volume step
- Skip the trade when the required stop produces an invalid volume or violates broker stop-distance rules

## Stop loss
Initial stop distance from entry equals 1.0 times the stored mean compression-phase H1 ATR(14).

No candle-body stop, box-width stop, break-even move, or minimum-distance override is permitted in the baseline.

## Four frozen baseline configurations
| ID | Expansion multiplier | Exit style |
|---|---:|---|
| B01 | 1.5x | Fixed 2.0R target |
| B02 | 2.0x | Fixed 2.0R target |
| B03 | 1.5x | Fast-fail time exit |
| B04 | 2.0x | Fast-fail time exit |

### Fixed-target exit
- TP at 2.0 times initial risk distance
- Exit at SL or TP only
- Force flat before weekly close if still open

### Fast-fail exit
- No fixed TP
- Exit at SL or at the close of the 8th completed H1 bar after entry, whichever occurs first
- Force flat before weekly close if still open

## One permitted revision only: B-R1
If no baseline configuration passes every frozen development gate, one revision is permitted:

Require the completed expansion bar's MT5 tick volume to be greater than the arithmetic mean tick volume of the previous 20 completed H1 bars.

All other rules and all four configurations remain unchanged. Tick volume is treated only as a broker-feed activity proxy, not centralized transaction volume. No second revision is allowed.

## Development windows
Use the five fixed annual windows already established by the PeakFX protocol:
- 2020-07-01 to 2021-06-30
- 2021-07-01 to 2022-06-30
- 2022-07-01 to 2023-06-30
- 2023-07-01 to 2024-06-30
- 2024-07-01 to 2025-06-30

## Frozen baseline gate
A configuration advances only if every condition passes:
- pooled net profit > 0 after modeled costs
- pooled PF >= 1.20
- pooled trades >= 100
- at least 4 of 5 annual windows profitable
- maximum consecutive losses <= 8
- worst equity drawdown <= 15%
- pooled recovery factor >= 1.25
- no safety or execution-integrity violation

Fewer than 100 trades is retirement for insufficient evidence, not an inconclusive or parked result.

## Frozen revision gate
A B-R1 configuration advances only if every condition passes:
- pooled net profit > 0
- pooled PF >= 1.30
- pooled trades >= 150
- at least 4 of 5 annual windows profitable
- maximum consecutive losses <= 8
- worst equity drawdown <= 15%
- pooled recovery factor >= 1.50
- no catastrophic annual window or safety violation

## Cost stress
Apply one exact stress model to any candidate that passes its stage:
- double the observed spread cost
- add 0.3 pip adverse slippage on entry
- add 0.3 pip adverse slippage on exit
- increase commission by 25%

Required stressed PF: >= 1.15, with positive stressed net profit.

## Robustness and locked OOS
OOS remains locked through baseline, B-R1, and robustness.

Robustness must include configuration-neighborhood consistency, annual stability, cost stress, and source/binary/set-file hash verification.

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

No parked, promising, inconclusive, or discretionary status is permitted.

## Freeze rule
After the first baseline result is viewed, no strategy definition, configuration, gate, cost assumption, or development window in this document may be changed. If all baselines fail, run B-R1 exactly once. If B-R1 fails, retire Architecture B and move to a genuinely orthogonal hypothesis.