from __future__ import annotations

import pytest

from research.evaluate_confirmed_breakout_exp2 import evaluate


def metrics(stage: str = "screen_12m") -> dict[str, object]:
    return {
        "stage": stage,
        "net_profit": 100.0,
        "profit_factor": 1.20,
        "expected_payoff": 2.0,
        "completed_trades": 40 if stage == "screen_12m" else 10,
        "safety_violations": 0,
    }


def test_passes_12_month_screen_at_declared_gates() -> None:
    payload = metrics()
    payload.update(
        net_profit=0.0,
        profit_factor=1.10,
        expected_payoff=0.01,
        completed_trades=30,
    )
    decision = evaluate(payload)
    assert decision.decision == "pass"
    assert decision.failed_gates == ()


def test_rejects_every_failed_12_month_gate() -> None:
    decision = evaluate(
        {
            "stage": "screen_12m",
            "net_profit": -1.0,
            "profit_factor": 1.09,
            "expected_payoff": 0.0,
            "completed_trades": 29,
            "safety_violations": 1,
        }
    )
    assert decision.decision == "reject"
    assert decision.failed_gates == (
        "negative_net_profit",
        "profit_factor_below_gate",
        "non_positive_expected_payoff",
        "insufficient_completed_trades",
        "safety_control_violation",
    )


def test_oos_uses_separate_profit_factor_gate() -> None:
    payload = metrics("oos_6m")
    payload["profit_factor"] = 1.049
    decision = evaluate(payload)
    assert decision.decision == "reject"
    assert decision.failed_gates == ("profit_factor_below_gate",)


@pytest.mark.parametrize(
    "mutation",
    [
        lambda p: p.update(extra=1),
        lambda p: p.pop("net_profit"),
        lambda p: p.update(stage="ten_year"),
        lambda p: p.update(completed_trades=3.5),
        lambda p: p.update(safety_violations=-1),
        lambda p: p.update(profit_factor=True),
    ],
)
def test_invalid_payloads_fail_closed(mutation) -> None:
    payload = metrics()
    mutation(payload)
    with pytest.raises(ValueError):
        evaluate(payload)
