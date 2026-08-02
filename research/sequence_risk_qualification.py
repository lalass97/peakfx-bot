from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Literal

from research.block_size_sensitivity import BlockSizeSensitivityReport

Decision = Literal["green", "red", "inconclusive"]


@dataclass(frozen=True)
class SequenceRiskThresholds:
    maximum_p95_drawdown_fraction: float = 0.20
    maximum_p99_drawdown_fraction: float = 0.30
    maximum_p95_to_historical_ratio: float = 1.50
    maximum_ruin_probability: float = 0.05
    minimum_terminal_equity_p05_fraction: float = 0.80
    minimum_block_sizes: int = 4


@dataclass(frozen=True)
class SequenceRiskQualificationReport:
    decision: Decision
    failed_gates: tuple[str, ...]
    evidence_gaps: tuple[str, ...]
    conservative_block_size: int
    conservative_p95_drawdown_fraction: float
    conservative_p99_drawdown_fraction: float
    maximum_ruin_probability: float
    minimum_terminal_equity_p05: float
    minimum_terminal_equity_p05_fraction: float
    maximum_p95_to_historical_ratio: float


def _validate_thresholds(thresholds: SequenceRiskThresholds) -> None:
    fraction_fields = (
        ("maximum_p95_drawdown_fraction", thresholds.maximum_p95_drawdown_fraction),
        ("maximum_p99_drawdown_fraction", thresholds.maximum_p99_drawdown_fraction),
        ("maximum_ruin_probability", thresholds.maximum_ruin_probability),
        ("minimum_terminal_equity_p05_fraction", thresholds.minimum_terminal_equity_p05_fraction),
    )
    for name, value in fraction_fields:
        if not isfinite(value) or not 0.0 <= value <= 1.0:
            raise ValueError(f"{name} must be finite and in [0, 1]")
    if (
        not isfinite(thresholds.maximum_p95_to_historical_ratio)
        or thresholds.maximum_p95_to_historical_ratio <= 0.0
    ):
        raise ValueError("maximum_p95_to_historical_ratio must be finite and positive")
    if isinstance(thresholds.minimum_block_sizes, bool) or thresholds.minimum_block_sizes <= 0:
        raise ValueError("minimum_block_sizes must be a positive integer")


def qualify_sequence_risk(
    sensitivity: BlockSizeSensitivityReport,
    *,
    initial_balance: float,
    thresholds: SequenceRiskThresholds = SequenceRiskThresholds(),
) -> SequenceRiskQualificationReport:
    """Apply explicit governance gates to a complete block-size sensitivity sweep.

    A red decision means at least one measured sequence-risk limit was breached.
    An inconclusive decision means no measured limit failed, but the evidence set is
    smaller than required. Green requires sufficient evidence and every gate to pass.
    """
    _validate_thresholds(thresholds)
    if not isfinite(initial_balance) or initial_balance <= 0.0:
        raise ValueError("initial_balance must be finite and positive")
    if not sensitivity.results:
        raise ValueError("sensitivity report must contain results")
    if len(sensitivity.results) != len(sensitivity.block_sizes):
        raise ValueError("sensitivity report result count must match block_sizes")

    max_ratio = max(result.p95_to_historical_ratio for result in sensitivity.results)
    terminal_p05_fraction = sensitivity.minimum_terminal_equity_p05 / initial_balance

    measured = (
        sensitivity.conservative_p95_max_drawdown_fraction,
        sensitivity.conservative_p99_max_drawdown_fraction,
        sensitivity.maximum_ruin_probability,
        sensitivity.minimum_terminal_equity_p05,
        terminal_p05_fraction,
        max_ratio,
    )
    if not all(isfinite(value) for value in measured):
        raise ValueError("sequence-risk measurements must be finite")

    failed: list[str] = []
    if sensitivity.conservative_p95_max_drawdown_fraction > thresholds.maximum_p95_drawdown_fraction:
        failed.append("p95_drawdown")
    if sensitivity.conservative_p99_max_drawdown_fraction > thresholds.maximum_p99_drawdown_fraction:
        failed.append("p99_drawdown")
    if max_ratio > thresholds.maximum_p95_to_historical_ratio:
        failed.append("historical_drawdown_ratio")
    if sensitivity.maximum_ruin_probability > thresholds.maximum_ruin_probability:
        failed.append("ruin_probability")
    if terminal_p05_fraction < thresholds.minimum_terminal_equity_p05_fraction:
        failed.append("terminal_equity_p05")

    evidence_gaps: list[str] = []
    if len(sensitivity.block_sizes) < thresholds.minimum_block_sizes:
        evidence_gaps.append("block_size_count")

    if failed:
        decision: Decision = "red"
    elif evidence_gaps:
        decision = "inconclusive"
    else:
        decision = "green"

    return SequenceRiskQualificationReport(
        decision=decision,
        failed_gates=tuple(failed),
        evidence_gaps=tuple(evidence_gaps),
        conservative_block_size=sensitivity.conservative_block_size,
        conservative_p95_drawdown_fraction=sensitivity.conservative_p95_max_drawdown_fraction,
        conservative_p99_drawdown_fraction=sensitivity.conservative_p99_max_drawdown_fraction,
        maximum_ruin_probability=sensitivity.maximum_ruin_probability,
        minimum_terminal_equity_p05=sensitivity.minimum_terminal_equity_p05,
        minimum_terminal_equity_p05_fraction=terminal_p05_fraction,
        maximum_p95_to_historical_ratio=max_ratio,
    )
