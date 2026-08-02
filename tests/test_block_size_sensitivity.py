import numpy as np
import pytest

from research.block_size_sensitivity import analyze_block_size_sensitivity


def test_reports_every_predeclared_size_and_conservative_maximum():
    trades = np.array([100.0, -80.0, 40.0, -60.0, 120.0, -50.0])

    report = analyze_block_size_sensitivity(
        trades,
        block_sizes=(1, 2, 3),
        simulations_per_block_size=200,
        initial_balance=1000.0,
        seed=7,
    )

    assert report.block_sizes == (1, 2, 3)
    assert tuple(result.block_size for result in report.results) == (1, 2, 3)
    assert report.conservative_p95_max_drawdown_fraction == max(
        result.p95_max_drawdown_fraction for result in report.results
    )
    assert report.conservative_block_size in report.block_sizes
    assert report.maximum_ruin_probability == max(
        result.ruin_probability for result in report.results
    )
    assert report.minimum_terminal_equity_p05 == min(
        result.terminal_equity_p05 for result in report.results
    )


def test_seed_is_deterministic_across_complete_sweep():
    trades = np.array([25.0, -10.0, 15.0, -20.0, 30.0, -5.0])
    kwargs = dict(
        block_sizes=(1, 2, 3),
        simulations_per_block_size=100,
        initial_balance=500.0,
        seed=11,
    )

    first = analyze_block_size_sensitivity(trades, **kwargs)
    second = analyze_block_size_sensitivity(trades, **kwargs)

    assert first == second


@pytest.mark.parametrize(
    "block_sizes,message",
    [
        ((), "must not be empty"),
        ((2, 1), "ascending"),
        ((1, 1), "duplicates"),
        ((0, 1), "between 1"),
        ((1, 7), "between 1"),
        ((1, 2.0), "integers"),
    ],
)
def test_invalid_block_size_declarations_fail_closed(block_sizes, message):
    trades = np.array([1.0, -1.0, 2.0, -2.0, 3.0, -3.0])

    with pytest.raises(ValueError, match=message):
        analyze_block_size_sensitivity(
            trades,
            block_sizes=block_sizes,
            simulations_per_block_size=10,
        )


@pytest.mark.parametrize(
    "kwargs,message",
    [
        ({"simulations_per_block_size": 0}, "simulations_per_block_size"),
        ({"initial_balance": 0.0}, "initial_balance"),
        ({"ruin_drawdown_fraction": 0.0}, "ruin_drawdown_fraction"),
        ({"seed": True}, "seed"),
    ],
)
def test_invalid_sweep_configuration_fails_closed(kwargs, message):
    trades = np.array([1.0, -1.0, 2.0, -2.0, 3.0, -3.0])

    with pytest.raises(ValueError, match=message):
        analyze_block_size_sensitivity(
            trades,
            block_sizes=(1, 2),
            **kwargs,
        )
