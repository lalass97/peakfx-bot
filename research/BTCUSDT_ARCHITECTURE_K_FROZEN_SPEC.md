# BTCUSDT Architecture K — Frozen Spec

Status: FROZEN BEFORE RESULTS

## Research-reset context
Architecture K is the second and penultimate architecture in the frozen J/K/L reset batch. Architecture J retired at Stage 1. No changes to J are permitted. Architecture K must be evaluated sequentially: Stage 1 (2021-2023), then only if Stage 1 passes may 2024 be opened, then only if 2024 passes may 2025 be opened. 2026 is prohibited.

## Hypothesis
Unusually strong bullish H4 returns accompanied by unusually high H4 volume, while BTC is already above a rising long-term trend filter, may reflect fresh information/liquidity demand that persists for a limited number of subsequent H4 bars.

## Instrument / data
- BTCUSDT Binance spot public monthly 1h klines.
- Aggregate only complete UTC H4 groups of four consecutive H1 bars.
- 2020 may be loaded only as indicator warm-up.
- Stage 1 may load 2021-2023 only.
- 2024 may be loaded only after a Stage-1 pass.
- 2025 may be loaded only after a 2024 pass.
- 2026 must never be requested by this architecture.

## Portfolio / costs
- Initial equity: 10,000 USDT at each stage.
- Long only, one position maximum, no leverage.
- Risk per trade: 0.25% of current equity.
- Gross notional capped at current equity.
- Commission: 0.10% per order.
- No modeled slippage.

## Indicators
On completed H4 bars:
- EMA200 of H4 close.
- EMA200 slope: current EMA200 > EMA200 12 completed H4 bars earlier.
- ATR14 Wilder.
- Mean H4 volume over the 20 completed H4 bars strictly preceding the signal bar.

## Signal / execution
A bullish volume-shock signal exists on a completed H4 bar when all are true:
1. close > EMA200;
2. EMA200 > EMA200 12 completed H4 bars earlier;
3. signal-bar return `(close/open - 1)` >= frozen impulse threshold;
4. signal-bar volume >= frozen volume multiple × mean volume of the preceding 20 completed H4 bars.

If flat, enter at the next H4 open.
- Initial stop = entry - 1.5 × signal ATR14.
- Fixed target = entry + target-R × initial stop distance.
- Time exit: after 12 completed H4 bars including the entry bar, exit at next H4 open if neither stop nor target has closed the position.
- Gap through stop/target fills at the opening price when worse/more conservative than the level.
- If stop and target are both touched inside one H4 bar, assume stop first.

## Frozen matrix
- BK01: impulse >= 2.0%, volume >= 1.50× prior-20 mean, target 2R.
- BK02: impulse >= 3.0%, volume >= 1.50× prior-20 mean, target 2R.
- BK03: impulse >= 2.0%, volume >= 2.00× prior-20 mean, target 3R.
- BK04: impulse >= 3.0%, volume >= 2.00× prior-20 mean, target 3R.

No additional K configurations are permitted after this freeze.

## Stage gates
### Stage 1: 2021-01-01 through 2023-12-31
Each configuration independently advances only if all are true:
- net profit > 0;
- PF >= 1.20;
- at least 40 closed trades;
- MTM max drawdown <= 20%;
- recovery factor >= 1.25;
- at least 2 of 3 calendar years profitable;
- no integrity violation.

If no K configuration advances, Architecture K is retired and 2024/2025 remain unopened for K.

### Stage 2: calendar 2024
Only Stage-1 advancing configurations may be evaluated. Fresh 10,000 USDT stage equity. Must have net > 0, PF >= 1.10, DD <= 20%, recovery >= 1.0, no integrity violation.

### Stage 3: calendar 2025
Only Stage-2 passing configurations may be evaluated. Same fresh-equity rules and same gate as Stage 2.

A configuration that fails any stage is retired permanently. No rescue, threshold change, or substitution after observing later-stage results.

## Interpretation
A K pass through 2025 is a staged historical candidate only. It is not live validation and does not erase prior A-J failures or E's 2026 OOS failure.