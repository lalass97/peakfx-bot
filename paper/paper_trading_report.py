from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

REQUIRED_COLUMNS = {
    "ticket",
    "entry_time",
    "exit_time",
    "side",
    "entry",
    "exit",
    "volume",
    "pnl",
    "spread_points",
    "slippage_points",
    "reason",
}


def load_journal(path: str | Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    missing = REQUIRED_COLUMNS.difference(df.columns)
    if missing:
        raise ValueError(f"Missing journal columns: {sorted(missing)}")
    df = df.copy()
    df["entry_time"] = pd.to_datetime(df["entry_time"], utc=True)
    df["exit_time"] = pd.to_datetime(df["exit_time"], utc=True)
    df = df.sort_values(["exit_time", "ticket"]).drop_duplicates("ticket", keep="last")
    numeric = ["entry", "exit", "volume", "pnl", "spread_points", "slippage_points"]
    df[numeric] = df[numeric].apply(pd.to_numeric, errors="raise")
    return df


def max_losing_streak(pnl: pd.Series) -> int:
    longest = current = 0
    for value in pnl:
        if value < 0:
            current += 1
            longest = max(longest, current)
        else:
            current = 0
    return longest


def summarize_journal(df: pd.DataFrame, starting_balance: float) -> dict[str, float | int]:
    if starting_balance <= 0:
        raise ValueError("starting_balance must be positive")
    if df.empty:
        return {
            "trades": 0,
            "net_pnl": 0.0,
            "return_pct": 0.0,
            "win_rate_pct": 0.0,
            "profit_factor": 0.0,
            "expectancy": 0.0,
            "max_drawdown_pct": 0.0,
            "max_losing_streak": 0,
            "average_spread_points": 0.0,
            "average_slippage_points": 0.0,
        }

    pnl = df["pnl"]
    wins = pnl[pnl > 0]
    losses = pnl[pnl < 0]
    equity = starting_balance + pnl.cumsum()
    running_max = equity.cummax().clip(lower=starting_balance)
    drawdown = equity / running_max - 1
    gross_profit = float(wins.sum())
    gross_loss = float(-losses.sum())

    return {
        "trades": int(len(df)),
        "net_pnl": float(pnl.sum()),
        "return_pct": float(pnl.sum() / starting_balance * 100),
        "win_rate_pct": float((pnl > 0).mean() * 100),
        "profit_factor": float(gross_profit / gross_loss) if gross_loss > 0 else 0.0,
        "expectancy": float(pnl.mean()),
        "max_drawdown_pct": float(drawdown.min() * 100),
        "max_losing_streak": max_losing_streak(pnl),
        "average_spread_points": float(df["spread_points"].mean()),
        "average_slippage_points": float(df["slippage_points"].mean()),
    }


def evaluate_gates(summary: dict[str, float | int], minimum_trades: int = 100) -> dict[str, bool]:
    return {
        "enough_trades": int(summary["trades"]) >= minimum_trades,
        "positive_expectancy": float(summary["expectancy"]) > 0,
        "profit_factor": float(summary["profit_factor"]) >= 1.20,
        "drawdown": float(summary["max_drawdown_pct"]) > -10.0,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a PeakFX paper-trading report")
    parser.add_argument("journal", type=Path)
    parser.add_argument("--starting-balance", type=float, default=10_000.0)
    parser.add_argument("--output", type=Path, default=Path("reports/paper"))
    args = parser.parse_args()

    journal = load_journal(args.journal)
    summary = summarize_journal(journal, args.starting_balance)
    gates = evaluate_gates(summary)
    args.output.mkdir(parents=True, exist_ok=True)
    journal.to_csv(args.output / "normalized_journal.csv", index=False)
    (args.output / "summary.json").write_text(json.dumps(summary, indent=2))
    (args.output / "gates.json").write_text(json.dumps(gates, indent=2))
    print(json.dumps({"summary": summary, "gates": gates}, indent=2))


if __name__ == "__main__":
    main()
