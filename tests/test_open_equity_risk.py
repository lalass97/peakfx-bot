import pytest

from research.open_equity_risk import (
    EquitySnapshot,
    OpenRiskThresholds,
    qualify_open_risk,
)


def snapshot(**overrides):
    values = dict(
        timestamp="2026-01-01T00:00:00+00:00",
        balance=10_000.0,
        equity=9_800.0,
        margin_used=500.0,
        gross_exposure=5_000.0,
        open_positions=1,
    )
    values.update(overrides)
    return EquitySnapshot(**values)


def test_green_when_all_open_risk_gates_pass():
    report = qualify_open_risk([snapshot()] * 100)
    assert report.decision == "green"
    assert report.failed_gates == ()


def test_small_sample_is_inconclusive_even_when_safe():
    report = qualify_open_risk([snapshot()] * 99)
    assert report.decision == "inconclusive"
    assert "minimum_snapshots" in report.failed_gates


def test_smooth_balance_cannot_hide_floating_drawdown():
    snapshots = [snapshot()] * 99 + [snapshot(equity=8_500.0)]
    report = qualify_open_risk(snapshots)
    assert report.decision == "red"
    assert "floating_drawdown" in report.failed_gates


def test_excess_margin_utilization_is_red():
    snapshots = [snapshot(margin_used=3_100.0)] * 100
    report = qualify_open_risk(snapshots)
    assert report.decision == "red"
    assert "margin_utilization" in report.failed_gates


def test_grid_like_position_accumulation_is_red():
    snapshots = [snapshot(open_positions=4, gross_exposure=15_000.0)] * 100
    report = qualify_open_risk(snapshots)
    assert report.decision == "red"
    assert "open_positions" in report.failed_gates
    assert "gross_exposure" in report.failed_gates


def test_exact_boundaries_are_accepted():
    thresholds = OpenRiskThresholds(minimum_snapshots=1)
    report = qualify_open_risk([
        snapshot(
            equity=9_000.0,
            margin_used=2_700.0,
            gross_exposure=9_000.0,
            open_positions=1,
        )
    ], thresholds)
    assert report.decision == "green"


@pytest.mark.parametrize(
    "bad",
    [
        snapshot(balance=0.0),
        snapshot(equity=-1.0),
        snapshot(margin_used=-1.0),
        snapshot(gross_exposure=-1.0),
        snapshot(open_positions=-1),
        snapshot(equity=float("nan")),
    ],
)
def test_invalid_snapshots_fail_closed(bad):
    with pytest.raises(ValueError):
        qualify_open_risk([bad], OpenRiskThresholds(minimum_snapshots=1))
