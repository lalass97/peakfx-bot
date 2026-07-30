# PeakFX EUR/USD H1 Paper-Trading Checklist

## Account

- Use a MetaTrader 5 **demo** account only.
- Use a realistic starting balance, default **$10,000**.
- Confirm the account trade mode is demo before attaching the EA.
- Do not change `DemoOnly=true`.

## Chart and EA

- Open the broker's EUR/USD symbol on the H1 timeframe.
- Attach `PeakFX_EURUSD_H1` to only one chart.
- Confirm Algo Trading is enabled.
- Confirm the Experts log shows successful initialization.
- Confirm the broker server timezone matches the configured session hours.

## Required safety inputs

- Risk per trade: 0.25%.
- Maximum risk input: never above 0.50%.
- Maximum two trades per day.
- Daily loss lock: 1.5%.
- Weekly loss lock: 3.0%.
- Equity circuit breaker: 5.0%.
- One open PeakFX position maximum.

## Daily checks

- MetaTrader terminal is connected.
- EUR/USD H1 chart is receiving current ticks.
- AutoTrading remains enabled.
- No duplicate EA instance is attached.
- No unexplained or manually opened position exists.
- Experts and Journal tabs contain no repeated errors.
- Spread and slippage are being recorded.

## Weekly review

Export the completed-trade journal and run:

```bash
python -m paper.paper_trading_report data/paper_trades.csv --starting-balance 10000
```

Review:

- Net profit or loss
- Expectancy
- Profit factor
- Maximum drawdown
- Losing streak
- Average spread
- Average slippage
- Any rejected, duplicated, or unexplained order

## Promotion rules

Do not consider live capital until all are true:

- At least 100 completed trades
- At least three months of uninterrupted demo operation
- Positive expectancy after costs
- Profit factor at least 1.20
- Maximum drawdown below 10%
- No risk-control violations
- No duplicate or unexplained orders
- Backtest and demo behavior are reasonably consistent
- EA compiles without errors in the target MetaTrader 5 build

A passing checklist is evidence for further evaluation, not a guarantee of profit.
