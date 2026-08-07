# Architecture B — Final Retirement Decision

## Status
**RETIRE**

Architecture B (Pre-Structure-Aligned Volatility Expansion) completed its frozen baseline and the one permitted revision B-R1. The specification explicitly allows no second revision.

## B-R1 execution integrity
- 20/20 development cells completed.
- EURUSD, H1 execution, fixed five annual development windows.
- `InpRequireTickVolume=true` in B-R1.
- OOS remained locked.
- No strategy-definition change beyond the single predeclared B-R1 tick-volume filter.

## B-R1 pooled results
| Configuration | Pooled net profit | Pooled trades | Profitable annual windows | Pooled PF |
|---|---:|---:|---:|---:|
| B01 | -152.76 | 17 | 0/5 | 0.52 |
| B02 | -1.71 | 15 | 1/5 | 0.99 |
| B03 | -215.74 | 17 | 0/5 | 0.33 |
| B04 | -162.61 | 15 | 0/5 | 0.40 |

## Frozen B-R1 gate
A configuration had to satisfy every condition:
- pooled net profit > 0
- pooled PF >= 1.30
- pooled trades >= 150
- at least 4 of 5 annual windows profitable
- maximum consecutive losses <= 8
- worst equity drawdown <= 15%
- pooled recovery factor >= 1.50
- no catastrophic annual window or safety violation

No configuration comes close to the evidence threshold. All four fail the minimum trade-count gate; all four fail the profitable-window gate; all four fail the pooled PF gate; and all four have non-positive pooled net profit.

## Decision
Per the frozen specification, fewer than the required trades is retirement for insufficient evidence, not an inconclusive result. Because B-R1 was the single allowed revision, Architecture B is permanently retired and OOS remains unopened.

No additional tuning, parameter search, second revision, or reuse of the locked OOS is allowed under Architecture B.

## Next research step
Move to a genuinely orthogonal hypothesis rather than modifying the volatility-expansion concept. Architecture C must be specified and frozen before its first development result is viewed.
