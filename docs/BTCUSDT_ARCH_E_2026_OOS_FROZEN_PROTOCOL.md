# BTCUSDT Architecture E — Frozen 2026 OOS Protocol

Status: FROZEN BEFORE 2026 OOS DATA ACCESS

## Evaluation window
- Primary OOS period: 2026-01-01 00:00 UTC through 2026-07-31 23:59:59 UTC.
- Rationale fixed before data access: 2026-07-31 is the latest fully completed calendar month as of 2026-08-08.
- No August 2026 partial-month data may be used.

## Data and state handling
- BTCUSDT spot, Binance public monthly 1h klines, aggregated to completed UTC H4 bars exactly as in the frozen Architecture E implementation.
- 2021-2025 data may be loaded only as indicator warm-up/history.
- OOS trading state starts FLAT at 2026-01-01; no development-period position is carried into OOS.
- No OOS trade may be entered from a signal generated before 2026-01-01.
- Initial OOS capital: 10,000 USDT.
- Commission: 0.10% per order; baseline slippage 0.
- Long-only, one position maximum, no leverage, 0.25% initial risk per trade, notional capped at current equity.

## Frozen candidates
- Primary: BE03 — ROC lookback 48 H4 bars, trail 4.0 ATR.
- Secondary supporting evidence only: BE01 — ROC lookback 48 H4 bars, trail 3.0 ATR.
- BE01 cannot substitute for or rescue a BE03 failure.

## Frozen rules
Strategy logic, EMA lengths, ROC logic, ATR calculation, signal timing, next-H4-open execution, stop handling, trailing-stop update order, EMA100 exit, position sizing, and costs remain exactly as frozen in Architecture E. No strategy parameter may be altered after OOS data is viewed.

## Primary BE03 OOS gate
BE03 passes only if all are true:
- net profit > 0 after modeled costs;
- profit factor >= 1.20;
- maximum equity drawdown <= 20%;
- recovery factor >= 1.25;
- no execution-integrity violation.

Trade-count and profitable-year development gates are not re-imposed on this partial-year OOS window.

## Interpretation fixed before results
Selection-adjusted confidence entering OOS is MODERATE, not high. Architecture E was discovered after four prior BTC architecture families failed. Family-wide development success across BE01-BE04 mitigates but does not eliminate research-selection bias.

A BE03 pass does not reset Architectures A-D to zero. A pass upgrades Architecture E only to an OOS-confirmed candidate under selection-adjusted evidence; it does not prove a universally persistent edge and does not justify immediate large-scale deployment.

A BE03 failure RETIRES Architecture E under this protocol. No post-2026 optimization, rescue, parameter change, alternate configuration substitution, or second clean OOS attempt is allowed.

## Output requirements
The run must emit source/spec/protocol commit identifiers, data-file SHA-256 hashes for 2026 source files, detailed trades, an equity curve with mark-to-market equity, summary metrics, and an explicit PASS/FAIL decision for BE03. The artifact must state that the OOS window is a partial 2026 calendar year.
