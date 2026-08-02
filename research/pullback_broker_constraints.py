from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BrokerConstraintResult:
    accepted: bool
    reason: str
    minimum_distance: float


def validate_stop_distances(
    *,
    entry: float,
    stop: float,
    target: float,
    stops_level_points: int,
    point: float,
) -> BrokerConstraintResult:
    """Mirror the recovered MT5 broker stop-distance gate.

    When the broker reports no minimum stop level, the plan is accepted.
    Otherwise both stop-loss and take-profit distances must be at least the
    broker minimum. Invalid broker metadata fails closed.

    A very small tolerance tied to the symbol point prevents binary floating-
    point representation from rejecting a distance that is exactly equal to
    the broker minimum.
    """
    if entry <= 0 or stop <= 0 or target <= 0:
        return BrokerConstraintResult(False, "invalid_price", 0.0)
    if stops_level_points < 0 or point <= 0:
        return BrokerConstraintResult(False, "invalid_stop_metadata", 0.0)

    minimum_distance = stops_level_points * point
    if minimum_distance <= 0:
        return BrokerConstraintResult(True, "accepted", minimum_distance)

    tolerance = max(abs(point) * 1e-9, 1e-15)
    if abs(entry - stop) + tolerance < minimum_distance:
        return BrokerConstraintResult(False, "stop_too_close", minimum_distance)
    if abs(entry - target) + tolerance < minimum_distance:
        return BrokerConstraintResult(False, "target_too_close", minimum_distance)

    return BrokerConstraintResult(True, "accepted", minimum_distance)


def validate_margin(*, required_margin: float, free_margin: float) -> BrokerConstraintResult:
    """Mirror the recovered EA's fail-closed free-margin comparison."""
    if required_margin < 0 or free_margin < 0:
        return BrokerConstraintResult(False, "invalid_margin_data", 0.0)
    if required_margin > free_margin:
        return BrokerConstraintResult(False, "insufficient_margin", 0.0)
    return BrokerConstraintResult(True, "accepted", 0.0)
