import numpy as np
import pandas as pd
import pytest

from research.backtest_eurusd_h1 import (
    Config,
    _max_consecutive_losses,
    add_indicators,
    create_signals,
    run_backtest,
    summarize,
)


def sample_bars(rows: int = 400) -> pd.DataFrame:
    idx = pd.date_range("2024-01-01", periods=rows, freq="h", tz="UTC")
    close = 1.08 + np.linspace(0, 0.03, rows) + np.sin(np.arange(rows) / 8) * 0.002
    return pd.DataFrame(
        {
            "open": close - 0.0001,
            "high": close + 0.0005,
            "low": close - 0.0005,
            "close": close,
        },
        index=idx,
    )


def test_signal_columns_are_boolean() -> None:
    result = create_signals(add_indicators(sample_bars(), Config())).dropna()
    assert result["long_signal"].dtype == bool
    assert result["short_signal"].dtype == bool


def test_signals_do_not_depend_on_future_rows() -> None:
    bars = sample_bars()
    cutoff = 300
    short = create_signals(add_indicators(bars.iloc[:cutoff], Config()))
    full = create_signals(add_indicators(bars, Config())).iloc[:cutoff]
    pd.testing.assert_series_equal(short["long_signal"], full["long_signal"])
    pd.testing.assert_series_equal(short["short_signal"], full["short_signal"])


def test_risk_per_trade_matches_config() -> None:
    trades, _ = run_backtest(sample_bars(), Config(starting_equity=10_000, risk_fraction=0.0025))
    if not trades.empty:
        assert np.isclose(trades.iloc[0]["risk_cash"], 25.0)


def test_backtest_returns_equity_curve() -> None:
    _, curve = run_backtest(sample_bars(), Config())
    assert not curve.empty
    assert "equity" in curve.columns


def test_config_rejects_excessive_risk() -> None:
    with pytest.raises(ValueError, match="Risk fraction"):
        Config(risk_fraction=0.01).validate()


def test_summary_contains_decision_metrics() -> None:
    trades = pd.DataFrame({"pnl": [100.0, -50.0, -40.0, 120.0]})
    curve = pd.DataFrame(
        {"equity": [10_000.0, 10_100.0, 10_050.0, 10_010.0, 10_130.0]},
        index=pd.date_range("2024-01-01", periods=5, freq="h", tz="UTC"),
    )
    result = summarize(trades, curve)
    assert result["average_win"] == 110.0
    assert result["average_loss"] == 45.0
    assert np.isclose(result["expectancy_per_trade"], 32.5)
    assert result["max_consecutive_losses"] == 2.0


def test_max_consecutive_losses_resets_after_win() -> None:
    trades = pd.DataFrame({"pnl": [-1.0, -1.0, 1.0, -1.0]})
    assert _max_consecutive_losses(trades) == 2
