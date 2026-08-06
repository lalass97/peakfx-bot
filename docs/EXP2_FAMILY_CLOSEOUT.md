# EXP2 Strategy Family Closeout

Status: Retired permanently
Decision date: 2026-08-06
Reserved OOS: Locked and unused

## Scope

The following candidates are closed research:

- EXP2
- EXP3A
- EXP6A
- EXP7
- EXP8

No additional threshold tuning, filter substitution, pullback modification, rescue experiment, or OOS test is authorized for this family.

## Verified evidence

### EXP2

- Net profit: +552.44
- Trades: 465
- Pooled PF: approximately 1.083
- Profitable annual windows: 4/5
- Maximum losing streak: 12

### EXP7

- Net profit: +525.36
- Trades: 466
- Pooled PF: 1.079
- Profitable annual windows: 4/5
- Maximum losing streak: 11

### EXP8

- Net profit: +398.61
- Trades: 414
- Pooled PF: 1.067
- Profitable annual windows: 3/5
- Maximum losing streak: 9

EXP3A and EXP6A were negative over the five-year comparison and failed breadth and consistency requirements.

## Decision basis

The family repeatedly produced marginal pooled PF, limited expectancy, long losing streaks, and sensitivity to small rule changes. Descendants did not create a materially stronger or more stable edge. The evidence supports an architecture-level weakness rather than a missing threshold.

## Permanent restrictions

1. The family cannot be reopened because a later diagnostic appears less bad than expected.
2. A cost-fragility run is permitted only as a read-only post-mortem calibration.
3. That diagnostic may not change the retirement decision or authorize new tuning.
4. Rules and thresholds from this family cannot serve as the base candidate for Architecture A, B, or C.

## Preserved lessons

- Single-window screening is unreliable.
- PF must be evaluated jointly with breadth, recovery, drawdown, trade count, and losing streak.
- Offline projections must be verified in the real MT5 implementation.
- Source hashes, compile logs, exact diffs, raw reports, and manifests are mandatory.
- Shared-function changes can affect both initial and replacement behavior.
- Near-miss results do not justify an undeclared rescue experiment.
