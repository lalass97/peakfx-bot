from __future__ import annotations

import argparse
import json
from pathlib import Path

from research.backtest_eurusd_h1 import Config, load_bars, run_backtest
from research.validation import (
    monte_carlo_trade_paths,
    parameter_sensitivity,
    validation_summary,
    walk_forward_validate,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run PeakFX EURUSD H1 robustness validation")
    parser.add_argument("csv", type=Path, help="CSV with time,open,high,low,close columns")
    parser.add_argument("--output", type=Path, default=Path("reports/validation"))
    parser.add_argument("--train-bars", type=int, default=24 * 365 * 2)
    parser.add_argument("--test-bars", type=int, default=24 * 90)
    parser.add_argument("--simulations", type=int, default=2_000)
    args = parser.parse_args()

    cfg = Config()
    bars = load_bars(args.csv)
    trades, _ = run_backtest(bars, cfg)
    walk_forward = walk_forward_validate(
        bars,
        cfg,
        train_bars=args.train_bars,
        test_bars=args.test_bars,
    )
    sensitivity = parameter_sensitivity(bars, cfg)
    monte_carlo = monte_carlo_trade_paths(
        trades,
        starting_equity=cfg.starting_equity,
        simulations=args.simulations,
    )
    summary = validation_summary(walk_forward, monte_carlo)

    args.output.mkdir(parents=True, exist_ok=True)
    walk_forward.to_csv(args.output / "walk_forward.csv", index=False)
    sensitivity.to_csv(args.output / "parameter_sensitivity.csv", index=False)
    monte_carlo.to_csv(args.output / "monte_carlo.csv", index=False)
    (args.output / "validation_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
