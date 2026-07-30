from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from research.backtest_eurusd_h1 import Config, load_bars
from research.robustness_audit import audit_baseline


def _json_default(value: object) -> object:
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run PeakFX baseline robustness audit")
    parser.add_argument("csv", type=Path, help="EURUSD H1 CSV with time,open,high,low,close")
    parser.add_argument("--output", type=Path, default=Path("reports/robustness_audit.json"))
    parser.add_argument("--spread-pips", type=float, default=1.0)
    parser.add_argument("--slippage-pips", type=float, default=0.2)
    args = parser.parse_args()

    bars = load_bars(args.csv)
    cfg = Config(spread_pips=args.spread_pips, slippage_pips=args.slippage_pips)
    report = audit_baseline(bars, cfg)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, default=_json_default), encoding="utf-8")

    baseline = report["baseline"]
    print(f"Trades: {int(baseline.get('trades', 0))}")
    print(f"Profit factor: {baseline.get('profit_factor', 0):.3f}")
    print(f"Expectancy/trade: {baseline.get('expectancy_per_trade', 0):.2f}")
    print(f"Max drawdown: {baseline.get('max_drawdown_pct', 0):.2f}%")
    print(f"Report: {args.output}")


if __name__ == "__main__":
    main()
