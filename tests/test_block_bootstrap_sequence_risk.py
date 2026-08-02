import numpy as np
import pytest

from research.block_bootstrap_sequence_risk import (
    BlockBootstrapConfig,
    analyze_block_bootstrap_sequence_risk,
    generate_circular_block_bootstrap_paths,
)


def test_paths_have_requested_shape_and_preserve_block_order():
    trades = np.array([1.0, 2.0, 3.0, 4.0])
    config = BlockBootstrapConfig(simulations=5, block_size=2, seed=7)

    paths = generate_circular_block_bootstrap_paths(trades, config)

    assert paths.shape == (5, 4)
    valid_pairs = {(1.0, 2.0), (2.0, 3.0), (3.0, 4.0), (4.0, 1.0)}
    for path in paths:
        assert tuple(path[:2]) in valid_pairs
        assert tuple(path[2:4]) in valid_pairs


def test_seed_makes_paths_deterministic():
    trades = np.array([10.0, -5.0, 7.0, -2.0])
    config = BlockBootstrapConfig(simulations=20, block_size=2, seed=11)

    first = generate_circular_block_bootstrap_paths(trades, config)
    second = generate_circular_block_bootstrap_paths(trades, config)

    np.testing.assert_array_equal(first, second)


def test_report_calculates_drawdown_terminal_equity_and_ratio():
    trades = np.array([100.0, -250.0, 75.0, -50.0, 150.0])
    config = BlockBootstrapConfig(
        simulations=200,
        block_size=2,
        initial_balance=1000.0,
        ruin_drawdown_fraction=0.50,
        seed=3,
    )

    report = analyze_block_bootstrap_sequence_risk(trades, config)

    assert report.trade_count == 5
    assert report.max_drawdown_fraction.shape == (200,)
    assert report.terminal_equity.shape == (200,)
    assert 0.0 <= report.ruin_probability <= 1.0
    assert report.p95_max_drawdown_fraction >= 0.0
    assert report.mdd_ratio >= 0.0


def test_block_bootstrap_can_change_terminal_equity():
    trades = np.array([100.0, -50.0, 25.0, -10.0])
    config = BlockBootstrapConfig(simulations=500, block_size=2, seed=8)

    report = analyze_block_bootstrap_sequence_risk(trades, config)

    assert np.unique(report.terminal_equity).size > 1


@pytest.mark.parametrize(
    "trades,config,message",
    [
        (np.array([1.0]), BlockBootstrapConfig(), "at least two"),
        (np.array([1.0, np.nan]), BlockBootstrapConfig(block_size=2), "finite"),
        (
            np.array([1.0, 2.0]),
            BlockBootstrapConfig(simulations=0, block_size=2),
            "simulations",
        ),
        (np.array([1.0, 2.0]), BlockBootstrapConfig(block_size=3), "block_size"),
        (
            np.array([1.0, 2.0]),
            BlockBootstrapConfig(block_size=2, initial_balance=0),
            "initial_balance",
        ),
        (
            np.array([1.0, 2.0]),
            BlockBootstrapConfig(block_size=2, ruin_drawdown_fraction=0),
            "ruin_drawdown_fraction",
        ),
    ],
)
def test_invalid_inputs_fail_closed(trades, config, message):
    with pytest.raises(ValueError, match=message):
        analyze_block_bootstrap_sequence_risk(trades, config)
