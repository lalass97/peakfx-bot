# BTCUSDT Architecture G — Frozen Specification

Status: FROZEN BEFORE IMPLEMENTATION RESULTS

## Research purpose
Architecture G tests a lower-frequency structure materially different from prior BTC architectures: a completed-week trend regime combined with a completed-day pullback-and-recovery entry. It is not a modification or rescue of Architecture E or F.

2026 data is prohibited from development and may not be accessed by this baseline runner.

## Market and data
- Instrument: BTCUSDT spot.
- Source: Binance public monthly 1h klines from data.binance.vision.
- Aggregate only complete UTC daily bars (24 consecutive hourly bars).
- Aggregate only complete UTC weeks from Monday 00:00 through Sunday 23:59; a weekly bar is valid only when all 7 complete daily bars are present.
- Development window: 2021-01-01 00:00 UTC through 2025-12-31 23:59 UTC.
- Warm-up history may begin before 2021.
- 2026 is locked and must not be downloaded or evaluated.

## Capital, exposure and costs
- Initial capital: 10,000 USDT.
- Long only.
- At most one open position.
- No leverage.
- Risk cash per trade: 0.25% of equity immediately before entry.
- Position notional capped at pre-entry equity.
- Baseline commission: 0.10% per order on entry and exit.
- Baseline slippage: 0.

## Indicators
All indicators use completed bars only.

### Weekly regime
- Weekly EMA30 on completed weekly closes.
- A daily signal is eligible only when the most recently completed weekly bar satisfies:
  1. weekly close > weekly EMA30; and
  2. weekly EMA30 > weekly EMA30 four completed weeks earlier.

The current incomplete week may never be used for the regime filter.

### Daily indicators
- EMA20 on completed daily closes.
- ATR14 using Wilder RMA on completed daily bars.
- RSI14 using Wilder smoothing on completed daily closes.

## Entry hypothesis: pullback recovery inside weekly uptrend
On completed daily bar t, while flat, a long signal occurs only if all are true:
1. the most recently completed weekly regime is bullish as defined above;
2. daily close[t] > EMA20[t];
3. daily close[t] > daily high[t-1];
4. within the immediately preceding `pullback_window` completed daily bars, excluding t, at least one daily low <= its corresponding EMA20;
5. within those same preceding bars, at least one RSI14 value <= `rsi_pullback_threshold`;
6. ATR14[t] is available.

Entry executes at the open of daily bar t+1. No same-close entry is allowed.

## Protective stop and target
At entry:
- initial stop distance = 2.0 * ATR14 from signal bar t;
- stop price = entry - stop distance;
- fixed profit target = entry + `target_r` * (entry - initial stop).

There is no trailing stop.

For every open daily bar:
1. If bar open <= stop, exit at bar open.
2. Else if bar open >= target, exit at bar open.
3. Else if both stop and target are inside the same daily bar's range, assume STOP occurs first (conservative intrabar ordering).
4. Else if low <= stop, exit at stop.
5. Else if high >= target, exit at target.

## Trend-failure exit
If a position survives the daily protective/target checks and the completed daily close falls below EMA20, schedule a discretionary exit at the next daily open. The next bar's protective gap logic takes precedence if worse.

## Frozen configuration matrix
- BG01: pullback_window=3 days, RSI threshold=40, target=2R.
- BG02: pullback_window=6 days, RSI threshold=40, target=2R.
- BG03: pullback_window=3 days, RSI threshold=45, target=3R.
- BG04: pullback_window=6 days, RSI threshold=45, target=3R.

No configuration may be added, removed, or changed after baseline results are observed.

## Development gate
A configuration advances only if all conditions hold:
- net profit > 0 after modeled costs;
- profit factor >= 1.20;
- at least 40 closed trades;
- maximum mark-to-market equity drawdown <= 20%;
- recovery factor >= 1.25;
- at least 4 of 5 calendar years 2021-2025 have positive closed-trade net PnL;
- no execution-integrity violation.

The 40-trade floor is frozen before results because Architecture G operates on daily entries under a weekly regime.

## Robustness gate
Only advancing configurations may proceed. Without changing strategy logic:
1. commission stress at 0.15% per order: net > 0 and PF >= 1.15;
2. pullback-window neighbor check: for each advancing configuration, test window -1 and +1 day, same RSI threshold and target; both neighbor net profits must be > 0;
3. leave-one-calendar-year-out closed-trade PF: at least 4 of 5 values must exceed 1.0.

No parameter may be selected or optimized from robustness outcomes.

## OOS rule
2026 remains locked unless a frozen configuration passes development, robustness, and an independent implementation/data audit. Any eventual OOS protocol must be frozen before 2026 data is accessed.

## Decisions
- Advance: development gate passed.
- Retire: development gate failed.
- No rescue/tuning after observing baseline results.
