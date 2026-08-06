# Architecture A — Regime-Aligned Session Breakout

Status: Protocol design frozen; implementation not yet qualified
Architecture family: New; not derived from EXP2
Symbol/timeframe: EUR/USD with H1 execution context
OOS: Locked

## Hypothesis

EUR/USD may exhibit directional expansion around the London session after an overnight consolidation. A breakout is eligible only when the direction agrees with a higher-timeframe regime. The proposed edge is liquidity expansion plus directional regime alignment, not pullback replacement or continuous trend-following entry search.

## Baseline concept

- Determine higher-timeframe regime from completed H4 or daily bars only.
- Measure a fixed Asian-session range using completed data.
- Permit a London-session breakout only in the regime direction.
- Maximum one initiated position per trading day.
- Use volatility-normalized risk and stop distance.
- Close any remaining position before the end of the New York session.
- No replacement pullback logic.
- No averaging down, martingale, grid, or recovery sizing.
- No access to reserved OOS.

## Items that must be frozen before coding

1. Broker/server timezone conversion and daylight-saving handling.
2. Exact Asian range start and end.
3. Exact London entry window.
4. Higher-timeframe regime definition.
5. Breakout confirmation rule.
6. ATR period and completed-bar reference.
7. Stop, target, break-even, and time-exit behavior.
8. Spread and execution-cost assumptions.
9. Position-risk percentage and daily loss control.
10. The one permitted revision and the condition it addresses.
11. Ten or fewer configurations to be evaluated.

No parameter may be selected after seeing its own test result unless it was part of the predeclared configuration set.

## Baseline gate

The baseline advances only if every active requirement in `PEAKFX_RESEARCH_RESET_PROTOCOL.md` passes, including PF, aggregate net, trade count, profitable-year breadth, losing streak, drawdown, recovery factor, and safety rules.

## Predeclared revision budget

Exactly one revision is permitted. It must be written before the baseline reports are opened and must change one coherent architectural element. It may not combine several rescue filters.

If the baseline fails, the predeclared revision is the final strike opportunity. If that revision fails the frozen joint gate, Architecture A is retired immediately.

## Prohibited actions

- Reusing EXP2 pullback or replacement logic.
- Searching extra session times after results are known.
- Adding a filter because one annual window performed badly.
- Opening OOS to choose between configurations.
- Reclassifying a failed candidate as parked or promising.
- Running more than the declared baseline and one revision.

## Required outputs

- Frozen design document and configuration registry.
- Source and binary hashes.
- Zero-error, zero-warning compile log.
- Five fixed annual real-tick reports.
- Cost and execution stress reports.
- Machine-readable manifest.
- Joint-gate decision table.
- Explicit Advance or Retire decision.
