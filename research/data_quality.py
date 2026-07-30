from __future__ import annotations

from dataclasses import dataclass, asdict

import pandas as pd


@dataclass(frozen=True)
class DataQualityReport:
    rows: int
    start: str
    end: str
    duplicate_timestamps: int
    non_monotonic_timestamps: bool
    invalid_ohlc_rows: int
    nonpositive_price_rows: int
    weekend_rows: int
    large_gap_count: int
    largest_gap_hours: float

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def inspect_h1_bars(df: pd.DataFrame, gap_hours: float = 4.0) -> DataQualityReport:
    required = {"open", "high", "low", "close"}
    missing = required.difference(df.columns)
    if missing:
        raise ValueError(f"Missing columns: {sorted(missing)}")
    if not isinstance(df.index, pd.DatetimeIndex):
        raise TypeError("DataFrame index must be a DatetimeIndex")
    if df.empty:
        raise ValueError("DataFrame is empty")

    ordered = df.sort_index()
    duplicate_count = int(ordered.index.duplicated().sum())
    non_monotonic = not df.index.is_monotonic_increasing
    invalid_ohlc = (
        (ordered["high"] < ordered[["open", "close", "low"]].max(axis=1))
        | (ordered["low"] > ordered[["open", "close", "high"]].min(axis=1))
    )
    nonpositive = (ordered[["open", "high", "low", "close"]] <= 0).any(axis=1)
    weekend = ordered.index.dayofweek >= 5
    gaps = ordered.index.to_series().diff().dt.total_seconds().div(3600).dropna()
    large_gaps = gaps[gaps > gap_hours]

    return DataQualityReport(
        rows=len(ordered),
        start=ordered.index[0].isoformat(),
        end=ordered.index[-1].isoformat(),
        duplicate_timestamps=duplicate_count,
        non_monotonic_timestamps=non_monotonic,
        invalid_ohlc_rows=int(invalid_ohlc.sum()),
        nonpositive_price_rows=int(nonpositive.sum()),
        weekend_rows=int(weekend.sum()),
        large_gap_count=int(len(large_gaps)),
        largest_gap_hours=float(gaps.max()) if not gaps.empty else 0.0,
    )


def assert_research_ready(report: DataQualityReport) -> None:
    failures: list[str] = []
    if report.rows < 5_000:
        failures.append("fewer than 5,000 H1 bars")
    if report.duplicate_timestamps:
        failures.append("duplicate timestamps")
    if report.non_monotonic_timestamps:
        failures.append("timestamps are not increasing")
    if report.invalid_ohlc_rows:
        failures.append("invalid OHLC relationships")
    if report.nonpositive_price_rows:
        failures.append("non-positive prices")
    if failures:
        raise ValueError("Dataset is not research-ready: " + ", ".join(failures))
