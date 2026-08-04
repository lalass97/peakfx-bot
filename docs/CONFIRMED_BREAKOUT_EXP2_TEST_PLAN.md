# Confirmed-breakout EXP2 test plan

## Single change
The completed trigger candle must close beyond the stored pullback extreme by `0.20 ATR` instead of `0.10 ATR`.

All other strategy and safety settings remain unchanged.

## Test sequence
1. Compile `PeakFX_EURUSD_H1_PULLBACK_CONFIRMED_BREAKOUT_EXP2.mq5` in MetaEditor and require `0 errors, 0 warnings`.
2. Smoke test EURUSD H1, real ticks, 2025-06-01 through 2025-06-30.
3. If technically sound, run one 12-month screen from 2024-07-01 through 2025-06-30.
4. Reject immediately if the 12-month screen has negative net profit, profit factor below 1.10, non-positive expected payoff, or fewer than 30 completed trades.
5. Only after passing, run one separate six-month out-of-sample check from 2025-07-01 through 2025-12-31.
6. Reject if the out-of-sample check has negative net profit, profit factor below 1.05, non-positive expected payoff, or any safety-control violation.
7. Do not run a 10-year backtest. The maximum required historical test for this candidate is the 12-month screen plus the separate six-month out-of-sample check.

## Decision rule
Promote the candidate to demo-forward testing only when both historical stages pass and the MT5 report shows no duplicate entries, missing stops, risk-limit violations, or unexplained orders.

## Scope limits
No optimization, no live trading, no claim of profitability, and no change to risk, stops, targets, hours, cooldown, expiry, or safety controls.
