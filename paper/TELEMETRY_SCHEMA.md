# PeakFX Paper-Trading Telemetry

The demo EA should write append-only CSV events using the following columns:

```text
time,event,symbol,magic,ticket,message
```

## Required conventions

- `time`: UTC ISO-8601 timestamp, for example `2026-07-30T11:30:00Z`.
- `event`: lowercase event type.
- `symbol`: broker symbol used by the EA. The current qualified version expects exactly `EURUSD`.
- `magic`: EA magic number. The current qualified version expects `26073001`.
- `ticket`: MT5 order, deal, or position ticket where applicable; otherwise `0`.
- `message`: short diagnostic text without credentials or account secrets.

## Recommended event types

- `startup`
- `shutdown`
- `heartbeat`
- `new_bar`
- `signal_long`
- `signal_short`
- `no_signal`
- `spread_block`
- `session_block`
- `cooldown_block`
- `risk_block`
- `daily_lock`
- `weekly_lock`
- `drawdown_lock`
- `volume_block`
- `margin_block`
- `order_submitted`
- `order_rejected`
- `order_filled`
- `position_opened`
- `position_closed`

## Health command

```powershell
python -m paper.health_monitor data/paper/peakfx_events.csv
```

The command writes `reports/paper_health.json` and exits with:

- `0` when healthy
- `2` when warning or critical

## Default alerts

- No event for more than 90 minutes
- More than three rejected orders in 24 hours
- More than 20 risk blocks in 24 hours
- Duplicate entry tickets
- Any symbol other than EURUSD
- Any nonzero magic number other than 26073001

Telemetry files belong under `data/paper/` and must not be committed to GitHub.
