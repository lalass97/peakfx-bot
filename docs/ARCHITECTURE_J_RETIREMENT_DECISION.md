# Architecture J — Retirement Decision

## Decision
**State: Retire**

Architecture J (Prior-Day Failed-Breakout Reversal) failed the frozen development gate and is retired. No cost stress, robustness stage, or locked OOS test is permitted.

## Artifact integrity
The uploaded Architecture J baseline artifact independently verified successfully:
- expected runs: 20
- observed runs: 20
- matrix complete: true
- verification errors: none
- OOS remained locked

## Pooled development results
| Configuration | Net profit | Pooled trades | Pooled PF | Profitable annual windows | Worst annual equity DD | Max consecutive losses |
|---|---:|---:|---:|---:|---:|---:|
| J01 | -$645.83 | 439 | 0.901 | 1/5 | 5.40% | 13 |
| J02 | -$206.15 | 204 | 0.922 | 2/5 | 3.47% | 8 |
| J03 | -$371.73 | 443 | 0.937 | 3/5 | 3.61% | 9 |
| J04 | +$57.73 | 207 | 1.022 | 2/5 | 2.35% | 8 |

## Gate outcome
No configuration satisfies the frozen development requirements. J01, J02, and J03 have negative pooled net profit and PF below 1.20. J04 has positive pooled net profit but PF is only approximately 1.02 and only 2 of 5 annual windows are profitable, so it also fails materially.

Architecture J is therefore retired without parameter rescue, threshold relaxation, or reuse of locked OOS data.

## Research implication
Repeated failures across several orthogonal architectures now justify a change in research method rather than simply generating an indefinite sequence of new lettered strategies. The next research stage should focus on diagnosing where any edge may exist using predeclared exploratory analysis, then freeze a new hypothesis only after that diagnostic stage is complete.
