# EUR/USD H1 Strategy Specification

## Scope

This specification defines Version 1 of the PeakFX EUR/USD H1 system. It is designed for historical testing and demo-forward testing. It is not approved for live capital.

## Signal timing

All indicator values are calculated from completed H1 candles. A signal generated at the close of bar `t` may be entered no earlier than the open/tick stream of bar `t+1`. No current unfinished candle may generate an entry.

## Long intent

A long trade intent exists when all conditions are true on the completed signal candle:

1. EMA 12 was less than or equal to EMA 50 on the previous completed candle.
2. EMA 12 is greater than EMA 50 on the signal candle.
3. Signal-candle close is above EMA 200.
4. EMA 200 is above its value five completed candles earlier.
5. ATR(14) is available and positive.

## Short intent

A short trade intent exists when all conditions are true on the completed signal candle:

1. EMA 12 was greater than or equal to EMA 50 on the previous completed candle.
2. EMA 12 is less than EMA 50 on the signal candle.
3. Signal-candle close is below EMA 200.
4. EMA 200 is below its value five completed candles earlier.
5. ATR(14) is available and positive.

## Initial execution model

- One PeakFX position at a time.
- Entry uses the next available market price after a valid completed-candle signal.
- Stop distance is `ATR(14) × 1.5`.
- Target distance is `stop distance × 1.5`.
- Risk per trade is 0.25% of current equity.
- Position size must respect broker minimum, maximum and step size.
- Orders with invalid stop distances, excessive spread or failed risk calculations are rejected.

## Portfolio safeguards

- Maximum two entries per broker/server day.
- Stop new entries after a 1.5% decline from start-of-day equity.
- No new entries outside 07:00-20:00 broker/server time.
- No weekend entries.
- No new entries after 16:00 broker/server time on Friday.
- Demo-only mode is enabled by default.

## Required before live consideration

1. Compile the EA without warnings or errors in the target MT5 build.
2. Backtest with real EUR/USD H1 bid/ask-aware data when available.
3. Confirm spread, commission, swap and slippage assumptions for the selected broker.
4. Run chronological development, validation and untouched test periods.
5. Perform walk-forward, parameter sensitivity and Monte Carlo analysis.
6. Complete at least 8-12 weeks of demo-forward trading.
7. Implement and verify a major EUR/USD news blackout guard.
8. Verify restart recovery, duplicate-order prevention and broker-day counter persistence.

## Known Version 1 limitations

- Daily counters reset in memory and are not yet reconstructed from account history after terminal restart.
- The Python model assumes conservative stop-first handling if stop and target occur in the same H1 candle.
- The MQL5 EA does not yet include a live economic-calendar integration.
- Weekly loss lock and high-water-mark equity circuit breaker are planned for Version 2.
- Python unit sizing is a normalized research approximation; MT5 uses broker tick value and tick size for executable sizing.
