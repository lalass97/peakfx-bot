import json

import pytest

from research.open_equity_risk import OpenRiskThresholds
from research.profitability_qualification import QualificationThresholds
from research.qualification_bundle import preflight_qualification_bundle
from research.qualification_manifest import sha256_text


TRADES = (
    "closed_at,net_pnl,r_multiple,side\n"
    "2025-01-02T10:00:00+00:00,50,0.5,long\n"
    "2025-01-03T10:00:00+00:00,50,0.5,short\n"
)
SNAPSHOTS = (
    "timestamp,balance,equity,margin_used,gross_exposure,open_positions\n"
    "2025-01-01T00:00:00+00:00,10000,9950,1000,5000,1\n"
    "2025-01-04T00:00:00+00:00,10100,10050,1000,5000,1\n"
)


def _manifest(**changes):
    value = {
        "schema_version": 1,
        "run_id": "baseline-001",
        "strategy_id": "PeakFX-Test4",
        "strategy_version": "1.42",
        "source_commit_sha": "a" * 40,
        "symbol": "EURUSD",
        "timeframe": "H1",
        "period_start": "2025-01-01T00:00:00+00:00",
        "period_end": "2025-01-04T00:00:00+00:00",
        "modeling_mode": "every_tick_based_on_real_ticks",
        "broker": "Test Broker",
        "account_currency": "USD",
        "initial_deposit": 10000,
        "leverage": 100,
        "spread_points": 15,
        "commission_per_lot": 7,
        "slippage_points": 2,
        "completed_trades_sha256": sha256_text(TRADES),
        "open_equity_sha256": sha256_text(SNAPSHOTS),
    }
    value.update(changes)
    return json.dumps(value)


PROFIT = QualificationThresholds(
    minimum_trades=2,
    minimum_profit_factor=1.2,
    minimum_expectancy_r=0.0,
    maximum_drawdown_r=2.0,
    minimum_profitable_year_fraction=1.0,
)
RISK = OpenRiskThresholds(
    minimum_snapshots=2,
    maximum_floating_drawdown_fraction=0.10,
    maximum_margin_utilization_fraction=0.30,
    maximum_gross_exposure_multiple=1.0,
    maximum_open_positions=1,
)


def test_accepts_one_complete_immutable_bundle():
    report = preflight_qualification_bundle(
        _manifest(), TRADES, SNAPSHOTS, PROFIT, RISK
    )

    assert report.manifest.run_id == "baseline-001"
    assert report.evidence.trade_count == 2
    assert report.evidence.snapshot_count == 2
    assert report.qualification.decision == "green"


def test_rejects_changed_export_before_scoring():
    changed = TRADES.replace("50,0.5,long", "51,0.5,long")

    with pytest.raises(ValueError, match="manifest SHA-256"):
        preflight_qualification_bundle(_manifest(), changed, SNAPSHOTS, PROFIT, RISK)


def test_rejects_snapshot_coverage_starting_after_manifest_period():
    late = SNAPSHOTS.replace(
        "2025-01-01T00:00:00+00:00", "2025-01-01T12:00:00+00:00"
    )

    with pytest.raises(ValueError, match="starts after the manifest test period"):
        preflight_qualification_bundle(
            _manifest(open_equity_sha256=sha256_text(late)),
            TRADES,
            late,
            PROFIT,
            RISK,
        )


def test_rejects_snapshot_coverage_ending_before_manifest_period():
    early = SNAPSHOTS.replace(
        "2025-01-04T00:00:00+00:00", "2025-01-03T12:00:00+00:00"
    )

    with pytest.raises(ValueError, match="ends before the manifest test period"):
        preflight_qualification_bundle(
            _manifest(open_equity_sha256=sha256_text(early)),
            TRADES,
            early,
            PROFIT,
            RISK,
        )
