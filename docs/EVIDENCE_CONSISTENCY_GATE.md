# Evidence consistency gate

A completed-trade export and an open-equity export are not accepted merely because each file is valid on its own.

The qualification pipeline must also verify that:

- the first open-equity snapshot is at or before the first completed-trade close;
- the last open-equity snapshot is at or after the last completed-trade close;
- the snapshot evidence covers a positive time interval;
- neither input is sorted, repaired, truncated, or otherwise altered during validation.

This gate prevents a result from being qualified when floating-risk evidence omits the beginning or end of the trading run.
