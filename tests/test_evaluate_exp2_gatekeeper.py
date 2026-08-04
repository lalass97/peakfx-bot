from __future__ import annotations

from research.evaluate_exp2_gatekeeper import evaluate_oos, evaluate_stage2


STAGE2_RULES = {
    "min_trades": 100,
    "min_profit_factor": 1.25,
    "min_expectancy_r": 0.15,
    "max_drawdown_pct": 15.0,
    "min_recovery_factor": 1.5,
    "max_consecutive_losses": 8,
    "require_tick_quality_pct": 99.0,
    "must_remain_net_positive": True,
    "require_zero_safety_violations": True,
}
OOS_RULES = {
    "min_profit_factor": 1.15,
    "max_drawdown_degradation_ratio": 1.35,
    "max_profit_factor_decay_ratio": 0.20,
    "absolute_profit_factor_floor": 1.10,
    "must_remain_net_positive": True,
    "require_zero_safety_violations": True,
}


def stage2_metrics() -> dict[str, object]:
    return {
        "net_profit": 1800.0,
        "profit_factor": 1.35,
        "expectancy_r": 0.18,
        "completed_trades": 124,
        "max_drawdown_percent": 9.0,
        "max_drawdown_amount": 900.0,
        "recovery_factor": 2.0,
        "max_consecutive_losses": 6,
        "tick_quality_percent": 99.9,
        "safety_violations": 0,
    }


def test_stage2_unlocks_oos_only_when_every_gate_passes() -> None:
    result = evaluate_stage2(stage2_metrics(), STAGE2_RULES)
    assert result.decision == "UNLOCK_OOS"
    assert result.failed_gates == ()


def test_stage2_rejects_all_failed_reasons() -> None:
    metrics = stage2_metrics()
    metrics.update({
        "net_profit": -1.0,
        "profit_factor": 1.1,
        "expectancy_r": 0.1,
        "completed_trades": 80,
        "max_drawdown_percent": 16.0,
        "recovery_factor": 0.5,
        "max_consecutive_losses": 9,
        "tick_quality_percent": 98.0,
        "safety_violations": 1,
    })
    result = evaluate_stage2(metrics, STAGE2_RULES)
    assert result.decision == "REJECTED_AT_STAGE_2"
    assert "profit_factor_below_gate" in result.failed_gates
    assert "recovery_factor_inconsistent" in result.failed_gates


def test_oos_passes_with_controlled_decay() -> None:
    stage2 = stage2_metrics()
    oos = {
        "net_profit": 500.0,
        "profit_factor": 1.18,
        "max_drawdown_percent": 11.0,
        "safety_violations": 0,
    }
    result = evaluate_oos(stage2, oos, OOS_RULES)
    assert result.decision == "OOS_PASS"


def test_oos_rejects_fragile_candidate() -> None:
    stage2 = stage2_metrics()
    oos = {
        "net_profit": -100.0,
        "profit_factor": 1.05,
        "max_drawdown_percent": 14.0,
        "safety_violations": 1,
    }
    result = evaluate_oos(stage2, oos, OOS_RULES)
    assert result.decision == "REJECTED_AT_STAGE_3"
    assert "oos_net_profit_not_positive" in result.failed_gates
    assert "profit_factor_decay_above_gate" in result.failed_gates
