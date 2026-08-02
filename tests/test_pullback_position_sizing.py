import pytest

from research.pullback_position_sizing import calculate_position_size


def test_sizes_from_equity_risk_and_stop_distance() -> None:
    result = calculate_position_size(
        equity=10_000.0,
        risk_percent=0.25,
        stop_distance_price=0.0015,
        tick_size=0.00001,
        tick_value_loss=1.0,
        tick_value_fallback=1.0,
        min_lot=0.01,
        max_lot=100.0,
        lot_step=0.01,
    )
    assert result.risk_amount == pytest.approx(25.0)
    assert result.loss_per_lot == pytest.approx(150.0)
    assert result.lots == pytest.approx(0.16)


def test_prefers_loss_side_tick_value() -> None:
    result = calculate_position_size(
        equity=10_000.0,
        risk_percent=0.25,
        stop_distance_price=0.0010,
        tick_size=0.00001,
        tick_value_loss=1.2,
        tick_value_fallback=1.0,
        min_lot=0.01,
        max_lot=100.0,
        lot_step=0.01,
    )
    assert result.lots == pytest.approx(0.20)


def test_falls_back_when_loss_tick_value_unavailable() -> None:
    result = calculate_position_size(
        equity=10_000.0,
        risk_percent=0.25,
        stop_distance_price=0.0010,
        tick_size=0.00001,
        tick_value_loss=0.0,
        tick_value_fallback=1.0,
        min_lot=0.01,
        max_lot=100.0,
        lot_step=0.01,
    )
    assert result.lots == pytest.approx(0.25)


def test_floors_instead_of_rounding_up() -> None:
    result = calculate_position_size(
        equity=10_000.0,
        risk_percent=0.25,
        stop_distance_price=0.0014,
        tick_size=0.00001,
        tick_value_loss=1.0,
        tick_value_fallback=1.0,
        min_lot=0.01,
        max_lot=100.0,
        lot_step=0.01,
    )
    assert result.lots == pytest.approx(0.17)
    assert result.lots * result.loss_per_lot <= result.risk_amount


def test_caps_at_broker_maximum() -> None:
    result = calculate_position_size(
        equity=1_000_000.0,
        risk_percent=0.25,
        stop_distance_price=0.0001,
        tick_size=0.00001,
        tick_value_loss=1.0,
        tick_value_fallback=1.0,
        min_lot=0.01,
        max_lot=2.0,
        lot_step=0.01,
    )
    assert result.lots == pytest.approx(2.0)


def test_rejects_below_minimum_instead_of_forcing_minimum() -> None:
    with pytest.raises(ValueError, match="volume_block"):
        calculate_position_size(
            equity=100.0,
            risk_percent=0.25,
            stop_distance_price=0.0100,
            tick_size=0.00001,
            tick_value_loss=1.0,
            tick_value_fallback=1.0,
            min_lot=0.01,
            max_lot=100.0,
            lot_step=0.01,
        )


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("tick_size", 0.0, "invalid_tick_data"),
        ("tick_value_loss", 0.0, "invalid_tick_data"),
        ("lot_step", 0.0, "invalid_volume_step"),
        ("stop_distance_price", 0.0, "invalid_stop_distance"),
    ],
)
def test_rejects_invalid_broker_or_stop_inputs(field: str, value: float, message: str) -> None:
    kwargs = dict(
        equity=10_000.0,
        risk_percent=0.25,
        stop_distance_price=0.0010,
        tick_size=0.00001,
        tick_value_loss=1.0,
        tick_value_fallback=0.0,
        min_lot=0.01,
        max_lot=100.0,
        lot_step=0.01,
    )
    kwargs[field] = value
    with pytest.raises(ValueError, match=message):
        calculate_position_size(**kwargs)
