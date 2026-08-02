# PeakFX EUR/USD H1 Pullback Baseline Specification

## Status

This document records the recovered Test 4 pullback baseline used for historical research. It is a research specification only.

- Demo and Strategy Tester use only
- Not approved for live capital
- No optimization variables are introduced here
- No breakeven, partial-profit, trailing-stop, ADX, RSI, MACD or higher-timeframe filter
- Magic number: `26073004`

The recovered source identifies itself as `PeakFX_EURUSD_H1_PULLBACK.mq5`, version 1.42. Later telemetry versions are observational derivatives and must not be treated as a different strategy unless trade-by-trade parity is disproved.

## Market and timing

- Symbol: EURUSD only
- Timeframe: H1 only
- Decisions use completed candles only
- The just-completed candle is evaluated at the first tick of the next H1 bar
- No unfinished candle may create or trigger a setup

## Fixed indicators

- EMA 12: fast trend average
- EMA 50: slow trend average
- EMA 200: major trend average
- ATR 14: stop-distance input

## Trend stack

A long setup may exist only while the bullish stack is intact:

- EMA 12 above EMA 50
- EMA 50 above EMA 200

A short setup may exist only while the bearish stack is intact:

- EMA 12 below EMA 50
- EMA 50 below EMA 200

The exact candle-touch and invalidation comparisons are defined by the recovered MQL5 source and must be mirrored literally in the parity backtester. This document must not substitute approximate verbal logic where the code is more precise.

## Pullback setup state

The EA maintains exactly one setup state:

- none
- long pending
- short pending

A qualifying pullback stores:

- direction
- pullback candle high
- pullback candle low
- pullback candle time
- elapsed-bar index

Only one pending setup exists at a time.

## Trigger

For a pending long setup, the completed trigger candle must satisfy the recovered long-trigger condition relative to the stored pullback high.

For a pending short setup, the completed trigger candle must satisfy the recovered short-trigger condition relative to the stored pullback low.

When a trigger fires, the EA evaluates the execution gates immediately. The setup is consumed whether the order is accepted or blocked. A blocked trigger must not create a delayed entry later.

## Evaluation order for a pending setup

On every completed H1 bar, the order is fixed:

1. Trigger check
2. Invalidation check
3. Same-direction pullback replacement check
4. Expiry-counter advance

Changing this order changes the strategy and requires a new named test.

## Replacement

A newer qualifying pullback in the same direction replaces the stored pullback high, low and time, and resets the age counter to zero.

## Expiry

- Fixed expiry: five bars
- The pullback candle is bar zero
- A setup is removed when its elapsed-bar index reaches the fixed five-bar limit
- A setup restored after a terminal restart is reconciled against elapsed H1 time and discarded when already expired

## Entry and execution gates

A valid trigger is still blocked when any applicable safety or execution condition fails, including:

- non-demo account while `DemoOnly=true`
- wrong symbol or timeframe
- an existing PeakFX position
- daily trade limit
- cooldown
- outside the configured session
- Friday cutoff
- spread limit
- daily, weekly or high-water drawdown lock
- invalid indicator or price data
- invalid stop distance
- failed lot sizing
- insufficient margin
- broker order rejection

A blocked trigger consumes the setup.

## Initial protection and target

- Stop distance: ATR(14) × 1.5
- Profit target: 1.5R
- Initial risk: 0.25% of equity
- Maximum permitted risk input: 0.50%
- Position volume must respect broker volume minimum, maximum and step
- Stop placement must respect broker stop-level constraints

No post-entry trade-management rule belongs to the frozen baseline.

## Portfolio safeguards

- Maximum one PeakFX position at a time
- Maximum two entries per broker/server day
- Daily loss lock: 1.5%
- Weekly loss lock: 3.0%
- High-water drawdown circuit breaker: 5.0%
- Trading window: 07:00–20:00 broker/server time
- Friday cutoff: 16:00 broker/server time
- Cooldown: two H1 bars after a PeakFX position closes
- Demo-only enabled by default

## Persistence

The recovered source persists setup and risk-control state outside Strategy Tester runs. Strategy Tester runs intentionally start with clean state. On normal terminal restart, restored pending setups are reconciled against elapsed bars before use.

## Rejected research changes

The following must not be silently folded into this baseline:

- ADX filter
- ADX plus EMA-separation filter
- confirmation-candle rule
- trigger-age-two exclusion
- fixed EMA50-distance exclusion
- partial profit at 0.75R or 1.00R
- breakeven at 0.50R, 0.75R or 1.00R

These ideas either worsened results, were unstable, removed excessive trades or destroyed too many original winners.

## Source-of-truth and parity rule

The exact recovered MQL5 file is the behavioral authority until a matching Python event-driven model achieves trade-level reconciliation.

Required reconciliation fields:

- direction
- pullback time
- stored pullback high and low
- trigger time
- setup age
- entry time and actual fill
- initial stop and target
- volume and initial cash risk
- exit time, price and reason
- realized P/L and R multiple

Aggregate net profit similarity is not sufficient. Unexplained trade-count or trade-sequence divergence fails parity.

## Promotion gates

No candidate may advance toward demo-forward qualification unless it demonstrates:

- positive expectancy after realistic costs
- materially stronger profit factor than the current near-break-even baseline
- improvement across most calendar years rather than one or two isolated periods
- acceptable performance at increased spread and slippage
- no dependence on a few exceptional trades
- stable walk-forward behavior
- verified MT5/Python parity

A backtest alone is never approval for live trading.