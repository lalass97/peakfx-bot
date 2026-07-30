from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class ReconciliationThresholds:
    match_window_minutes: int = 90
    warning_entry_slippage_pips: float = 0.8
    critical_entry_slippage_pips: float = 2.0
    warning_exit_slippage_pips: float = 1.0
    critical_exit_slippage_pips: float = 2.5
    warning_missed_trade_rate: float = 0.05
    critical_missed_trade_rate: float = 0.15

    def validate(self) -> None:
        if self.match_window_minutes <= 0:
            raise ValueError("match_window_minutes must be positive")
        for value in (
            self.warning_entry_slippage_pips,
            self.critical_entry_slippage_pips,
            self.warning_exit_slippage_pips,
            self.critical_exit_slippage_pips,
            self.warning_missed_trade_rate,
            self.critical_missed_trade_rate,
        ):
            if value < 0:
                raise ValueError("thresholds cannot be negative")
        if self.warning_entry_slippage_pips > self.critical_entry_slippage_pips:
            raise ValueError("entry warning threshold cannot exceed critical threshold")
        if self.warning_exit_slippage_pips > self.critical_exit_slippage_pips:
            raise ValueError("exit warning threshold cannot exceed critical threshold")
        if self.warning_missed_trade_rate > self.critical_missed_trade_rate:
            raise ValueError("missed-trade warning threshold cannot exceed critical threshold")


MODELED_REQUIRED = {"entry_time", "side", "entry", "exit_time", "exit", "pnl"}
LIVE_REQUIRED = {
    "entry_time",
    "side",
    "entry",
    "exit_time",
    "exit",
    "pnl",
    "ticket",
}


def _normalize_trades(frame: pd.DataFrame, required: set[str], label: str) -> pd.DataFrame:
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(f"{label} trades missing columns: {sorted(missing)}")
    out = frame.copy()
    out["entry_time"] = pd.to_datetime(out["entry_time"], utc=True)
    out["exit_time"] = pd.to_datetime(out["exit_time"], utc=True)
    out["side"] = out["side"].astype(int)
    if not out["side"].isin([-1, 1]).all():
        raise ValueError(f"{label} side must be -1 or 1")
    for column in ("entry", "exit", "pnl"):
        out[column] = pd.to_numeric(out[column], errors="raise")
    return out.sort_values("entry_time").reset_index(drop=True)


def reconcile_trades(
    modeled: pd.DataFrame,
    live: pd.DataFrame,
    thresholds: ReconciliationThresholds = ReconciliationThresholds(),
) -> pd.DataFrame:
    """Match modeled trades to paper trades by side and nearest entry time.

    Matching is one-to-one. Unmatched modeled rows are marked ``missed_live``;
    unmatched live rows are marked ``unexpected_live``.
    """
    thresholds.validate()
    model = _normalize_trades(modeled, MODELED_REQUIRED, "modeled")
    actual = _normalize_trades(live, LIVE_REQUIRED, "live")
    used_live: set[int] = set()
    rows: list[dict[str, object]] = []
    max_delta = pd.Timedelta(minutes=thresholds.match_window_minutes)
    pip = 0.0001

    for model_index, expected in model.iterrows():
        candidates = actual.loc[(actual["side"] == expected["side"]) & (~actual.index.isin(used_live))].copy()
        if not candidates.empty:
            candidates["time_delta"] = (candidates["entry_time"] - expected["entry_time"]).abs()
            candidates = candidates.loc[candidates["time_delta"] <= max_delta]

        if candidates.empty:
            rows.append(
                {
                    "status": "missed_live",
                    "modeled_index": int(model_index),
                    "ticket": 0,
                    "side": int(expected["side"]),
                    "modeled_entry_time": expected["entry_time"],
                    "live_entry_time": pd.NaT,
                    "entry_delay_seconds": np.nan,
                    "entry_slippage_pips": np.nan,
                    "exit_slippage_pips": np.nan,
                    "modeled_pnl": float(expected["pnl"]),
                    "live_pnl": np.nan,
                    "pnl_difference": np.nan,
                }
            )
            continue

        live_index = int(candidates["time_delta"].idxmin())
        observed = actual.loc[live_index]
        used_live.add(live_index)
        side = int(expected["side"])
        entry_slippage = (float(observed["entry"]) - float(expected["entry"])) * side / pip
        exit_slippage = (float(expected["exit"]) - float(observed["exit"])) * side / pip
        live_pnl = float(observed["pnl"])
        modeled_pnl = float(expected["pnl"])
        rows.append(
            {
                "status": "matched",
                "modeled_index": int(model_index),
                "ticket": int(observed["ticket"]),
                "side": side,
                "modeled_entry_time": expected["entry_time"],
                "live_entry_time": observed["entry_time"],
                "entry_delay_seconds": float((observed["entry_time"] - expected["entry_time"]).total_seconds()),
                "entry_slippage_pips": float(entry_slippage),
                "exit_slippage_pips": float(exit_slippage),
                "modeled_pnl": modeled_pnl,
                "live_pnl": live_pnl,
                "pnl_difference": live_pnl - modeled_pnl,
            }
        )

    for live_index, observed in actual.loc[~actual.index.isin(used_live)].iterrows():
        rows.append(
            {
                "status": "unexpected_live",
                "modeled_index": -1,
                "ticket": int(observed["ticket"]),
                "side": int(observed["side"]),
                "modeled_entry_time": pd.NaT,
                "live_entry_time": observed["entry_time"],
                "entry_delay_seconds": np.nan,
                "entry_slippage_pips": np.nan,
                "exit_slippage_pips": np.nan,
                "modeled_pnl": np.nan,
                "live_pnl": float(observed["pnl"]),
                "pnl_difference": np.nan,
            }
        )

    return pd.DataFrame(rows)


