# BTC/USDT Architecture B — Frozen Baseline Specification

## Identity
**Name:** H4 Trend / H1 Pullback-Reclaim Continuation

**Research hypothesis:** BTC/USDT may offer a more durable continuation edge after a controlled H1 pullback inside an established H4 uptrend than after direct channel breakouts.

This is a genuinely different hypothesis from Architecture A. It is frozen before baseline results are viewed.

## Market and chart
- Instrument: BTC/USDT spot using Binance public BTCUSDT data.
- Signal/execution timeframe: H1.
- Higher-timeframe regime: H4.
- Standard candles only.
- Long-only.
- 24/7 including weekends.
- One open position maximum.
- Signals use completed bars only.

## H4 regime
A new long is permitted only when the most recently completed H4 bar satisfies all of:
- H4 close > H4 EMA200.
- H4 EMA50 > H4 EMA200.
- H4 EMA50 > its value four completed H4 bars earlier.

## H1 pullback-reclaim signal
Two predeclared pullback windows are tested: 3 completed H1 bars and 6 completed H1 bars.

For a valid signal bar:
1. H1 close is above H1 EMA50.
2. H1 EMA20 is above H1 EMA50.
3. Within the configured pullback window ending on the signal bar, at least one bar low is at or below that bar's H1 EMA20.
4. The signal bar closes above its own H1 EMA20.
5. The signal bar closes strictly above the immediately previous H1 bar high.
6. The signal bar closes above its open.

Entry occurs at the next H1 bar open.

## Stop
- ATR = H1 ATR14 from the completed signal bar.
- Initial stop distance = 2.0 × ATR14.
- Fixed stop = entry price - stop distance.
- No trailing stop, averaging, pyramiding, martingale, grid, or recovery sizing.

## Target
Two predeclared fixed-R targets are tested:
- 2.0R
- 3.0R

## Four frozen configurations
| ID | Pullback window | Target |
|---|---:|---:|
| BB01 | 3 H1 bars | 2.0R |
| BB02 | 6 H1 bars | 2.0R |
| BB03 | 3 H1 bars | 3.0R |
| BB04 | 6 H1 bars | 3.0R |

No additional windows, EMA lengths, ATR multipliers, targets, oscillators, volume filters, or session filters may be introduced after baseline results are viewed.

## Position sizing
- Initial capital: 10,000 USDT.
- Risk per trade: 0.25% of current strategy equity.
- BTC quantity = risk cash / initial stop distance in USDT per BTC.
- No leverage.
- Gross notional capped at current strategy equity.

## Costs
Baseline:
- Commission = 0.10% per order.
- Slippage = 0 initially.

If a configuration passes development, cost stress is commission = 0.15% per order. No other parameters change.

## Development period and locked OOS
Development:
- 2021-01-01 through 2025-12-31.

Locked OOS:
- 2026-01-01 onward.

2026 must remain untouched until a configuration passes development and stress gates.

## Development gate
A configuration advances only if all are true:
- net profit > 0 after modeled commission
- profit factor >= 1.20
- at least 100 closed trades
- maximum equity drawdown <= 20%
- recovery factor >= 1.25
- at least 4 of 5 calendar years profitable
- no execution-integrity violation

Fewer than 100 trades means Retire for insufficient evidence.

## Cost stress gate
Only development-passing configurations are stressed at 0.15% commission per order.
Required:
- stressed net profit > 0
- stressed PF >= 1.15

## OOS gate
If one final candidate survives development and stress, test once on 2026-01-01 onward. Required:
- net profit > 0
- PF >= 1.20
- max equity DD <= 20%
- recovery factor >= 1.25
- no integrity violation

OOS failure means retirement. OOS may not be reused for redesign.

## Decision states
Only:
- Advance
- Retire
- Validated

## Freeze rule
This specification is frozen before Architecture B baseline results are observed. If all four configurations fail, Architecture B is retired and research moves to a genuinely different hypothesis rather than post-result tuning.