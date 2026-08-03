# Confirmed-breakout experiment 1

This is the next isolated repair experiment after the long-only candidate failed to improve the completed 2016–2025 result.

## Single strategy change

The baseline enters when the completed trigger candle closes beyond the stored pullback high or low. This candidate requires the close to clear that level by an additional fixed `0.10 ATR`.

- Long: close > pullback high + 0.10 ATR
- Short: close < pullback low - 0.10 ATR

No other strategy setting changes. Both directions remain available. Stops, reward/risk, position sizing, session, cooldown, expiry, daily limits, weekly limits, high-water drawdown control, spread, and deviation stay unchanged.

## Test order

1. Compile in MetaEditor and require `0 errors, 0 warnings`.
2. One-month smoke test to confirm operation and both-direction eligibility.
3. One-year screening test using real ticks.
4. Run the full 2016-01-01 through 2025-07-31 comparison only when the one-year screen improves profit factor and expectancy without unacceptable drawdown.

This candidate is for Strategy Tester and demo research only. It does not authorize optimization or live trading and carries no profitability claim.
