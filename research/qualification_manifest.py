from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime
from math import isfinite
from typing import Literal

ModelingMode = Literal["every_tick_based_on_real_ticks"]

_REQUIRED_KEYS = {
    "schema_version",
    "run_id",
    "strategy_id",
    "strategy_version",
    "source_commit_sha",
    "symbol",
    "timeframe",
    "period_start",
    "period_end",
    "modeling_mode",
    "broker",
    "account_currency",
    "initial_deposit",
    "leverage",
    "spread_points",
    "commission_per_lot",
    "slippage_points",
    "completed_trades_sha256",
    "open_equity_sha256",
}
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_COMMIT_SHA = re.compile(r"^[0-9a-f]{40}$")
_IDENTIFIER = re.compile(r"^[A-Za-z0-9._-]+$")


@dataclass(frozen=True)
class QualificationRunManifest:
    schema_version: int
    run_id: str
    strategy_id: str
    strategy_version: str
    source_commit_sha: str
    symbol: str
    timeframe: str
    period_start: str
    period_end: str
    modeling_mode: ModelingMode
    broker: str
    account_currency: str
    initial_deposit: float
    leverage: int
    spread_points: float
    commission_per_lot: float
    slippage_points: float
    completed_trades_sha256: str
    open_equity_sha256: str


def sha256_text(text: str) -> str:
    """Return a stable SHA-256 digest of the exact UTF-8 export text."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _timestamp(value: object, field: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty ISO-8601 timestamp")
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ValueError(f"{field} must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{field} must include a timezone")
    return parsed


def _identifier(value: object, field: str) -> str:
    if not isinstance(value, str) or not _IDENTIFIER.fullmatch(value):
        raise ValueError(f"{field} contains invalid characters")
    return value


def _finite_nonnegative(value: object, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field} must be numeric")
    parsed = float(value)
    if not isfinite(parsed) or parsed < 0:
        raise ValueError(f"{field} must be finite and non-negative")
    return parsed


def load_qualification_manifest(text: str) -> QualificationRunManifest:
    """Parse an exact, versioned research-run manifest without filling defaults."""
    try:
        raw = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError("manifest must be valid JSON") from exc
    if not isinstance(raw, dict):
        raise ValueError("manifest root must be an object")

    keys = set(raw)
    missing = sorted(_REQUIRED_KEYS - keys)
    extra = sorted(keys - _REQUIRED_KEYS)
    if missing:
        raise ValueError("manifest missing keys: " + ", ".join(missing))
    if extra:
        raise ValueError("manifest contains unknown keys: " + ", ".join(extra))

    if raw["schema_version"] != 1:
        raise ValueError("schema_version must be 1")
    if isinstance(raw["leverage"], bool) or not isinstance(raw["leverage"], int):
        raise ValueError("leverage must be an integer")
    if raw["leverage"] <= 0:
        raise ValueError("leverage must be positive")

    initial_deposit = _finite_nonnegative(raw["initial_deposit"], "initial_deposit")
    if initial_deposit <= 0:
        raise ValueError("initial_deposit must be positive")

    period_start = _timestamp(raw["period_start"], "period_start")
    period_end = _timestamp(raw["period_end"], "period_end")
    if period_end <= period_start:
        raise ValueError("period_end must be after period_start")

    source_commit_sha = raw["source_commit_sha"]
    if not isinstance(source_commit_sha, str) or not _COMMIT_SHA.fullmatch(source_commit_sha):
        raise ValueError("source_commit_sha must be a lowercase 40-character SHA")

    for field in ("completed_trades_sha256", "open_equity_sha256"):
        value = raw[field]
        if not isinstance(value, str) or not _SHA256.fullmatch(value):
            raise ValueError(f"{field} must be a lowercase SHA-256 digest")

    if raw["modeling_mode"] != "every_tick_based_on_real_ticks":
        raise ValueError("modeling_mode must be every_tick_based_on_real_ticks")

    broker = raw["broker"]
    if not isinstance(broker, str) or not broker.strip():
        raise ValueError("broker must be non-empty")

    currency = raw["account_currency"]
    if not isinstance(currency, str) or len(currency) != 3 or not currency.isalpha():
        raise ValueError("account_currency must be a three-letter code")

    return QualificationRunManifest(
        schema_version=1,
        run_id=_identifier(raw["run_id"], "run_id"),
        strategy_id=_identifier(raw["strategy_id"], "strategy_id"),
        strategy_version=_identifier(raw["strategy_version"], "strategy_version"),
        source_commit_sha=source_commit_sha,
        symbol=_identifier(raw["symbol"], "symbol").upper(),
        timeframe=_identifier(raw["timeframe"], "timeframe").upper(),
        period_start=period_start.isoformat(),
        period_end=period_end.isoformat(),
        modeling_mode="every_tick_based_on_real_ticks",
        broker=broker.strip(),
        account_currency=currency.upper(),
        initial_deposit=initial_deposit,
        leverage=raw["leverage"],
        spread_points=_finite_nonnegative(raw["spread_points"], "spread_points"),
        commission_per_lot=_finite_nonnegative(
            raw["commission_per_lot"], "commission_per_lot"
        ),
        slippage_points=_finite_nonnegative(raw["slippage_points"], "slippage_points"),
        completed_trades_sha256=raw["completed_trades_sha256"],
        open_equity_sha256=raw["open_equity_sha256"],
    )


def verify_manifest_exports(
    manifest: QualificationRunManifest,
    completed_trades_csv: str,
    open_equity_csv: str,
) -> None:
    """Reject evidence that does not exactly match the manifest fingerprints."""
    if sha256_text(completed_trades_csv) != manifest.completed_trades_sha256:
        raise ValueError("completed-trade export does not match manifest SHA-256")
    if sha256_text(open_equity_csv) != manifest.open_equity_sha256:
        raise ValueError("open-equity export does not match manifest SHA-256")
