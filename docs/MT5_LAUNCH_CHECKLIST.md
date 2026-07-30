# PeakFX MT5 Launch Checklist

Use this checklist before the EA is allowed to paper trade. Do not use a live-money account.

## 1. Install and compile

1. Open MetaTrader 5 on Windows.
2. Select **File → Open Data Folder**.
3. Open `MQL5/Experts`.
4. Copy `mt5/PeakFX_EURUSD_H1.mq5` into that folder.
5. Open MetaEditor with **F4**.
6. Open `PeakFX_EURUSD_H1.mq5` and press **F7**.
7. Launch is blocked unless compilation reports **0 errors**.
8. Save a screenshot or copy of the compiler result for the project record.

## 2. Confirm the account and chart

- Account must be a broker demo account.
- Chart must be the broker's EUR/USD symbol.
- Chart timeframe must be H1.
- Algo Trading must remain off until the checks below pass.
- Confirm the broker's server timezone.
- Confirm symbol digits, point size, tick size, tick value, volume minimum, volume step, and minimum stop distance.

## 3. Strategy Tester validation

Run the MT5 Strategy Tester using:

- Expert: `PeakFX_EURUSD_H1`
- Symbol: broker EUR/USD symbol
- Period: H1
- Modeling: Every tick based on real ticks, when available
- Deposit: 10,000 USD
- Demo-only input: enabled
- Risk per trade: 0.25%
- Visual mode: enabled for the first short test

The tester must demonstrate:

- No entry before a completed H1 signal candle
- Correct stop-loss and take-profit placement
- No more than one PeakFX position at a time
- No more than two entries per day
- Correct daily, weekly, and drawdown locks
- No new trades after the Friday cutoff
- Telemetry file creation in MT5 Common Files
- No repeated or unexplained orders after terminal restart

## 4. Historical-data run

Export broker H1 data and run the Python audit before starting the long demo test.

Required evidence:

- Normal, 2x, and 3x cost results
- Best-trade removal results
- Bootstrap and block-bootstrap confidence intervals
- Quarterly stability
- Walk-forward windows
- Risk comparison for 0.25%, 0.50%, and paper-only 0.75%

No profitability claim may be made from incomplete or synthetic data.

## 5. Start the demo sandbox

Only after compilation and Strategy Tester validation:

1. Open one EUR/USD H1 chart.
2. Attach `PeakFX_EURUSD_H1`.
3. Keep `DemoOnly=true`.
4. Keep risk at 0.25% initially.
5. Confirm the displayed magic number is `26073001`.
6. Enable Algo Trading.
7. Keep MT5 and the internet connection running.
8. Check the Experts and Journal tabs for startup errors.
9. Confirm `PeakFX/peakfx_events.csv` receives startup and heartbeat events.

## 6. Immediate shutdown conditions

Disable Algo Trading immediately when any of these occur:

- A live account is detected
- Duplicate or unexplained order
- Incorrect symbol or timeframe
- Missing stop loss
- Position risk exceeds the configured amount
- Daily, weekly, or drawdown lock fails
- Repeated order rejection
- Stale price feed or abnormal spread behavior
- Telemetry stops updating

## 7. Promotion rule

The EA remains demo-only until it completes the declared paper-trading qualification gates and its live-versus-model reconciliation shows acceptable execution drift. Passing a backtest alone is not permission to trade real money.
