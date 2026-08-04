from __future__ import annotations

import pytest

from research.qualify_candidate_robustness import qualify


def scenario() -> dict[str, object]:
    return {
        "net_profit": 120.0,
        "profit_factor": 1.20,
        "expected_payoff": 1.5,
        "max_drawdown_percent": 6.0,
        "completed_trades": 40,
        "safety_violations": 0,
    }


def payload() -> dict[str, object]:
    return {
        "candidate": "exp2",
        "scenarios": {
            "normal": scenario(),
            "double_cost": scenario(),
            "delayed_entry": scenario(),
            "missed_best_trade": scenario(),
        },
    }


def test_passes_only_when_all_stress_scenarios_hold() -> None:
    result = qualify(payload())
    assert result.decision == "pass"
    assert result.failed_gates == ()
    assert result.worst_profit_factor == pytest.approx(1.20)


def test_rejects_cost_fragility() -> None:
    data = payload()
    data["scenarios"]["double_cost"]["profit_factor"] = 1.01
    result = qualify(data)
    assert result.decision == "reject"
    assert "double_cost:profit_factor_below_1_05" in result.failed_gates
    assert "worst_profit_factor_below_1_05" in result.failed_gates


def test_rejects_best_trade_dependency() -> None:
    data = payload()
    stressed = data["scenarios"]["missed_best_trade"]
    stressed["net_profit"] = -5.0
    stressed["expected_payoff"] = -0.1
    result = qualify(data)
    assert "missed_best_trade:non_positive_net_profit" in result.failed_gates
    assert "missed_best_trade:non_positive_expected_payoff" in result.failed_gates


def test_rejects_drawdown_and_safety_failure() -> None:
    data = payload()
    stressed = data["scenarios"]["delayed_entry"]
    stressed["max_drawdown_percent"] = 10.01
    stressed["safety_violations"] = 1
    result = qualify(data)
    assert "delayed_entry:drawdown_above_10" in result.failed_gates
    assert "delayed_entry:safety_violation" in result.failed_gates


def test_rejects_weak_median_even_when_each_pf_clears_floor() -> None:
    data = payload()
    for name in data["scenarios"]:
        data["scenarios"][name]["profit_factor"] = 1.06
    result = qualify(data)
    assert result.decision == "reject"
    assert result.failed_gates == ("median_profit_factor_below_1_10",)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda d: d.update(extra=True),
        lambda d: d["scenarios"].pop("double_cost"),
        lambda d: d["scenarios"]["normal"].update(extra=1),
        lambda d: d["scenarios"]["normal"].update(completed_trades=2.5),
        lambda d: d.update(candidate=""),
    ],
)
def test_invalid_payloads_fail_closed(mutate) -> None:
    data = payload()
    mutate(data)
    with pytest.raises(ValueError):
        qualify(data)
