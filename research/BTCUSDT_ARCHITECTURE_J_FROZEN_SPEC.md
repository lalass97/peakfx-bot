# BTCUSDT Architecture J — Frozen Baseline Spec

Status: FROZEN BEFORE IMPLEMENTATION
Parent research protocol: `research/BTCUSDT_JKL_RESEARCH_RESET_PROTOCOL.md`

## Hypothesis
BTC may exhibit short directional continuation after transitioning from an unusually low realized-volatility regime into a large bullish daily expansion. The proposed edge is the regime transition itself, not an ordinary moving-average crossover or breakout family.

## Market and data
- BTCUSDT spot.
- Binance public standard monthly 1h klines.
- Aggregate only complete UTC daily bars containing exactly 24 consecutive hourly bars.
- Load 2020 only for indicator warm-up.
- Never request 2026 data in this architecture baseline.

## Indicators
On completed daily bars:
- RV20: population standard deviation of the previous 20 close-to-close log returns, annualization not required because only relative ranking is used.
- RV percentile: percentile rank of the current RV20 against the immediately preceding 252 available RV20 observations. Current RV20 is not included in its own reference distribution.
- ATR20: Wilder ATR(20).

## Regime and signal
For a bullish expansion signal on completed day `i`:
1. At least one of the previous five completed days, including day `i-1` but excluding day `i`, had RV percentile <= the configuration's frozen low-vol percentile threshold.
2. Day `i` is bullish: close > open.
3. Day `i` true range >= frozen expansion multiple × ATR20 measured from day `i-1` (so the expansion bar cannot inflate its own threshold).
4. Day `i` closes in the upper 25% of its daily range: `(close-low)/(high-low) >= 0.75`.
5. Day `i` close is above the close 20 completed days earlier. This is only a coarse directional guard, not the architecture's trigger.

Entry executes at the next completed daily bar open if flat.

## Risk and exits
- Initial stop = entry price - 1.5 × ATR20 from the completed signal day.
- Position quantity = min(0.25% current equity / stop distance, current equity / entry price).
- Fixed target = entry + frozen target-R × stop distance.
- Time exit after 10 completed daily bars including entry day, executed at the next daily open after the time condition is known.
- Protective stop and target are evaluated intraday from daily OHLC. If both are touched in the same daily bar, stop is assumed first (conservative).
- Gap through stop fills at daily open if worse than the stop. Gap beyond target fills at daily open if favorable.
- Entry and exit commission = 0.10% of notional per order.
- One position maximum, long only, no leverage.

## Frozen matrix
- BJ01: low-vol percentile 15%, expansion 1.50 × prior ATR20, target 2.0R
- BJ02: low-vol percentile 25%, expansion 1.50 × prior ATR20, target 2.0R
- BJ03: low-vol percentile 15%, expansion 2.00 × prior ATR20, target 3.0R
- BJ04: low-vol percentile 25%, expansion 2.00 × prior ATR20, target 3.0R

No other Architecture J configurations may be added after the first baseline result.

## Evaluation
Use the exact staged gates frozen in `BTCUSDT_JKL_RESEARCH_RESET_PROTOCOL.md`:
- Stage 1: 2021-2023 development.
- Stage 2: 2024 holdout, only Stage-1 passers.
- Stage 3: 2025 confirmation, only Stage-2 passers.

Every stage begins from fresh 10,000 USDT capital but indicators retain prior historical warm-up. No state or open trade is carried across stage boundaries.

## Freeze rule
No rescue, threshold adjustment, added filter, altered cost, or alternate execution rule is allowed after baseline results are produced.
