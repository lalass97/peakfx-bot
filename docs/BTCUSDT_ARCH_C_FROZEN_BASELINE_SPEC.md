# BTC/USDT Architecture C — Frozen Baseline Specification

## Identity
**Name:** H4 Trend / H1 Compression-to-Expansion Momentum (BTC Architecture C)

**Research hypothesis:** BTC/USDT may exhibit persistent continuation after periods of short-term volatility compression when a high-energy bullish expansion candle occurs in the direction of the higher-timeframe trend.

This is a genuinely different hypothesis from Architecture A breakout chasing and Architecture B pullback reclaim. The rules below are frozen before baseline results are viewed.

## Market and chart
- Instrument: BTC/USDT spot, Binance public BTCUSDT data.
- Signal/execution timeframe: H1.
- Higher-timeframe regime: H4.
- Long-only.
- Completed bars only for signals.
- 24/7 market; weekends allowed.
- One open position maximum.

## H4 trend regime
On the most recently completed H4 bar:
- H4 close must be above H4 EMA200.
- H4 EMA200 must be above its value four completed H4 bars earlier.

## H1 compression condition
Use Bollinger Bands on H1 close with length 20 and 2 standard deviations.

Band width = (upper band - lower band) / middle band.

Two frozen compression lookbacks are tested:
- 48 completed H1 bars
- 96 completed H1 bars

A signal bar is eligible only if the Bollinger Band width on the immediately preceding completed H1 bar is less than or equal to the 20th percentile of Bollinger Band width values over the configured compression lookback ending on that prior bar.

The signal bar itself is excluded from the compression percentile calculation.

## H1 expansion trigger
On the completed signal bar, all of the following must be true:
- close > open
- true range >= 1.5 × ATR20 measured on the signal bar
- close location value within the candle range >= 0.75, where CLV = (close - low) / (high - low)
- volume >= 1.5 × SMA20(volume)
- H4 trend regime is valid

No separate price-channel breakout is required.

## Entry
- Enter long at the next H1 bar open after a valid completed signal.

## Stop
- ATR = H1 ATR14 on the completed signal bar.
- Initial stop distance = 2.0 × ATR14.
- Fixed initial stop at entry minus stop distance.
- No trailing stop, averaging, grid, martingale, pyramiding, or recovery sizing.

## Targets
Two frozen fixed-R targets are tested:
- 3.0R
- 4.0R

R is the initial entry-to-stop distance.

## Four frozen configurations
| ID | Compression lookback | Target |
|---|---:|---:|
| BC01 | 48 bars | 3.0R |
| BC02 | 96 bars | 3.0R |
| BC03 | 48 bars | 4.0R |
| BC04 | 96 bars | 4.0R |

No threshold, Bollinger setting, ATR multiplier, volume multiple, compression percentile, trend filter, or target may be changed after results are viewed.

## Position sizing
- Initial capital: 10,000 USDT.
- Risk per trade: 0.25% of current strategy equity.
- BTC quantity = risk cash / initial stop distance.
- No leverage.
- Gross notional capped at current equity.

## Costs
- Commission: 0.10% per order.
- Slippage: 0 in baseline.

## Development period and locked OOS
Development:
- 2021-01-01 through 2025-12-31.

Locked OOS:
- 2026-01-01 onward.

2026 must remain unopened unless a configuration passes development and stress gates.

## Development gate
A configuration advances only if all pass:
- net profit > 0 after commission
- profit factor >= 1.20
- at least 100 closed trades
- max equity drawdown <= 20%
- recovery factor >= 1.25
- at least 4 of 5 calendar years profitable
- no execution-integrity violation

Fewer than 100 trades means retirement for insufficient evidence.

## Cost-stress gate
Only development-passing configurations may be retested with:
- commission increased to 0.15% per order

Required stressed result:
- net profit > 0
- profit factor >= 1.15

## OOS gate
A single final candidate may be tested once on 2026 only after development and stress pass.
Required:
- net profit > 0
- PF >= 1.20
- max DD <= 20%
- recovery >= 1.25
- no integrity violation

## Decision states
Only:
- Advance
- Retire
- Validated

## Freeze rule
This specification is frozen before Architecture C baseline results are viewed. If all four configurations fail, Architecture C is retired rather than tuned after the fact.
