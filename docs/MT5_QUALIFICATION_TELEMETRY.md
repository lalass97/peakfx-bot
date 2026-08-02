# MT5 qualification telemetry

`PeakFX_QualificationTelemetry.mqh` is an append-only research logger. It does not calculate signals, size positions, submit orders, modify orders, or close positions.

## Required integration points

1. Construct one `CPeakFXQualificationTelemetry` instance.
2. Call `Open(run_id, broker_utc_offset_minutes)` during initialization.
3. Call `AppendSnapshot(...)` at a fixed, documented cadence and immediately before/after every trade transaction that changes exposure.
4. Call `AppendCompletedTrade(...)` only after a PeakFX-owned position is fully closed and its cost-inclusive net P&L and original-risk R multiple are known.
5. Call `Close()` during deinitialization.

## Evidence files

The module writes:

- `PeakFX_<run_id>_completed_trades.csv`
- `PeakFX_<run_id>_open_equity_snapshots.csv`

The headers exactly match the strict Python loaders used by the qualification runner.

## Non-negotiable rules

- `run_id` must uniquely identify one tester run.
- The UTC offset must match the broker/tester server time used by the EA for that run.
- Snapshot order must be strictly increasing.
- `net_pnl` must include commission and swap attributable to the completed trade.
- `r_multiple` must use the actual initial stop risk recorded at entry; it must not be reconstructed from a later modified stop.
- `gross_exposure` must be the total absolute notional exposure of PeakFX-owned positions only.
- No manual editing, sorting, deduplication, or spreadsheet resaving is allowed before hashing and qualification.

## Current limitation

This branch provides the telemetry module and contract tests only. It is not yet inserted into the recovered v1.42 EA, because baseline behavior must first be preserved and the integration must be reviewed line by line. MQL5 compilation and Strategy Tester validation still require MetaEditor/MT5 on Windows.
