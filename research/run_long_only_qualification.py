from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from research.long_only_ab_qualification import (
    ExperimentMetrics,
    LongOnlyABThresholds,
    qualify_long_only_ab,
)
from research.long_only_evidence_bundle import validate_long_only_evidence_bundle
from research.run_long_only_bundle_validation import _load_manifest

_REQUIRED_METRIC_FIELDS = {
    "trade_count",
    "net_profit",
    "profit_factor",
    "maximum_drawdown_fraction",
    "profitable_year_fraction",
    "two_x_cost_net_profit",
    "sequence_risk_decision",
}


def _load_metrics(path: str) -> tuple[ExperimentMetrics, ExperimentMetrics]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if set(data) != {"baseline", "candidate"}:
        raise ValueError("metrics document must contain exactly baseline and candidate")

    def parse(name: str) -> ExperimentMetrics:
        value = data[name]
        if not isinstance(value, dict) or set(value) != _REQUIRED_METRIC_FIELDS:
            raise ValueError(f"{name} metrics fields mismatch")
        return ExperimentMetrics(**value)

    return parse("baseline"), parse("candidate")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate immutable evidence and qualify one isolated long-only candidate"
    )
    parser.add_argument("manifest", help="Path to strict evidence-bundle manifest JSON")
    parser.add_argument("metrics", help="Path to strict baseline/candidate metrics JSON")
    parser.add_argument("--output", help="Optional deterministic JSON result path")
    args = parser.parse_args(argv)

    try:
        bundle = _load_manifest(args.manifest)
        validate_long_only_evidence_bundle(bundle)
        baseline, candidate = _load_metrics(args.metrics)
        report = qualify_long_only_ab(
            baseline,
            candidate,
            LongOnlyABThresholds(),
        )
        result = {
            "status": "qualified",
            "decision": report.decision,
            "failed_gates": list(report.failed_gates),
            "baseline_strategy_id": bundle.baseline_strategy_id,
            "candidate_strategy_id": bundle.candidate_strategy_id,
            "net_profit_improvement": report.net_profit_improvement,
            "drawdown_improvement_fraction": report.drawdown_improvement_fraction,
            "retained_trade_fraction": report.retained_trade_fraction,
            "baseline": asdict(report.baseline),
            "candidate": asdict(report.candidate),
        }
        exit_code = {"promote": 0, "reject": 2, "inconclusive": 3}[report.decision]
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
