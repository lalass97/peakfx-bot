import pandas as pd

from paper.health_monitor import HealthConfig, evaluate_health


def event_frame(rows: list[dict]) -> pd.DataFrame:
    frame = pd.DataFrame(rows)
    frame["time"] = pd.to_datetime(frame["time"], utc=True)
    return frame


def test_healthy_recent_telemetry() -> None:
    now = pd.Timestamp("2026-07-30T12:00:00Z")
    events = event_frame(
        [
            {
                "time": "2026-07-30T11:30:00Z",
                "event": "heartbeat",
                "symbol": "EURUSD",
                "magic": 26073001,
                "ticket": 0,
                "message": "ok",
            }
        ]
    )
    result = evaluate_health(events, now=now)
    assert result.status == "healthy"
    assert result.alerts == []


def test_stale_telemetry_is_warning() -> None:
    now = pd.Timestamp("2026-07-30T12:00:00Z")
    events = event_frame(
        [
            {
                "time": "2026-07-30T09:00:00Z",
                "event": "heartbeat",
                "symbol": "EURUSD",
                "magic": 26073001,
                "ticket": 0,
                "message": "old",
            }
        ]
    )
    result = evaluate_health(events, HealthConfig(stale_after_minutes=90), now=now)
    assert result.status == "warning"
    assert any("stale" in alert.lower() for alert in result.alerts)


def test_duplicate_ticket_is_critical() -> None:
    now = pd.Timestamp("2026-07-30T12:00:00Z")
    events = event_frame(
        [
            {
                "time": "2026-07-30T11:00:00Z",
                "event": "entry",
                "symbol": "EURUSD",
                "magic": 26073001,
                "ticket": 123,
                "message": "first",
            },
            {
                "time": "2026-07-30T11:01:00Z",
                "event": "entry",
                "symbol": "EURUSD",
                "magic": 26073001,
                "ticket": 123,
                "message": "duplicate",
            },
        ]
    )
    result = evaluate_health(events, now=now)
    assert result.status == "critical"
    assert result.duplicate_entry_tickets == [123]


def test_unexpected_symbol_is_critical() -> None:
    now = pd.Timestamp("2026-07-30T12:00:00Z")
    events = event_frame(
        [
            {
                "time": "2026-07-30T11:30:00Z",
                "event": "heartbeat",
                "symbol": "GBPUSD",
                "magic": 26073001,
                "ticket": 0,
                "message": "wrong chart",
            }
        ]
    )
    result = evaluate_health(events, now=now)
    assert result.status == "critical"
    assert result.unexpected_symbols == ["GBPUSD"]
