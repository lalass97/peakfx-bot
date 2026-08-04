from __future__ import annotations

import argparse
import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

SCREEN_PF_GATE = 1.10
OOS_PF_GATE = 1.05
SCREEN_MIN_TRADES = 30
MAX_DRAWDOWN_PERCENT = 10.0


@dataclass(frozen=True)
class CandidateResult:
    candidate_id: str
    qualified: bool
    failed_gates: tuple[str, ...]
    worst_profit_factor: float
    total_net_profit: float
    worst_drawdown_percent: float


def _number(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be numeric")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{name} must be finite")
    return number


def _stage(payload: dict[str, Any], name: str) -> dict[str, float | int]:
    if not isinstance(payload, dict):
        raise ValueError(f"{name} must be an object")
    required = {
        "net_profit",
        "profit_factor",
        "expected_payoff",
        "completed_trades",
        "max_drawdown_percent",
        "safety_violations",
    }
    if set(payload) != required:
        raise ValueError(f"{name} must contain exactly {sorted(required)}")

    completed_trades = payload["completed_trades"]
    safety_violations = payload["safety_violations"]
    if isinstance(completed_trades, bool) or not isinstance(completed_trades, int) or completed_trades < 0:
        raise ValueError(f"{name}.completed_trades must be a non-negative integer")
    if isinstance(safety_violations, bool) or not isinstance(safety_violations, int) or safety_violations < 0:
        raise ValueError(f"{name}.safety_violations must be a non-negative integer")

    result: dict[str, float | int] = {
        "net_profit": _number(payload["net_profit"], f"{name}.net_profit"),
        "profit_factor": _number(payload["profit_factor"], f"{name}.profit_factor"),
        "expected_payoff": _number(payload["expected_payoff"], f"{name}.expected_payoff"),
        "completed_trades": completed_trades,
        "max_drawdown_percent": _number(payload["max_drawdown_percent"], f"{name}.max_drawdown_percent"),
        "safety_violations": safety_violations,
    }
    if result["profit_factor"] < 0:
        raise ValueError(f"{name}.profit_factor cannot be negative")
    if result["max_drawdown_percent"] < 0:
        raise ValueError(f"{name}.max_drawdown_percent cannot be negative")
    return result


def evaluate_candidate(payload: dict[str, Any]) -> CandidateResult:
    if not isinstance(payload, dict):
        raise ValueError("candidate must be an object")
    if set(payload) != {"candidate_id", "screen_12m", "oos_6m"}:
        raise ValueError("candidate must contain exactly candidate_id, screen_12m, and oos_6m")
    candidate_id = payload["candidate_id"]
    if not isinstance(candidate_id, str) or not candidate_id.strip():
        raise ValueError("candidate_id must be a non-empty string")

    screen = _stage(payload["screen_12m"], "screen_12m")
    oos = _stage(payload["oos_6m"], "oos_6m")
    failed: list[str] = []

    if screen["net_profit"] < 0:
        failed.append("screen_negative_net_profit")
    if screen["profit_factor"] < SCREEN_PF_GATE:
        failed.append("screen_profit_factor_below_gate")
    if screen["expected_payoff"] <= 0:
        failed.append("screen_non_positive_expected_payoff")
    if screen["completed_trades"] < SCREEN_MIN_TRADES:
        failed.append("screen_insufficient_trades")
    if oos["net_profit"] < 0:
        failed.append("oos_negative_net_profit")
    if oos["profit_factor"] < OOS_PF_GATE:
        failed.append("oos_profit_factor_below_gate")
    if oos["expected_payoff"] <= 0:
        failed.append("oos_non_positive_expected_payoff")
    if max(screen["max_drawdown_percent"], oos["max_drawdown_percent"]) > MAX_DRAWDOWN_PERCENT:
        failed.append("drawdown_above_gate")
    if screen["safety_violations"] or oos["safety_violations"]:
        failed.append("safety_control_violation")

    return CandidateResult(
        candidate_id=candidate_id,
        qualified=not failed,
        failed_gates=tuple(failed),
        worst_profit_factor=min(float(screen["profit_factor"]), float(oos["profit_factor"])),
        total_net_profit=float(screen["net_profit"]) + float(oos["net_profit"]),
        worst_drawdown_percent=max(float(screen["max_drawdown_percent"]), float(oos["max_drawdown_percent"])),
    )


def select_best(payload: list[dict[str, Any]]) -> dict[str, Any]:
    if not isinstance(payload, list) or not payload:
        raise ValueError("at least one candidate is required")
    results = [evaluate_candidate(item) for item in payload]
    candidate_ids = [item.candidate_id for item in results]
    if len(candidate_ids) != len(set(candidate_ids)):
        raise ValueError("candidate_id values must be unique")

    qualified = [item for item in results if item.qualified]
    qualified.sort(
        key=lambda item: (
            -item.worst_profit_factor,
            -item.total_net_profit,
            item.worst_drawdown_percent,
            item.candidate_id,
        )
    )
    winner = qualified[0].candidate_id if qualified else None
    return {
        "decision": "promote_to_demo" if winner else "reject_all",
        "winner": winner,
        "results": [asdict(item) for item in results],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Select the most robust PeakFX candidate")
    parser.add_argument("candidates", help="JSON array of candidate metrics")
    parser.add_argument("--output", help="Optional output JSON path")
    args = parser.parse_args(argv)

    payload = json.loads(Path(args.candidates).read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("candidate file must contain a JSON array")
    result = select_best(payload)
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0 if result["winner"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
