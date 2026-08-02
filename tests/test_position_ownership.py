import pytest

from research.position_ownership import (
    PositionSnapshot,
    has_owned_position,
    is_owned_position,
    owned_positions,
)


SYMBOL = "EURUSD"
MAGIC = 26073004


def test_requires_both_symbol_and_magic_to_match() -> None:
    assert is_owned_position(
        PositionSnapshot(ticket=1, symbol=SYMBOL, magic=MAGIC),
        expected_symbol=SYMBOL,
        expected_magic=MAGIC,
    )


def test_matching_symbol_with_foreign_magic_is_ignored() -> None:
    assert not is_owned_position(
        PositionSnapshot(ticket=2, symbol=SYMBOL, magic=999),
        expected_symbol=SYMBOL,
        expected_magic=MAGIC,
    )


def test_matching_magic_on_foreign_symbol_is_ignored() -> None:
    assert not is_owned_position(
        PositionSnapshot(ticket=3, symbol="GBPUSD", magic=MAGIC),
        expected_symbol=SYMBOL,
        expected_magic=MAGIC,
    )


def test_manual_trade_is_ignored() -> None:
    assert not is_owned_position(
        PositionSnapshot(ticket=4, symbol=SYMBOL, magic=0),
        expected_symbol=SYMBOL,
        expected_magic=MAGIC,
    )


def test_invalid_ticket_is_never_owned() -> None:
    assert not is_owned_position(
        PositionSnapshot(ticket=0, symbol=SYMBOL, magic=MAGIC),
        expected_symbol=SYMBOL,
        expected_magic=MAGIC,
    )


def test_filters_only_exact_strategy_positions() -> None:
    positions = [
        PositionSnapshot(ticket=10, symbol=SYMBOL, magic=MAGIC),
        PositionSnapshot(ticket=11, symbol=SYMBOL, magic=0),
        PositionSnapshot(ticket=12, symbol="USDJPY", magic=MAGIC),
        PositionSnapshot(ticket=13, symbol=SYMBOL, magic=MAGIC),
    ]
    result = owned_positions(
        positions,
        expected_symbol=SYMBOL,
        expected_magic=MAGIC,
    )
    assert [position.ticket for position in result] == [10, 13]


def test_foreign_positions_do_not_block_new_peakfx_trade() -> None:
    foreign_positions = [
        PositionSnapshot(ticket=20, symbol=SYMBOL, magic=0),
        PositionSnapshot(ticket=21, symbol="GBPUSD", magic=MAGIC),
    ]
    assert not has_owned_position(
        foreign_positions,
        expected_symbol=SYMBOL,
        expected_magic=MAGIC,
    )


def test_owned_position_blocks_duplicate_strategy_trade() -> None:
    positions = [
        PositionSnapshot(ticket=30, symbol=SYMBOL, magic=0),
        PositionSnapshot(ticket=31, symbol=SYMBOL, magic=MAGIC),
    ]
    assert has_owned_position(
        positions,
        expected_symbol=SYMBOL,
        expected_magic=MAGIC,
    )


def test_empty_expected_symbol_fails_closed() -> None:
    with pytest.raises(ValueError, match="expected_symbol"):
        is_owned_position(
            PositionSnapshot(ticket=1, symbol=SYMBOL, magic=MAGIC),
            expected_symbol="",
            expected_magic=MAGIC,
        )
