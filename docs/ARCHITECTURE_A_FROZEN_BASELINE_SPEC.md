# Architecture A — Frozen Baseline Specification

Status: FROZEN BEFORE IMPLEMENTATION
Branch: `research/architecture-a-session-breakout`
Reserved OOS: LOCKED
Architecture lineage: New architecture; no EXP2 pullback or replacement logic

## 1. Market and clock

- Symbol: EURUSD
- Execution timeframe: M15
- Higher-timeframe regime: H4
- Session definitions: UTC
- The EA converts each bar timestamp to UTC using the tester/server offset available at that timestamp. No fixed broker offset is hard-coded.
- Asian range: 00:00:00 through 06:59:59 UTC.
- London entry window: 07:00:00 through 10:59:59 UTC.
- Forced flat time: 20:00:00 UTC.
- One initiated trade maximum per UTC calendar day.

## 2. Higher-timeframe regime

Use completed H4 bars only.

- Fast EMA: 20 periods, H4 close.
- Slow EMA: 50 periods, H4 close.
- Long regime: EMA20 on the last completed H4 bar is above EMA50, and the completed H4 close is above EMA20.
- Short regime: EMA20 is below EMA50, and the completed H4 close is below EMA20.
- Otherwise, no trade is permitted.

## 3. Asian range

- Range high: highest M15 high from 00:00 through 06:45 UTC inclusive.
- Range low: lowest M15 low over the same completed bars.
- At least 24 valid M15 bars are required.
- Range width must be between 0.40 and 1.50 times ATR(14) measured on the last completed H1 bar at the start of the London window.
- The range is frozen for the day when the first eligible London-window bar is processed.

## 4. Breakout entry

Signals use completed M15 bars only.

Long entry requires:

1. Long H4 regime.
2. Previous completed M15 close is at or below the frozen Asian high.
3. Most recently completed M15 close is above the Asian high plus 0.10 times H1 ATR(14).
4. Current spread is no greater than 2.0 pips.
5. No position is open and no trade has been initiated that UTC day.

Short entry is symmetric below the Asian low.

Entry type: market order immediately after the confirming M15 bar closes.

## 5. Risk and exits

- Risk per trade: 0.50% of current equity.
- ATR reference: H1 ATR(14), last completed H1 bar.
- Stop distance: max of 1.00 ATR and the distance to the opposite side of the Asian range plus 0.10 ATR.
- Profit target: 1.50 times initial risk.
- No break-even move.
- No trailing stop.
- No partial close.
- Time exit: close any open position at or after 20:00 UTC.
- Daily loss control: no additional trade is possible because the baseline permits only one initiated trade per UTC day.
- Maximum open positions: one for this symbol and magic number.

## 6. Execution costs and safety

- Real-tick model is required.
- Native historical spread is used.
- Maximum entry spread: 2.0 pips.
- Slippage/deviation allowance: 10 points on a five-digit EURUSD quote.
- Commission is the broker/tester commission embedded in the selected account data. Any zero-commission environment must be disclosed in the manifest and later stressed separately.
- No martingale, grid, averaging down, recovery sizing, position addition, or simultaneous opposite position.
- Orders without valid stop loss and take profit are prohibited.

## 7. Baseline configuration registry

Only the following six predeclared configurations may be run. They differ on one small grid fixed before results are opened.

| ID | Breakout buffer | Stop ATR floor | Target R |
|---|---:|---:|---:|
| A01 | 0.05 ATR | 1.00 ATR | 1.25R |
| A02 | 0.05 ATR | 1.00 ATR | 1.50R |
| A03 | 0.10 ATR | 1.00 ATR | 1.25R |
| A04 — canonical baseline | 0.10 ATR | 1.00 ATR | 1.50R |
| A05 | 0.15 ATR | 1.00 ATR | 1.25R |
| A06 | 0.15 ATR | 1.00 ATR | 1.50R |

All other parameters remain identical. Selection among configurations must use the complete joint gate, not highest PF alone. If more than one passes, select the configuration with the lowest worst-year drawdown; ties are resolved by higher recovery factor, then more trades.

## 8. Predeclared single revision

Revision A-R1 is written now, before baseline results are opened.

- Coherent change: require the H4 EMA20 slope to agree with the regime direction.
- Long: EMA20 on the last completed H4 bar must exceed EMA20 on the preceding completed H4 bar.
- Short: EMA20 must be lower than on the preceding completed H4 bar.
- No other rule or configuration changes are permitted in A-R1.

Purpose: address false breakouts occurring while the EMA ordering remains technically aligned but the immediate higher-timeframe trend has flattened or reversed.

If no baseline configuration passes the baseline joint gate, A-R1 is the only final revision. If A-R1 fails the frozen joint gate, Architecture A is retired immediately.

## 9. Fixed annual development windows

1. 2020-07-01 through 2021-06-30
2. 2021-07-01 through 2022-06-30
3. 2022-07-01 through 2023-06-30
4. 2023-07-01 through 2024-06-30
5. 2024-07-01 through 2025-06-30

## 10. Joint baseline gate

Every condition must pass:

- pooled PF at least 1.20 after modeled costs;
- positive pooled net profit;
- at least 100 trades;
- at least four of five profitable annual windows;
- maximum consecutive losses no greater than 8;
- worst equity drawdown no greater than 15%;
- recovery factor at least 1.25;
- no safety violation.

OOS remains inaccessible until the frozen candidate later passes the complete robustness gate.