from math import isinf

import pytest

from research.profitability_qualification import (
    QualificationThresholds,
    TradeResult,
    qualify_profitability,
)


def _trade(r: float, *, year: int, side: str = "long") -> TradeResult:
    return TradeResult(net_pnl=r * 100.0, r_multiple=r, side=side, year=year)


def test_small_sample_is_inconclusive_even_when_profitable() -> None:
    trades = [_trade(0.5, year=2024) for _ in range(20)]
    report = qualify_profitability(trades)
    assert report.decision == "inconclusive"
    assert "minimum_trades" in report.failed_gates


def test_green_requires_all_explicit_gates() -> None:
    trades = []
    for year in (2021, 2022, 2023, 2024, 2025):
        for index in range(20):
            r = 1.0 if index % 2 == 0 else -0.5
            trades.append(_trade(r, year=year, side="long" if index % 4 < 2 else "short"))
    report = qualify_profitability(trades)
    assert report.decision == "green"
    assert report.trade_count == 100
    assert report.profit_factor == pytest.approx(2.0)
    assert report.expectancy_r == pytest.approx(0.25)
    assert report.failed_gates == ()


def test_positive_net_result_can_still_be_red_on_profit_factor() -> None:
    trades = [_trade(1.0, year=2024) for _ in range(51)] + [
        _trade(-1.0, year=2024) for _ in range(49)
    ]
    report = qualify_profitability(trades)
    assert report.net_r > 0
    assert report.decision == "red"
    assert "profit_factor" in report.failed_gates


def test_drawdown_uses_original_trade_sequence() -> None:
    trades = [_trade(1.0, year=2024) for _ in range(50)]
    trades += [_trade(-1.0, year=2024) for _ in range(11)]
    trades += [_trade(1.0, year=2024) for _ in range(39)]
    report = qualify_profitability(trades)
    assert report.maximum_drawdown_r == pytest.approx(11.0)
    assert "maximum_drawdown" in report.failed_gates


def test_year_stability_blocks_one_period_wonder() -> None:
    trades = []
    for year in (2021, 2022, 2023, 2024):
        trades.extend(_trade(-0.1, year=year) for _ in range(20))
    trades.extend(_trade(2.0, year=2025) for _ in range(20))
    report = qualify_profitability(trades)
    assert report.net_r > 0
    assert report.profitable_year_fraction == pytest.approx(0.2)
    assert report.decision == "red"
    assert "year_stability" in report.failed_gates


def test_direction_gate_can_expose_profitable_long_and_losing_short() -> None:
    trades = []
    for index in range(50):
        trades.append(_trade(1.0 if index % 2 == 0 else -0.25, year=2024, side="long"))
        trades.append(_trade(0.25 if index % 2 == 0 else -0.5, year=2024, side="short"))
    thresholds = QualificationThresholds(
        minimum_profit_factor=1.0,
        minimum_profitable_year_fraction=0.0,
        require_both_directions_positive=True,
    )
    report = qualify_profitability(trades, thresholds)
    assert report.long_expectancy_r is not None and report.long_expectancy_r > 0
    assert report.short_expectancy_r is not None and report.short_expectancy_r < 0
    assert report.decision == "red"
    assert "short_expectancy" in report.failed_gates


def test_no_losses_produces_infinite_profit_factor() -> None:
    trades = [_trade(0.2, year=2024) for _ in range(100)]
    report = qualify_profitability(trades)
    assert isinf(report.profit_factor)


def test_empty_results_are_inconclusive() -> None:
    report = qualify_profitability([])
    assert report.decision == "inconclusive"
    assert report.trade_count == 0
