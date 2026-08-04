from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
from typing import Any

_ALLOWED_KEYS = {
    "candidate_id",
    "stage",
    "symbol",
    "timeframe",
    "modeling",
    "start_date",
    "end_date",
    "deposit",
    "currency",
    "leverage",
    "demo_only",
    "source_sha256",
    "report_sha256",
    "metrics",
}
_ALLOWED_METRIC_KEYS = {
    "net_profit",
    "profit_factor",
    "expected_payoff",
    "completed_trades",
    "max_drawdown_percent",
    "safety_violations",
}
_STAGE_DATES = {
    "smoke_1m": ("2025-06-01", "2025-06-30"),
    "screen_12m": ("2024-07-01", "2025-06-30"),
    "oos_6m": ("2025-07-01", "2025-12-31"),
}


@dataclass(frozen=True)
class ValidationResult:
    valid: bool
    errors: tuple[str, ...]


def _is_sha256(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value)


def validate_run(payload: dict[str, Any]) -> ValidationResult:
    errors: list[str] = []

    unknown = set(payload) - _ALLOWED_KEYS
    missing = _ALLOWED_KEYS - set(payload)
    if unknown:
        errors.append(f"unknown_field:{','.join(sorted(unknown))}")
    if missing:
        errors.append(f"missing_field:{','.join(sorted(missing))}")
    if errors:
        return ValidationResult(False, tuple(errors))

    if payload["candidate_id"] != "peakfx_confirmed_breakout_exp2_v1_45":
        errors.append("wrong_candidate_id")

    stage = payload["stage"]
    if stage not in _STAGE_DATES:
        errors.append("unsupported_stage")
    else:
        expected_start, expected_end = _STAGE_DATES[stage]
        if payload["start_date"] != expected_start:
            errors.append("wrong_start_date")
        if payload["end_date"] != expected_end:
            errors.append("wrong_end_date")

    for key in ("start_date", "end_date"):
        try:
            date.fromisoformat(payload[key])
        except (TypeError, ValueError):
            errors.append(f"invalid_{key}")

    if payload["symbol"] != "EURUSD":
        errors.append("wrong_symbol")
    if payload["timeframe"] != "H1":
        errors.append("wrong_timeframe")
    if payload["modeling"] != "every_tick_based_on_real_ticks":
        errors.append("wrong_modeling")
    if payload["currency"] != "USD":
        errors.append("wrong_currency")
    if payload["demo_only"] is not True:
        errors.append("demo_only_required")

    deposit = payload["deposit"]
    if isinstance(deposit, bool) or not isinstance(deposit, (int, float)) or deposit <= 0:
        errors.append("invalid_deposit")
    leverage = payload["leverage"]
    if not isinstance(leverage, str) or not leverage.startswith("1:"):
        errors.append("invalid_leverage")

    if not _is_sha256(payload["source_sha256"]):
        errors.append("invalid_source_sha256")
    if not _is_sha256(payload["report_sha256"]):
        errors.append("invalid_report_sha256")

    metrics = payload["metrics"]
    if not isinstance(metrics, dict):
        errors.append("metrics_must_be_object")
    else:
        metric_unknown = set(metrics) - _ALLOWED_METRIC_KEYS
        metric_missing = _ALLOWED_METRIC_KEYS - set(metrics)
        if metric_unknown:
            errors.append(f"unknown_metric:{','.join(sorted(metric_unknown))}")
        if metric_missing:
            errors.append(f"missing_metric:{','.join(sorted(metric_missing))}")
        if not metric_unknown and not metric_missing:
            for key in ("net_profit", "profit_factor", "expected_payoff", "max_drawdown_percent"):
                value = metrics[key]
                if isinstance(value, bool) or not isinstance(value, (int, float)):
                    errors.append(f"invalid_metric_type:{key}")
            for key in ("completed_trades", "safety_violations"):
                value = metrics[key]
                if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                    errors.append(f"invalid_metric_type:{key}")

    return ValidationResult(not errors, tuple(errors))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate immutable MT5 EXP2 run metadata")
    parser.add_argument("run_json")
    parser.add_argument("--output")
    args = parser.parse_args(argv)

    payload = json.loads(Path(args.run_json).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("run JSON must be an object")

    result = validate_run(payload)
    rendered = json.dumps(asdict(result), indent=2, sort_keys=True) + "\n"
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0 if result.valid else 4


if __name__ == "__main__":
    raise SystemExit(main())
