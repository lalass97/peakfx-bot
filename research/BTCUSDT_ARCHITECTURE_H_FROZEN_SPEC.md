# BTCUSDT Architecture H — Frozen Specification

Status: FROZEN BEFORE IMPLEMENTATION OR RESULTS

## Hypothesis
ETH can occasionally lead broad crypto risk-on moves. When ETH has a strong completed-H4 multi-bar advance while BTC has materially lagged, BTC may exhibit a short-lived catch-up move. This architecture trades only BTCUSDT; ETHUSDT is an external signal input.

## Data
- Binance public spot monthly 1h klines for BTCUSDT and ETHUSDT.
- Aggregate to completed UTC H4 bars only when all four constituent H1 bars exist.
- Align BTC and ETH strictly by identical H4 open timestamps; unmatched H4 bars are omitted.
- Development: 2021-01-01 through 2025-12-31 UTC.
- Warm-up may use 2020 data.
- 2026 MUST NOT be downloaded or tested during development.

## Capital/risk/costs
- Initial capital: 10,000 USDT.
- Long BTC only, one position maximum, no leverage.
- Risk budget: 0.25% of current equity per trade.
- Notional capped at current equity.
- Commission: 0.10% per order, no modeled slippage.

## Indicators
- BTC EMA200 on completed H4 closes.
- BTC ATR14 Wilder RMA.
- ROC24 = close[t] / close[t-6] - 1 (24 hours on H4).
- Relative lead = ETH ROC24 - BTC ROC24.

## Entry
On completed aligned H4 bar t, while flat, require all:
1. BTC close[t] > BTC EMA200[t].
2. BTC EMA200[t] > BTC EMA200[t-12].
3. ETH ROC24[t] >= frozen ETH momentum threshold.
4. Relative lead[t] >= frozen lead-gap threshold.
5. BTC ROC24[t] > -2.0% and < ETH ROC24[t].

Enter BTC at open of aligned H4 bar t+1. No signal bar execution.

Initial stop = entry - 1.5 * BTC ATR14[t].
Target = entry + target_R * initial stop distance.

## Exit
- Protective stop and target are fixed from entry.
- Gap below stop exits at current H4 open; gap above target exits at current H4 open.
- If both stop and target are touched within the same H4 bar, assume stop first (conservative).
- Time exit after 6 completed H4 bars in position (24 hours), executed at next H4 open if neither stop nor target has exited first.
- Development-end open positions are marked to market, not fabricated closed trades.

## Frozen matrix
- BH01: ETH ROC24 >= +3.0%, lead gap >= +2.0%, target 1.5R.
- BH02: ETH ROC24 >= +4.0%, lead gap >= +2.0%, target 1.5R.
- BH03: ETH ROC24 >= +3.0%, lead gap >= +3.0%, target 2.0R.
- BH04: ETH ROC24 >= +4.0%, lead gap >= +3.0%, target 2.0R.

## Development gate
A configuration advances only if all are true:
- net profit > 0 after costs;
- profit factor >= 1.20;
- at least 60 closed trades;
- maximum mark-to-market drawdown <= 20%;
- recovery factor >= 1.25;
- at least 4 of 5 calendar years 2021-2025 profitable;
- no integrity violation.

If no frozen configuration passes, Architecture H is RETIRED. No tuning/rescue follows the baseline. Robustness and any OOS protocol may be defined only if a frozen configuration first passes development.
