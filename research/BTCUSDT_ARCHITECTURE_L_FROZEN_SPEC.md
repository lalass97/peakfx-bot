# BTCUSDT Architecture L — Frozen Baseline Spec

## Research reset context
Architecture L is the third and final architecture in the frozen J/K/L reset batch. Architecture J and K both retired at Stage 1. No Architecture M may be created inside this reset batch.

## Hypothesis
Short-horizon BTC continuation should be more reliable when recent H4 returns themselves are in a statistically persistent regime. The strategy therefore does not trade every momentum impulse; it trades only when the rolling lag-1 autocorrelation of completed H4 log returns is materially positive and price is above a long-term trend filter.

## Instrument and data
- BTCUSDT Binance spot public monthly 1h klines.
- Aggregate only complete UTC H4 bars.
- Long-only, maximum one open position.
- Initial capital: 10,000 USDT.
- Risk per trade: 0.25% of current equity.
- Gross notional capped at current equity; no leverage.
- Commission: 0.10% per order; no slippage.

## Frozen stages
- Stage 1 development: 2021-01-01 through 2023-12-31.
- Stage 2 validation: 2024-01-01 through 2024-12-31, opened only if a configuration passes Stage 1.
- Stage 3 confirmation: 2025-01-01 through 2025-12-31, opened only if the same configuration passes Stage 2.
- 2026 is excluded from this architecture.

## Indicators and signal
All calculations use completed H4 bars only.
- EMA200 of H4 close, SMA-seeded then recursive.
- H4 log return = ln(close[t] / close[t-1]).
- Rolling lag-1 Pearson autocorrelation of the latest N completed H4 returns.
- ATR14 Wilder.

A long signal occurs at a completed H4 close when all are true:
1. close > EMA200;
2. rolling lag-1 return autocorrelation >= the frozen threshold;
3. current completed H4 log return >= +0.75%;
4. previous completed H4 log return > 0;
5. flat.

Entry executes at the next H4 open.

## Exit and risk
- Initial stop: entry price - 2.5 * signal-bar ATR14.
- Profit target: entry price + frozen target-R * initial risk distance.
- Maximum holding period: frozen number of H4 bars; if still open, exit at the next H4 open after the maximum hold is reached.
- Stop and target active from entry bar onward. If both occur inside the same H4 bar and ordering is unknowable from H1 aggregation, count the stop first (conservative).
- Gap-through stop fills at the worse of stop price or H4 open.
- Target gaps fill at target price, not a better open.

## Frozen matrix
- BL01: autocorr lookback 42 H4 returns; threshold +0.15; max hold 6 H4 bars; target 1.5R.
- BL02: autocorr lookback 84 H4 returns; threshold +0.15; max hold 6 H4 bars; target 1.5R.
- BL03: autocorr lookback 42 H4 returns; threshold +0.25; max hold 9 H4 bars; target 2.0R.
- BL04: autocorr lookback 84 H4 returns; threshold +0.25; max hold 9 H4 bars; target 2.0R.

## Stage 1 gate
A configuration advances only if ALL are true on 2021-2023:
- net profit > 0;
- profit factor >= 1.20;
- at least 40 closed trades;
- maximum mark-to-market drawdown <= 20%;
- recovery factor >= 1.25;
- at least 2 of 3 calendar years profitable;
- no integrity violation.

## Stage 2 gate
For any Stage-1 passer, 2024 is evaluated with frozen rules and fresh 10,000 USDT starting equity. It advances only if:
- net profit > 0;
- profit factor >= 1.20;
- maximum drawdown <= 20%;
- recovery factor >= 1.25;
- no integrity violation.

## Stage 3 gate
For any Stage-2 passer, 2025 is evaluated with frozen rules and fresh 10,000 USDT starting equity. It confirms only if:
- net profit > 0;
- profit factor >= 1.20;
- maximum drawdown <= 20%;
- recovery factor >= 1.25;
- no integrity violation.

## Freeze rule
No parameter, condition, execution rule, gate, or configuration may be changed after this commit in response to results. A failed stage retires that configuration. If every BL configuration retires, Architecture L retires and the J/K/L BTC architecture-search cycle stops.