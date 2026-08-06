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

## Development protocol

1. Rebuild the authoritative EXP2 source and verify its established hash.
2. Add exactly one pullback-formation condition; do not alter exits, risk, sessions, cooldown, or trigger confirmation.
3. Produce an exact EXP2-to-EXP8 diff and source hashes.
4. Compile with 0 errors and 0 warnings.
5. Run the same five fixed annual windows on 100% real ticks.
6. Reject EXP8 unless it passes all formal gates:
   - total trades >= 100
   - pooled PF >= 1.25
   - profitable years >= 4/5
   - maximum consecutive losses <= 8
   - worst equity drawdown <= 15%
   - recovery factor >= 1.50
   - positive aggregate net
   - no safety violations
7. Do not access the reserved OOS period unless every in-sample gate passes.

## Anti-overfitting rules

- One frozen threshold per MT5 batch.
- No repeated threshold search until one happens to pass.
- Offline projections are screening evidence only, never validation.
- A failed real-MT5 result closes the frozen candidate.
