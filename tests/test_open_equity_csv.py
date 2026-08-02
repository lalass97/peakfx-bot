import pytest

from research.open_equity_csv import load_open_equity_snapshots


VALID = """timestamp,balance,equity,margin_used,gross_exposure,open_positions
2025-01-02T10:00:00+00:00,10000,9950,250,5000,1
2025-01-02T11:00:00+00:00,10020,10010,200,4000,1
"""


def test_loads_ordered_snapshots_and_normalizes_timestamp():
    snapshots = load_open_equity_snapshots(VALID)

    assert len(snapshots) == 2
    assert snapshots[0].timestamp == "2025-01-02T10:00:00+00:00"
    assert snapshots[0].balance == 10000
    assert snapshots[0].equity == 9950
    assert snapshots[0].open_positions == 1


def test_requires_exact_column_order_and_names():
    csv_text = "balance,timestamp,equity,margin_used,gross_exposure,open_positions\n10000,2025-01-02T10:00:00+00:00,9950,250,5000,1\n"

    with pytest.raises(ValueError, match="columns must exactly match"):
        load_open_equity_snapshots(csv_text)


@pytest.mark.parametrize(
    "timestamp",
    ["2025-01-02T10:00:00", "not-a-time", ""],
)
def test_rejects_missing_invalid_or_timezone_free_timestamps(timestamp):
    csv_text = f"timestamp,balance,equity,margin_used,gross_exposure,open_positions\n{timestamp},10000,9950,250,5000,1\n"

    with pytest.raises(ValueError, match="timestamp"):
        load_open_equity_snapshots(csv_text)


def test_rejects_duplicate_or_descending_timestamps_without_sorting():
    duplicate = VALID.replace("2025-01-02T11:00:00+00:00", "2025-01-02T10:00:00+00:00")
    descending = VALID.replace("2025-01-02T11:00:00+00:00", "2025-01-02T09:00:00+00:00")

    with pytest.raises(ValueError, match="strictly increasing"):
        load_open_equity_snapshots(duplicate)
    with pytest.raises(ValueError, match="strictly increasing"):
        load_open_equity_snapshots(descending)


@pytest.mark.parametrize("bad", ["nan", "inf", "-inf", "abc", ""])
def test_rejects_nonfinite_or_invalid_numeric_values(bad):
    csv_text = f"timestamp,balance,equity,margin_used,gross_exposure,open_positions\n2025-01-02T10:00:00+00:00,10000,{bad},250,5000,1\n"

    with pytest.raises(ValueError, match="equity"):
        load_open_equity_snapshots(csv_text)


@pytest.mark.parametrize("bad", ["1.0", "1.5", "abc", ""])
def test_rejects_noninteger_position_counts(bad):
    csv_text = f"timestamp,balance,equity,margin_used,gross_exposure,open_positions\n2025-01-02T10:00:00+00:00,10000,9950,250,5000,{bad}\n"

    with pytest.raises(ValueError, match="open_positions"):
        load_open_equity_snapshots(csv_text)


def test_rejects_negative_risk_values():
    csv_text = "timestamp,balance,equity,margin_used,gross_exposure,open_positions\n2025-01-02T10:00:00+00:00,10000,9950,-1,5000,1\n"

    with pytest.raises(ValueError, match="cannot be negative"):
        load_open_equity_snapshots(csv_text)


def test_rejects_blank_rows_and_empty_files():
    with pytest.raises(ValueError, match="blank rows"):
        load_open_equity_snapshots(VALID + ",,,,,\n")

    with pytest.raises(ValueError, match="at least one snapshot"):
        load_open_equity_snapshots(
            "timestamp,balance,equity,margin_used,gross_exposure,open_positions\n"
        )


def test_rejects_extra_columns():
    csv_text = "timestamp,balance,equity,margin_used,gross_exposure,open_positions\n2025-01-02T10:00:00+00:00,10000,9950,250,5000,1,extra\n"

    with pytest.raises(ValueError, match="extra columns"):
        load_open_equity_snapshots(csv_text)
