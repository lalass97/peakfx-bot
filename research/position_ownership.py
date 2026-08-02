from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class PositionSnapshot:
    ticket: int
    symbol: str
    magic: int


def is_owned_position(
    position: PositionSnapshot,
    *,
    expected_symbol: str,
    expected_magic: int,
) -> bool:
    """Return True only for positions owned by this exact strategy instance.

    This mirrors the recovered EA's symbol-and-magic ownership rule. A matching
    symbol alone or matching magic number alone is never sufficient.
    """
    if not expected_symbol:
        raise ValueError("expected_symbol must not be empty")
    if position.ticket <= 0:
        return False
    return position.symbol == expected_symbol and position.magic == expected_magic


def owned_positions(
    positions: Iterable[PositionSnapshot],
    *,
    expected_symbol: str,
    expected_magic: int,
) -> tuple[PositionSnapshot, ...]:
    return tuple(
        position
        for position in positions
        if is_owned_position(
            position,
            expected_symbol=expected_symbol,
            expected_magic=expected_magic,
        )
    )


def has_owned_position(
    positions: Iterable[PositionSnapshot],
    *,
    expected_symbol: str,
    expected_magic: int,
) -> bool:
    return any(
        is_owned_position(
            position,
            expected_symbol=expected_symbol,
            expected_magic=expected_magic,
        )
        for position in positions
    )
