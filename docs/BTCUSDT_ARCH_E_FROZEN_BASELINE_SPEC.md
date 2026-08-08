# BTC/USDT Architecture E — Frozen Baseline Specification

## Identity
**Name:** H4 Time-Series Momentum / Chandelier Trend Capture

**Hypothesis:** BTC may reward lower-turnover H4 momentum participation more reliably than frequent H1 entries. The design deliberately reduces trading frequency and commission drag and allows large trends to run without fixed profit targets.

## Market and data
- BTC/USDT spot using Binance public BTCUSDT data.
- H1 public klines aggregated to completed UTC H4 bars.
- Development period: 2021-01-01 through 2025-12-31.
- 2026-01-01 onward is locked OOS.
- Long-only, one position maximum, no leverage.

## Indicators
- H4 EMA200 trend filter.
- H4 rate of change (ROC) over a frozen lookback.
- H4 ATR14 using Wilder smoothing.

## Entry
On a completed H4 signal bar:
1. close > EMA200;
2. EMA200 > its value 6 completed H4 bars earlier;
3. ROC over the configured lookback is > 0.

Enter long at the next H4 bar open if flat.

## Stop and exit
- Initial stop = entry - configured ATR multiple × ATR14 from signal bar.
- After entry, maintain a chandelier stop = highest completed H4 close since entry - configured ATR multiple × current ATR14.
- Stop may only tighten, never loosen.
- Also exit at the next H4 bar open after a completed H4 close falls below EMA100.
- No fixed profit target.

## Frozen matrix
| ID | ROC lookback | ATR trail |
|---|---:|---:|
| BE01 | 48 H4 bars (8 days) | 3.0 ATR |
| BE02 | 96 H4 bars (16 days) | 3.0 ATR |
| BE03 | 48 H4 bars (8 days) | 4.0 ATR |
| BE04 | 96 H4 bars (16 days) | 4.0 ATR |

No additional lookbacks, EMA lengths, ATR multiples, profit targets, oscillators, or session filters may be introduced after baseline results are viewed.

## Position sizing
- Initial capital: 10,000 USDT.
- Risk per trade: 0.25% of current strategy equity.
- BTC quantity = risk cash / initial stop distance.
- Quantity capped so gross notional <= current equity.

## Costs
- Commission: 0.10% per order.
- Baseline slippage: 0.
- If a candidate passes development, stress commission to 0.15% per order before OOS.

## Development gate
A configuration advances only if all are true:
- net profit > 0 after costs;
- profit factor >= 1.20;
- at least 50 closed trades (lower-frequency H4 architecture);
- max equity drawdown <= 20%;
- recovery factor >= 1.25;
- at least 4 of 5 calendar years profitable;
- no execution-integrity violation.

Fewer than 50 trades means Retire for insufficient evidence.

## Cost stress
Only development-passing configurations are stressed at 0.15% commission per order. Stress requires net profit > 0 and PF >= 1.15.

## OOS gate
2026 remains locked until one candidate passes development and stress. If opened once, OOS requires net > 0, PF >= 1.20, DD <= 20%, recovery >= 1.25, and no integrity violation.

## Decision states
Advance, Retire, Validated.

## Freeze rule
This architecture is frozen before baseline results are viewed. Failed configurations may not be rescued by post-result parameter tuning.