from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

_STAGE_DATES = {
    "smoke_1m": ("2025-06-01", "2025-06-30"),
    "screen_12m": ("2024-07-01", "2025-06-30"),
    "oos_6m": ("2025-07-01", "2025-12-31"),
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_manifest(
    *,
    stage: str,
    source_path: Path,
    report_path: Path,
    deposit: float,
    leverage: str,
    net_profit: float,
    profit_factor: float,
    expected_payoff: float,
    completed_trades: int,
    max_drawdown_percent: float,
    safety_violations: int,
) -> dict[str, object]:
    if stage not in _STAGE_DATES:
        raise ValueError(f"unsupported stage: {stage}")
    if deposit <= 0:
        raise ValueError("deposit must be positive")
    if not leverage.startswith("1:"):
        raise ValueError("leverage must use 1:N format")
    if completed_trades < 0 or safety_violations < 0:
        raise ValueError("trade and violation counts cannot be negative")

    start_date, end_date = _STAGE_DATES[stage]
    return {
        "candidate_id": "peakfx_confirmed_breakout_exp2_v1_45",
        "stage": stage,
        "symbol": "EURUSD",
        "timeframe": "H1",
        "modeling": "every_tick_based_on_real_ticks",
        "start_date": start_date,
        "end_date": end_date,
        "deposit": deposit,
        "currency": "USD",
        "leverage": leverage,
        "demo_only": True,
        "source_sha256": sha256_file(source_path),
        "report_sha256": sha256_file(report_path),
        "metrics": {
            "net_profit": net_profit,
            "profit_factor": profit_factor,
            "expected_payoff": expected_payoff,
            "completed_trades": completed_trades,
            "max_drawdown_percent": max_drawdown_percent,
            "safety_violations": safety_violations,
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build immutable MT5 EXP2 evidence manifest")
    parser.add_argument("--stage", required=True, choices=sorted(_STAGE_DATES))
    parser.add_argument("--source", required=True)
    parser.add_argument("--report", required=True)
    parser.add_argument("--deposit", required=True, type=float)
    parser.add_argument("--leverage", required=True)
    parser.add_argument("--net-profit", required=True, type=float)
    parser.add_argument("--profit-factor", required=True, type=float)
    parser.add_argument("--expected-payoff", required=True, type=float)
    parser.add_argument("--completed-trades", required=True, type=int)
    parser.add_argument("--max-drawdown-percent", required=True, type=float)
    parser.add_argument("--safety-violations", required=True, type=int)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)

    manifest = build_manifest(
        stage=args.stage,
        source_path=Path(args.source),
        report_path=Path(args.report),
        deposit=args.deposit,
        leverage=args.leverage,
        net_profit=args.net_profit,
        profit_factor=args.profit_factor,
        expected_payoff=args.expected_payoff,
        completed_trades=args.completed_trades,
        max_drawdown_percent=args.max_drawdown_percent,
        safety_violations=args.safety_violations,
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
