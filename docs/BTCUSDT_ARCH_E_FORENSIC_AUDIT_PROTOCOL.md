# BTC/USDT Architecture E — Forensic Audit Protocol

Purpose: verify the already-frozen Architecture E implementation without changing any trading rule and without opening 2026 OOS.

## Locked inputs
- Frozen spec commit: `1702a3b14f3f9df93715e18fb335d54d9b2eac7c`
- Frozen source commit: `f974d17f9f69d3bd26f869612d4eb7cdaa4b2221`
- Frozen source path: `research/backtest_btcusdt_arch_e.py`
- Frozen spec path: `docs/BTCUSDT_ARCH_E_FROZEN_BASELINE_SPEC.md`
- Development data only: Binance BTCUSDT spot H1, 2021-01-01 through 2025-12-31.
- OOS 2026 remains locked and must not be downloaded or tested.

## Audit candidates
Re-audit BE01 and BE03 exactly as frozen. No parameter changes.

## Required checks
1. Independently replay entries, exits, sizing and commissions from raw Binance H1 data aggregated to completed UTC H4 bars.
2. Verify signal-on-completed-H4 and execution-at-next-H4-open sequencing.
3. Recompute realized net profit, PF, trade count, annual profitability and recovery.
4. Compute mark-to-market equity at every H4 close while a position is open.
5. Compute conservative intrabar adverse equity using the H4 low, bounded by the executable stop/gap logic.
6. Recompute max drawdown on realized balance, close mark-to-market equity and conservative intrabar equity.
7. Identify every zero-duration H4 trade and verify from constituent H1 candles that the stop was actually reachable after entry; report the first H1 trigger timestamp.
8. Generate SHA-256 hashes for every downloaded monthly Binance ZIP and a combined manifest hash.
9. Record Git commit/blob identities and SHA-256 file hashes for the frozen spec and source.
10. Compare independent replay summary against the frozen baseline numbers and report any mismatch.

## Integrity gate before OOS
Architecture E may proceed toward OOS only if:
- independent replay matches frozen trade count and realized PnL within rounding tolerance;
- no look-ahead/off-by-one sequencing violation is found;
- every zero-duration trade is explainable by post-entry H1 price action;
- mark-to-market and conservative intrabar max drawdown remain <= 20%;
- BE01 and/or BE03 still meet the original development gate when the stricter drawdown measure is substituted;
- 2026 remains untouched.

This audit is diagnostic only. It may not modify Architecture E rules or optimize parameters based on results.