PeakFX qualification runner

Use:
python -m research.run_qualification --trades completed_trades.csv --snapshots open_equity_snapshots.csv --output qualification_report.json

Exit codes:
0 green
2 red
3 inconclusive
4 invalid input

The runner never sorts, repairs, optimizes, executes a backtest, or submits orders.
