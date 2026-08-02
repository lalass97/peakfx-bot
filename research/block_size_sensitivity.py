from __future__ import annotations

from dataclasses import dataclass
from math import isfinite

import numpy as np

from research.block_bootstrap_sequence_risk import (
    BlockBootstrapConfig,
    analyze_block_bootstrap_sequence_risk,
)


@dataclass(frozen=True)
class BlockSizeResult:
    block_size: int
    p95_max_drawdown_fraction: float
    p99_max_drawdown_fraction: float
    median_max_drawdown_fraction: float
    terminal_equity_p05: float
    terminal_equity_median: float
    terminal_equity_p95: float
    ruin_probability: float
    historical_max_drawdown_fraction: float
    p95_to_historical_ratio: float


@dataclass(frozen=True)
class BlockSizeSensitivityReport:
    simulations_per_block_size: int
    trade_count: int
    block_sizes: tuple[int, ...]
    results: tuple[BlockSizeResult, ...]
    conservative_block_size: int
    conservative_p95_max_drawdown_fraction: float
    conservative_p99_max_drawdown_fraction: float
    maximum_ruin_probability: float
    minimum_terminal_equity_p05: float


def _validate_block_sizes(block_sizes: tuple[int, ...], trade_count: int) -> tuple[int, ...]:
    if not block_sizes:
        raise ValueError("block_sizes must not be empty")
    if any(isinstance(size, bool) or not isinstance(size, int) for size in block_sizes):
        raise ValueError("block_sizes must contain integers")
    if any(size < 1 or size > trade_count for size in block_sizes):
        raise ValueError("each block size must be between 1 and the number of trades")
    if len(set(block_sizes)) != len(block_sizes):
        raise ValueError("block_sizes must not contain duplicates")
    if tuple(sorted(block_sizes)) != block_sizes:
        raise ValueError("block_sizes must be predeclared in ascending order")
    return block_sizes


def analyze_block_size_sensitivity(
    trades: np.ndarray,
    *,
    block_sizes: tuple[int, ...] = (5, 10, 20, 40),
    simulations_per_block_size: int = 2000,
    initial_balance: float = 10000.0,
    ruin_drawdown_fraction: float = 0.50,
    seed: int = 42,
) -> BlockSizeSensitivityReport:
    """Run a predeclared block-size sweep and retain the most adverse estimates.

    The function deliberately does not select a favorable block size. It reports all
    requested sizes and uses the largest P95 drawdown as the conservative planning
    estimate. All simulation work remains inside the vectorized bootstrap engine.
    """
    values = np.asarray(trades, dtype=np.float64)
    if values.ndim != 1 or values.size < 2:
        raise ValueError("trades must be one-dimensional with at least two values")
    if not np.all(np.isfinite(values)):
        raise ValueError("trades must contain only finite values")
    sizes = _validate_block_sizes(block_sizes, values.size)
    if isinstance(simulations_per_block_size, bool) or simulations_per_block_size <= 0:
        raise ValueError("simulations_per_block_size must be positive")
    if not isfinite(initial_balance) or initial_balance <= 0:
        raise ValueError("initial_balance must be finite and positive")
    if not isfinite(ruin_drawdown_fraction) or not 0 < ruin_drawdown_fraction <= 1:
        raise ValueError("ruin_drawdown_fraction must be in (0, 1]")
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise ValueError("seed must be an integer")

    results: list[BlockSizeResult] = []
    for size in sizes:
        report = analyze_block_bootstrap_sequence_risk(
            values,
            BlockBootstrapConfig(
                simulations=simulations_per_block_size,
                block_size=size,
                initial_balance=initial_balance,
                ruin_drawdown_fraction=ruin_drawdown_fraction,
                seed=seed,
            ),
        )
        results.append(
            BlockSizeResult(
                block_size=size,
                p95_max_drawdown_fraction=report.p95_max_drawdown_fraction,
                p99_max_drawdown_fraction=float(np.percentile(report.max_drawdown_fraction, 99.0)),
                median_max_drawdown_fraction=float(np.median(report.max_drawdown_fraction)),
                terminal_equity_p05=float(np.percentile(report.terminal_equity, 5.0)),
                terminal_equity_median=float(np.median(report.terminal_equity)),
                terminal_equity_p95=float(np.percentile(report.terminal_equity, 95.0)),
                ruin_probability=report.ruin_probability,
                historical_max_drawdown_fraction=report.historical_max_drawdown_fraction,
                p95_to_historical_ratio=report.mdd_ratio,
            )
        )

    frozen_results = tuple(results)
    conservative = max(frozen_results, key=lambda result: result.p95_max_drawdown_fraction)

    return BlockSizeSensitivityReport(
        simulations_per_block_size=simulations_per_block_size,
        trade_count=values.size,
        block_sizes=sizes,
        results=frozen_results,
        conservative_block_size=conservative.block_size,
        conservative_p95_max_drawdown_fraction=conservative.p95_max_drawdown_fraction,
        conservative_p99_max_drawdown_fraction=max(
            result.p99_max_drawdown_fraction for result in frozen_results
        ),
        maximum_ruin_probability=max(result.ruin_probability for result in frozen_results),
        minimum_terminal_equity_p05=min(result.terminal_equity_p05 for result in frozen_results),
    )
