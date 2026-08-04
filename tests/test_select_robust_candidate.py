from __future__ import annotations

import pytest

from research.select_robust_candidate import evaluate_candidate, select_best


def candidate(candidate_id: str, *, screen_pf: float = 1.20, oos_pf: float = 1.10) -> dict[str, object]:
    return {
        "candidate_id": candidate_id,
        "screen_12m": {
            "net_profit": 200.0,
            "profit_factor": screen_pf,
            "expected_payoff": 2.0,
            "completed_trades": 40,
            "max_drawdown_percent": 5.0,
            "safety_violations": 0,
        },
        "oos_6m": {
            "net_profit": 80.0,
            "profit_factor": oos_pf,
            "expected_payoff": 1.0,
            "completed_trades": 15,
            "max_drawdown_percent": 4.0,
            "safety_violations": 0,
        },
    }


def test_selects_candidate_with_best_worst_period_profit_factor() -> None:
    result = select_best([
        candidate("high_train_weak_oos", screen_pf=1.60, oos_pf=1.06),
        candidate("balanced", screen_pf=1.25, oos_pf=1.15),
    ])
    assert result["decision"] == "promote_to_demo"
    assert result["winner"] == "balanced"


def test_rejects_candidate_that_only_looks_profitable_in_sample() -> None:
    payload = candidate("overfit", screen_pf=1.80, oos_pf=1.01)
    result = evaluate_candidate(payload)
    assert not result.qualified
    assert result.failed_gates == ("oos_profit_factor_below_gate",)


def test_rejects_drawdown_and_safety_failures() -> None:
    payload = candidate("unsafe")
    payload["screen_12m"]["max_drawdown_percent"] = 10.01
    payload["oos_6m"]["safety_violations"] = 1
    result = evaluate_candidate(payload)
    assert result.failed_gates == ("drawdown_above_gate", "safety_control_violation")


def test_rejects_all_when_nothing_qualifies() -> None:
    result = select_best([candidate("bad", oos_pf=1.00)])
    assert result["decision"] == "reject_all"
    assert result["winner"] is None


@pytest.mark.parametrize(
    "payload",
    [
        [],
        [{"candidate_id": "missing"}],
    ],
)
def test_invalid_inputs_fail_closed(payload) -> None:
    with pytest.raises(ValueError):
        select_best(payload)
