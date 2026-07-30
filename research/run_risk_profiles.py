from __future__ import annotations

import argparse
from pathlib import Path

from research.backtest_eurusd_h1 import Config, load_bars
from research.risk_profile_comparison import compare_risk_profiles


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compare PeakFX paper-trading risk profiles without changing EA defaults"
    )
    parser.add_argument("csv", type=Path, help="EURUSD H1 CSV with time,open,high,low,close")
    parser.add_argument("--output", type=Path, default=Path("reports/risk_profiles.csv"))
    args = parser.parse_args()

    bars = load_bars(args.csv)
    report = compare_risk_profiles(bars, Config())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    report.to_csv(args.output, index=False)
    print(report.to_string(index=False))


if __name__ == "__main__":
    main()
