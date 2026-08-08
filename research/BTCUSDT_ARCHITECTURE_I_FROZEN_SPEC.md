# BTCUSDT Architecture I — Frozen Specification

## Status
FROZEN BEFORE IMPLEMENTATION RESULTS. No 2026 data may be loaded or inspected by this architecture during development.

## Hypothesis
BTC weekend strength may exhibit short-lived continuation into the early UTC weekday session because participation/liquidity changes between weekend and weekday trading. This is a calendar/seasonality hypothesis, materially different from prior BTC trend, pullback, compression, range, momentum, failed-breakdown, weekly-pullback, and ETH-led catch-up architectures.

## Market and data
- Instrument: BTCUSDT spot.
- Source: Binance public monthly 1h klines from data.binance.vision.
- Aggregate only complete UTC daily bars containing exactly 24 consecutive hourly bars.
- Development: 2021-01-01 00:00 UTC through 2025-12-31 23:59 UTC.
- Warm-up data may begin in 2020.
- 2026 is locked and must not be requested.
- Long only, one position maximum, no leverage.

## Indicators
- Daily ATR(14), Wilder RMA, computed only from completed UTC daily bars.
- Daily EMA(100), standard recursive EMA on completed daily closes.

## Weekend signal
For each completed UTC Sunday bar `s`:
1. Identify the completed Friday bar immediately two calendar days earlier.
2. Compute weekend return = `Sunday close / Friday close - 1`.
3. Sunday close must be above EMA100[s].
4. Weekend return must be >= the configuration threshold.
5. Strategy must be flat.

If all conditions hold, arm an entry for the next completed bar's open, which must be Monday 00:00 UTC. No signal generated before the development start may create a development trade.

## Entry and risk
- Entry: next Monday UTC daily open.
- Initial stop = entry - 1.5 * ATR14[Sunday].
- Risk cash = 0.25% of current pre-entry equity.
- Quantity = risk cash / stop distance, capped so entry notional <= current equity.
- Commission = 0.10% per order.
- Slippage = 0 baseline.

## Exit
There is no profit target.
- Protective stop is active intraday against the daily bar low. If the daily open is below the stop, exit at the open; otherwise if low <= stop, exit at stop.
- If the stop has not exited the position, exit at the open of the Nth weekday-hold boundary specified by the configuration, counting Monday entry as day 0. Thus a hold of 2 exits Wednesday 00:00 UTC; hold of 3 exits Thursday 00:00 UTC.
- If development ends with an open position, mark it to market at the final completed 2025 daily close rather than fabricating a closed trade.

## Frozen configuration matrix
- BI01: weekend threshold 1.5%, hold 2 days.
- BI02: weekend threshold 2.5%, hold 2 days.
- BI03: weekend threshold 1.5%, hold 3 days.
- BI04: weekend threshold 2.5%, hold 3 days.

## Accounting
- Initial capital: 10,000 USDT.
- Entry commission deducted immediately.
- Closed-trade PnL includes allocated entry and exit commissions.
- Mark-to-market equity includes unrealized PnL and estimated exit commission.
- Maximum drawdown is computed on the daily mark-to-market equity series.

## Frozen development gate
A configuration advances only if all are true:
- net profit > 0 after modeled costs;
- profit factor >= 1.20;
- at least 40 closed trades;
- maximum MTM drawdown <= 20%;
- recovery factor >= 1.25;
- at least 4 of 5 calendar years 2021-2025 have positive closed-trade net PnL;
- no integrity violation.

If no configuration advances, Architecture I is Retired. No threshold, hold period, stop multiple, fee assumption, or gate may be changed after seeing baseline results. No 2026 test occurs unless a frozen configuration later clears development and a separately frozen robustness protocol.
