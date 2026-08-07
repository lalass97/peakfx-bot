# Architecture G — Retirement Record

## Decision
**RETIRE**

## Artifact
GitHub Actions run: `31220009149`

Independent artifact verification: **PASSED**
- expected runs: 20
- observed runs: 20
- matrix complete: true
- verification errors: none

## Pooled development results
| Config | Net profit | Pooled PF | Trades | Profitable annual windows | Worst equity DD | Max consecutive losses |
|---|---:|---:|---:|---:|---:|---:|
| G01 | -1845.97 | 0.820 | 712 | 0/5 | 7.90% | 11 |
| G02 | -1901.59 | 0.813 | 703 | 0/5 | 7.66% | 10 |
| G03 | -2496.78 | 0.781 | 696 | 1/5 | 11.46% | 15 |
| G04 | -2595.48 | 0.770 | 688 | 1/5 | 11.22% | 15 |

All configurations fail the frozen development gate because pooled net profit is negative, pooled PF is below 1.20, annual stability is insufficient, and several variants exceed the maximum-consecutive-loss gate.

No post-result tuning is permitted. Architecture G is retired and OOS remains unopened.