from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from research.backtest_eurusd_h1 import Config
from research.robustness_audit import (
    block_bootstrap_expectancy,
    bootstrap_expectancy,
    cost_stress_test,
    period_stability,
    remove_best_trades,
    walk_forward_efficiency,
)


def sample_bars(rows: int = 800) -> pd.DataFrame:
    index = pd.date_range("2024-01-01", periods=rows, freq="h", tz="UTC")
    trend = np.linspace(1.08, 1.12, rows)
    wave = np.sin(np.arange(rows) / 15.0) * 0.002
    close = trend + wave
    return pd.DataFrame(
        {
            "open": close - 0.0001,
            "high": close + 0.0008,
            "low": close - 0.0008,
            "close": close,
        },
        index=index,
    )


def sample_trades() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "exit_time": pd.to_datetime(
                ["2024-01-15", "2024-02-15", "2024-04-15", "2024-07-15", "2024-10-15"], utc=True
            ),
            "pnl": [100.0, -50.0, 80.0, -40.0, 60.0],
        }
    )


def test_cost_stress_uses_declared_multipliers() -> None:
    result = cost_stress_test(sample_bars(), Config(), multipliers=(1.0, 2.0, 3.0))
    assert result["cost_multiplier"].tolist() == [1.0, 2.0, 3.0]
    assert result["spread_pips"].tolist() == [1.0, 2.0, 3.0]
    assert result["slippage_pips"].tolist() == pytest.approx([0.2, 0.4, 0.6])


def test_remove_best_trades_reduces_pnl() -> None:
    result = remove_best_trades(sample_trades(), counts=(0, 1, 3))
    assert result.loc[0, "net_pnl"] == 150.0
    assert result.loc[1, "net_pnl"] == 50.0
    assert result.loc[2, "remaining_trades"] == 2


def test_bootstrap_is_reproducible_and_bounded() -> None:
    first = bootstrap_expectancy(sample_trades(), simulations=1_000, seed=7)
    second = bootstrap_expectancy(sample_trades(), simulations=1_000, seed=7)
    assert first == second
    assert first["ci_low"] <= first["mean_expectancy"] <= first["ci_high"]
    assert 0.0 <= first["probability_positive"] <= 1.0


def test_block_bootstrap_preserves_valid_contract() -> None:
    result = block_bootstrap_expectancy(sample_trades(), block_size=2, simulations=500, seed=9)
    assert result["block_size"] == 2.0
    assert result["ci_low"] <= result["ci_high"]
    assert 0.0 <= result["probability_positive"] <= 1.0


def test_period_stability_groups_by_quarter() -> None:
    result = period_stability(sample_trades())
    assert result["period"].tolist() == ["2024Q1", "2024Q2", "2024Q3", "2024Q4"]
    assert int(result.loc[0, "trades"]) == 2


def test_walk_forward_efficiency_requires_positive_in_sample_return() -> None:
    assert walk_forward_efficiency(10.0, 5.0) == 50.0
    assert np.isnan(walk_forward_efficiency(0.0, 5.0))
    assert np.isnan(walk_forward_efficiency(-2.0, 5.0))


def test_invalid_inputs_are_rejected() -> None:
    with pytest.raises(ValueError):
        bootstrap_expectancy(sample_trades(), simulations=0)
    with pytest.raises(ValueError):
        block_bootstrap_expectancy(sample_trades(), block_size=0)
    with pytest.raises(ValueError):
        cost_stress_test(sample_bars(), Config(), multipliers=(0.0,))
