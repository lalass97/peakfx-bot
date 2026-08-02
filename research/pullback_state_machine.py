from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Literal


Side = Literal["long", "short"]


class SetupState(str, Enum):
    NONE = "none"
    LONG_PENDING = "long_pending"
    SHORT_PENDING = "short_pending"


@dataclass(frozen=True)
class CompletedBar:
    time: object
    high: float
    low: float
    close: float
    ema_fast: float
    ema_slow: float
    ema_trend: float


@dataclass(frozen=True)
class PullbackSetup:
    state: SetupState = SetupState.NONE
    pullback_high: float = 0.0
    pullback_low: float = 0.0
    pullback_time: object | None = None
    bar_index: int = 0

    @property
    def side(self) -> Side | None:
        if self.state is SetupState.LONG_PENDING:
            return "long"
        if self.state is SetupState.SHORT_PENDING:
            return "short"
        return None


@dataclass(frozen=True)
class Transition:
    setup: PullbackSetup
    event: str
    side: Side | None = None


PULLBACK_EXPIRY_BARS = 5


def long_trend_stack(bar: CompletedBar) -> bool:
    return bar.ema_fast > bar.ema_slow > bar.ema_trend


def short_trend_stack(bar: CompletedBar) -> bool:
    return bar.ema_fast < bar.ema_slow < bar.ema_trend


def long_pullback(bar: CompletedBar) -> bool:
    """Price trades into the EMA12/EMA50 zone while the bullish stack remains valid."""
    return long_trend_stack(bar) and bar.low <= bar.ema_fast and bar.low >= bar.ema_slow


def short_pullback(bar: CompletedBar) -> bool:
    """Price trades into the EMA12/EMA50 zone while the bearish stack remains valid."""
    return short_trend_stack(bar) and bar.high >= bar.ema_fast and bar.high <= bar.ema_slow


def triggered(setup: PullbackSetup, bar: CompletedBar) -> bool:
    if setup.state is SetupState.LONG_PENDING:
        return bar.high > setup.pullback_high
    if setup.state is SetupState.SHORT_PENDING:
        return bar.low < setup.pullback_low
    return False


def invalidated(setup: PullbackSetup, bar: CompletedBar) -> bool:
    if setup.state is SetupState.LONG_PENDING:
        return not long_trend_stack(bar) or bar.close < bar.ema_slow
    if setup.state is SetupState.SHORT_PENDING:
        return not short_trend_stack(bar) or bar.close > bar.ema_slow
    return False


def _new_setup(side: Side, bar: CompletedBar) -> PullbackSetup:
    return PullbackSetup(
        state=SetupState.LONG_PENDING if side == "long" else SetupState.SHORT_PENDING,
        pullback_high=bar.high,
        pullback_low=bar.low,
        pullback_time=bar.time,
        bar_index=0,
    )


def advance(setup: PullbackSetup, bar: CompletedBar) -> Transition:
    """Advance the frozen Test 4 setup state machine by one completed H1 bar.

    Ordering intentionally mirrors the recovered EA:
    1. create a new setup when none exists;
    2. trigger consumes a pending setup immediately;
    3. invalidation cancels it;
    4. a newer qualifying pullback replaces it;
    5. otherwise increment age and expire at five bars.

    This function models setup lifecycle only. It does not decide whether execution
    gates allow an order and it does not simulate fills, stops, targets, or risk.
    """
    if setup.state is SetupState.NONE:
        if long_pullback(bar):
            return Transition(_new_setup("long", bar), "pullback_new", "long")
        if short_pullback(bar):
            return Transition(_new_setup("short", bar), "pullback_new", "short")
        return Transition(setup, "none")

    side = setup.side
    if triggered(setup, bar):
        return Transition(PullbackSetup(), "trigger_fired", side)

    if invalidated(setup, bar):
        return Transition(PullbackSetup(), "setup_invalidated", side)

    replacement = long_pullback(bar) if side == "long" else short_pullback(bar)
    if replacement:
        return Transition(_new_setup(side, bar), "pullback_replaced", side)

    aged = PullbackSetup(
        state=setup.state,
        pullback_high=setup.pullback_high,
        pullback_low=setup.pullback_low,
        pullback_time=setup.pullback_time,
        bar_index=setup.bar_index + 1,
    )
    if aged.bar_index >= PULLBACK_EXPIRY_BARS:
        return Transition(PullbackSetup(), "setup_expired", side)
    return Transition(aged, "setup_aged", side)