def reconciliation_summary(
    reconciled: pd.DataFrame,
    thresholds: ReconciliationThresholds = ReconciliationThresholds(),
) -> dict[str, object]:
    thresholds.validate()
    if reconciled.empty:
        return {
            "status": "warning",
            "modeled_trades": 0,
            "matched_trades": 0,
            "missed_live": 0,
            "unexpected_live": 0,
            "missed_trade_rate": 0.0,
            "median_entry_slippage_pips": 0.0,
            "p95_entry_slippage_pips": 0.0,
            "median_exit_slippage_pips": 0.0,
            "p95_exit_slippage_pips": 0.0,
            "total_pnl_difference": 0.0,
            "reasons": ["no reconciliation records"],
        }

    matched = reconciled.loc[reconciled["status"] == "matched"]
    missed = reconciled.loc[reconciled["status"] == "missed_live"]
    unexpected = reconciled.loc[reconciled["status"] == "unexpected_live"]
    modeled_count = len(matched) + len(missed)
    missed_rate = len(missed) / modeled_count if modeled_count else 0.0

    entry_abs = matched["entry_slippage_pips"].abs().dropna()
    exit_abs = matched["exit_slippage_pips"].abs().dropna()
    p95_entry = float(entry_abs.quantile(0.95)) if not entry_abs.empty else 0.0
    p95_exit = float(exit_abs.quantile(0.95)) if not exit_abs.empty else 0.0
    reasons: list[str] = []
    status = "healthy"

    if missed_rate >= thresholds.critical_missed_trade_rate:
        status = "critical"
        reasons.append("critical missed-trade rate")
    elif missed_rate >= thresholds.warning_missed_trade_rate:
        status = "warning"
        reasons.append("elevated missed-trade rate")

    if p95_entry >= thresholds.critical_entry_slippage_pips or p95_exit >= thresholds.critical_exit_slippage_pips:
        status = "critical"
        reasons.append("critical execution slippage")
    elif (
        p95_entry >= thresholds.warning_entry_slippage_pips
        or p95_exit >= thresholds.warning_exit_slippage_pips
    ) and status == "healthy":
        status = "warning"
        reasons.append("elevated execution slippage")

    if len(unexpected):
        if status == "healthy":
            status = "warning"
        reasons.append("unexpected live trades detected")

    return {
        "status": status,
        "modeled_trades": int(modeled_count),
        "matched_trades": int(len(matched)),
        "missed_live": int(len(missed)),
        "unexpected_live": int(len(unexpected)),
        "missed_trade_rate": float(missed_rate),
        "median_entry_slippage_pips": float(entry_abs.median()) if not entry_abs.empty else 0.0,
        "p95_entry_slippage_pips": p95_entry,
        "median_exit_slippage_pips": float(exit_abs.median()) if not exit_abs.empty else 0.0,
        "p95_exit_slippage_pips": p95_exit,
        "total_pnl_difference": float(matched["pnl_difference"].sum()) if not matched.empty else 0.0,
        "reasons": reasons,
    }


def main() -> None:
    import argparse
    import json

    parser = argparse.ArgumentParser(description="Reconcile modeled PeakFX trades with MT5 paper trades")
    parser.add_argument("modeled_csv", type=Path)
    parser.add_argument("live_csv", type=Path)
    parser.add_argument("--output", type=Path, default=Path("reports/execution_reconciliation.csv"))
    parser.add_argument("--summary", type=Path, default=Path("reports/execution_reconciliation.json"))
    args = parser.parse_args()

    reconciled = reconcile_trades(pd.read_csv(args.modeled_csv), pd.read_csv(args.live_csv))
    summary = reconciliation_summary(reconciled)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.summary.parent.mkdir(parents=True, exist_ok=True)
    reconciled.to_csv(args.output, index=False)
    args.summary.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
