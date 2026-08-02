from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from research.pullback_broker_constraints import validate_margin, validate_stop_distances
from research.pullback_execution_plan import ExecutionPlan, build_execution_plan
from research.pullback_position_sizing import PositionSizeResult, calculate_position_size


Side = Literal["long", "short"]


@dataclass(frozen=True)
class TradePlanResult:
    accepted: bool
    reason: str
    execution: ExecutionPlan | None = None
    sizing: PositionSizeResult | None = None


def build_trade_plan(
    *,
    side: Side,
    bid: float,
    ask: float,
    atr: float,
    equity: float,
    risk_percent: float,
    tick_size: float,
    tick_value_loss: float,
    tick_value_fallback: float,
    min_lot: float,
    max_lot: float,
    lot_step: float,
    stops_level_points: int,
    point: float,
    required_margin_per_lot: float,
    free_margin: float,
    atr_stop_multiplier: float = 1.5,
    reward_risk: float = 1.5,
    digits: int = 5,
) -> TradePlanResult:
    """Compose the parity components into one fail-closed pre-trade plan.

    This remains a research model. It does not send orders, simulate slippage,
    or claim that a technically valid plan is profitable.
    """
    try:
        execution = build_execution_plan(
            side=side,
            bid=bid,
            ask=ask,
            atr=atr,
            atr_stop_multiplier=atr_stop_multiplier,
            reward_risk=reward_risk,
            digits=digits,
        )
    except ValueError as exc:
        return TradePlanResult(False, str(exc))

    stop_check = validate_stop_distances(
        entry=execution.entry,
        stop=execution.stop,
        target=execution.target,
        stops_level_points=stops_level_points,
        point=point,
    )
    if not stop_check.accepted:
        return TradePlanResult(False, stop_check.reason, execution=execution)

    try:
        sizing = calculate_position_size(
            equity=equity,
            risk_percent=risk_percent,
            stop_distance_price=execution.stop_distance,
            tick_size=tick_size,
            tick_value_loss=tick_value_loss,
            tick_value_fallback=tick_value_fallback,
            min_lot=min_lot,
            max_lot=max_lot,
            lot_step=lot_step,
        )
    except ValueError as exc:
        return TradePlanResult(False, str(exc), execution=execution)

    margin_check = validate_margin(
        required_margin=required_margin_per_lot * sizing.lots,
        free_margin=free_margin,
    )
    if not margin_check.accepted:
        return TradePlanResult(False, margin_check.reason, execution=execution, sizing=sizing)

    return TradePlanResult(True, "accepted", execution=execution, sizing=sizing)
