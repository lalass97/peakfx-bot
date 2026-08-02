from __future__ import annotations

import argparse
import json
from pathlib import Path

from research.long_only_evidence_bundle import (
    EvidenceFile,
    LongOnlyEvidenceBundle,
    validate_long_only_evidence_bundle,
)


def _load_manifest(path: str) -> LongOnlyEvidenceBundle:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    required = {
        "baseline_report",
        "candidate_report",
        "baseline_trades",
        "candidate_trades",
        "candidate_open_equity",
        "baseline_strategy_id",
        "candidate_strategy_id",
        "symbol",
        "timeframe",
        "test_start",
        "test_end",
        "initial_deposit",
        "leverage",
        "modeling_mode",
        "cost_stress_multiple",
    }
    if set(data) != required:
        missing = sorted(required - set(data))
        extra = sorted(set(data) - required)
        raise ValueError(f"manifest fields mismatch; missing={missing}, extra={extra}")

    def evidence(name: str) -> EvidenceFile:
        value = data[name]
        if not isinstance(value, dict) or set(value) != {"path", "sha256_hex"}:
            raise ValueError(f"{name} must contain exactly path and sha256_hex")
        return EvidenceFile(path=value["path"], sha256_hex=value["sha256_hex"])

    return LongOnlyEvidenceBundle(
        baseline_report=evidence("baseline_report"),
        candidate_report=evidence("candidate_report"),
        baseline_trades=evidence("baseline_trades"),
        candidate_trades=evidence("candidate_trades"),
        candidate_open_equity=evidence("candidate_open_equity"),
        baseline_strategy_id=data["baseline_strategy_id"],
        candidate_strategy_id=data["candidate_strategy_id"],
        symbol=data["symbol"],
        timeframe=data["timeframe"],
        test_start=data["test_start"],
        test_end=data["test_end"],
        initial_deposit=data["initial_deposit"],
        leverage=data["leverage"],
        modeling_mode=data["modeling_mode"],
        cost_stress_multiple=data["cost_stress_multiple"],
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate one immutable long-only A/B evidence bundle")
    parser.add_argument("manifest", help="Path to strict JSON manifest")
    parser.add_argument("--output", help="Optional JSON result path")
    args = parser.parse_args(argv)

    try:
        bundle = _load_manifest(args.manifest)
        validate_long_only_evidence_bundle(bundle)
        result = {
            "status": "valid",
            "baseline_strategy_id": bundle.baseline_strategy_id,
            "candidate_strategy_id": bundle.candidate_strategy_id,
            "symbol": bundle.symbol,
            "timeframe": bundle.timeframe,
            "test_start": bundle.test_start,
            "test_end": bundle.test_end,
            "cost_stress_multiple": bundle.cost_stress_multiple,
        }
        exit_code = 0
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        result = {"status": "invalid", "error": str(exc)}
        exit_code = 4

    rendered = json.dumps(result, sort_keys=True, separators=(",", ":"), allow_nan=False)
    print(rendered)
    if args.output:
        Path(args.output).write_text(rendered + "\n", encoding="utf-8")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
