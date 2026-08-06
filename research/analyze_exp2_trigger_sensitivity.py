from __future__ import annotations

import argparse
import io
import json
import zipfile
from pathlib import Path

import pandas as pd

WINDOWS = [
    "2020_2021",
    "2021_2022",
    "2022_2023",
    "2023_2024",
    "2024_2025",
]
LOWERS = [0.45, 0.50, 0.55, 0.5667, 0.60, 0.65]
UPPERS = [0.85, 0.90, 0.933, 0.95, 1.00, 1.05]


def load_trades(zip_path: Path) -> pd.DataFrame:
    rows: list[dict] = []
    with zipfile.ZipFile(zip_path) as archive:
        for window in WINDOWS:
            raw = archive.read(f"{window}/trade_deals.csv")
            deals = pd.read_csv(io.BytesIO(raw))
            deals["deal_time"] = pd.to_datetime(deals["deal_time"])
            for position_id, group in deals.groupby("position_id", sort=False):
                entries = group[group["deal_entry"] == "DEAL_ENTRY_IN"].sort_values("deal_time")
                exits = group[group["deal_entry"] == "DEAL_ENTRY_OUT"].sort_values("deal_time")
                if len(entries) != 1 or exits.empty:
                    raise ValueError(
                        f"Unexpected deal structure for {window} position {position_id}: "
                        f"entries={len(entries)} exits={len(exits)}"
                    )
                entry = entries.iloc[0]
                net = float(group[["profit", "commission", "swap", "fee"]].sum().sum())
                rows.append(
                    {
                        "window": window,
                        "entry_time": entry["deal_time"].isoformat(),
                        "position_id": int(position_id),
                        "trigger_clearance_atr": float(entry["trigger_clearance_atr"]),
                        "net_profit": net,
                    }
                )
    trades = pd.DataFrame(rows)
    if len(trades) != 465:
        raise ValueError(f"Expected 465 trades, found {len(trades)}")
    if round(float(trades["net_profit"].sum()), 2) != 552.44:
        raise ValueError(f"Baseline net mismatch: {trades['net_profit'].sum():.2f}")
    return trades


def max_consecutive_losses(values: pd.Series) -> int:
    best = current = 0
    for value in values:
        if value < 0:
            current += 1
            best = max(best, current)
        else:
            current = 0
    return best


def evaluate(trades: pd.DataFrame, lower: float, upper: float) -> dict:
    filtered_mask = trades["trigger_clearance_atr"].between(lower, upper, inclusive="both")
    kept = trades.loc[~filtered_mask].copy()
    by_year = kept.groupby("window")["net_profit"].sum().reindex(WINDOWS, fill_value=0.0)
    baseline = trades.groupby("window")["net_profit"].sum().reindex(WINDOWS)
    gross_profit = float(kept.loc[kept["net_profit"] > 0, "net_profit"].sum())
    gross_loss = float(-kept.loc[kept["net_profit"] < 0, "net_profit"].sum())
    profit_factor = gross_profit / gross_loss if gross_loss else None
    ordered = kept.sort_values(["window", "entry_time"])
    loss_reduction = (by_year["2021_2022"] - baseline["2021_2022"]) / abs(
        baseline["2021_2022"]
    )
    retention_2022_2023 = by_year["2022_2023"] / baseline["2022_2023"]
    retention_2024_2025 = by_year["2024_2025"] / baseline["2024_2025"]
    tier_pass = (
        loss_reduction >= 0.50
        and retention_2022_2023 >= 0.80
        and retention_2024_2025 >= 0.80
        and len(kept) >= 100
    )
    formal_gate_projection = (
        tier_pass
        and profit_factor is not None
        and profit_factor >= 1.25
        and int((by_year > 0).sum()) >= 4
        and max_consecutive_losses(ordered["net_profit"]) <= 8
    )
    return {
        "lower": lower,
        "upper": upper,
        "filtered_trades": int(filtered_mask.sum()),
        "trades_left": int(len(kept)),
        "net_profit": round(float(kept["net_profit"].sum()), 2),
        "profit_factor": round(float(profit_factor), 6) if profit_factor is not None else None,
        "profitable_years": int((by_year > 0).sum()),
        "max_consecutive_losses": max_consecutive_losses(ordered["net_profit"]),
        "loss_reduction_2021_2022": round(float(loss_reduction), 6),
        "retention_2022_2023": round(float(retention_2022_2023), 6),
        "retention_2024_2025": round(float(retention_2024_2025), 6),
        "tier_pass": bool(tier_pass),
        "formal_gate_projection": bool(formal_gate_projection),
        "yearly_net": {key: round(float(value), 2) for key, value in by_year.items()},
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("artifact_zip", type=Path)
    parser.add_argument("--json", type=Path, required=True)
    parser.add_argument("--csv", type=Path, required=True)
    args = parser.parse_args()

    trades = load_trades(args.artifact_zip)
    results = [evaluate(trades, lower, upper) for lower in LOWERS for upper in UPPERS if lower < upper]
    passing = [row for row in results if row["tier_pass"]]
    passing.sort(key=lambda row: row["net_profit"], reverse=True)
    payload = {
        "protocol": "EXP2 predefined trigger-clearance sensitivity analysis",
        "baseline_trades": 465,
        "baseline_net_profit": 552.44,
        "oos_locked": True,
        "grid": {"lower_bounds": LOWERS, "upper_bounds": UPPERS},
        "best_tier_pass": passing[0] if passing else None,
        "formal_gate_pass_count": sum(row["formal_gate_projection"] for row in results),
        "results": results,
    }
    args.json.parent.mkdir(parents=True, exist_ok=True)
    args.csv.parent.mkdir(parents=True, exist_ok=True)
    args.json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    pd.DataFrame(results).drop(columns=["yearly_net"]).to_csv(args.csv, index=False)
    print(json.dumps(payload["best_tier_pass"], indent=2))
    print(f"Formal gate projected passes: {payload['formal_gate_pass_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
