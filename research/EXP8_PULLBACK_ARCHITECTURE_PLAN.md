# EXP8 Pullback Architecture

## Status

Active research branch. EXP7 is closed. Reserved OOS remains locked.

## Reason for redesign

EXP2 is the strongest verified candidate but fails the formal robustness gate. EXP7 proved that static post-hoc deletion is not a valid predictor for trigger-level state-machine changes: the projected trade count was 369 while the real MT5 run produced 466 trades.

## Frozen baseline

- Candidate: EXP2
- Five-year net: +$552.44
- Trades: 465
- Pooled PF: 1.083
- Profitable years: 4/5
- Maximum consecutive losses: 12
- Modeling: EURUSD H1, every tick based on real ticks

## EXP8 hypothesis

Stop tuning trigger-clearance bands. Test a genuinely different pullback-formation hypothesis: shallow pullbacks form low-quality setups because price has not retraced enough to create favorable reward-to-risk and is more likely to fail quickly.

The first real-MT5 candidate will require minimum wick-based pullback depth at setup qualification, before the trigger state is created. This is intentionally upstream of the trigger and must be evaluated through a full MT5 rerun rather than static trade deletion.

## Frozen rule

- Long pullback depth: `(EMA12 - candle low) / ATR`
- Short pullback depth: `(candle high - EMA12) / ATR`
- Minimum required depth: `0.50 ATR`
- The threshold is a fixed round structural value selected before any EXP8 result is observed.
- The only trading-rule change is the additional depth qualification inside the existing long and short pullback predicates.

## Explicit replacement semantics — Option A

EXP8 intentionally applies the same 0.50 ATR depth standard to both first-time pullback creation and replacement pullbacks because the existing state machine uses the same long/short pullback predicates at both call sites.

Consequences are part of the single frozen hypothesis:

- A shallow candle cannot create a new setup.
- A shallow candle also cannot replace or refresh an already-active setup.
- Therefore, an active setup may advance toward expiry one bar earlier than under EXP2 when a would-be replacement candle fails the new depth standard.
- Later completed bars are still evaluated normally and may qualify as replacement pullbacks if they meet the unchanged baseline pullback rules plus the frozen 0.50 ATR depth requirement.
- Trigger logic, setup lifetime length, cooldown, risk, exits, and all other state-machine rules remain unchanged.

This replacement/expiry interaction is not described as unchanged. It is an acknowledged second-order consequence of consistently redefining what counts as a valid pullback candle. The implementation must not introduce a separate creation-only path, parameter, wrapper, or special replacement exception.

## Development protocol

1. Rebuild the authoritative EXP2 source and verify its established hash.
2. Add exactly one shared pullback-qualification condition using the frozen wick-depth formula; do not alter exits, risk, sessions, cooldown, trigger confirmation, or the numeric setup lifetime.
3. Confirm by diff that both creation and replacement continue to call the same pullback predicates and no call-site branching was added.
4. Produce an exact EXP2-to-EXP8 diff and source hashes.
5. Compile with 0 errors and 0 warnings.
6. Run the same five fixed annual windows on 100% real ticks.
7. Reject EXP8 unless it passes all formal gates:
   - total trades >= 100
   - pooled PF >= 1.25
   - profitable years >= 4/5
   - maximum consecutive losses <= 8
   - worst equity drawdown <= 15%
   - recovery factor >= 1.50
   - positive aggregate net
   - no safety violations
8. Do not access the reserved OOS period unless every in-sample gate passes.

## Anti-overfitting rules

- One frozen threshold per MT5 batch.
- No repeated threshold search until one happens to pass.
- Offline projections are screening evidence only, never validation.
- A failed real-MT5 result closes the frozen candidate.
