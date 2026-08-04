from __future__ import annotations

import argparse
import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

_STAGE2_KEYS = {
    "net_profit",
    "profit_factor",
    "expectancy_r",
    "completed_trades",
    "max_drawdown_percent",
    "max_drawdown_amount",
    "recovery_factor",
    "max_consecutive_losses",
    "tick_quality_percent",
    "safety_violations",
}
_OOS_KEYS = {
    "net_profit",
    "profit_factor",
    "max_drawdown_percent",
    "safety_violations",
}


@dataclass(frozen=True)
class GateDecision:
    decision: str
    failed_gates: tuple[str, ...]
    diagnostics: dict[str, float]


def _number(payload: dict[str, Any], key: str) -> float:
    value = payload.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{key} must be a finite number")
    value = float(value)
    if not math.isfinite(value):
        raise ValueError(f"{key} must be a finite number")
    return value


def _integer(payload: dict[str, Any], key: str) -> int:
    value = payload.get(key)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{key} must be a non-negative integer")
    return value


def _strict_keys(payload: dict[str, Any], expected: set[str], label: str) -> None:
    unknown = set(payload) - expected
    missing = expected - set(payload)
    if unknown:
        raise ValueError(f"unknown {label} field(s): {sorted(unknown)}")
    if missing:
        raise ValueError(f"missing {label} field(s): {sorted(missing)}")


def evaluate_stage2(metrics: dict[str, Any], rules: dict[str, Any]) -> GateDecision:
    _strict_keys(metrics, _STAGE2_KEYS, "stage2")
    net = _number(metrics, "net_profit")
    pf = _number(metrics, "profit_factor")
    expectancy_r = _number(metrics, "expectancy_r")
    trades = _integer(metrics, "completed_trades")
    dd_pct = _number(metrics, "max_drawdown_percent")
    dd_amount = _number(metrics, "max_drawdown_amount")
    recovery = _number(metrics, "recovery_factor")
    max_losses = _integer(metrics, "max_consecutive_losses")
    tick_quality = _number(metrics, "tick_quality_percent")
    violations = _integer(metrics, "safety_violations")

    if dd_amount < 0 or dd_pct < 0:
        raise ValueError("drawdown values cannot be negative")

    failed: list[str] = []
    if bool(rules["must_remain_net_positive"]) and net <= 0:
        failed.append("net_profit_not_positive")
    if trades < int(rules["min_trades"]):
        failed.append("insufficient_completed_trades")
    if pf < float(rules["min_profit_factor"]):
        failed.append("profit_factor_below_gate")
    if expectancy_r < float(rules["min_expectancy_r"]):
        failed.append("expectancy_r_below_gate")
    if dd_pct > float(rules["max_drawdown_pct"]):
        failed.append("drawdown_above_gate")
    if recovery < float(rules["min_recovery_factor"]):
        failed.append("recovery_factor_below_gate")
    if max_losses > int(rules["max_consecutive_losses"]):
        failed.append("consecutive_losses_above_gate")
    if tick_quality < float(rules["require_tick_quality_pct"]):
        failed.append("tick_quality_below_gate")
    if bool(rules["require_zero_safety_violations"]) and violations != 0:
        failed.append("safety_control_violation")

    calculated_recovery = net / dd_amount if dd_amount > 0 else math.inf
    if dd_amount > 0 and not math.isclose(recovery, calculated_recovery, rel_tol=0.02, abs_tol=0.02):
        failed.append("recovery_factor_inconsistent")

    return GateDecision(
        decision="UNLOCK_OOS" if not failed else "REJECTED_AT_STAGE_2",
        failed_gates=tuple(failed),
        diagnostics={"calculated_recovery_factor": calculated_recovery},
    )


def evaluate_oos(stage2: dict[str, Any], oos: dict[str, Any], rules: dict[str, Any]) -> GateDecision:
    _strict_keys(oos, _OOS_KEYS, "oos")
    stage2_pf = _number(stage2, "profit_factor")
    stage2_dd = _number(stage2, "max_drawdown_percent")
    oos_net = _number(oos, "net_profit")
    oos_pf = _number(oos, "profit_factor")
    oos_dd = _number(oos, "max_drawdown_percent")
    violations = _integer(oos, "safety_violations")

    failed: list[str] = []
    if bool(rules["must_remain_net_positive"]) and oos_net <= 0:
        failed.append("oos_net_profit_not_positive")
    if oos_pf < float(rules["min_profit_factor"]):
        failed.append("oos_profit_factor_below_gate")
    if oos_pf < float(rules["absolute_profit_factor_floor"]):
        failed.append("oos_profit_factor_below_absolute_floor")
    if bool(rules["require_zero_safety_violations"]) and violations != 0:
        failed.append("safety_control_violation")

    dd_ratio = oos_dd / stage2_dd if stage2_dd > 0 else (1.0 if oos_dd == 0 else math.inf)
    if dd_ratio > float(rules["max_drawdown_degradation_ratio"]):
        failed.append("drawdown_degradation_above_gate")

    pf_decay = max(0.0, (stage2_pf - oos_pf) / stage2_pf) if stage2_pf > 0 else math.inf
    if pf_decay > float(rules["max_profit_factor_decay_ratio"]):
        failed.append("profit_factor_decay_above_gate")

    return GateDecision(
        decision="OOS_PASS" if not failed else "REJECTED_AT_STAGE_3",
        failed_gates=tuple(failed),
        diagnostics={
            "drawdown_degradation_ratio": dd_ratio,
            "profit_factor_decay_ratio": pf_decay,
        },
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Evaluate EXP2 Stage 2 or OOS gatekeeper metrics")
    parser.add_argument("rules")
    parser.add_argument("stage2")
    parser.add_argument("--oos")
    parser.add_argument("--output")
    args = parser.parse_args(argv)

    rules = json.loads(Path(args.rules).read_text(encoding="utf-8"))
    stage2 = json.loads(Path(args.stage2).read_text(encoding="utf-8"))
    if args.oos:
        oos = json.loads(Path(args.oos).read_text(encoding="utf-8"))
        decision = evaluate_oos(stage2, oos, rules["stage3_oos_qualification_rules"])
    else:
        decision = evaluate_stage2(stage2, rules["stage2_screening_rules"])

    rendered = json.dumps(asdict(decision), indent=2, sort_keys=True) + "\n"
    if args.output:
        Path(args.output).write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0 if decision.decision in {"UNLOCK_OOS", "OOS_PASS"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
