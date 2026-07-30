import numpy as np
import pandas as pd
import pytest

from research.data_quality import assert_research_ready, inspect_h1_bars


def valid_bars(rows: int = 6000) -> pd.DataFrame:
    idx = pd.date_range("2024-01-01", periods=rows, freq="h", tz="UTC")
    price = 1.08 + np.arange(rows) * 0.000001
    return pd.DataFrame(
        {
            "open": price,
            "high": price + 0.0005,
            "low": price - 0.0005,
            "close": price + 0.0001,
        },
        index=idx,
    )


def test_valid_dataset_is_research_ready() -> None:
    report = inspect_h1_bars(valid_bars())
    assert report.invalid_ohlc_rows == 0
    assert report.duplicate_timestamps == 0
    assert_research_ready(report)


def test_invalid_ohlc_is_detected() -> None:
    bars = valid_bars()
    bars.iloc[10, bars.columns.get_loc("high")] = bars.iloc[10]["low"] - 0.001
    report = inspect_h1_bars(bars)
    assert report.invalid_ohlc_rows == 1
    with pytest.raises(ValueError, match="invalid OHLC"):
        assert_research_ready(report)


def test_short_dataset_is_rejected() -> None:
    report = inspect_h1_bars(valid_bars(100))
    with pytest.raises(ValueError, match="5,000"):
        assert_research_ready(report)
