from research.pullback_state_machine import (
    CompletedBar,
    PullbackSetup,
    SetupState,
    advance,
)


def bar(
    *,
    time: int,
    high: float,
    low: float,
    close: float,
    fast: float,
    slow: float,
    trend: float,
) -> CompletedBar:
    return CompletedBar(
        time=time,
        high=high,
        low=low,
        close=close,
        ema_fast=fast,
        ema_slow=slow,
        ema_trend=trend,
    )


def test_creates_long_pullback_from_none() -> None:
    result = advance(
        PullbackSetup(),
        bar(time=1, high=1.1100, low=1.1050, close=1.1090, fast=1.1080, slow=1.1040, trend=1.1000),
    )
    assert result.event == "pullback_new"
    assert result.side == "long"
    assert result.setup.state is SetupState.LONG_PENDING
    assert result.setup.bar_index == 0


def test_trigger_consumes_setup_before_replacement_or_ageing() -> None:
    setup = PullbackSetup(
        state=SetupState.LONG_PENDING,
        pullback_high=1.1100,
        pullback_low=1.1050,
        pullback_time=1,
        bar_index=2,
    )
    result = advance(
        setup,
        bar(time=2, high=1.1110, low=1.1060, close=1.1090, fast=1.1080, slow=1.1040, trend=1.1000),
    )
    assert result.event == "trigger_fired"
    assert result.setup.state is SetupState.NONE


def test_invalidation_cancels_pending_setup() -> None:
    setup = PullbackSetup(
        state=SetupState.LONG_PENDING,
        pullback_high=1.1150,
        pullback_low=1.1050,
        pullback_time=1,
        bar_index=1,
    )
    result = advance(
        setup,
        bar(time=2, high=1.1090, low=1.0990, close=1.1010, fast=1.1080, slow=1.1040, trend=1.1000),
    )
    assert result.event == "setup_invalidated"
    assert result.setup.state is SetupState.NONE


def test_newer_pullback_replaces_pending_setup_and_resets_age() -> None:
    setup = PullbackSetup(
        state=SetupState.LONG_PENDING,
        pullback_high=1.1150,
        pullback_low=1.1060,
        pullback_time=1,
        bar_index=3,
    )
    result = advance(
        setup,
        bar(time=2, high=1.1140, low=1.1050, close=1.1100, fast=1.1090, slow=1.1040, trend=1.1000),
    )
    assert result.event == "pullback_replaced"
    assert result.setup.pullback_time == 2
    assert result.setup.pullback_high == 1.1140
    assert result.setup.bar_index == 0


def test_setup_expires_on_fifth_aged_bar_when_no_higher_priority_event_occurs() -> None:
    setup = PullbackSetup(
        state=SetupState.SHORT_PENDING,
        pullback_high=1.1150,
        pullback_low=1.1000,
        pullback_time=1,
        bar_index=4,
    )
    result = advance(
        setup,
        bar(time=2, high=1.1060, low=1.1010, close=1.1030, fast=1.1000, slow=1.1040, trend=1.1080),
    )
    assert result.event == "setup_expired"
    assert result.setup.state is SetupState.NONE


def test_trigger_still_has_priority_on_the_bar_that_would_otherwise_expire() -> None:
    setup = PullbackSetup(
        state=SetupState.SHORT_PENDING,
        pullback_high=1.1150,
        pullback_low=1.1050,
        pullback_time=1,
        bar_index=4,
    )
    result = advance(
        setup,
        bar(time=2, high=1.1030, low=1.1010, close=1.1020, fast=1.1000, slow=1.1040, trend=1.1080),
    )
    assert result.event == "trigger_fired"
    assert result.setup.state is SetupState.NONE


def test_short_pullback_creation_is_symmetric() -> None:
    result = advance(
        PullbackSetup(),
        bar(time=1, high=1.1050, low=1.0990, close=1.1000, fast=1.1010, slow=1.1060, trend=1.1100),
    )
    assert result.event == "pullback_new"
    assert result.side == "short"
    assert result.setup.state is SetupState.SHORT_PENDING
