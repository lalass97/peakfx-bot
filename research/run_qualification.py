from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any, Sequence

from research.combined_qualification import qualify_exported_run

EXIT_GREEN = 0
EXIT_RED = 2
EXIT_INCONCLUSIVE = 3
EXIT_INVALID_INPUT = 4


def _json_safe(value: Any) -> Any:
    """Convert a report tree into strict, deterministic JSON-compatible values."""
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        if math.isnan(value):
            return "nan"
        return "infinity" if value > 0 else "-infinity"
    return value


def render_report_json(report: object) -> str:
    payload = _json_safe(asdict(report))
    return json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n"


def _exit_code(decision: str) -> int:
    return {
        "green": EXIT_GREEN,
        "red": EXIT_RED,
        "inconclusive": EXIT_INCONCLUSIVE,
    }[decision]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Score one PeakFX research run using completed trades and ordered "
            "mark-to-market equity snapshots."
        )
    )
    parser.add_argument("--trades", required=True, type=Path, help="Completed-trade CSV")
    parser.add_argument(
        "--snapshots", required=True, type=Path, help="Open-equity snapshot CSV"
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional path for the strict JSON report; stdout is always populated",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        trades_csv = args.trades.read_text(encoding="utf-8")
        snapshots_csv = args.snapshots.read_text(encoding="utf-8")
        report = qualify_exported_run(trades_csv, snapshots_csv)
        rendered = render_report_json(report)
        if args.output is not None:
            args.output.write_text(rendered, encoding="utf-8")
        sys.stdout.write(rendered)
        return _exit_code(report.decision)
    except (OSError, UnicodeError, ValueError) as exc:
        sys.stderr.write(f"qualification input error: {exc}\n")
        return EXIT_INVALID_INPUT


if __name__ == "__main__":
    raise SystemExit(main())
