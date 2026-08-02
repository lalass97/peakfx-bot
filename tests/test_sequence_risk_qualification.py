import pytest

from research.block_size_sensitivity import (
    BlockSizeResult,
    BlockSizeSensitivityReport,
)
from research.sequence_risk_qualification import (
    SequenceRiskThresholds,
    qualify_sequence_risk,
)


def _result(
    size: int,
    *,
    p95: float = 0.15,
    p99: float = 0.22,
    ratio: float = 1.20,
    ruin: float = 0.01,
    terminal_p05: float = 9000.0,
) -> BlockSizeResult:
    return BlockSizeResult(
        block_size=size,
        p95_max_drawdown_fraction=p95,
        p99_max_drawdown_fraction=p99,
        median_max_drawdown_fraction=0.10,
        terminal_equity_p05=terminal_p05,
        terminal_equity_median=10000.0,
        terminal_equity_p95=11000.0,
        ruin_probability=ruin,
        historical_max_drawdown_fraction=0.125,
        p95_to_historical_ratio=ratio,
    )


def _report(results: tuple[BlockSizeResult, ...]) -> BlockSizeSensitivityReport:
    conservative = max(results, key=lambda item: item.p95_max_drawdown_fraction)
    return BlockSizeSensitivityReport(
        simulations_per_block_size=2000,
        trade_count=500,
        block_sizes=tuple(item.block_size for item in results),
        results=results,
        conservative_block_size=conservative.block_size,
        conservative_p95_max_drawdown_fraction=conservative.p95_max_drawdown_fraction,
        conservative_p99_max_drawdown_fraction=max(item.p99_max_drawdown_fraction for item in results),
        maximum_ruin_probability=max(item.ruin_probability for item in results),
        minimum_terminal_equity_p05=min(item.terminal_equity_p05 for item in results),
    )


def test_green_requires_sufficient_sweep_and_all_gates_to_pass():
    report = qualify_sequence_risk(
        _report(tuple(_result(size) for size in (5, 10, 20, 40))),
        initial_balance=10000.0,
    )

    assert report.decision == "green"
    assert report.failed_gates == ()
    assert report.evidence_gaps == ()


def test_any_measured_limit_breach_is_red():
    sensitivity = _report(
        (
            _result(5),
            _result(10, p95=0.24, p99=0.32, ratio=1.70, ruin=0.08, terminal_p05=7600.0),
            _result(20),
            _result(40),
        )
    )

    report = qualify_sequence_risk(sensitivity, initial_balance=10000.0)

    assert report.decision == "red"
    assert report.failed_gates == (
        "p95_drawdown",
        "p99_drawdown",
        "historical_drawdown_ratio",
        "ruin_probability",
        "terminal_equity_p05",
    )


def test_insufficient_block_size_count_is_inconclusive_not_green():
    report = qualify_sequence_risk(
        _report((_result(5), _result(10))),
        initial_balance=10000.0,
    )

    assert report.decision == "inconclusive"
    assert report.failed_gates == ()
    assert report.evidence_gaps == ("block_size_count",)


def test_exact_threshold_boundaries_pass():
    thresholds = SequenceRiskThresholds(
        maximum_p95_drawdown_fraction=0.20,
        maximum_p99_drawdown_fraction=0.30,
        maximum_p95_to_historical_ratio=1.50,
        maximum_ruin_probability=0.05,
        minimum_terminal_equity_p05_fraction=0.80,
        minimum_block_sizes=1,
    )
    sensitivity = _report(
        (_result(5, p95=0.20, p99=0.30, ratio=1.50, ruin=0.05, terminal_p05=8000.0),)
    )

    report = qualify_sequence_risk(
        sensitivity,
        initial_balance=10000.0,
        thresholds=thresholds,
    )

    assert report.decision == "green"


@pytest.mark.parametrize(
    "thresholds,message",
    [
        (SequenceRiskThresholds(maximum_p95_drawdown_fraction=-0.1), "maximum_p95_drawdown_fraction"),
        (SequenceRiskThresholds(maximum_p99_drawdown_fraction=1.1), "maximum_p99_drawdown_fraction"),
        (SequenceRiskThresholds(maximum_p95_to_historical_ratio=0.0), "maximum_p95_to_historical_ratio"),
        (SequenceRiskThresholds(maximum_ruin_probability=-0.1), "maximum_ruin_probability"),
        (SequenceRiskThresholds(minimum_terminal_equity_p05_fraction=1.1), "minimum_terminal_equity_p05_fraction"),
        (SequenceRiskThresholds(minimum_block_sizes=0), "minimum_block_sizes"),
    ],
)
def test_invalid_thresholds_fail_closed(thresholds, message):
    with pytest.raises(ValueError, match=message):
        qualify_sequence_risk(
            _report((_result(5),)),
            initial_balance=10000.0,
            thresholds=thresholds,
        )


def test_invalid_initial_balance_fails_closed():
    with pytest.raises(ValueError, match="initial_balance"):
        qualify_sequence_risk(_report((_result(5),)), initial_balance=0.0)
