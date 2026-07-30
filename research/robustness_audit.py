from __future__ import annotations

from dataclasses import replace
from typing import Iterable

import numpy as np
import pandas as pd

from research.backtest_eurusd_h1 import Config, run_backtest, summarize


def cost_stress_test(
    bars: pd.DataFrame,
    cfg: Config,
    multipliers: Iterable[float] = (1.0, 2.0, 3.0),
) -> pd.DataFrame:
    """Re-run the unchanged strategy under progressively worse spread/slippage assumptions."""
    rows: list[dict] = []
    for multiplier in multipliers:
        if multiplier <= 0:
            raise ValueError("cost multipliers must be positive")
        stressed = replace(
            cfg,
            spread_pips=cfg.spread_pips * multiplier,
            slippage_pips=cfg.slippage_pips * multiplier,
        )
        trades, curve = run_backtest(bars, stressed)
        rows.append(
            {
                "cost_multiplier": float(multiplier),
                "spread_pips": stressed.spread_pips,
                "slippage_pips": stressed.slippage_pips,
                **summarize(trades, curve),
            }
        )
    return pd.DataFrame(rows)


def remove_best_trades(trades: pd.DataFrame, counts: Iterable[int] = (1, 3, 5)) -> pd.DataFrame:
    """Measure how dependent total P&L and expectancy are on the largest winners."""
    if trades.empty:
        return pd.DataFrame(columns=["removed", "remaining_trades", "net_pnl", "expectancy", "profit_factor"])
    pnl = trades["pnl"].astype(float).sort_values(ascending=False)
    rows: list[dict] = []
    for count in counts:
        if count < 0:
            raise ValueError("remove counts cannot be negative")
        remaining = pnl.iloc[min(count, len(pnl)) :]
        wins = remaining[remaining > 0]
        losses = remaining[remaining < 0]
        gross_loss = float(-losses.sum())
        rows.append(
            {
                "removed": int(min(count, len(pnl))),
                "remaining_trades": int(len(remaining)),
                "net_pnl": float(remaining.sum()),
                "expectancy": float(remaining.mean()) if len(remaining) else 0.0,
                "profit_factor": float(wins.sum() / gross_loss) if gross_loss > 0 else np.inf,
            }
        )
    return pd.DataFrame(rows)


def bootstrap_expectancy(
    trades: pd.DataFrame,
    simulations: int = 10_000,
    confidence: float = 0.95,
    seed: int = 42,
) -> dict[str, float]:
    """Bootstrap completed trade P&L to estimate uncertainty around mean expectancy."""
    if simulations <= 0:
        raise ValueError("simulations must be positive")
    if not 0 < confidence < 1:
        raise ValueError("confidence must be between zero and one")
    if trades.empty:
        return {
            "trades": 0.0,
            "mean_expectancy": 0.0,
            "ci_low": 0.0,
            "ci_high": 0.0,
            "probability_positive": 0.0,
        }
    pnl = trades["pnl"].to_numpy(dtype=float)
    rng = np.random.default_rng(seed)
    samples = rng.choice(pnl, size=(simulations, len(pnl)), replace=True)
    means = samples.mean(axis=1)
    alpha = (1.0 - confidence) / 2.0
    return {
        "trades": float(len(pnl)),
        "mean_expectancy": float(pnl.mean()),
        "ci_low": float(np.quantile(means, alpha)),
        "ci_high": float(np.quantile(means, 1.0 - alpha)),
        "probability_positive": float((means > 0).mean()),
    }


def block_bootstrap_expectancy(
    trades: pd.DataFrame,
    block_size: int = 5,
    simulations: int = 5_000,
    confidence: float = 0.95,
    seed: int = 42,
) -> dict[str, float]:
    """Bootstrap contiguous trade blocks to retain short-run clustering and regime dependence."""
    if block_size <= 0:
        raise ValueError("block_size must be positive")
    if simulations <= 0:
        raise ValueError("simulations must be positive")
    if not 0 < confidence < 1:
        raise ValueError("confidence must be between zero and one")
    if trades.empty:
        return bootstrap_expectancy(trades, simulations=simulations, confidence=confidence, seed=seed)
    pnl = trades["pnl"].to_numpy(dtype=float)
    n = len(pnl)
    block = min(block_size, n)
    starts = np.arange(0, n - block + 1)
    rng = np.random.default_rng(seed)
    means = np.empty(simulations, dtype=float)
    blocks_needed = int(np.ceil(n / block))
    for i in range(simulations):
        selected = rng.choice(starts, size=blocks_needed, replace=True)
        sample = np.concatenate([pnl[start : start + block] for start in selected])[:n]
        means[i] = sample.mean()
    alpha = (1.0 - confidence) / 2.0
    return {
        "trades": float(n),
        "block_size": float(block),
        "mean_expectancy": float(pnl.mean()),
        "ci_low": float(np.quantile(means, alpha)),
        "ci_high": float(np.quantile(means, 1.0 - alpha)),
        "probability_positive": float((means > 0).mean()),
    }


def period_stability(trades: pd.DataFrame, frequency: str = "Q") -> pd.DataFrame:
    """Summarize completed trade performance by quarter or another pandas period frequency."""
    columns = ["period", "trades", "net_pnl", "expectancy", "win_rate_pct", "profit_factor"]
    if trades.empty:
        return pd.DataFrame(columns=columns)
    data = trades.copy()
    data["exit_time"] = pd.to_datetime(data["exit_time"], utc=True)
    # PeriodIndex does not retain timezone information; remove it explicitly to
    # avoid warnings while keeping the calendar period unchanged.
    period_source = data["exit_time"].dt.tz_convert("UTC").dt.tz_localize(None)
    data["period"] = period_source.dt.to_period(frequency).astype(str)
    rows: list[dict] = []
    for period, group in data.groupby("period", sort=True):
        pnl = group["pnl"].astype(float)
        wins = pnl[pnl > 0]
        losses = pnl[pnl < 0]
        gross_loss = float(-losses.sum())
        rows.append(
            {
                "period": period,
                "trades": int(len(group)),
                "net_pnl": float(pnl.sum()),
                "expectancy": float(pnl.mean()),
                "win_rate_pct": float((pnl > 0).mean() * 100.0),
                "profit_factor": float(wins.sum() / gross_loss) if gross_loss > 0 else np.inf,
            }
        )
    return pd.DataFrame(rows, columns=columns)


def walk_forward_efficiency(in_sample_return_pct: float, out_of_sample_return_pct: float) -> float:
    """Return OOS/IS efficiency when the denominator is positive and meaningful."""
    if in_sample_return_pct <= 0:
        return float("nan")
    return float(out_of_sample_return_pct / in_sample_return_pct * 100.0)


def audit_baseline(bars: pd.DataFrame, cfg: Config) -> dict[str, object]:
    """Run the minimum baseline audit without changing the entry rules."""
    trades, curve = run_backtest(bars, cfg)
    return {
        "baseline": summarize(trades, curve),
        "cost_stress": cost_stress_test(bars, cfg).to_dict(orient="records"),
        "best_trade_removal": remove_best_trades(trades).to_dict(orient="records"),
        "bootstrap_expectancy": bootstrap_expectancy(trades),
        "block_bootstrap_expectancy": block_bootstrap_expectancy(trades),
        "quarterly_stability": period_stability(trades).to_dict(orient="records"),
    }
