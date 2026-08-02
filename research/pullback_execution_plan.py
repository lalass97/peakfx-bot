from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


Side = Literal["long", "short"]


@dataclass(frozen=True)
class ExecutionPlan:
    side: Side
    entry: float
    stop: float
    target: float
    stop_distance: float

    @property
    def reward_distance(self) -> float:
        return abs(self.target - self.entry)

    @property
    def reward_risk(self) -> float:
        return self.reward_distance / self.stop_distance


def build_execution_plan(
    *,
    side: Side,
    bid: float,
    ask: float,
    atr: float,
    atr_stop_multiplier: float = 1.5,
    reward_risk: float = 1.5,
    digits: int = 5,
) -> ExecutionPlan:
    """Mirror the recovered MT5 entry/SL/TP arithmetic.

    The recovered EA reads ATR from the completed bar, enters longs at ask and
    shorts at bid, sets stop distance to ATR * multiplier, and places the target
    at stop_distance * reward_risk. This function intentionally does not model
    broker stop-level checks, margin, lot sizing, slippage, or order rejection.
    """
    if side not in ("long", "short"):
        raise ValueError("side must be 'long' or 'short'")
    if atr <= 0:
        raise ValueError("atr must be positive")
    if atr_stop_multiplier <= 0:
        raise ValueError("atr_stop_multiplier must be positive")
    if reward_risk < 1.0:
        raise ValueError("reward_risk must be at least 1.0")
    if digits < 0:
        raise ValueError("digits must be non-negative")
    if ask < bid:
        raise ValueError("ask must be greater than or equal to bid")

    stop_distance = atr * atr_stop_multiplier
    entry = ask if side == "long" else bid

    if side == "long":
        stop = entry - stop_distance
        target = entry + stop_distance * reward_risk
    else:
        stop = entry + stop_distance
        target = entry - stop_distance * reward_risk

    return ExecutionPlan(
        side=side,
        entry=entry,
        stop=round(stop, digits),
        target=round(target, digits),
        stop_distance=stop_distance,
    )
