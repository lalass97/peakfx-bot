from __future__ import annotations

from dataclasses import replace
from itertools import product

import numpy as np
import pandas as pd

from research.backtest_eurusd_h1 import Config, run_backtest, summarize


def walk_forward_validate(
    bars: pd.DataFrame,
    cfg: Config,
    train_bars: int = 24 * 365 * 2,
    test_bars: int = 24 * 90,
    step_bars: int | None = None,
) -> pd.DataFrame:
    """Run anchored walk-forward tests without allowing future data into earlier windows."""
    if train_bars <= 0 or test_bars <= 0:
        raise ValueError("train_bars and test_bars must be positive")
    step = test_bars if step_bars is None else step_bars
    if step <= 0:
        raise ValueError("step_bars must be positive")

    rows: list[dict] = []
    test_start = train_bars
    window = 0
    while test_start + test_bars <= len(bars):
        train = bars.iloc[:test_start]
        test = bars.iloc[test_start : test_start + test_bars]

        # Warm the indicators using training history, but score only trades entered in the test window.
        combined = pd.concat([train, test])
        trades, curve = run_backtest(combined, cfg)
        cutoff = test.index[0]
        test_trades = trades.loc[trades["entry_time"] >= cutoff].copy() if not trades.empty else trades
        test_curve = curve.loc[curve.index >= cutoff].copy() if not curve.empty else curve
        stats = summarize(test_trades, test_curve)
        rows.append(
            {
                "window": window,
                "train_start": train.index[0],
                "train_end": train.index[-1],
                "test_start": test.index[0],
                "test_end": test.index[-1],
                **stats,
            }
        )
        window += 1
        test_start += step

    return pd.DataFrame(rows)


def parameter_sensitivity(
    bars: pd.DataFrame,
    base_cfg: Config,
    fast_values: tuple[int, ...] = (10, 12, 14),
    slow_values: tuple[int, ...] = (45, 50, 55),
    atr_values: tuple[float, ...] = (1.25, 1.5, 1.75),
) -> pd.DataFrame:
    """Evaluate a small, declared parameter neighborhood rather than searching an unlimited grid."""
    rows: list[dict] = []
    for fast, slow, atr_mult in product(fast_values, slow_values, atr_values):
        if fast >= slow:
            continue
        cfg = replace(base_cfg, fast_ema=fast, slow_ema=slow, atr_stop_multiplier=atr_mult)
        trades, curve = run_backtest(bars, cfg)
        rows.append(
            {
                "fast_ema": fast,
                "slow_ema": slow,
                "atr_stop_multiplier": atr_mult,
                **summarize(trades, curve),
            }
        )
    return pd.DataFrame(rows)


def monte_carlo_trade_paths(
    trades: pd.DataFrame,
    starting_equity: float,
    simulations: int = 2_000,
    seed: int = 42,
) -> pd.DataFrame:
    """Bootstrap completed trade P&L to estimate path-dependent drawdown risk."""
    if simulations <= 0:
        raise ValueError("simulations must be positive")
    if starting_equity <= 0:
        raise ValueError("starting_equity must be positive")
    if trades.empty:
        return pd.DataFrame(columns=["simulation", "ending_equity", "max_drawdown_pct"])

    pnl = trades["pnl"].to_numpy(dtype=float)
    rng = np.random.default_rng(seed)
    rows: list[dict] = []
    for simulation in range(simulations):
        sample = rng.choice(pnl, size=len(pnl), replace=True)
        equity = starting_equity + np.cumsum(sample)
        equity_with_start = np.concatenate([[starting_equity], equity])
        peak = np.maximum.accumulate(equity_with_start)
        drawdown = equity_with_start / peak - 1.0
        rows.append(
            {
                "simulation": simulation,
                "ending_equity": float(equity[-1]),
                "max_drawdown_pct": float(drawdown.min() * 100.0),
            }
        )
    return pd.DataFrame(rows)


def validation_summary(walk_forward: pd.DataFrame, monte_carlo: pd.DataFrame) -> dict[str, float]:
    """Create compact robustness statistics for reporting and release gates."""
    profitable_windows = 0.0
    median_window_return = 0.0
    if not walk_forward.empty:
        profitable_windows = float((walk_forward["net_profit"] > 0).mean() * 100.0)
        median_window_return = float(walk_forward["return_pct"].median())

    result = {
        "walk_forward_windows": float(len(walk_forward)),
        "profitable_windows_pct": profitable_windows,
        "median_window_return_pct": median_window_return,
    }
    if not monte_carlo.empty:
        result.update(
            {
                "mc_median_ending_equity": float(monte_carlo["ending_equity"].median()),
                "mc_5pct_ending_equity": float(monte_carlo["ending_equity"].quantile(0.05)),
                "mc_95pct_worst_drawdown": float(monte_carlo["max_drawdown_pct"].quantile(0.05)),
            }
        )
    return result
