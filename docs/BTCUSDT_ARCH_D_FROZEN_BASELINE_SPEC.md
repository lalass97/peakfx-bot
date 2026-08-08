# BTC/USDT Architecture D — Frozen Baseline Specification

## Hypothesis
BTC/USDT may exhibit short-horizon mean reversion after an H1 downside volatility excursion when the higher-timeframe market is non-trending.

## Market and data
- Binance BTCUSDT spot public 1-hour klines.
- Development: 2021-01-01 through 2025-12-31.
- 2026-01-01 onward is locked OOS and must not be opened unless a development configuration advances.
- Long-only, one position maximum, completed-bar signals only, next-H1-open entry.

## Higher-timeframe range regime
Construct completed UTC H4 bars. Compute H4 ADX(14). A new long is permitted only when the most recently completed H4 ADX is <= 20.

## H1 setup and trigger
Compute H1 Bollinger Bands(20, 2.0), RSI(14), and ATR(14).
A signal requires the immediately previous completed H1 bar to close strictly below its lower Bollinger Band, followed by the current completed H1 bar closing back above its lower Bollinger Band. The current bar must also close above its open.

Two predeclared RSI thresholds are tested on the excursion bar:
- RSI <= 25
- RSI <= 30

## Stop and target
- Initial stop distance: 2.0 x H1 ATR14 measured on the reclaim signal bar.
- Stop fixed at entry minus that distance.
- Fixed-R targets: 1.5R and 2.0R.

## Frozen matrix
| ID | RSI threshold | Target |
|---|---:|---:|
| BD01 | 25 | 1.5R |
| BD02 | 30 | 1.5R |
| BD03 | 25 | 2.0R |
| BD04 | 30 | 2.0R |

No post-result tuning of ADX, RSI, Bollinger settings, ATR multiplier, or targets is allowed.

## Position sizing and costs
- Initial capital: 10,000 USDT.
- Risk: 0.25% of strategy equity per trade.
- Quantity = risk cash / initial stop distance, capped so gross notional does not exceed current equity; no leverage.
- Baseline commission: 0.10% per order.
- Baseline slippage: 0.

## Development gate
Advance only if all pass:
- net profit > 0 after costs
- PF >= 1.20
- at least 100 closed trades
- maximum equity drawdown <= 20%
- recovery factor >= 1.25
- at least 4 of 5 calendar years profitable
- no integrity violation

Fewer than 100 trades means Retire for insufficient evidence.

## Cost stress before OOS
Only development-passing configurations may be rerun at 0.15% commission per order. Stress requires net profit > 0 and PF >= 1.15.

## OOS
2026 stays locked until one final candidate passes development and stress. OOS failure retires the architecture. OOS may not be reused for redesign.

## Decisions
Only Advance, Retire, or Validated.