import numpy as np
import pandas as pd

from research.backtest_eurusd_h1 import Config, add_indicators, create_signals, run_backtest


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
