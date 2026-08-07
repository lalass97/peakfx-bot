# Architecture C — Retirement Record

## Decision
**RETIRE** — Session Exhaustion Mean Reversion (Architecture C)

Architecture C was frozen before testing. The complete 20-cell baseline matrix (C01–C04 across five annual development windows) executed and the independent artifact verifier reported a complete, verified matrix with OOS still locked.

## Frozen development gate
A configuration could advance only if every condition passed: pooled net profit > 0; pooled PF >= 1.20; pooled trades >= 100; at least 4/5 annual windows profitable; maximum consecutive losses <= 8; worst equity drawdown <= 15%; pooled recovery factor >= 1.25; and no safety/execution-integrity violation.

## Baseline results
| Config | Pooled net | Pooled PF | Trades | Profitable years | Max consecutive losses | Worst equity DD | Pooled recovery* | Decision |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| C01 | +144.13 | 1.186 | 166 | 4/5 | 2 | 1.08% | 1.329 | Retire |
| C02 | +202.84 | 2.442 | 67 | 3/5 | 1 | 0.50% | 4.064 | Retire |
| C03 | -183.08 | 0.934 | 224 | 1/5 | 7 | 2.86% | -0.636 | Retire |
| C04 | +204.03 | 1.208 | 91 | 2/5 | 5 | 1.49% | 1.366 | Retire |

\*Pooled recovery shown as pooled net profit divided by the worst annual maximal equity drawdown in money, consistent with the project decision calculation used for this record.

## Why each configuration failed
- C01: passed net profit, trade count, annual stability, consecutive-loss, drawdown, and recovery requirements, but pooled PF was 1.186, below the frozen 1.20 threshold.
- C02: failed the minimum evidence requirement (67 < 100 trades) and annual stability (3/5 profitable years).
- C03: failed pooled profitability, pooled PF, annual stability, and pooled recovery.
- C04: failed minimum evidence (91 < 100 trades) and annual stability (2/5 profitable years).

## Integrity
The uploaded artifact's `independent_verification.json` reported `verified: true`, `expected_run_count: 20`, `observed_run_count: 20`, `matrix_complete: true`, and no errors. All manifest entries retained `oos_locked: true`; reserved OOS was not tested.

## Freeze-rule consequence
The frozen specification explicitly states that if all four configurations fail, Architecture C is retired and research moves to a genuinely orthogonal hypothesis. No threshold, stop, target, session, or gate may now be modified to rescue Architecture C.

## Final state
**Architecture C: RETIRED.**

No cost stress, robustness promotion, or locked OOS test is authorized because no configuration cleared the frozen development gate.
