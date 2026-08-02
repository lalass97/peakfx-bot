from __future__ import annotations

from dataclasses import dataclass
from math import isfinite

import numpy as np


@dataclass(frozen=True)
class BlockBootstrapConfig:
    simulations: int = 2000
    block_size: int = 10
    initial_balance: float = 10000.0
    ruin_drawdown_fraction: float = 0.50
    seed: int = 42


@dataclass(frozen=True)
class BlockBootstrapReport:
    block_size: int
    simulations: int
    trade_count: int
    max_drawdown_currency: np.ndarray
    max_drawdown_fraction: np.ndarray
    terminal_equity: np.ndarray
    ruin_probability: float
    historical_max_drawdown_fraction: float
    p95_max_drawdown_fraction: float
    mdd_ratio: float


def _validate(trades: np.ndarray, config: BlockBootstrapConfig) -> np.ndarray:
    values = np.asarray(trades, dtype=np.float64)
    if values.ndim != 1 or values.size < 2:
        raise ValueError("trades must be a one-dimensional array with at least two values")
    if not np.all(np.isfinite(values)):
        raise ValueError("trades must contain only finite values")
    if isinstance(config.simulations, bool) or config.simulations <= 0:
        raise ValueError("simulations must be a positive integer")
    if isinstance(config.block_size, bool) or not 1 <= config.block_size <= values.size:
        raise ValueError("block_size must be between 1 and the number of trades")
    if not isfinite(config.initial_balance) or config.initial_balance <= 0:
        raise ValueError("initial_balance must be finite and positive")
    if not isfinite(config.ruin_drawdown_fraction) or not 0 < config.ruin_drawdown_fraction <= 1:
        raise ValueError("ruin_drawdown_fraction must be in (0, 1]")
    return values


def _equity_metrics(paths: np.ndarray, initial_balance: float) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    starts = np.full((paths.shape[0], 1), initial_balance, dtype=np.float64)
    equity = np.concatenate((starts, initial_balance + np.cumsum(paths, axis=1)), axis=1)
    peaks = np.maximum.accumulate(equity, axis=1)
    drawdown_currency = peaks - equity
    drawdown_fraction = np.divide(
        drawdown_currency,
        peaks,
        out=np.zeros_like(drawdown_currency),
        where=peaks > 0,
    )
    return equity, np.max(drawdown_currency, axis=1), np.max(drawdown_fraction, axis=1)


def generate_circular_block_bootstrap_paths(
    trades: np.ndarray,
    config: BlockBootstrapConfig = BlockBootstrapConfig(),
) -> np.ndarray:
    """Generate fixed-length circular moving-block bootstrap paths.

    Blocks are sampled with replacement while preserving the original order inside
    each block. Circular indexing allows every historical trade to be a block start.
    The implementation is fully vectorized across simulations and block positions.
    """
    values = _validate(trades, config)
    blocks_needed = (values.size + config.block_size - 1) // config.block_size
    rng = np.random.default_rng(config.seed)
    starts = rng.integers(0, values.size, size=(config.simulations, blocks_needed))
    offsets = np.arange(config.block_size, dtype=np.int64)
    indices = (starts[:, :, None] + offsets[None, None, :]) % values.size
    sampled = values[indices].reshape(config.simulations, -1)
    return sampled[:, : values.size]


def analyze_block_bootstrap_sequence_risk(
    trades: np.ndarray,
    config: BlockBootstrapConfig = BlockBootstrapConfig(),
) -> BlockBootstrapReport:
    """Estimate drawdown and terminal-equity risk while preserving local dependence."""
    values = _validate(trades, config)
    paths = generate_circular_block_bootstrap_paths(values, config)
    equity, max_dd_currency, max_dd_fraction = _equity_metrics(paths, config.initial_balance)

    historical_equity, _, historical_dd = _equity_metrics(values[None, :], config.initial_balance)
    historical_mdd = float(historical_dd[0])
    p95_mdd = float(np.percentile(max_dd_fraction, 95.0))
    ratio = float("inf") if historical_mdd == 0 and p95_mdd > 0 else (
        1.0 if historical_mdd == 0 else p95_mdd / historical_mdd
    )

    ruin_level = config.initial_balance * (1.0 - config.ruin_drawdown_fraction)
    ruin_probability = float(np.mean(np.any(equity <= ruin_level, axis=1)))

    return BlockBootstrapReport(
        block_size=config.block_size,
        simulations=config.simulations,
        trade_count=values.size,
        max_drawdown_currency=max_dd_currency,
        max_drawdown_fraction=max_dd_fraction,
        terminal_equity=equity[:, -1],
        ruin_probability=ruin_probability,
        historical_max_drawdown_fraction=historical_mdd,
        p95_max_drawdown_fraction=p95_mdd,
        mdd_ratio=ratio,
    )
