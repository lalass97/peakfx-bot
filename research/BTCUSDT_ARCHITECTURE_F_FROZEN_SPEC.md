# BTCUSDT Architecture F — Frozen Failed-Breakdown Reversal Specification

Status: FROZEN BEFORE IMPLEMENTATION OR RESULTS

## Research objective
Test a materially different BTC/USDT long-only hypothesis after Architecture E failed 2026 OOS. Architecture F is a failed-breakdown reversal model: buy only after price first breaks a recent H4 support level and then reclaims that same level on a completed H4 bar while the long-term trend remains constructive. This is not a momentum continuation, compression breakout, Bollinger/RSI range system, or Architecture E parameter variation.

## Market and data
- Instrument: BTCUSDT spot.
- Source: Binance public spot monthly 1h klines from data.binance.vision.
- Aggregate only complete groups of four consecutive UTC H1 bars into completed UTC H4 bars.
- Development window: 2021-01-01 00:00 UTC through 2025-12-31 23:59 UTC.
- Pre-2021 data may be used only for indicator warm-up.
- 2026 data is locked and MUST NOT be downloaded, loaded, or inspected during Architecture F development or robustness.

## Capital and costs
- Initial capital: 10,000 USDT.
- Long only; maximum one open position.
- No leverage.
- Initial risk cash: 0.25% of current equity per trade.
- Notional capped at current equity.
- Baseline commission: 0.10% per order on entry and exit.
- Baseline slippage: 0.

## Indicators
All indicators use completed H4 bars only.
- EMA200 of H4 closes.
- ATR14, Wilder RMA.
- Support level for lookback L on bar t: minimum low of completed bars t-L through t-1, excluding bar t.

## Setup state
A breakdown candidate is created on completed H4 bar t only when all conditions hold:
1. EMA200[t] exists.
2. close[t] > EMA200[t]. This keeps the architecture in a constructive long-term regime even though the current bar probes support.
3. EMA200[t] > EMA200[t-12].
4. low[t] < support[t]. Price trades below the prior support level.
5. close[t] <= support[t]. The breakdown bar closes at or below that prior support level.

When a breakdown candidate occurs, store:
- breakdown support = support[t]
- breakdown low = low[t]
- breakdown ATR = ATR14[t]
- expiry = N completed H4 bars after t, where N is the frozen reclaim window for the configuration.

Only one breakdown candidate may be active while flat. A newer qualifying breakdown replaces the older active candidate before reclaim.

## Reclaim trigger
While flat and an unexpired breakdown candidate exists, completed H4 bar r triggers a long entry only when all conditions hold:
1. r occurs after the breakdown bar and no later than the configuration's reclaim-window expiry.
2. close[r] > stored breakdown support.
3. close[r] > open[r] (bullish reclaim candle).
4. close[r] > close[r-1].
5. ATR14[r] exists.

Entry executes at open[r+1]. No entry may occur on the reclaim/signal bar itself.

## Initial stop and sizing
At entry:
- structural stop reference = stored breakdown low - 0.25 * ATR14[reclaim bar].
- stop distance = entry price - structural stop reference.
- Entry is skipped if stop distance <= 0 or stop reference <= 0.
- risk_cash = 0.25% of pre-entry equity.
- quantity = risk_cash / stop_distance, capped so entry notional <= pre-entry equity.

## Exit
Each configuration has a fixed R target.
- Profit target = entry + target_R * initial stop distance.
- Initial stop remains fixed; Architecture F has no trailing stop.
- On each H4 bar after entry, protective stop and target are evaluated using that bar's OHLC.
- Gap below stop: exit at bar open if open < stop; otherwise at stop.
- Gap above target: exit at bar open if open > target; otherwise at target.
- If both stop and target are touched within the same H4 bar and neither is resolved by an opening gap, assume STOP first. This is deliberately conservative because intrabar order is unknown from H4 OHLC.
- Time exit: if position survives for 18 completed H4 bars after entry (72 hours), exit at the next H4 open.
- Development-end open positions are marked to market for ending equity but are not fabricated as closed trades.

## Frozen configuration matrix
Exactly four baseline configurations:
- BF01: support lookback L=18 H4 bars, reclaim window N=2 H4 bars, target=2R.
- BF02: support lookback L=36 H4 bars, reclaim window N=2 H4 bars, target=2R.
- BF03: support lookback L=18 H4 bars, reclaim window N=3 H4 bars, target=3R.
- BF04: support lookback L=36 H4 bars, reclaim window N=3 H4 bars, target=3R.

No other configuration may be introduced after baseline results are seen.

## Development gate
A configuration Advances only if all are true:
- net profit > 0 after baseline costs;
- profit factor >= 1.20;
- at least 40 closed trades;
- maximum mark-to-market equity drawdown <= 20%;
- recovery factor >= 1.25 using net profit / maximum mark-to-market drawdown dollars;
- at least 4 of 5 calendar years 2021-2025 have positive realized closed-trade PnL;
- no execution-integrity violation.

The 40-trade floor is frozen now because failed-breakdown reversals are intentionally event-driven and lower-frequency than the earlier H1 systems.

## Frozen robustness if a configuration Advances
Only advancing configurations proceed.
1. Cost stress: commission 0.15% per order; require net profit > 0 and PF >= 1.15.
2. Support-neighbor check with all other rules unchanged: test L-6 and L+6 H4 bars; both neighbors must have net profit > 0 at baseline cost.
3. Reclaim-window neighbor check: test N-1 and N+1 completed H4 bars, bounded at minimum 1; both neighbors must have net profit > 0 at baseline cost.
4. Leave-one-year-out closed-trade stability: remove each calendar year's closed trades in turn; at least 4 of 5 resulting PF values must be > 1.0.

No parameter is selected, tuned, or changed based on robustness output.

## OOS rule
2026 remains locked unless a frozen Architecture F configuration passes both development and the complete frozen robustness suite. Any later OOS protocol must be committed before 2026 data is accessed. Architecture E's failed 2026 OOS data may not be used to tune Architecture F.

## Interpretation
Architecture F is one additional architecture family in an already adaptive research program. A development pass is not validation. Multiplicity and selection history must remain visible in any later interpretation.