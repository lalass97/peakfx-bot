# Architecture C — Draft Orthogonal Hypothesis

## Working name
**Session Exhaustion Mean Reversion**

## Why this is orthogonal to Architecture B
Architecture B was a D1/H1 volatility-compression breakout and continuation hypothesis. Architecture C deliberately tests the opposite market behavior: whether a statistically extreme intraday extension away from a completed-session reference tends to mean-revert during the same trading day.

Architecture C must not reuse Architecture B's compression box, pre-compression swing direction, expansion multiplier, or continuation entry logic.

## Research hypothesis
On EURUSD, after the European session has produced an unusually large directional extension relative to recent completed-session ranges, a failed continuation and completed H1 reversal signal may have positive expectancy toward the session reference price.

This is a price/time hypothesis only. It does not claim centralized order flow or institutional-flow observation.

## Candidate structure to freeze before testing
- Symbol: EURUSD only.
- Signal/execution: H1 completed bars only.
- Session clock: UTC with explicit broker-server conversion in artifacts.
- Reference: completed Asian-session range and midpoint calculated before European-session trading begins.
- Exhaustion requirement: European-session price must extend beyond the Asian range by a predeclared multiple of recent median Asian-session range.
- Reversal requirement: a completed H1 bar must close back inside the extended boundary after the excursion.
- Direction: fade the excursion (short after upside exhaustion, long after downside exhaustion).
- Maximum one trade per direction per day and one open position at a time.
- Fixed fractional risk; no martingale, grid, averaging down, or pyramiding.
- Exit candidates to predeclare before testing: midpoint target versus fixed-R target.
- Development windows: preserve the five annual PeakFX development windows.
- OOS: remain locked until a final candidate clears development, cost stress, and robustness.

## Required pre-test work
Before any Architecture C backtest is run:
1. Freeze exact Asian and European session UTC times.
2. Freeze the lookback and definition of the range-extremeness threshold.
3. Freeze reversal-bar definition.
4. Freeze stop basis and exit styles.
5. Freeze no more than four configurations.
6. Freeze minimum evidence, PF, annual stability, recovery, drawdown, and cost-stress gates.
7. Implement integrity checks and artifact verification before running the matrix.

## Current state
**DRAFT — NOT TESTED.**

No Architecture C development result may be generated until the specification is converted from this draft into a frozen baseline specification with hashes and a locked matrix.
