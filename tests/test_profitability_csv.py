import pytest

from research.profitability_csv import (
    load_completed_trades_csv,
    render_trade_csv_template,
)


def test_loads_cost_inclusive_trades_in_original_order():
    trades = load_completed_trades_csv(
        "closed_at,net_pnl,r_multiple,side\n"
        "2024-01-02T10:00:00+00:00,25.50,0.50,LONG\n"
        "2024-01-03T11:30:00+00:00,-10.25,-0.20,short\n"
    )

    assert [trade.net_pnl for trade in trades] == [25.50, -10.25]
    assert [trade.r_multiple for trade in trades] == [0.50, -0.20]
    assert [trade.side for trade in trades] == ["long", "short"]
    assert [trade.year for trade in trades] == [2024, 2024]


def test_accepts_zulu_timestamp_and_derives_year():
    trade = load_completed_trades_csv(
        "closed_at,net_pnl,r_multiple,side\n"
        "2025-12-31T23:59:59Z,1.0,0.1,long\n"
    )[0]

    assert trade.year == 2025


def test_rejects_missing_required_column():
    with pytest.raises(ValueError, match="missing required columns: r_multiple"):
        load_completed_trades_csv(
            "closed_at,net_pnl,side\n"
            "2024-01-02T10:00:00+00:00,10,long\n"
        )


def test_rejects_naive_timestamp():
    with pytest.raises(ValueError, match="must include a timezone"):
        load_completed_trades_csv(
            "closed_at,net_pnl,r_multiple,side\n"
            "2024-01-02T10:00:00,10,0.2,long\n"
        )


def test_rejects_out_of_order_trades_instead_of_sorting_them():
    with pytest.raises(ValueError, match="ordered by closed_at ascending"):
        load_completed_trades_csv(
            "closed_at,net_pnl,r_multiple,side\n"
            "2024-01-03T10:00:00+00:00,10,0.2,long\n"
            "2024-01-02T10:00:00+00:00,-5,-0.1,short\n"
        )


def test_rejects_non_finite_numbers():
    with pytest.raises(ValueError, match="net_pnl must be finite"):
        load_completed_trades_csv(
            "closed_at,net_pnl,r_multiple,side\n"
            "2024-01-02T10:00:00+00:00,nan,0.2,long\n"
        )


def test_rejects_invalid_side():
    with pytest.raises(ValueError, match="side must be long or short"):
        load_completed_trades_csv(
            "closed_at,net_pnl,r_multiple,side\n"
            "2024-01-02T10:00:00+00:00,10,0.2,buy\n"
        )


def test_rejects_blank_rows():
    with pytest.raises(ValueError, match="blank rows are not allowed"):
        load_completed_trades_csv(
            "closed_at,net_pnl,r_multiple,side\n"
            "2024-01-02T10:00:00+00:00,10,0.2,long\n"
            ",,,\n"
        )


def test_rejects_empty_trade_file():
    with pytest.raises(ValueError, match="contains no completed trades"):
        load_completed_trades_csv("closed_at,net_pnl,r_multiple,side\n")


def test_template_matches_required_schema():
    assert render_trade_csv_template() == "closed_at,net_pnl,r_multiple,side\n"
