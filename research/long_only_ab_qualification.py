from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Literal

Decision = Literal["promote", "reject", "inconclusive"]
SequenceDecision = Literal["green", "red", "inconclusive"]


@dataclass(frozen=True)
class ExperimentMetrics:
    trade_count: int
    net_profit: float
    profit_factor: float
    maximum_drawdown_fraction: float
    profitable_year_fraction: float
    two_x_cost_net_profit: float
    sequence_risk_decision: SequenceDecision


@dataclass(frozen=True)
class LongOnlyABThresholds:
    minimum_candidate_trades: int = 300
    minimum_profit_factor: float = 1.20
    minimum_profitable_year_fraction: float = 0.60
    require_positive_two_x_cost_net_profit: bool = True
    require_green_sequence_risk: bool = True
    maximum_trade_count_reduction_fraction: float = 0.65


@dataclass(frozen=True)
class LongOnlyABReport:
    decision: Decision
    failed_gates: tuple[str, ...]
    baseline: ExperimentMetrics
    candidate: ExperimentMetrics
    net_profit_improvement: float
    drawdown_improvement_fraction: float
    retained_trade_fraction: float


def _validate_metrics(name: str, metrics: ExperimentMetrics) -> None:
    if isinstance(metrics.trade_count, bool) or metrics.trade_count <= 0:
        raise ValueError(f"{name}.trade_count must be a positive integer")
    numeric = {
        "net_profit": metrics.net_profit,
        "profit_factor": metrics.profit_factor,
        "maximum_drawdown_fraction": metrics.maximum_drawdown_fraction,
        "profitable_year_fraction": metrics.profitable_year_fraction,
        "two_x_cost_net_profit": metrics.two_x_cost_net_profit,
    }
    if any(not isfinite(value) for value in numeric.values()):
        raise ValueError(f"{name} metrics must be finite")
    if metrics.profit_factor < 0:
        raise ValueError(f"{name}.profit_factor must be non-negative")
    if not 0 <= metrics.maximum_drawdown_fraction <= 1:
        raise ValueError(f"{name}.maximum_drawdown_fraction must be in [0, 1]")
    if not 0 <= metrics.profitable_year_fraction <= 1:
        raise ValueError(f"{name}.profitable_year_fraction must be in [0, 1]")
    if metrics.sequence_risk_decision not in ("green", "red", "inconclusive"):
        raise ValueError(f"{name}.sequence_risk_decision is invalid")


def qualify_long_only_ab(
    baseline: ExperimentMetrics,
    candidate: ExperimentMetrics,
    thresholds: LongOnlyABThresholds = LongOnlyABThresholds(),
) -> LongOnlyABReport:
    """Compare an unchanged baseline with one isolated long-only candidate.

    Promotion is deliberately strict: the candidate must be profitable after normal
    and doubled costs, meet the absolute profitability and stability gates, avoid a
    worse drawdown, retain enough observations, and pass sequence-risk qualification.
    """
    _validate_metrics("baseline", baseline)
    _validate_metrics("candidate", candidate)
    if thresholds.minimum_candidate_trades <= 0:
        raise ValueError("minimum_candidate_trades must be positive")
    if thresholds.minimum_profit_factor <= 0:
        raise ValueError("minimum_profit_factor must be positive")
    if not 0 <= thresholds.minimum_profitable_year_fraction <= 1:
        raise ValueError("minimum_profitable_year_fraction must be in [0, 1]")
    if not 0 <= thresholds.maximum_trade_count_reduction_fraction < 1:
        raise ValueError("maximum_trade_count_reduction_fraction must be in [0, 1)")

    retained_fraction = candidate.trade_count / baseline.trade_count
    failed: list[str] = []

    if candidate.trade_count < thresholds.minimum_candidate_trades:
        failed.append("minimum_candidate_trades")
    if retained_fraction < 1.0 - thresholds.maximum_trade_count_reduction_fraction:
        failed.append("trade_count_retention")
    if candidate.net_profit <= 0:
        failed.append("positive_net_profit")
    if candidate.net_profit <= baseline.net_profit:
        failed.append("improves_baseline_net_profit")
    if candidate.profit_factor < thresholds.minimum_profit_factor:
        failed.append("minimum_profit_factor")
    if candidate.profitable_year_fraction < thresholds.minimum_profitable_year_fraction:
        failed.append("profitable_year_fraction")
    if candidate.maximum_drawdown_fraction > baseline.maximum_drawdown_fraction:
        failed.append("drawdown_not_worse")
    if thresholds.require_positive_two_x_cost_net_profit and candidate.two_x_cost_net_profit <= 0:
        failed.append("positive_two_x_cost_net_profit")
    if thresholds.require_green_sequence_risk and candidate.sequence_risk_decision != "green":
        failed.append("green_sequence_risk")

    insufficient = (
        candidate.trade_count < thresholds.minimum_candidate_trades
        or candidate.sequence_risk_decision == "inconclusive"
    )
    if failed:
        decision: Decision = "inconclusive" if insufficient and not any(
            gate in failed
            for gate in (
                "positive_net_profit",
                "improves_baseline_net_profit",
                "minimum_profit_factor",
                "profitable_year_fraction",
                "drawdown_not_worse",
                "positive_two_x_cost_net_profit",
            )
        ) else "reject"
    else:
        decision = "promote"

    return LongOnlyABReport(
        decision=decision,
        failed_gates=tuple(failed),
        baseline=baseline,
        candidate=candidate,
        net_profit_improvement=candidate.net_profit - baseline.net_profit,
        drawdown_improvement_fraction=(
            baseline.maximum_drawdown_fraction - candidate.maximum_drawdown_fraction
        ),
        retained_trade_fraction=retained_fraction,
    )
