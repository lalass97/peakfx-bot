from __future__ import annotations

from dataclasses import replace

import pandas as pd

from research.backtest_eurusd_h1 import Config, run_backtest, summarize


RISK_PROFILES: tuple[tuple[str, float], ...] = (
    ("baseline", 0.0025),
    ("moderate", 0.0050),
    ("aggressive_paper_only", 0.0075),
)


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
            trades, curve = run_backtest(bars, cfg)
            stats = summarize(trades, curve)
        else:
            baseline_cfg = replace(base_cfg, risk_fraction=0.0025)
            trades, _ = run_backtest(bars, baseline_cfg)
            stats = _rescale_trade_path(
                trades=trades,
                starting_equity=base_cfg.starting_equity,
                scale=risk_fraction / 0.0025,
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
        return {
            "trades": 0.0,
            "net_profit": 0.0,
            "return_pct": 0.0,
            "win_rate_pct": 0.0,
            "expectancy_per_trade": 0.0,
            "profit_factor": 0.0,
            "max_drawdown_pct": 0.0,
        }

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
    wins = pnl_series[pnl_series > 0]
    losses = pnl_series[pnl_series < 0]
    gross_profit = float(wins.sum())
    gross_loss = float(-losses.sum())

    return {
        "trades": float(len(pnl_series)),
        "net_profit": float(equity - starting_equity),
        "return_pct": float((equity / starting_equity - 1.0) * 100.0),
        "win_rate_pct": float((pnl_series > 0).mean() * 100.0),
        "expectancy_per_trade": float(pnl_series.mean()),
        "profit_factor": float(gross_profit / gross_loss) if gross_loss > 0 else float("inf"),
        "max_drawdown_pct": float(worst_drawdown * 100.0),
    }
