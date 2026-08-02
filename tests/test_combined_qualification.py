from research.combined_qualification import qualify_exported_run
from research.open_equity_risk import OpenRiskThresholds
from research.profitability_qualification import QualificationThresholds


PROFIT_THRESHOLDS = QualificationThresholds(
    minimum_trades=2,
    minimum_profit_factor=1.20,
    minimum_expectancy_r=0.0,
    maximum_drawdown_r=2.0,
    minimum_profitable_year_fraction=1.0,
)
RISK_THRESHOLDS = OpenRiskThresholds(
    minimum_snapshots=2,
    maximum_floating_drawdown_fraction=0.10,
    maximum_margin_utilization_fraction=0.30,
    maximum_gross_exposure_multiple=1.0,
    maximum_open_positions=1,
)


def _trades(second_r: float = 0.5, second_pnl: float = 50.0) -> str:
    return (
        "closed_at,net_pnl,r_multiple,side\n"
        "2025-01-02T10:00:00+00:00,50,0.5,long\n"
        f"2025-01-03T10:00:00+00:00,{second_pnl},{second_r},short\n"
    )


def _snapshots(second_equity: float = 10050, second_positions: int = 1) -> str:
    return (
        "timestamp,balance,equity,margin_used,gross_exposure,open_positions\n"
        "2025-01-02T10:00:00+00:00,10000,9950,1000,5000,1\n"
        f"2025-01-03T10:00:00+00:00,10100,{second_equity},1000,5000,{second_positions}\n"
    )


def test_green_requires_both_sections_green():
    report = qualify_exported_run(
        _trades(), _snapshots(), PROFIT_THRESHOLDS, RISK_THRESHOLDS
    )

    assert report.decision == "green"
    assert report.failed_sections == ()


def test_profitable_closed_trades_cannot_hide_open_risk_failure():
    report = qualify_exported_run(
        _trades(),
        _snapshots(second_equity=8000, second_positions=3),
        PROFIT_THRESHOLDS,
        RISK_THRESHOLDS,
    )

    assert report.profitability.decision == "green"
    assert report.open_risk.decision == "red"
    assert report.decision == "red"
    assert report.failed_sections == ("open_risk",)


def test_safe_open_equity_cannot_hide_unprofitable_trades():
    report = qualify_exported_run(
        _trades(second_r=-1.0, second_pnl=-100.0),
        _snapshots(),
        PROFIT_THRESHOLDS,
        RISK_THRESHOLDS,
    )

    assert report.profitability.decision == "red"
    assert report.open_risk.decision == "green"
    assert report.decision == "red"
    assert report.failed_sections == ("profitability",)


def test_any_insufficient_section_makes_combined_result_inconclusive():
    report = qualify_exported_run(
        _trades(),
        _snapshots(),
        QualificationThresholds(
            minimum_trades=3,
            minimum_profit_factor=1.20,
            maximum_drawdown_r=2.0,
            minimum_profitable_year_fraction=1.0,
        ),
        RISK_THRESHOLDS,
    )

    assert report.profitability.decision == "inconclusive"
    assert report.open_risk.decision == "green"
    assert report.decision == "inconclusive"
    assert report.failed_sections == ("profitability",)


def test_malformed_input_is_not_repaired_or_scored():
    bad_trades = (
        "closed_at,net_pnl,r_multiple,side\n"
        "2025-01-03T10:00:00+00:00,50,0.5,long\n"
        "2025-01-02T10:00:00+00:00,50,0.5,short\n"
    )

    try:
        qualify_exported_run(
            bad_trades, _snapshots(), PROFIT_THRESHOLDS, RISK_THRESHOLDS
        )
    except ValueError as exc:
        assert "ordered by closed_at ascending" in str(exc)
    else:
        raise AssertionError("out-of-order input must be rejected")
