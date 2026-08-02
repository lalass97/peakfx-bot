from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

import numpy as np

from research.block_bootstrap_sequence_risk import (
    BlockBootstrapConfig,
    analyze_block_bootstrap_sequence_risk,
)
from research.profitability_csv import load_completed_trades_csv


def _summary(values: np.ndarray) -> dict[str, float]:
    return {
        "mean": float(np.mean(values)),
        "median": float(np.median(values)),
        "p05": float(np.percentile(values, 5.0)),
        "p95": float(np.percentile(values, 95.0)),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run PeakFX block-bootstrap sequence-risk analysis")
    parser.add_argument("--trades", required=True, type=Path)
    parser.add_argument("--simulations", type=int, default=2000)
    parser.add_argument("--block-size", type=int, default=10)
    parser.add_argument("--initial-balance", type=float, default=10000.0)
    parser.add_argument("--ruin-drawdown", type=float, default=0.50)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    try:
        text = args.trades.read_text(encoding="utf-8")
        trades = load_completed_trades_csv(text)
        values = np.array([trade.net_pnl for trade in trades], dtype=np.float64)
        config = BlockBootstrapConfig(
            simulations=args.simulations,
            block_size=args.block_size,
            initial_balance=args.initial_balance,
            ruin_drawdown_fraction=args.ruin_drawdown,
            seed=args.seed,
        )
        report = analyze_block_bootstrap_sequence_risk(values, config)
    except (OSError, ValueError) as exc:
        print(json.dumps({"error": str(exc)}, sort_keys=True))
        return 4

    payload = {
        "schema_version": 1,
        "method": "circular_moving_block_bootstrap",
        "config": asdict(config),
        "trade_count": report.trade_count,
        "historical_max_drawdown_fraction": report.historical_max_drawdown_fraction,
        "p95_max_drawdown_fraction": report.p95_max_drawdown_fraction,
        "mdd_ratio": report.mdd_ratio,
        "ruin_probability": report.ruin_probability,
        "max_drawdown_currency": _summary(report.max_drawdown_currency),
        "max_drawdown_fraction": _summary(report.max_drawdown_fraction),
        "terminal_equity": _summary(report.terminal_equity),
    }
    output = json.dumps(payload, allow_nan=False, indent=2, sort_keys=True) + "\n"
    print(output, end="")
    if args.output is not None:
        args.output.write_text(output, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
