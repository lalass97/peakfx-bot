from __future__ import annotations

from dataclasses import replace

import pandas as pd

from research.backtest_eurusd_h1 import Config, run_backtest, summarize


RISK_PROFILES: tuple[tuple[str, float], ...] = (
    ("baseline", 0.0025),
    ("moderate", 0.0050),
    ("aggressive_paper_only", 0.0075),
)


_EMPTY_STATS: dict[str, float] = {
    "trades": 0.0,
    "net_profit": 0.0,
    "return_pct": 0.0,
    "win_rate_pct": 0.0,
    "average_win": 0.0,
    "average_loss": 0.0,
    "payoff_ratio": 0.0,
    "expectancy_per_trade": 0.0,
    "profit_factor": 0.0,
    "max_consecutive_losses": 0.0,
    "max_drawdown_pct": 0.0,
    "volatility_pct": 0.0,
}


def _run_or_empty(bars: pd.DataFrame, cfg: Config) -> tuple[pd.DataFrame, dict[str, float]]:
    """Run the backtest while treating insufficient warm-up data as no trades."""
    minimum_bars = max(cfg.trend_ema + 7, cfg.slow_ema + 7, cfg.atr_period + 7)
    if len(bars) < minimum_bars:
        return pd.DataFrame(), dict(_EMPTY_STATS)
    trades, curve = run_backtest(bars, cfg)
    if curve.empty:
        return trades, dict(_EMPTY_STATS)
    return trades, {**_EMPTY_STATS, **summarize(trades, curve)}


def compare_risk_profiles(
    bars: pd.DataFrame,
    base_cfg: Config,
    profiles: tuple[tuple[str, float], ...] = RISK_PROFILES,
) -> pd.DataFrame:
    """Run identical signals under several paper-trading risk levels.

    The aggressive profile is analysis-only. It does not change the MT5 EA's
    0.25% default or its enforced 0.50% production input cap.
    """
    rows: list[dict[str, float | str]] = []
    for name, risk_fraction in profiles:
        if risk_fraction <= 0:
            raise ValueError("risk fractions must be positive")

        # Config intentionally caps production research at 0.50%. For the
        # 0.75% paper-only scenario, run the baseline trade path first and
        # scale each realized return proportionally to isolate sizing risk.
        if risk_fraction <= 0.005:
            cfg = replace(base_cfg, risk_fraction=risk_fraction)
            _, stats = _run_or_empty(bars, cfg)
        else:
            baseline_cfg = replace(base_cfg, risk_fraction=0.0025)
            trades, baseline_stats = _run_or_empty(bars, baseline_cfg)
            stats = (
                _rescale_trade_path(
                    trades=trades,
                    starting_equity=base_cfg.starting_equity,
                    scale=risk_fraction / 0.0025,
                )
                if not trades.empty
                else baseline_stats
            )

        rows.append(
            {
                "profile": name,
                "risk_fraction": risk_fraction,
                "risk_percent": risk_fraction * 100.0,
                **stats,
            }
        )

    return pd.DataFrame(rows)


def _rescale_trade_path(
    trades: pd.DataFrame,
    starting_equity: float,
    scale: float,
) -> dict[str, float]:
    if starting_equity <= 0:
        raise ValueError("starting_equity must be positive")
    if scale <= 0:
        raise ValueError("scale must be positive")
    if trades.empty:
        return dict(_EMPTY_STATS)

    equity = starting_equity
    peak = starting_equity
    worst_drawdown = 0.0
    pnls: list[float] = []

    for _, trade in trades.iterrows():
        base_risk = float(trade.get("risk_cash", 0.0))
        if base_risk <= 0:
            continue
        r_multiple = float(trade["pnl"]) / base_risk
        pnl = equity * 0.0025 * scale * r_multiple
        pnls.append(pnl)
        equity += pnl
        peak = max(peak, equity)
        worst_drawdown = min(worst_drawdown, equity / peak - 1.0)

    pnl_series = pd.Series(pnls, dtype=float)
    if pnl_series.empty:
        return dict(_EMPTY_STATS)
    wins = pnl_series[pnl_series > 0]
    losses = pnl_series[pnl_series < 0]
    gross_profit = float(wins.sum())
    gross_loss = float(-losses.sum())

    return {
        **_EMPTY_STATS,
        "trades": float(len(pnl_series)),
        "net_profit": float(equity - starting_equity),
        "return_pct": float((equity / starting_equity - 1.0) * 100.0),
        "win_rate_pct": float((pnl_series > 0).mean() * 100.0),
        "expectancy_per_trade": float(pnl_series.mean()),
        "profit_factor": float(gross_profit / gross_loss) if gross_loss > 0 else float("inf"),
        "max_drawdown_pct": float(worst_drawdown * 100.0),
    }
