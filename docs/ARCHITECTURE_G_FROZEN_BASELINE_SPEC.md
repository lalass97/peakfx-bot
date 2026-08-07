# Architecture G — Frozen Baseline Specification

## Identity
**Name:** Multi-Timeframe Trend Pullback Continuation (Architecture G)

**Research hypothesis:** On EURUSD, when a completed H4 trend is directionally aligned and sufficiently separated, a completed H1 pullback into a shorter moving-average zone followed by same-direction rejection may have positive expectancy.

Architecture G is deliberately different from prior session-breakout, session-exhaustion, prior-day, and opening-range hypotheses. It uses a persistent H4 trend state plus H1 pullback/rejection rather than a one-session range event.

## Market and timeframes
- Symbol: EURUSD only.
- Trend timeframe: H4.
- Signal/execution timeframe: H1.
- Completed bars only.
- Entry on first tradable tick of the H1 bar after a valid completed signal.
- Maximum one open position and one trade per UTC day.
- No weekend entries; no Friday entries after 15:00 UTC.
- Force flat Friday at or after 20:00 UTC.

## H4 trend state
Use EMA(50), EMA(200), and ATR(14) on completed H4 bars.

Bullish trend requires:
1. H4 EMA50 > EMA200.
2. Latest completed H4 close > EMA50.
3. EMA50 - EMA200 >= configured separation multiple × H4 ATR14.

Bearish trend is the exact inverse.

Two predeclared separation thresholds are tested: 0.10 × H4 ATR and 0.20 × H4 ATR.

## H1 pullback and rejection
Use EMA(20) and ATR(14) on H1.

Bullish setup requires a completed H1 signal bar with all conditions:
1. H4 bullish trend state.
2. Signal low <= H1 EMA20.
3. Signal close > H1 EMA20.
4. Signal close > signal open.
5. Signal close > prior H1 close.

Bearish setup is inverse:
1. H4 bearish trend state.
2. Signal high >= H1 EMA20.
3. Signal close < H1 EMA20.
4. Signal close < signal open.
5. Signal close < prior H1 close.

The first valid signal consumes the UTC day even if execution is skipped.

## Entry and risk
- Skip if spread > 2.0 pips.
- Risk per trade: 0.25% current equity.
- Daily loss limit: 1.0% start-of-day equity.
- Weekly loss limit: 2.0% start-of-week equity.
- No grid, martingale, averaging, pyramiding, break-even move, or trailing stop.

## Stop
- Long: signal low - 0.25 × H1 ATR14.
- Short: signal high + 0.25 × H1 ATR14.

## Targets
Two predeclared fixed-R targets are tested: 1.25R and 1.75R.

## Frozen configurations
| ID | H4 EMA separation | Target |
|---|---:|---:|
| G01 | 0.10 × H4 ATR | 1.25R |
| G02 | 0.20 × H4 ATR | 1.25R |
| G03 | 0.10 × H4 ATR | 1.75R |
| G04 | 0.20 × H4 ATR | 1.75R |

No additional trend filters, EMA lengths, ATR multiples, signal definitions, stop variants, or targets may be introduced after the first result is viewed.

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
Only a development-pass candidate receives stress:
- double observed spread cost
- add 0.3 pip adverse slippage on entry
- add 0.3 pip adverse slippage on exit
- increase commission by 25%

Required stressed PF >= 1.15 and stressed net profit > 0.

## Locked OOS
OOS remains locked through development, stress, and robustness. A final frozen candidate may open OOS once only after passing those stages. OOS gate: positive net profit, PF >= 1.20, at least 50 trades, equity DD <= 15%, recovery factor >= 1.25, no safety violation.

## Freeze rule
This specification is frozen before the first Architecture G result is viewed. If all four configurations fail, Architecture G is retired without redesign using these development results.
