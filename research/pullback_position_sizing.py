from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_FLOOR


@dataclass(frozen=True)
class PositionSizeResult:
    lots: float
    risk_amount: float
    loss_per_lot: float


def _floor_to_step(value: float, step: float) -> float:
    value_d = Decimal(str(value))
    step_d = Decimal(str(step))
    steps = (value_d / step_d).to_integral_value(rounding=ROUND_FLOOR)
    return float(steps * step_d)


def calculate_position_size(
    *,
    equity: float,
    risk_percent: float,
    stop_distance_price: float,
    tick_size: float,
    tick_value_loss: float,
    tick_value_fallback: float,
    min_lot: float,
    max_lot: float,
    lot_step: float,
) -> PositionSizeResult:
    """Mirror the recovered MT5 equity-based lot-sizing rules.

    The EA prefers the loss-side tick value, falls back to the general tick
    value, floors to the broker lot step, caps at broker maximum, and rejects
    sizes below the broker minimum rather than rounding risk upward.
    """
    if equity <= 0:
        raise ValueError("equity must be positive")
    if risk_percent <= 0:
        raise ValueError("risk_percent must be positive")
    if stop_distance_price <= 0:
        raise ValueError("invalid_stop_distance")
    if tick_size <= 0:
        raise ValueError("invalid_tick_data")
    if lot_step <= 0:
        raise ValueError("invalid_volume_step")
    if min_lot <= 0 or max_lot < min_lot:
        raise ValueError("invalid_volume_limits")

    tick_value = tick_value_loss if tick_value_loss > 0 else tick_value_fallback
    if tick_value <= 0:
        raise ValueError("invalid_tick_data")

    risk_amount = equity * (risk_percent / 100.0)
    value_per_price_unit = tick_value / tick_size
    loss_per_lot = stop_distance_price * value_per_price_unit
    if loss_per_lot <= 0:
        raise ValueError("invalid_stop_distance")

    raw_lots = risk_amount / loss_per_lot
    lots = _floor_to_step(raw_lots, lot_step)
    lots = min(lots, max_lot)

    if lots < min_lot:
        raise ValueError("volume_block")

    return PositionSizeResult(
        lots=lots,
        risk_amount=risk_amount,
        loss_per_lot=loss_per_lot,
    )
