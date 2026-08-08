# BTC/USDT Architecture A — Frozen Baseline Specification

## Identity
**Name:** H4 Trend / H1 Channel Breakout (BTC Architecture A)

**Research hypothesis:** BTC/USDT may exhibit persistent directional continuation when an H1 close breaks a recent H1 price channel in the direction of an established H4 trend.

This is a fresh Bitcoin research track. It does not inherit EUR/USD session rules.

## Market and chart
- Intended chart: BTC/USDT spot, preferably BINANCE:BTCUSDT.
- TradingView standard candlestick chart only.
- Signal/execution timeframe: H1.
- Higher-timeframe regime: H4.
- Signals use completed bars only.
- 24/7 market: weekend trading is allowed.
- Long-only baseline to remain compatible with spot BTC/USDT.
- One open position maximum.

## H4 regime
On the most recently completed H4 bar:
- H4 close must be above H4 EMA200.
- H4 EMA200 must be above its value four completed H4 bars earlier.

If either condition is false, no new long may be opened.

## H1 breakout
Two predeclared channel lengths are tested:
- 20 completed H1 bars
- 40 completed H1 bars

A valid signal occurs when the completed H1 signal bar closes strictly above the highest high of the configured number of H1 bars immediately preceding the signal bar.

The signal bar itself is excluded from the lookback channel.

Entry occurs on the next bar under TradingView strategy execution semantics.

## Stop
- ATR = H1 ATR14 on the completed signal bar.
- Initial stop distance = 2.0 × ATR14.
- Stop is fixed at entry price minus the ATR stop distance.
- No averaging, grid, martingale, pyramiding, or recovery sizing.

## Target
Two predeclared fixed-R targets are tested:
- 2.0R
- 3.0R

R is the initial entry-to-stop distance.

## Four frozen configurations
| ID | H1 channel | Target |
|---|---:|---:|
| BA01 | 20 bars | 2.0R |
| BA02 | 40 bars | 2.0R |
| BA03 | 20 bars | 3.0R |
| BA04 | 40 bars | 3.0R |

No additional channel lengths, targets, EMA lengths, ATR multipliers, oscillators, or session filters may be introduced after baseline results are viewed.

## Position sizing
- Initial capital for research: 10,000 USDT.
- Risk per trade: 0.25% of strategy equity.
- BTC quantity = risk cash / initial stop distance in USDT per BTC.
- No leverage is assumed in the baseline.
- Order quantity is capped so gross notional does not exceed current strategy equity.

## Costs
Baseline TradingView model:
- Commission: 0.10% per order.
- Slippage: 0 in the initial baseline because exchange- and order-type-specific tick slippage is not yet calibrated.

Any later cost-stress test must be declared before OOS is opened.

## Development period and locked OOS
Development data:
- 2021-01-01 through 2025-12-31.

Reserved OOS:
- 2026-01-01 onward.

The 2026 OOS period must remain locked until a configuration passes all development and robustness requirements.

## Development evaluation
A configuration advances only if all conditions pass:
- net profit > 0 after modeled commission
- profit factor >= 1.20
- at least 100 closed trades
- maximum equity drawdown <= 20%
- recovery factor >= 1.25
- at least 4 of the 5 calendar years 2021, 2022, 2023, 2024, 2025 profitable
- no execution-integrity violation

Fewer than 100 trades means retirement for insufficient evidence.

## Robustness before OOS
Before OOS can be opened, a development-passing configuration must also survive:
- commission increased from 0.10% to 0.15% per order
- neighboring frozen configuration comparison only (BA01–BA04)
- year-by-year stability review
- confirmation that results use standard candles and the intended BTC/USDT spot chart

Required stressed result:
- stressed net profit > 0
- stressed profit factor >= 1.15

## OOS gate
If one final candidate reaches OOS, it may be tested once on 2026-01-01 onward.
It must satisfy:
- net profit > 0
- PF >= 1.20
- max equity drawdown <= 20%
- recovery factor >= 1.25
- no safety or integrity violation

OOS failure means retirement. OOS may not be reused for redesign.

## Decision states
Only:
- Advance
- Retire
- Validated

## Freeze rule
This specification is frozen before viewing BTC Architecture A baseline results. If all four configurations fail, the architecture is retired and BTC research moves to a genuinely different hypothesis rather than tuning this one after the fact.
