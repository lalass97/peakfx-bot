import json

import pytest

from research.qualification_manifest import (
    load_qualification_manifest,
    sha256_text,
    verify_manifest_exports,
)


TRADES = "closed_at,net_pnl,r_multiple,side\n2025-01-02T10:00:00+00:00,50,0.5,long\n"
SNAPSHOTS = "timestamp,balance,equity,margin_used,gross_exposure,open_positions\n2025-01-02T10:00:00+00:00,10000,9950,1000,5000,1\n"


def _manifest(**overrides):
    data = {
        "schema_version": 1,
        "run_id": "eurusd-h1-2025-baseline",
        "strategy_id": "peakfx-pullback",
        "strategy_version": "1.42",
        "source_commit_sha": "a" * 40,
        "symbol": "eurusd",
        "timeframe": "h1",
        "period_start": "2025-01-01T00:00:00+00:00",
        "period_end": "2025-12-31T23:59:59+00:00",
        "modeling_mode": "every_tick_based_on_real_ticks",
        "broker": "Demo Broker",
        "account_currency": "usd",
        "initial_deposit": 10000,
        "leverage": 100,
        "spread_points": 15,
        "commission_per_lot": 7.0,
        "slippage_points": 2,
        "completed_trades_sha256": sha256_text(TRADES),
        "open_equity_sha256": sha256_text(SNAPSHOTS),
    }
    data.update(overrides)
    return json.dumps(data)


def test_loads_complete_manifest_and_normalizes_codes():
    manifest = load_qualification_manifest(_manifest())

    assert manifest.symbol == "EURUSD"
    assert manifest.timeframe == "H1"
    assert manifest.account_currency == "USD"
    assert manifest.initial_deposit == 10000.0
    verify_manifest_exports(manifest, TRADES, SNAPSHOTS)


def test_export_fingerprints_bind_exact_bytes():
    manifest = load_qualification_manifest(_manifest())

    with pytest.raises(ValueError, match="completed-trade export"):
        verify_manifest_exports(manifest, TRADES + "\n", SNAPSHOTS)
    with pytest.raises(ValueError, match="open-equity export"):
        verify_manifest_exports(manifest, TRADES, SNAPSHOTS.replace("9950", "9949"))


def test_rejects_missing_and_unknown_keys_instead_of_filling_defaults():
    raw = json.loads(_manifest())
    del raw["commission_per_lot"]
    with pytest.raises(ValueError, match="missing keys: commission_per_lot"):
        load_qualification_manifest(json.dumps(raw))

    raw = json.loads(_manifest())
    raw["optimized_after_test"] = True
    with pytest.raises(ValueError, match="unknown keys: optimized_after_test"):
        load_qualification_manifest(json.dumps(raw))


@pytest.mark.parametrize(
    "field,value,match",
    [
        ("schema_version", 2, "schema_version"),
        ("source_commit_sha", "ABC", "source_commit_sha"),
        ("modeling_mode", "open_prices_only", "modeling_mode"),
        ("initial_deposit", 0, "initial_deposit"),
        ("leverage", 0, "leverage"),
        ("spread_points", -1, "spread_points"),
        ("commission_per_lot", float("nan"), "commission_per_lot"),
        ("slippage_points", -0.1, "slippage_points"),
        ("account_currency", "US", "account_currency"),
    ],
)
def test_rejects_invalid_research_conditions(field, value, match):
    with pytest.raises(ValueError, match=match):
        load_qualification_manifest(_manifest(**{field: value}))


def test_rejects_timezone_free_or_reversed_period():
    with pytest.raises(ValueError, match="period_start must include a timezone"):
        load_qualification_manifest(_manifest(period_start="2025-01-01T00:00:00"))

    with pytest.raises(ValueError, match="period_end must be after period_start"):
        load_qualification_manifest(
            _manifest(
                period_start="2025-12-31T23:59:59+00:00",
                period_end="2025-01-01T00:00:00+00:00",
            )
        )


def test_rejects_invalid_json_and_non_object_root():
    with pytest.raises(ValueError, match="valid JSON"):
        load_qualification_manifest("{")
    with pytest.raises(ValueError, match="root must be an object"):
        load_qualification_manifest("[]")
