from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any


class CloseState(str, Enum):
    NONE = "none"
    PENDING = "pending"


@dataclass(frozen=True)
class DeferredClose:
    state: CloseState = CloseState.NONE
    reason: str = ""
    requested_at: int | None = None
    attempts: int = 0
    last_attempt_at: int | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["state"] = self.state.value
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "DeferredClose":
        try:
            state = CloseState(payload["state"])
            reason = str(payload.get("reason", ""))
            requested_at = payload.get("requested_at")
            attempts = int(payload.get("attempts", 0))
            last_attempt_at = payload.get("last_attempt_at")
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("invalid_deferred_close_state") from exc

        if requested_at is not None and not isinstance(requested_at, int):
            raise ValueError("invalid_deferred_close_state")
        if last_attempt_at is not None and not isinstance(last_attempt_at, int):
            raise ValueError("invalid_deferred_close_state")
        if attempts < 0:
            raise ValueError("invalid_deferred_close_state")
        if state is CloseState.PENDING and (not reason or requested_at is None):
            raise ValueError("invalid_deferred_close_state")
        if state is CloseState.NONE and (reason or requested_at is not None or attempts or last_attempt_at is not None):
            raise ValueError("invalid_deferred_close_state")

        return cls(state, reason, requested_at, attempts, last_attempt_at)


@dataclass(frozen=True)
class CloseTransition:
    state: DeferredClose
    action: str


def request_close(current: DeferredClose, *, reason: str, now: int) -> CloseTransition:
    """Record a required close without creating duplicate pending requests."""
    if not reason.strip():
        raise ValueError("close_reason_required")
    if now < 0:
        raise ValueError("invalid_timestamp")
    if current.state is CloseState.PENDING:
        return CloseTransition(current, "already_pending")
    return CloseTransition(
        DeferredClose(CloseState.PENDING, reason.strip(), now, 0, None),
        "close_requested",
    )


def advance_close(
    current: DeferredClose,
    *,
    now: int,
    owned_position_exists: bool,
    execution_available: bool,
    close_succeeded: bool | None = None,
) -> CloseTransition:
    """Advance a deferred close using fail-closed, first-valid-opportunity rules.

    The caller must only pass the owned-position result for the configured symbol
    and magic number. This function never sends an order.
    """
    if now < 0:
        raise ValueError("invalid_timestamp")
    if current.state is CloseState.NONE:
        return CloseTransition(current, "no_pending_close")

    if not owned_position_exists:
        return CloseTransition(DeferredClose(), "position_already_closed")

    if not execution_available:
        return CloseTransition(current, "waiting_for_execution")

    if close_succeeded is None:
        return CloseTransition(current, "close_attempt_required")

    attempted = DeferredClose(
        state=CloseState.PENDING,
        reason=current.reason,
        requested_at=current.requested_at,
        attempts=current.attempts + 1,
        last_attempt_at=now,
    )
    if close_succeeded:
        return CloseTransition(DeferredClose(), "close_confirmed")
    return CloseTransition(attempted, "close_failed_retry_pending")
