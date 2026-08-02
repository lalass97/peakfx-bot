import pandas as pd
import pytest

from research.stratified_trade_diagnostics import analyze_stratified_trades


def _frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "closed_at": [
                "2024-01-02T10:00:00+00:00",
                "2024-02-02T10:00:00+00:00",
                "2025-01-02T10:00:00+00:00",
                "2025-02-02T10:00:00+00:00",
            ],
            "net_pnl": [100.0, -50.0, 25.0, -100.0],
            "side": ["long", "short", "long", "short"],
        }
    )


def test_reports_direction_and_year_asymmetry():
    report = analyze_stratified_trades(_frame())

    assert report.overall_net_pnl == -25.0
    assert report.weakest_side == "short"
    assert report.weakest_year == "2025"
    assert {result.segment for result in report.by_side} == {"long", "short"}
    short = next(result for result in report.by_side if result.segment == "short")
    assert short.trades == 2
    assert short.net_pnl == -150.0
    assert short.win_rate == 0.0


def test_input_order_is_not_repaired():
    frame = _frame().iloc[::-1].reset_index(drop=True)
    with pytest.raises(ValueError, match="ordered by closed_at ascending"):
        analyze_stratified_trades(frame)


@pytest.mark.parametrize(
    "mutation,message",
    [
        (lambda frame: frame.drop(columns=["side"]), "missing required columns"),
        (lambda frame: frame.iloc[0:0], "must not be empty"),
        (lambda frame: frame.assign(side=["long", "flat", "long", "short"]), "long or short"),
        (lambda frame: frame.assign(net_pnl=[100.0, "bad", 25.0, -100.0]), "Unable to parse"),
    ],
)
def test_malformed_inputs_fail_closed(mutation, message):
    with pytest.raises((ValueError, TypeError), match=message):
        analyze_stratified_trades(mutation(_frame()))
