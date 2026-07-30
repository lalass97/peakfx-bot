# PeakFX Paper-Trading Telemetry

The demo EA writes append-only CSV events using these columns:

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

## Native MT5 location

By default, the EA writes:

```text
PeakFX\peakfx_events.csv
```

inside the MetaTrader **Common Files** directory. In MT5, open it with:

```text
File → Open Shared Data Folder → Files → PeakFX
```

The location is shared across terminals on the same Windows user account. It is intentionally outside the Git repository so account activity is not committed accidentally.

For analysis, copy the file into:

```text
data\paper\peakfx_events.csv
```

The `data/` directory is ignored by Git.

## Event types written by the EA

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

The EA records a heartbeat every five minutes by default. The heartbeat includes equity, daily loss, weekly loss, trade count, and whether a PeakFX position is open.

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

Never add telemetry files to GitHub. They can expose account activity even though the EA does not log credentials or the account number.
