from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from datetime import datetime

from research.open_equity_csv import load_open_equity_snapshots
from research.profitability_csv import load_completed_trades_csv


@dataclass(frozen=True)
class EvidenceConsistencyReport:
    trade_count: int
    snapshot_count: int
    first_trade_close: str
    last_trade_close: str
    first_snapshot: str
    last_snapshot: str


def _parse_iso_timestamp(value: str, field: str, row_number: int) -> datetime:
    text = value.strip()
    normalized = text[:-1] + "+00:00" if text.endswith("Z") else text
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ValueError(f"row {row_number}: {field} must be ISO-8601") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"row {row_number}: {field} must include a timezone")
    return parsed


def _timestamps(csv_text: str, field: str) -> tuple[datetime, ...]:
    reader = csv.DictReader(io.StringIO(csv_text))
    if reader.fieldnames is None or field not in reader.fieldnames:
        raise ValueError(f"CSV must contain {field}")
    values: list[datetime] = []
    for row_number, row in enumerate(reader, start=2):
        raw = row.get(field)
        if raw is None:
            raise ValueError(f"row {row_number}: {field} is required")
        values.append(_parse_iso_timestamp(raw, field, row_number))
    if not values:
        raise ValueError(f"CSV contains no {field} values")
    return tuple(values)


def verify_evidence_consistency(
    completed_trades_csv: str,
    open_equity_csv: str,
) -> EvidenceConsistencyReport:
    """Fail closed when the two exports cannot describe the same test run.

    The strict loaders validate each file independently. This function then verifies
    that mark-to-market evidence begins no later than the first completed trade and
    ends no earlier than the last completed trade. Inputs are never sorted or fixed.
    """
    trades = load_completed_trades_csv(completed_trades_csv)
    snapshots = load_open_equity_snapshots(open_equity_csv)
    trade_times = _timestamps(completed_trades_csv, "closed_at")
    snapshot_times = _timestamps(open_equity_csv, "timestamp")

    first_trade = trade_times[0]
    last_trade = trade_times[-1]
    first_snapshot = snapshot_times[0]
    last_snapshot = snapshot_times[-1]

    if first_snapshot > first_trade:
        raise ValueError("open-equity evidence starts after the first completed trade")
    if last_snapshot < last_trade:
        raise ValueError("open-equity evidence ends before the last completed trade")
    if first_snapshot >= last_snapshot:
        raise ValueError("open-equity evidence must cover a positive time interval")

    return EvidenceConsistencyReport(
        trade_count=len(trades),
        snapshot_count=len(snapshots),
        first_trade_close=first_trade.isoformat(),
        last_trade_close=last_trade.isoformat(),
        first_snapshot=first_snapshot.isoformat(),
        last_snapshot=last_snapshot.isoformat(),
    )
