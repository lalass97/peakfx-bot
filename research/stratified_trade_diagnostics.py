from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class SegmentResult:
    segment: str
    trades: int
    net_pnl: float
    average_pnl: float
    win_rate: float
    profit_factor: float


@dataclass(frozen=True)
class StratifiedDiagnosticsReport:
    overall_net_pnl: float
    by_side: tuple[SegmentResult, ...]
    by_year: tuple[SegmentResult, ...]
    weakest_side: str
    weakest_year: str


def _profit_factor(values: pd.Series) -> float:
    gross_profit = float(values[values > 0].sum())
    gross_loss = float(-values[values < 0].sum())
    if gross_loss == 0:
        return float("inf") if gross_profit > 0 else 0.0
    return gross_profit / gross_loss


def _summarize(frame: pd.DataFrame, key: str) -> tuple[SegmentResult, ...]:
    results: list[SegmentResult] = []
    for value, group in frame.groupby(key, sort=True):
        pnl = group["net_pnl"]
        results.append(
            SegmentResult(
                segment=str(value),
                trades=int(len(group)),
                net_pnl=float(pnl.sum()),
                average_pnl=float(pnl.mean()),
                win_rate=float((pnl > 0).mean()),
                profit_factor=_profit_factor(pnl),
            )
        )
    return tuple(results)


def analyze_stratified_trades(trades: pd.DataFrame) -> StratifiedDiagnosticsReport:
    """Expose direction and year asymmetry without recommending a strategy change."""
    required = {"closed_at", "net_pnl", "side"}
    missing = required.difference(trades.columns)
    if missing:
        raise ValueError(f"missing required columns: {sorted(missing)}")
    if trades.empty:
        raise ValueError("trades must not be empty")

    frame = trades.loc[:, ["closed_at", "net_pnl", "side"]].copy()
    frame["closed_at"] = pd.to_datetime(frame["closed_at"], utc=True, errors="raise")
    frame["net_pnl"] = pd.to_numeric(frame["net_pnl"], errors="raise")
    frame["side"] = frame["side"].astype(str).str.lower()
    if not frame["side"].isin({"long", "short"}).all():
        raise ValueError("side must contain only long or short")
    if not frame["closed_at"].is_monotonic_increasing:
        raise ValueError("trades must be ordered by closed_at ascending")
    if not frame["net_pnl"].map(pd.notna).all():
        raise ValueError("net_pnl must contain finite values")

    frame["year"] = frame["closed_at"].dt.year.astype(str)
    by_side = _summarize(frame, "side")
    by_year = _summarize(frame, "year")
    weakest_side = min(by_side, key=lambda result: result.net_pnl).segment
    weakest_year = min(by_year, key=lambda result: result.net_pnl).segment

    return StratifiedDiagnosticsReport(
        overall_net_pnl=float(frame["net_pnl"].sum()),
        by_side=by_side,
        by_year=by_year,
        weakest_side=weakest_side,
        weakest_year=weakest_year,
    )
