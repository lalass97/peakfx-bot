from __future__ import annotations

import numpy as np
import pandas as pd

from research.backtest_eurusd_h1 import Config
from research.risk_profile_comparison import _rescale_trade_path, compare_risk_profiles


def test_rescaled_aggressive_path_magnifies_profit_and_drawdown() -> None:
    trades = pd.DataFrame(
        {
            "pnl": [37.5, -25.0, -25.0, 37.5],
            "risk_cash": [25.0, 25.0, 25.0, 25.0],
        }
    )
    baseline = _rescale_trade_path(trades, starting_equity=10_000.0, scale=1.0)
    aggressive = _rescale_trade_path(trades, starting_equity=10_000.0, scale=3.0)

    assert aggressive["return_pct"] > baseline["return_pct"]
    assert aggressive["max_drawdown_pct"] < baseline["max_drawdown_pct"]
    assert aggressive["trades"] == baseline["trades"]


def test_comparison_keeps_three_declared_profiles() -> None:
    index = pd.date_range("2024-01-01", periods=500, freq="h", tz="UTC")
    close = pd.Series(1.10 + np.arange(500) * 0.00002, index=index)
    bars = pd.DataFrame(
        {
            "open": close.shift(1).fillna(close.iloc[0]),
            "high": close + 0.0005,
            "low": close - 0.0005,
            "close": close,
        },
        index=index,
    )

    result = compare_risk_profiles(bars, Config())

    assert list(result["profile"]) == ["baseline", "moderate", "aggressive_paper_only"]
    assert list(result["risk_percent"]) == [0.25, 0.5, 0.75]
