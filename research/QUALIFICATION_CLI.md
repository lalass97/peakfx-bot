# Qualification command-line contract

Run the combined research gate with two exported CSV files:

```bash
python -m research.run_qualification \
  --trades completed_trades.csv \
  --snapshots open_equity_snapshots.csv \
  --output qualification_report.json
```

The runner writes the same strict JSON report to stdout and, when requested, to the output path.

Exit codes are stable and intended for CI or scripted research runs:

- `0`: green
- `2`: red
- `3`: inconclusive
- `4`: malformed, unreadable, or invalid input

The command does not sort, repair, optimize, or alter either export. It does not execute a backtest or submit orders.
