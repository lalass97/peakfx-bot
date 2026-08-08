# BTCUSDT J/K/L Research Reset Protocol

Status: FROZEN BEFORE ARCHITECTURE J IMPLEMENTATION

## Purpose
After BTC Architectures A-I, this research program is capped to exactly three additional BTC architecture families: J, K, and L. No Architecture M is permitted under this protocol without a separate written research reset.

## Data boundary
- Instrument: BTCUSDT spot, Binance public monthly 1h klines aggregated as needed.
- 2026 is excluded from all J/K/L development and staged historical evaluation.
- The program records that Jan-Jul 2026 has already been exposed by Architecture E and is therefore not treated as globally pristine BTC holdout data for J/K/L.

## Staged historical sequence
Every architecture must use one frozen rule set and frozen configuration matrix before any results are generated.

Stage 1 — Development: 2021-01-01 through 2023-12-31 UTC.
A configuration advances only if all are true:
- net profit > 0 after modeled costs;
- profit factor >= 1.20;
- at least 25 closed trades;
- maximum mark-to-market drawdown <= 20%;
- recovery factor >= 1.25;
- at least 2 of 3 calendar years profitable;
- no integrity violation.

Stage 2 — 2024 holdout:
Only Stage-1 advancing configurations are scored. No parameter changes are allowed. A configuration advances only if all are true:
- net profit > 0;
- profit factor >= 1.10;
- maximum mark-to-market drawdown <= 20%;
- recovery factor >= 1.00;
- no integrity violation.

Stage 3 — 2025 confirmation:
Only configurations that passed both prior stages are scored. No parameter changes are allowed. A configuration passes the architecture sequence only if all are true:
- net profit > 0;
- profit factor >= 1.10;
- maximum mark-to-market drawdown <= 20%;
- recovery factor >= 1.00;
- no integrity violation.

## Research multiplicity rules
- J, K, and L must be genuinely different mechanism families, not threshold rescue variants of a failed family.
- Each architecture may freeze at most four configurations.
- No configuration may be added after that architecture's first result is produced.
- A failed stage cannot be rescued by changing parameters, gates, execution assumptions, or costs.
- Passing one architecture does not erase the prior failures A-I or the Architecture E 2026 OOS failure.
- Any future positive 2026 result is interpreted cautiously because 2026 is already globally exposed in this research program.

## Common portfolio assumptions
- Initial capital: 10,000 USDT for each independently scored stage.
- Long-only, one position maximum, no leverage.
- Risk budget: 0.25% current equity per trade where stop-based sizing applies.
- Gross notional capped at current equity.
- Commission: 0.10% per order.
- Slippage: 0 in baseline; this is a modeling limitation, not a live-execution claim.

## Stop condition
If J, K, and L all fail, this protocol ends the current BTC architecture search. The project must not continue to Architecture M by default.
