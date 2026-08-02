import pytest

from research.deferred_close_state_machine import (
    CloseState,
    DeferredClose,
    advance_close,
    request_close,
)


def pending() -> DeferredClose:
    return DeferredClose(
        state=CloseState.PENDING,
        reason="friday_cutoff",
        requested_at=1_000,
    )


def test_request_close_is_idempotent_while_pending() -> None:
    first = request_close(DeferredClose(), reason="friday_cutoff", now=1_000)
    second = request_close(first.state, reason="emergency_stop", now=1_100)
    assert first.action == "close_requested"
    assert second.action == "already_pending"
    assert second.state == first.state


def test_waits_when_market_or_trade_context_is_unavailable() -> None:
    result = advance_close(
        pending(),
        now=1_100,
        owned_position_exists=True,
        execution_available=False,
    )
    assert result.action == "waiting_for_execution"
    assert result.state == pending()


def test_requests_attempt_at_first_valid_opportunity() -> None:
    result = advance_close(
        pending(),
        now=1_100,
        owned_position_exists=True,
        execution_available=True,
    )
    assert result.action == "close_attempt_required"
    assert result.state.attempts == 0


def test_failed_close_remains_pending_and_tracks_attempt() -> None:
    result = advance_close(
        pending(),
        now=1_100,
        owned_position_exists=True,
        execution_available=True,
        close_succeeded=False,
    )
    assert result.action == "close_failed_retry_pending"
    assert result.state.state is CloseState.PENDING
    assert result.state.attempts == 1
    assert result.state.last_attempt_at == 1_100


def test_successful_close_clears_pending_state() -> None:
    result = advance_close(
        pending(),
        now=1_100,
        owned_position_exists=True,
        execution_available=True,
        close_succeeded=True,
    )
    assert result.action == "close_confirmed"
    assert result.state == DeferredClose()


def test_external_or_previous_close_clears_pending_state() -> None:
    result = advance_close(
        pending(),
        now=1_100,
        owned_position_exists=False,
        execution_available=False,
    )
    assert result.action == "position_already_closed"
    assert result.state == DeferredClose()


def test_round_trip_persistence_restores_pending_close() -> None:
    original = DeferredClose(
        state=CloseState.PENDING,
        reason="emergency_stop",
        requested_at=1_000,
        attempts=2,
        last_attempt_at=1_120,
    )
    restored = DeferredClose.from_dict(original.to_dict())
    assert restored == original


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"state": "unknown"},
        {"state": "pending", "reason": "", "requested_at": 1},
        {"state": "pending", "reason": "risk", "requested_at": None},
        {"state": "pending", "reason": "risk", "requested_at": 1, "attempts": -1},
        {"state": "none", "reason": "risk", "requested_at": 1},
    ],
)
def test_corrupt_persisted_state_fails_closed(payload: dict) -> None:
    with pytest.raises(ValueError, match="invalid_deferred_close_state"):
        DeferredClose.from_dict(payload)


def test_empty_reason_and_invalid_timestamp_are_rejected() -> None:
    with pytest.raises(ValueError, match="close_reason_required"):
        request_close(DeferredClose(), reason=" ", now=1)
    with pytest.raises(ValueError, match="invalid_timestamp"):
        advance_close(
            pending(),
            now=-1,
            owned_position_exists=True,
            execution_available=True,
        )
