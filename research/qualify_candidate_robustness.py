from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from statistics import median
from typing import Any

_REQUIRED_SCENARIOS = ("normal", "double_cost", "delayed_entry", "missed_best_trade")
_ALLOWED_TOP_LEVEL = {"candidate", "scenarios"}
_ALLOWED_METRICS = {
    "net_profit",
    "profit_factor",
    "expected_payoff",
    "max_drawdown_percent",
    "completed_trades",
    "safety_violations",
}


@dataclass(frozen=True)
class RobustnessDecision:
    candidate: str
    decision: str
    failed_gates: tuple[str, ...]
    worst_profit_factor: float
    median_profit_factor: float
    worst_drawdown_percent: float


def _number(metrics: dict[str, Any], key: str) -> float:
    value = metrics.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{key} must be numeric")
    return float(value)


def _validate_metrics(name: str, metrics: Any) -> dict[str, Any]:
    if not isinstance(metrics, dict):
        raise ValueError(f"scenario {name} must be an object")
    missing = _ALLOWED_METRICS - set(metrics)
    unknown = set(metrics) - _ALLOWED_METRICS
    if missing:
        raise ValueError(f"scenario {name} missing fields: {sorted(missing)}")
    if unknown:
        raise ValueError(f"scenario {name} unknown fields: {sorted(unknown)}")
    return metrics


def qualify(payload: dict[str, Any]) -> RobustnessDecision:
    if not isinstance(payload, dict):
        raise ValueError("payload must be an object")
    missing = _ALLOWED_TOP_LEVEL - set(payload)
    unknown = set(payload) - _ALLOWED_TOP_LEVEL
    if missing:
        raise ValueError(f"missing top-level fields: {sorted(missing)}")
    if unknown:
        raise ValueError(f"unknown top-level fields: {sorted(unknown)}")

    candidate = payload["candidate"]
    if not isinstance(candidate, str) or not candidate.strip():
        raise ValueError("candidate must be a non-empty string")

    scenarios = payload["scenarios"]
    if not isinstance(scenarios, dict):
        raise ValueError("scenarios must be an object")
    if tuple(sorted(scenarios)) != tuple(sorted(_REQUIRED_SCENARIOS)):
        raise ValueError(f"scenarios must be exactly: {list(_REQUIRED_SCENARIOS)}")

    failed: list[str] = []
    profit_factors: list[float] = []
    drawdowns: list[float] = []

    for name in _REQUIRED_SCENARIOS:
        metrics = _validate_metrics(name, scenarios[name])
        net_profit = _number(metrics, "net_profit")
        profit_factor = _number(metrics, "profit_factor")
        expected_payoff = _number(metrics, "expected_payoff")
        drawdown = _number(metrics, "max_drawdown_percent")
        trades = metrics["completed_trades"]
        violations = metrics["safety_violations"]

        if isinstance(trades, bool) or not isinstance(trades, int) or trades < 0:
            raise ValueError(f"scenario {name} completed_trades must be a non-negative integer")
        if isinstance(violations, bool) or not isinstance(violations, int) or violations < 0:
            raise ValueError(f"scenario {name} safety_violations must be a non-negative integer")

        profit_factors.append(profit_factor)
        drawdowns.append(drawdown)

        if net_profit <= 0:
            failed.append(f"{name}:non_positive_net_profit")
        if profit_factor < 1.05:
            failed.append(f"{name}:profit_factor_below_1_05")
        if expected_payoff <= 0:
            failed.append(f"{name}:non_positive_expected_payoff")
        if drawdown > 10.0:
            failed.append(f"{name}:drawdown_above_10")
        if trades < 20:
            failed.append(f"{name}:fewer_than_20_trades")
        if violations:
            failed.append(f"{name}:safety_violation")

    worst_pf = min(profit_factors)
    median_pf = float(median(profit_factors))
    worst_dd = max(drawdowns)

    if median_pf < 1.10:
        failed.append("median_profit_factor_below_1_10")
    if worst_pf < 1.05:
        failed.append("worst_profit_factor_below_1_05")

    return RobustnessDecision(
        candidate=candidate.strip(),
        decision="pass" if not failed else "reject",
        failed_gates=tuple(failed),
        worst_profit_factor=worst_pf,
        median_profit_factor=median_pf,
        worst_drawdown_percent=worst_dd,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Qualify PeakFX candidate under execution and cost stress")
    parser.add_argument("input", help="Strict robustness JSON")
    parser.add_argument("--output", help="Optional result path")
    args = parser.parse_args(argv)

    payload = json.loads(Path(args.input).read_text(encoding="utf-8"))
    result = qualify(payload)
    rendered = json.dumps(asdict(result), indent=2, sort_keys=True) + "\n"
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0 if result.decision == "pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())
