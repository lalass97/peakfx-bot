from __future__ import annotations

import csv
import io
from datetime import datetime
from math import isfinite
from typing import Iterable, TextIO

from research.open_equity_risk import EquitySnapshot

EXPECTED_COLUMNS = (
    "timestamp",
    "balance",
    "equity",
    "margin_used",
    "gross_exposure",
    "open_positions",
)


def _parse_timestamp(raw: str, row_number: int) -> datetime:
    value = raw.strip()
    if not value:
        raise ValueError(f"row {row_number}: timestamp is required")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"row {row_number}: timestamp must be ISO-8601") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"row {row_number}: timestamp must include a timezone")
    return parsed


def _parse_finite_float(raw: str, field: str, row_number: int) -> float:
    value = raw.strip()
    if not value:
        raise ValueError(f"row {row_number}: {field} is required")
    try:
        parsed = float(value)
    except ValueError as exc:
        raise ValueError(f"row {row_number}: {field} must be numeric") from exc
    if not isfinite(parsed):
        raise ValueError(f"row {row_number}: {field} must be finite")
    return parsed


def _parse_open_positions(raw: str, row_number: int) -> int:
    value = raw.strip()
    if not value:
        raise ValueError(f"row {row_number}: open_positions is required")
    try:
        parsed = int(value)
    except ValueError as exc:
        raise ValueError(f"row {row_number}: open_positions must be an integer") from exc
    if str(parsed) != value and value not in {f"+{parsed}"}:
        raise ValueError(f"row {row_number}: open_positions must be an integer")
    return parsed


def load_open_equity_snapshots(source: str | TextIO) -> tuple[EquitySnapshot, ...]:
    """Load ordered mark-to-market snapshots without sorting or repairing input."""
    stream = io.StringIO(source) if isinstance(source, str) else source
    reader = csv.DictReader(stream)
    if reader.fieldnames is None:
        raise ValueError("CSV header is required")
    if tuple(reader.fieldnames) != EXPECTED_COLUMNS:
        raise ValueError(
            "CSV columns must exactly match: " + ",".join(EXPECTED_COLUMNS)
        )

    snapshots: list[EquitySnapshot] = []
    previous_timestamp: datetime | None = None
    for row_number, row in enumerate(reader, start=2):
        if None in row:
            raise ValueError(f"row {row_number}: unexpected extra columns")
        if all((value or "").strip() == "" for value in row.values()):
            raise ValueError(f"row {row_number}: blank rows are not allowed")

        timestamp = _parse_timestamp(row["timestamp"] or "", row_number)
        if previous_timestamp is not None and timestamp <= previous_timestamp:
            raise ValueError(
                f"row {row_number}: timestamps must be strictly increasing"
            )
        previous_timestamp = timestamp

        balance = _parse_finite_float(row["balance"] or "", "balance", row_number)
        equity = _parse_finite_float(row["equity"] or "", "equity", row_number)
        margin_used = _parse_finite_float(
            row["margin_used"] or "", "margin_used", row_number
        )
        gross_exposure = _parse_finite_float(
            row["gross_exposure"] or "", "gross_exposure", row_number
        )
        open_positions = _parse_open_positions(
            row["open_positions"] or "", row_number
        )

        if balance <= 0:
            raise ValueError(f"row {row_number}: balance must be positive")
        if equity < 0:
            raise ValueError(f"row {row_number}: equity cannot be negative")
        if margin_used < 0 or gross_exposure < 0:
            raise ValueError(
                f"row {row_number}: margin and exposure cannot be negative"
            )
        if open_positions < 0:
            raise ValueError(f"row {row_number}: open_positions cannot be negative")

        snapshots.append(
            EquitySnapshot(
                timestamp=timestamp.isoformat(),
                balance=balance,
                equity=equity,
                margin_used=margin_used,
                gross_exposure=gross_exposure,
                open_positions=open_positions,
            )
        )

    if not snapshots:
        raise ValueError("CSV must contain at least one snapshot")
    return tuple(snapshots)
