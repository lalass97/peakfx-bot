# PeakFX Execution Reconciliation

This report compares the Python model's completed trades with trades completed on the MT5 demo account. It is designed to answer whether live paper execution behaves like the assumptions used during research.

## Inputs

Modeled trade CSV columns:

```text
entry_time,side,entry,exit_time,exit,pnl
```

Paper trade CSV columns:

```text
entry_time,side,entry,exit_time,exit,pnl,ticket
```

`side` must be `1` for long or `-1` for short. Timestamps are parsed as UTC.

## Command

```powershell
python -m paper.execution_reconciliation reports/trades.csv data/paper/live_trades.csv
```

Outputs:

- `reports/execution_reconciliation.csv`: one record for every modeled or unexpected live trade.
- `reports/execution_reconciliation.json`: compact execution-health summary.

## Matching rules

- One-to-one matching by trade direction and nearest entry timestamp.
- Default matching window: 90 minutes.
- A modeled trade without a live match is `missed_live`.
- A live trade without a modeled match is `unexpected_live`.

## Default warnings

- Missed-trade rate at least 5%: warning.
- Missed-trade rate at least 15%: critical.
- Entry slippage p95 at least 0.8 pip: warning.
- Entry slippage p95 at least 2.0 pips: critical.
- Exit slippage p95 at least 1.0 pip: warning.
- Exit slippage p95 at least 2.5 pips: critical.
- Any unexpected live trade: warning or worse.

These values are operating thresholds, not claims about broker quality. They should later be calibrated from observed demo fills without loosening them merely to make a weak result look acceptable.

## Interpretation

A profitable backtest is not sufficient when the live demo account repeatedly misses signals, receives materially worse fills, or places unexplained trades. Reconciliation must remain within acceptable limits before the strategy can pass paper-trading qualification.
