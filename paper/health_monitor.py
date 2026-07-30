from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path

import pandas as pd

REQUIRED_COLUMNS = {
    "time",
    "event",
    "symbol",
    "magic",
    "ticket",
    "message",
}


@dataclass(frozen=True)
class HealthConfig:
    expected_symbol: str = "EURUSD"
    expected_magic: int = 26073001
    stale_after_minutes: int = 90
    max_rejections_24h: int = 3
    max_risk_blocks_24h: int = 20


@dataclass(frozen=True)
class HealthResult:
    status: str
    latest_event_time: str | None
    age_minutes: float | None
    rejected_orders_24h: int
    risk_blocks_24h: int
    duplicate_entry_tickets: list[int]
    unexpected_symbols: list[str]
    unexpected_magic_numbers: list[int]
    alerts: list[str]


def load_events(path: str | Path) -> pd.DataFrame:
    events = pd.read_csv(path)
    missing = REQUIRED_COLUMNS.difference(events.columns)
    if missing:
        raise ValueError(f"Missing event columns: {sorted(missing)}")

    events = events.copy()
    events["time"] = pd.to_datetime(events["time"], utc=True, errors="raise")
    events["event"] = events["event"].astype(str).str.strip().str.lower()
    events["symbol"] = events["symbol"].fillna("").astype(str).str.strip()
    events["magic"] = pd.to_numeric(events["magic"], errors="coerce").fillna(0).astype(int)
    events["ticket"] = pd.to_numeric(events["ticket"], errors="coerce").fillna(0).astype(int)
    return events.sort_values("time").drop_duplicates()


def evaluate_health(
    events: pd.DataFrame,
    cfg: HealthConfig = HealthConfig(),
    now: pd.Timestamp | None = None,
) -> HealthResult:
    if events.empty:
        return HealthResult(
            status="critical",
            latest_event_time=None,
            age_minutes=None,
            rejected_orders_24h=0,
            risk_blocks_24h=0,
            duplicate_entry_tickets=[],
            unexpected_symbols=[],
            unexpected_magic_numbers=[],
            alerts=["No telemetry events were found."],
        )

    now = pd.Timestamp.now(tz="UTC") if now is None else pd.Timestamp(now)
    if now.tzinfo is None:
        now = now.tz_localize("UTC")
    else:
        now = now.tz_convert("UTC")

    latest = events["time"].max()
    age_minutes = max(0.0, (now - latest).total_seconds() / 60.0)
    cutoff = now - pd.Timedelta(hours=24)
    recent = events.loc[events["time"] >= cutoff]

    rejected = int(recent["event"].isin({"order_rejected", "trade_rejected"}).sum())
    risk_blocks = int(recent["event"].isin({"risk_block", "daily_lock", "weekly_lock", "drawdown_lock"}).sum())

    entries = events.loc[events["event"].isin({"order_filled", "position_opened", "entry"}) & (events["ticket"] > 0)]
    duplicate_tickets = sorted(entries.loc[entries["ticket"].duplicated(keep=False), "ticket"].unique().tolist())

    symbols = sorted(s for s in events["symbol"].unique().tolist() if s and s != cfg.expected_symbol)
    magic_numbers = sorted(m for m in events["magic"].unique().tolist() if m not in {0, cfg.expected_magic})

    alerts: list[str] = []
    if age_minutes > cfg.stale_after_minutes:
        alerts.append(f"Telemetry is stale by {age_minutes:.1f} minutes.")
    if rejected > cfg.max_rejections_24h:
        alerts.append(f"Order rejections exceeded the 24-hour limit: {rejected}.")
    if risk_blocks > cfg.max_risk_blocks_24h:
        alerts.append(f"Risk blocks are unusually frequent: {risk_blocks} in 24 hours.")
    if duplicate_tickets:
        alerts.append(f"Duplicate entry tickets detected: {duplicate_tickets}.")
    if symbols:
        alerts.append(f"Unexpected symbols detected: {symbols}.")
    if magic_numbers:
        alerts.append(f"Unexpected magic numbers detected: {magic_numbers}.")

    if any("Duplicate" in alert or "Unexpected" in alert for alert in alerts):
        status = "critical"
    elif alerts:
        status = "warning"
    else:
        status = "healthy"

    return HealthResult(
        status=status,
        latest_event_time=latest.isoformat(),
        age_minutes=round(age_minutes, 2),
        rejected_orders_24h=rejected,
        risk_blocks_24h=risk_blocks,
        duplicate_entry_tickets=duplicate_tickets,
        unexpected_symbols=symbols,
        unexpected_magic_numbers=magic_numbers,
        alerts=alerts,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Check PeakFX paper-trading telemetry health")
    parser.add_argument("events_csv", type=Path)
    parser.add_argument("--output", type=Path, default=Path("reports/paper_health.json"))
    parser.add_argument("--stale-minutes", type=int, default=90)
    args = parser.parse_args()

    cfg = HealthConfig(stale_after_minutes=args.stale_minutes)
    result = evaluate_health(load_events(args.events_csv), cfg)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(asdict(result), indent=2), encoding="utf-8")
    print(json.dumps(asdict(result), indent=2))
    raise SystemExit(0 if result.status == "healthy" else 2)


if __name__ == "__main__":
    main()
