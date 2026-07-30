from pathlib import Path


EA_PATH = Path("mt5/PeakFX_EURUSD_H1.mq5")


def read_ea() -> str:
    return EA_PATH.read_text(encoding="utf-8")


def test_demo_and_risk_defaults_remain_conservative() -> None:
    source = read_ea()
    assert "input bool DemoOnly = true;" in source
    assert "input double RiskPercent = 0.25;" in source
    assert "RiskPercent > 0.5" in source
    assert "input double MaxDailyLossPercent = 1.5;" in source
    assert "input double MaxWeeklyLossPercent = 3.0;" in source
    assert "input double MaxHighWaterDrawdownPercent = 5.0;" in source
    assert "input int MaxTradesPerDay = 2;" in source


def test_ea_remains_locked_to_eurusd_h1() -> None:
    source = read_ea()
    assert 'input string InpSymbol = "EURUSD";' in source
    assert "input ENUM_TIMEFRAMES InpTimeframe = PERIOD_H1;" in source
    assert 'InpSymbol != "EURUSD" || InpTimeframe != PERIOD_H1' in source


def test_telemetry_schema_and_lifecycle_events_exist() -> None:
    source = read_ea()
    for column in ("time", "event", "symbol", "magic", "ticket", "message"):
        assert f'"{column}"' in source

    for event in (
        "startup",
        "shutdown",
        "heartbeat",
        "new_bar",
        "signal_long",
        "signal_short",
        "no_signal",
        "spread_block",
        "session_block",
        "cooldown_block",
        "risk_block",
        "daily_lock",
        "weekly_lock",
        "drawdown_lock",
        "volume_block",
        "margin_block",
        "order_submitted",
        "order_rejected",
        "order_filled",
        "position_opened",
        "position_closed",
    ):
        assert f'"{event}"' in source


def test_heartbeat_and_trade_transactions_are_wired() -> None:
    source = read_ea()
    assert "EventSetTimer(HeartbeatSeconds);" in source
    assert "void OnTimer()" in source
    assert "void OnTradeTransaction(" in source
    assert "TRADE_TRANSACTION_DEAL_ADD" in source
