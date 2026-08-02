import pytest

from research.evidence_consistency import verify_evidence_consistency


TRADES = (
    "closed_at,net_pnl,r_multiple,side\n"
    "2025-01-02T10:00:00+00:00,50,0.5,long\n"
    "2025-01-03T10:00:00+00:00,-25,-0.25,short\n"
)


def snapshots(first: str = "2025-01-02T09:00:00+00:00", last: str = "2025-01-03T11:00:00+00:00") -> str:
    return (
        "timestamp,balance,equity,margin_used,gross_exposure,open_positions\n"
        f"{first},10000,10000,0,0,0\n"
        f"{last},10025,10025,0,0,0\n"
    )


def test_accepts_snapshot_coverage_spanning_all_trade_closes():
    report = verify_evidence_consistency(TRADES, snapshots())

    assert report.trade_count == 2
    assert report.snapshot_count == 2
    assert report.first_trade_close == "2025-01-02T10:00:00+00:00"
    assert report.last_snapshot == "2025-01-03T11:00:00+00:00"


def test_rejects_snapshots_starting_after_first_trade():
    with pytest.raises(ValueError, match="starts after the first completed trade"):
        verify_evidence_consistency(
            TRADES,
            snapshots(first="2025-01-02T10:30:00+00:00"),
        )


def test_rejects_snapshots_ending_before_last_trade():
    with pytest.raises(ValueError, match="ends before the last completed trade"):
        verify_evidence_consistency(
            TRADES,
            snapshots(last="2025-01-03T09:30:00+00:00"),
        )


def test_rejects_zero_duration_snapshot_evidence():
    same = "2025-01-02T10:00:00+00:00"
    with pytest.raises(ValueError, match="strictly increasing|positive time interval"):
        verify_evidence_consistency(TRADES, snapshots(first=same, last=same))


def test_does_not_bypass_individual_csv_validation():
    bad_trades = TRADES.replace("2025-01-03T10:00:00+00:00", "2025-01-01T10:00:00+00:00")
    with pytest.raises(ValueError, match="ordered by closed_at ascending"):
        verify_evidence_consistency(bad_trades, snapshots())
