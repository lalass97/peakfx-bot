import pytest

from research.pullback_execution_plan import build_execution_plan


def test_long_uses_ask_and_places_symmetric_atr_stop_and_target() -> None:
    plan = build_execution_plan(
        side="long",
        bid=1.10000,
        ask=1.10020,
        atr=0.00100,
    )
    assert plan.entry == 1.10020
    assert plan.stop == 1.09870
    assert plan.target == 1.10245
    assert plan.reward_risk == pytest.approx(1.5)


def test_short_uses_bid_and_places_symmetric_atr_stop_and_target() -> None:
    plan = build_execution_plan(
        side="short",
        bid=1.10000,
        ask=1.10020,
        atr=0.00100,
    )
    assert plan.entry == 1.10000
    assert plan.stop == 1.10150
    assert plan.target == 1.09775
    assert plan.reward_risk == pytest.approx(1.5)


def test_spread_changes_long_and_short_entry_reference() -> None:
    long_plan = build_execution_plan(
        side="long", bid=1.20000, ask=1.20030, atr=0.00080
    )
    short_plan = build_execution_plan(
        side="short", bid=1.20000, ask=1.20030, atr=0.00080
    )
    assert long_plan.entry - short_plan.entry == pytest.approx(0.00030)


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"side": "long", "bid": 1.0, "ask": 1.0, "atr": 0.0}, "atr"),
        ({"side": "long", "bid": 1.1, "ask": 1.0, "atr": 0.1}, "ask"),
        (
            {
                "side": "short",
                "bid": 1.0,
                "ask": 1.0,
                "atr": 0.1,
                "reward_risk": 0.5,
            },
            "reward_risk",
        ),
    ],
)
def test_invalid_execution_inputs_fail_closed(kwargs: dict, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        build_execution_plan(**kwargs)
