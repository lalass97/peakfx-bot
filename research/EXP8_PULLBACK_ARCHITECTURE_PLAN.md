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

The first real-MT5 candidate will require minimum pullback depth at setup formation, before the trigger state is created. This is intentionally upstream of the trigger and must be evaluated through a full MT5 rerun rather than static trade deletion.

## Frozen EXP8 rule

The threshold is fixed before any EXP8 result is observed.

- Threshold: `0.50 ATR`
- Long pullback depth: `(EMA12 - candle_low) / ATR`
- Short pullback depth: `(candle_high - EMA12) / ATR`
- Long setup may be created only when long pullback depth is `>= 0.50`.
- Short setup may be created only when short pullback depth is `>= 0.50`.
- ATR, EMA12, candle high, and candle low must be taken from the same completed bar already evaluated by the existing EXP2 pullback condition.
- No band-width normalization, no EMA50-distance rule, and no second threshold are permitted in this frozen candidate.

The value `0.50 ATR` is a round structural threshold selected before the run. It is not the result of searching EXP8 outcomes.

## State-machine isolation requirement

The only behavioral change is candidate qualification at pullback setup creation.

- A bar that satisfies the original EXP2 pullback condition but fails the new depth minimum must not create or replace a setup.
- The setup state, expiry logic, trigger logic, cooldown, risk, exits, and trade management remain identical to EXP2.
- Later completed bars remain eligible for independent evaluation under the original Step 3 loop. Therefore, rejecting one shallow bar does not disable future pullback hunting and does not create a new cooldown or suppression state.
- The EXP2-to-EXP8 diff must show the depth predicate added only to `LongPullbackCondition` and `ShortPullbackCondition`, or to one pure helper called only by those two conditions.
- Any modification to setup replacement, setup expiry, trigger confirmation, or reset behavior invalidates the experiment as non-isolated.

## Development protocol

1. Rebuild the authoritative EXP2 source and verify its established hash.
2. Add exactly the frozen `0.50 ATR` pullback-depth condition; do not alter exits, risk, sessions, cooldown, setup expiry, replacement behavior, or trigger confirmation.
3. Produce an exact EXP2-to-EXP8 diff and source hashes.
4. Perform a state-machine isolation review before compiling.
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
