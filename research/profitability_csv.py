from __future__ import annotations

import csv
import io
from datetime import datetime
from math import isfinite
from typing import Iterable

from research.profitability_qualification import TradeResult

_REQUIRED_COLUMNS = ("closed_at", "net_pnl", "r_multiple", "side")
_ALLOWED_SIDES = {"long", "short"}


def _parse_timestamp(value: str, row_number: int) -> datetime:
    text = value.strip()
    if not text:
        raise ValueError(f"row {row_number}: closed_at is required")
    normalized = text[:-1] + "+00:00" if text.endswith("Z") else text
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ValueError(
            f"row {row_number}: closed_at must be an ISO-8601 timestamp"
        ) from exc
    if parsed.tzinfo is None:
        raise ValueError(f"row {row_number}: closed_at must include a timezone")
    return parsed


def _parse_finite_float(value: str, field: str, row_number: int) -> float:
    text = value.strip()
    if not text:
        raise ValueError(f"row {row_number}: {field} is required")
    try:
        parsed = float(text)
    except ValueError as exc:
        raise ValueError(f"row {row_number}: {field} must be numeric") from exc
    if not isfinite(parsed):
        raise ValueError(f"row {row_number}: {field} must be finite")
    return parsed


def load_completed_trades_csv(text: str) -> tuple[TradeResult, ...]:
    """Load completed, cost-inclusive trades without sorting or altering them.

    Required columns are closed_at, net_pnl, r_multiple, and side. Input order is
    preserved because profitability drawdown must be evaluated sequentially.
    """
    if not text.strip():
        raise ValueError("CSV input is empty")

    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None:
        raise ValueError("CSV header is missing")

    fieldnames = tuple(name.strip() for name in reader.fieldnames)
    if len(fieldnames) != len(set(fieldnames)):
        raise ValueError("CSV header contains duplicate columns")

    missing = [name for name in _REQUIRED_COLUMNS if name not in fieldnames]
    if missing:
        raise ValueError(f"CSV missing required columns: {', '.join(missing)}")

    trades: list[TradeResult] = []
    previous_closed_at: datetime | None = None
    for row_number, row in enumerate(reader, start=2):
        if None in row:
            raise ValueError(f"row {row_number}: contains more values than the header")
        if all((value or "").strip() == "" for value in row.values()):
            raise ValueError(f"row {row_number}: blank rows are not allowed")

        closed_at = _parse_timestamp(row["closed_at"], row_number)
        if previous_closed_at is not None and closed_at < previous_closed_at:
            raise ValueError(
                f"row {row_number}: trades must be ordered by closed_at ascending"
            )
        previous_closed_at = closed_at

        side = row["side"].strip().lower()
        if side not in _ALLOWED_SIDES:
            raise ValueError(f"row {row_number}: side must be long or short")

        trades.append(
            TradeResult(
                net_pnl=_parse_finite_float(row["net_pnl"], "net_pnl", row_number),
                r_multiple=_parse_finite_float(
                    row["r_multiple"], "r_multiple", row_number
                ),
                side=side,
                year=closed_at.year,
            )
        )

    if not trades:
        raise ValueError("CSV contains no completed trades")
    return tuple(trades)


def render_trade_csv_template() -> str:
    """Return the exact header expected from an MT5/Python trade export."""
    return ",".join(_REQUIRED_COLUMNS) + "\n"
