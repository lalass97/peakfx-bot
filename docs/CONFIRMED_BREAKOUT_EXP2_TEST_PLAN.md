# Confirmed-breakout EXP2 test plan

## Single change
The completed trigger candle must close beyond the stored pullback extreme by `0.20 ATR` instead of `0.10 ATR`.

All other strategy and safety settings remain unchanged.

## Test sequence
1. Compile `PeakFX_EURUSD_H1_PULLBACK_CONFIRMED_BREAKOUT_EXP2.mq5` in MetaEditor and require `0 errors, 0 warnings`.
2. Smoke test EURUSD H1, real ticks, 2025-06-01 through 2025-06-30.
3. If technically sound, screen 2024-06-01 through 2025-06-30.
4. Reject immediately if the one-year screen has negative net profit, profit factor below 1.10, or non-positive expected payoff.
5. Run 2016-2025 only after passing the screen.

## Scope limits
No optimization, no live trading, no claim of profitability, and no change to risk, stops, targets, hours, cooldown, expiry, or safety controls.
