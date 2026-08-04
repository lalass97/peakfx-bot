from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

_ALLOWED_KEYS = {
    "stage",
    "net_profit",
    "profit_factor",
    "expected_payoff",
    "completed_trades",
    "safety_violations",
}
_STAGE_LIMITS = {
    "screen_12m": {"min_profit_factor": 1.10, "min_trades": 30},
    "oos_6m": {"min_profit_factor": 1.05, "min_trades": 1},
}


@dataclass(frozen=True)
class Decision:
    stage: str
    decision: str
    failed_gates: tuple[str, ...]


def _require_number(payload: dict[str, Any], key: str) -> float:
    value = payload.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{key} must be a number")
    return float(value)


def evaluate(payload: dict[str, Any]) -> Decision:
    unknown = set(payload) - _ALLOWED_KEYS
    missing = _ALLOWED_KEYS - set(payload)
    if unknown:
        raise ValueError(f"unknown field(s): {sorted(unknown)}")
    if missing:
        raise ValueError(f"missing field(s): {sorted(missing)}")

    stage = payload["stage"]
    if stage not in _STAGE_LIMITS:
        raise ValueError(f"unsupported stage: {stage}")

    net_profit = _require_number(payload, "net_profit")
    profit_factor = _require_number(payload, "profit_factor")
    expected_payoff = _require_number(payload, "expected_payoff")
    completed_trades = payload["completed_trades"]
    safety_violations = payload["safety_violations"]

    if isinstance(completed_trades, bool) or not isinstance(completed_trades, int):
        raise ValueError("completed_trades must be an integer")
    if completed_trades < 0:
        raise ValueError("completed_trades cannot be negative")
    if isinstance(safety_violations, bool) or not isinstance(safety_violations, int):
        raise ValueError("safety_violations must be an integer")
    if safety_violations < 0:
        raise ValueError("safety_violations cannot be negative")

    limits = _STAGE_LIMITS[stage]
    failed: list[str] = []
    if net_profit < 0:
        failed.append("negative_net_profit")
    if profit_factor < limits["min_profit_factor"]:
        failed.append("profit_factor_below_gate")
    if expected_payoff <= 0:
        failed.append("non_positive_expected_payoff")
    if completed_trades < limits["min_trades"]:
        failed.append("insufficient_completed_trades")
    if safety_violations:
        failed.append("safety_control_violation")

    return Decision(
        stage=stage,
        decision="pass" if not failed else "reject",
        failed_gates=tuple(failed),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Evaluate PeakFX confirmed-breakout EXP2 stage metrics")
    parser.add_argument("metrics", help="Strict JSON metrics file")
    parser.add_argument("--output", help="Optional decision JSON path")
    args = parser.parse_args(argv)

    payload = json.loads(Path(args.metrics).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("metrics JSON must be an object")
    decision = evaluate(payload)
    rendered = json.dumps(asdict(decision), indent=2, sort_keys=True) + "\n"
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0 if decision.decision == "pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())
