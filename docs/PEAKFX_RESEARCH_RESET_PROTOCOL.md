# PeakFX Architecture Reset Protocol

Status: Active
Adopted: 2026-08-06

## Closed research

EXP2, EXP3A, EXP6A, EXP7, and EXP8 are permanently closed. Their rules and thresholds may be studied as historical evidence, but they may not be reused as the foundation of a new candidate or reopened through additional tuning.

Reserved out-of-sample data remains locked.

## Research budget

The next cycle permits no more than three genuinely different architectures:

1. Higher-timeframe regime plus intraday session breakout
2. Intraday mean reversion with execution constraints
3. Trend-carry hybrid

Each architecture receives exactly:

- one frozen baseline;
- one predeclared revision;
- no more than ten configurations declared before testing;
- no additional rescue experiment, threshold search, or parked status.

The only permitted statuses are Advance, Retire, and Validated.

## Baseline joint gate

A baseline advances only when every requirement passes:

- pooled profit factor at least 1.20 after modeled costs;
- positive aggregate net profit;
- at least 100 trades;
- at least four of five profitable annual windows;
- maximum consecutive losses no greater than 8;
- worst equity drawdown no greater than 15%;
- recovery factor at least 1.25;
- no safety-rule violation.

Passing the baseline gate grants permission only for the single predeclared revision.

## Frozen revised joint gate

The one permitted revision advances only when every requirement passes:

- pooled profit factor at least 1.30 after modeled costs;
- positive aggregate net profit;
- at least 150 trades;
- at least four of five profitable annual windows;
- maximum consecutive losses no greater than 8;
- worst equity drawdown no greater than 15%;
- recovery factor at least 1.50;
- no catastrophic individual-year degradation;
- no safety-rule violation.

Failure to reach this gate after the single revision retires the architecture immediately.

## Robustness joint gate

The frozen candidate must survive the predeclared stress suite:

- wider execution costs;
- added slippage;
- modest parameter perturbations;
- delayed execution where applicable;
- trade-order Monte Carlo analysis.

Every requirement must pass:

- stressed pooled profit factor at least 1.15;
- positive stressed aggregate net profit;
- at least four of five annual windows remain profitable;
- losing streak and drawdown remain within their declared limits;
- no single stress condition destroys the strategy;
- no safety-rule violation.

## Locked OOS joint gate

OOS may be opened only after all prior gates pass. Validation requires:

- profit factor at least 1.20;
- positive net profit;
- at least 50 trades;
- no catastrophic drawdown;
- no material safety-rule violation;
- degradation consistent with the provisional allowance.

The 1.30 development requirement and 1.20 OOS requirement encode a provisional 0.10 degradation allowance. It is informed by the approximately 0.09 difference previously observed between EXP7's offline projection and verified MT5 result. This is a practical allowance, not a universal statistical constant.

## Two-strike retirement rule

Failure of the baseline gate is strike one. The architecture may receive only its already-written revision. Failure of the revised frozen gate is strike two and causes immediate retirement.

An architecture may not remain parked, promising, unfinished, or awaiting another filter. Results cannot be reclassified after inspection.

## Project stop rule

If all three permitted architectures are retired, PeakFX strategy research pauses for at least three months. Resumption requires a written methodological post-mortem and a new protocol approved before any additional backtest.

## Evidence requirements

Every run must preserve:

- exact source commit and SHA-256 hashes;
- compile logs showing zero errors and zero warnings;
- exact configuration and date windows;
- raw MT5 reports;
- declared costs and execution assumptions;
- machine-readable manifest;
- pass/fail table for every joint gate;
- confirmation that reserved OOS remains locked until authorized.
