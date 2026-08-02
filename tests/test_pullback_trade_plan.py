import pytest

from research.pullback_trade_plan import build_trade_plan


def base_kwargs() -> dict:
    return dict(
        side="long",
        bid=1.1000,
        ask=1.1002,
        atr=0.0010,
        equity=10_000.0,
        risk_percent=0.25,
        tick_size=0.00001,
        tick_value_loss=1.0,
        tick_value_fallback=1.0,
        min_lot=0.01,
        max_lot=100.0,
        lot_step=0.01,
        stops_level_points=20,
        point=0.00001,
        required_margin_per_lot=1_000.0,
        free_margin=10_000.0,
    )


def test_builds_complete_accepted_trade_plan() -> None:
    result = build_trade_plan(**base_kwargs())
    assert result.accepted is True
    assert result.reason == "accepted"
    assert result.execution is not None
    assert result.sizing is not None
    assert result.execution.entry == pytest.approx(1.1002)
    assert result.sizing.lots == pytest.approx(0.16)


def test_rejects_before_sizing_when_stops_too_close() -> None:
    kwargs = base_kwargs()
    kwargs["stops_level_points"] = 200
    result = build_trade_plan(**kwargs)
    assert result.accepted is False
    assert result.reason == "stop_too_close"
    assert result.execution is not None
    assert result.sizing is None


def test_rejects_when_risk_size_is_below_broker_minimum() -> None:
    kwargs = base_kwargs()
    kwargs["equity"] = 100.0
    kwargs["atr"] = 0.01
    result = build_trade_plan(**kwargs)
    assert result.accepted is False
    assert result.reason == "volume_block"


def test_rejects_when_margin_is_insufficient() -> None:
    kwargs = base_kwargs()
    kwargs["required_margin_per_lot"] = 100_000.0
    kwargs["free_margin"] = 1_000.0
    result = build_trade_plan(**kwargs)
    assert result.accepted is False
    assert result.reason == "insufficient_margin"
    assert result.sizing is not None


def test_short_trade_uses_bid_entry() -> None:
    kwargs = base_kwargs()
    kwargs["side"] = "short"
    result = build_trade_plan(**kwargs)
    assert result.accepted is True
    assert result.execution is not None
    assert result.execution.entry == pytest.approx(1.1000)
