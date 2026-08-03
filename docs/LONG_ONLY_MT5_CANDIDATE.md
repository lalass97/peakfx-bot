# Long-only MT5 candidate

This branch adds a deterministic builder for the first isolated strategy repair experiment.

## Source and output

Input must be the exact recovered `PeakFX_EURUSD_H1_PULLBACK.mq5` v1.42 source. Generate the separate candidate with:

```bash
python -m research.build_long_only_mt5_candidate \
  PeakFX_EURUSD_H1_PULLBACK.mq5 \
  PeakFX_EURUSD_H1_PULLBACK_LONG_ONLY_EXP1.mq5
```

The builder fails closed when the expected v1.42 structure is missing, duplicated, or already modified.

## Deliberate differences only

- Version changes from 1.42 to 1.43.
- Magic number changes from `26073004` to `26073014` for position and persisted-state isolation.
- Telemetry filename changes to `peakfx_pullback_long_only_exp1_events.csv`.
- New short pullback setups are ignored.
- Any restored short setup is discarded.
- `ExecuteEntry(false)` is blocked before sizing, margin checks, or order submission.

Stops, targets, risk, trading hours, spread limits, cooldown, pullback expiry, trigger logic, long entry logic, and risk controls remain unchanged.

## Required local verification

1. Compile the generated file in MetaEditor and require 0 errors.
2. Run a short visual Strategy Tester smoke test and verify no short entry occurs.
3. Run the declared 2016-01-01 through 2025-07-31 real-tick test with the same baseline settings.
4. Save the HTML report and exports before changing any setting.
5. Repeat the candidate with doubled trading costs.
6. Score the immutable evidence using the long-only qualification command.

This candidate is Strategy Tester and demo research only. It is not approved for live trading and carries no profitability claim.
