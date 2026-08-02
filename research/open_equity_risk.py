from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Iterable, Literal

Decision = Literal["green", "red", "inconclusive"]


@dataclass(frozen=True)
class EquitySnapshot:
    timestamp: str
    balance: float
    equity: float
    margin_used: float
    gross_exposure: float
    open_positions: int


@dataclass(frozen=True)
class OpenRiskThresholds:
    minimum_snapshots: int = 100
    maximum_floating_drawdown_fraction: float = 0.10
    maximum_margin_utilization_fraction: float = 0.30
    maximum_gross_exposure_multiple: float = 1.0
    maximum_open_positions: int = 1


@dataclass(frozen=True)
class OpenRiskReport:
    decision: Decision
    snapshot_count: int
    maximum_floating_drawdown_fraction: float
    maximum_margin_utilization_fraction: float
    maximum_gross_exposure_multiple: float
    maximum_open_positions: int
    failed_gates: tuple[str, ...]


def qualify_open_risk(
    snapshots: Iterable[EquitySnapshot],
    thresholds: OpenRiskThresholds = OpenRiskThresholds(),
) -> OpenRiskReport:
    """Score mark-to-market exposure without repairing or reordering observations."""
    ordered = tuple(snapshots)
    if thresholds.minimum_snapshots <= 0:
        raise ValueError("minimum_snapshots must be positive")
    for value in (
        thresholds.maximum_floating_drawdown_fraction,
        thresholds.maximum_margin_utilization_fraction,
        thresholds.maximum_gross_exposure_multiple,
    ):
        if not isfinite(value) or value <= 0:
            raise ValueError("risk thresholds must be finite and positive")
    if thresholds.maximum_open_positions <= 0:
        raise ValueError("maximum_open_positions must be positive")

    max_floating_dd = 0.0
    max_margin = 0.0
    max_exposure = 0.0
    max_positions = 0

    for snapshot in ordered:
        numeric = (
            snapshot.balance,
            snapshot.equity,
            snapshot.margin_used,
            snapshot.gross_exposure,
        )
        if not all(isfinite(value) for value in numeric):
            raise ValueError("snapshot values must be finite")
        if snapshot.balance <= 0 or snapshot.equity < 0:
            raise ValueError("balance must be positive and equity non-negative")
        if snapshot.margin_used < 0 or snapshot.gross_exposure < 0:
            raise ValueError("margin and exposure cannot be negative")
        if snapshot.open_positions < 0:
            raise ValueError("open_positions cannot be negative")

        floating_dd = max(0.0, (snapshot.balance - snapshot.equity) / snapshot.balance)
        margin_fraction = snapshot.margin_used / snapshot.equity if snapshot.equity else float("inf")
        exposure_multiple = snapshot.gross_exposure / snapshot.equity if snapshot.equity else float("inf")

        max_floating_dd = max(max_floating_dd, floating_dd)
        max_margin = max(max_margin, margin_fraction)
        max_exposure = max(max_exposure, exposure_multiple)
        max_positions = max(max_positions, snapshot.open_positions)

    failed: list[str] = []
    if len(ordered) < thresholds.minimum_snapshots:
        failed.append("minimum_snapshots")
    if max_floating_dd > thresholds.maximum_floating_drawdown_fraction:
        failed.append("floating_drawdown")
    if max_margin > thresholds.maximum_margin_utilization_fraction:
        failed.append("margin_utilization")
    if max_exposure > thresholds.maximum_gross_exposure_multiple:
        failed.append("gross_exposure")
    if max_positions > thresholds.maximum_open_positions:
        failed.append("open_positions")

    if len(ordered) < thresholds.minimum_snapshots:
        decision: Decision = "inconclusive"
    elif failed:
        decision = "red"
    else:
        decision = "green"

    return OpenRiskReport(
        decision=decision,
        snapshot_count=len(ordered),
        maximum_floating_drawdown_fraction=max_floating_dd,
        maximum_margin_utilization_fraction=max_margin,
        maximum_gross_exposure_multiple=max_exposure,
        maximum_open_positions=max_positions,
        failed_gates=tuple(failed),
    )
