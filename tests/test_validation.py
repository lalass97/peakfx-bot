import numpy as np
import pandas as pd

from research.backtest_eurusd_h1 import Config
from research.validation import (
    monte_carlo_trade_paths,
    parameter_sensitivity,
    validation_summary,
    walk_forward_validate,
)


def sample_bars(rows: int = 800) -> pd.DataFrame:
    idx = pd.date_range("2024-01-01", periods=rows, freq="h", tz="UTC")
    close = 1.08 + np.linspace(0, 0.025, rows) + np.sin(np.arange(rows) / 9) * 0.002
    return pd.DataFrame(
        {
            "open": close - 0.0001,
            "high": close + 0.0006,
            "low": close - 0.0006,
            "close": close,
        },
        index=idx,
    )


def test_walk_forward_windows_do_not_overlap_future_training_data() -> None:
    result = walk_forward_validate(sample_bars(), Config(), train_bars=400, test_bars=100)
    assert len(result) == 4
    assert (result["train_end"] < result["test_start"]).all()
    assert (result["test_start"].shift(-1).dropna() > result["test_start"].iloc[:-1].to_numpy()).all()


def test_parameter_sensitivity_declares_each_configuration() -> None:
    result = parameter_sensitivity(
        sample_bars(),
        Config(),
        fast_values=(10, 12),
        slow_values=(45, 50),
        atr_values=(1.25, 1.5),
    )
    assert len(result) == 8
    assert {"fast_ema", "slow_ema", "atr_stop_multiplier", "max_drawdown_pct"}.issubset(result.columns)


def test_monte_carlo_is_reproducible_and_preserves_trade_count() -> None:
    trades = pd.DataFrame({"pnl": [25.0, -15.0, 40.0, -10.0]})
    first = monte_carlo_trade_paths(trades, 10_000.0, simulations=50, seed=7)
    second = monte_carlo_trade_paths(trades, 10_000.0, simulations=50, seed=7)
    pd.testing.assert_frame_equal(first, second)
    assert len(first) == 50
    assert (first["max_drawdown_pct"] <= 0).all()


def test_validation_summary_handles_empty_inputs() -> None:
    summary = validation_summary(pd.DataFrame(), pd.DataFrame())
    assert summary["walk_forward_windows"] == 0.0
    assert summary["profitable_windows_pct"] == 0.0
