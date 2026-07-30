from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class Config:
    fast_ema: int = 12
    slow_ema: int = 50
    trend_ema: int = 200
    atr_period: int = 14
    atr_stop_multiplier: float = 1.5
    reward_risk: float = 1.5
    risk_fraction: float = 0.0025
    spread_pips: float = 1.0
    slippage_pips: float = 0.2
    starting_equity: float = 10_000.0


def load_bars(path: str | Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    required = {"time", "open", "high", "low", "close"}
    missing = required.difference(df.columns.str.lower())
    if missing:
        raise ValueError(f"Missing columns: {sorted(missing)}")
    df.columns = [c.lower() for c in df.columns]
    df["time"] = pd.to_datetime(df["time"], utc=True)
    df = df.sort_values("time").drop_duplicates("time").set_index("time")
    return df.astype({"open": float, "high": float, "low": float, "close": float})


def add_indicators(df: pd.DataFrame, cfg: Config) -> pd.DataFrame:
    out = df.copy()
    out["ema_fast"] = out["close"].ewm(span=cfg.fast_ema, adjust=False).mean()
    out["ema_slow"] = out["close"].ewm(span=cfg.slow_ema, adjust=False).mean()
    out["ema_trend"] = out["close"].ewm(span=cfg.trend_ema, adjust=False).mean()
    prev_close = out["close"].shift(1)
    true_range = pd.concat(
        [
            out["high"] - out["low"],
            (out["high"] - prev_close).abs(),
            (out["low"] - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    out["atr"] = true_range.ewm(alpha=1 / cfg.atr_period, adjust=False).mean()
    out["trend_slope"] = out["ema_trend"] - out["ema_trend"].shift(5)
    return out


def create_signals(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    crossed_up = (out["ema_fast"].shift(1) <= out["ema_slow"].shift(1)) & (
        out["ema_fast"] > out["ema_slow"]
    )
    crossed_down = (out["ema_fast"].shift(1) >= out["ema_slow"].shift(1)) & (
        out["ema_fast"] < out["ema_slow"]
    )
    out["long_signal"] = crossed_up & (out["close"] > out["ema_trend"]) & (out["trend_slope"] > 0)
    out["short_signal"] = crossed_down & (out["close"] < out["ema_trend"]) & (out["trend_slope"] < 0)
    return out


def run_backtest(df: pd.DataFrame, cfg: Config) -> tuple[pd.DataFrame, pd.DataFrame]:
    data = create_signals(add_indicators(df, cfg)).dropna().copy()
    pip = 0.0001
    entry_cost = (cfg.spread_pips + cfg.slippage_pips) * pip
    equity = cfg.starting_equity
    equity_curve: list[dict] = []
    trades: list[dict] = []
    position: dict | None = None

    for i in range(1, len(data)):
        ts = data.index[i]
        row = data.iloc[i]
        # Signals are generated from the just-closed candle and entered at the next bar open.
        prior = data.iloc[i - 1]

        if position is not None:
            exit_price = None
            reason = None
            if position["side"] == 1:
                if row["low"] <= position["stop"]:
                    exit_price, reason = position["stop"] - cfg.slippage_pips * pip, "stop"
                elif row["high"] >= position["target"]:
                    exit_price, reason = position["target"] - cfg.slippage_pips * pip, "target"
            else:
                if row["high"] >= position["stop"]:
                    exit_price, reason = position["stop"] + cfg.slippage_pips * pip, "stop"
                elif row["low"] <= position["target"]:
                    exit_price, reason = position["target"] + cfg.slippage_pips * pip, "target"

            if exit_price is not None:
                pnl_per_unit = (exit_price - position["entry"]) * position["side"]
                pnl = pnl_per_unit * position["units"]
                equity += pnl
                trades.append({**position, "exit_time": ts, "exit": exit_price, "pnl": pnl, "reason": reason})
                position = None

        if position is None and prior["atr"] > 0:
            side = 1 if bool(prior["long_signal"]) else -1 if bool(prior["short_signal"]) else 0
            if side:
                raw_entry = float(row["open"])
                entry = raw_entry + entry_cost if side == 1 else raw_entry - entry_cost
                stop_distance = float(prior["atr"]) * cfg.atr_stop_multiplier
                risk_cash = equity * cfg.risk_fraction
                units = risk_cash / stop_distance
                stop = entry - stop_distance * side
                target = entry + stop_distance * cfg.reward_risk * side
                position = {
                    "entry_time": ts,
                    "side": side,
                    "entry": entry,
                    "stop": stop,
                    "target": target,
                    "units": units,
                    "risk_cash": risk_cash,
                }

        equity_curve.append({"time": ts, "equity": equity})

    return pd.DataFrame(trades), pd.DataFrame(equity_curve).set_index("time")


def summarize(trades: pd.DataFrame, curve: pd.DataFrame) -> dict[str, float]:
    if curve.empty:
        return {"trades": 0.0}
    returns = curve["equity"].pct_change().fillna(0)
    rolling_max = curve["equity"].cummax()
    drawdown = curve["equity"] / rolling_max - 1
    wins = trades.loc[trades["pnl"] > 0, "pnl"] if not trades.empty else pd.Series(dtype=float)
    losses = trades.loc[trades["pnl"] < 0, "pnl"] if not trades.empty else pd.Series(dtype=float)
    gross_profit = wins.sum()
    gross_loss = -losses.sum()
    return {
        "trades": float(len(trades)),
        "net_profit": float(curve["equity"].iloc[-1] - curve["equity"].iloc[0]),
        "return_pct": float((curve["equity"].iloc[-1] / curve["equity"].iloc[0] - 1) * 100),
        "win_rate_pct": float((trades["pnl"] > 0).mean() * 100) if len(trades) else 0.0,
        "profit_factor": float(gross_profit / gross_loss) if gross_loss > 0 else np.inf,
        "max_drawdown_pct": float(drawdown.min() * 100),
        "volatility_pct": float(returns.std() * np.sqrt(24 * 252) * 100),
    }


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Backtest PeakFX EURUSD H1 strategy")
    parser.add_argument("csv", type=Path, help="CSV with time,open,high,low,close columns")
    parser.add_argument("--output", type=Path, default=Path("reports"))
    args = parser.parse_args()

    cfg = Config()
    bars = load_bars(args.csv)
    trades, curve = run_backtest(bars, cfg)
    args.output.mkdir(parents=True, exist_ok=True)
    trades.to_csv(args.output / "trades.csv", index=False)
    curve.to_csv(args.output / "equity_curve.csv")
    summary = summarize(trades, curve)
    pd.Series(summary).to_json(args.output / "summary.json", indent=2)
    print(pd.Series(summary).to_string())


if __name__ == "__main__":
    main()
