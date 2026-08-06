# PeakFX Architecture B — Restart Charter

Status: RESEARCH RESET
Branch: `research/architecture-b-volatility-regime`
OOS: LOCKED

## What is preserved from earlier work

- MT5 real-tick testing infrastructure
- Annual-window testing and pooled analysis
- Source, binary, parameter-set, and report hashing
- Frozen pre-test specifications
- Strict risk controls: fixed fractional risk, one-position cap, no martingale/grid/averaging
- Hard pass/fail gates and immediate retirement rules
- Separation of development, robustness, and locked OOS

## What is discarded

- Architecture A session-breakout logic
- EXP2-family pullback logic
- Indicator or threshold tuning based on observed results
- Reusing weak configurations because they were close to breakeven
- Any claim of edge before evidence

## New research direction

Architecture B will test a distinct volatility-regime hypothesis rather than another London breakout variation.

### Structural hypothesis

EUR/USD directional movement is more persistent when a multi-day low-volatility regime transitions into expansion while the completed higher-timeframe price structure is already directionally aligned.

The intended behavior is:

1. Volatility clusters and regimes persist.
2. Compression can precede a genuine expansion phase.
3. Large participants often execute directional flows over multiple sessions rather than in one isolated breakout bar.
4. Expansion aligned with the broader completed trend should have better continuation characteristics than unfiltered expansion.

This hypothesis will be translated into objective rules before any result is opened.

## Research constraints

- EUR/USD only for the first architecture test.
- No more than six predeclared baseline configurations.
- One predeclared coherent revision maximum.
- No parameter changes after baseline results are viewed.
- No OOS access until development and robustness gates pass.
- No live or demo deployment based only on development results.

## Required gates

Baseline candidate must satisfy every condition:

- pooled PF at least 1.20 after modeled costs
- positive pooled net profit
- at least 100 trades
- at least four of five profitable annual windows
- maximum consecutive losses no greater than 8
- worst equity drawdown no greater than 15%
- recovery factor at least 1.25
- no safety violation

The frozen revision, if used, must satisfy the stricter project revision gate already documented in `docs/PEAKFX_RESEARCH_RESET_PROTOCOL.md`.

## Immediate next steps

1. Complete the Architecture A final closeout separately; it cannot influence Architecture B rules.
2. Write the Architecture B frozen specification before implementation.
3. Build one EA and one deterministic five-year runner.
4. Run only the predeclared configuration matrix.
5. Advance, revise once, or retire strictly from the gate.
