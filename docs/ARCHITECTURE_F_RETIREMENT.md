# Architecture F Retirement Record

## Decision
**RETIRE**

Architecture F (London Opening-Range Breakout) completed its frozen 20-cell development matrix and independent artifact verification passed.

Pooled development results from the verified artifact:

| Config | Net profit | Trades | Pooled PF | Profitable annual windows | Worst annual equity DD |
|---|---:|---:|---:|---:|---:|
| F01 | -1839.76 | 1289 | 0.887 | 0/5 | 8.64% |
| F02 | -2182.44 | 1289 | 0.866 | 0/5 | 8.33% |
| F03 | -2798.15 | 1289 | 0.853 | 0/5 | 12.31% |
| F04 | -2973.48 | 1289 | 0.843 | 0/5 | 12.62% |

All four configurations fail the frozen development gate because pooled net profit is negative, pooled PF is below 1.20, and 0 of 5 annual windows are profitable.

No parameter, target, buffer, session window, stop basis, or gate may be modified after viewing these results. Architecture F is retired and OOS remains unopened.
