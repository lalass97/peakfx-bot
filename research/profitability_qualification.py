from __future__ import annotations

from dataclasses import dataclass
from math import inf
from typing import Iterable, Literal

Side = Literal["long", "short"]
Decision = Literal["green", "red", "inconclusive"]


@dataclass(frozen=True)
class TradeResult:
    net_pnl: float
    r_multiple: float
    side: Side
    year: int


@dataclass(frozen=True)
class QualificationThresholds:
    minimum_trades: int = 100
    minimum_profit_factor: float = 1.20
    minimum_expectancy_r: float = 0.0
    maximum_drawdown_r: float = 10.0
    minimum_profitable_year_fraction: float = 0.60
    require_both_directions_positive: bool = False


@dataclass(frozen=True)
class ProfitabilityReport:
    decision: Decision
    trade_count: int
    net_pnl: float
    net_r: float
    profit_factor: float
    expectancy_r: float
    maximum_drawdown_r: float
    profitable_year_fraction: float
    long_expectancy_r: float | None
    short_expectancy_r: float | None
    failed_gates: tuple[str, ...]


def _profit_factor(trades: tuple[TradeResult, ...]) -> float:
    gross_profit = sum(t.net_pnl for t in trades if t.net_pnl > 0)
    gross_loss = -sum(t.net_pnl for t in trades if t.net_pnl < 0)
    if gross_loss == 0:
        return inf if gross_profit > 0 else 0.0
    return gross_profit / gross_loss


def _maximum_drawdown_r(trades: tuple[TradeResult, ...]) -> float:
    equity = 0.0
    peak = 0.0
    maximum = 0.0
    for trade in trades:
        equity += trade.r_multiple
        peak = max(peak, equity)
        maximum = max(maximum, peak - equity)
    return maximum


def _expectancy_for_side(trades: tuple[TradeResult, ...], side: Side) -> float | None:
    selected = [t.r_multiple for t in trades if t.side == side]
    if not selected:
        return None
    return sum(selected) / len(selected)


def _profitable_year_fraction(trades: tuple[TradeResult, ...]) -> float:
    by_year: dict[int, float] = {}
    for trade in trades:
        by_year[trade.year] = by_year.get(trade.year, 0.0) + trade.r_multiple
    if not by_year:
        return 0.0
    profitable = sum(total > 0 for total in by_year.values())
    return profitable / len(by_year)


def qualify_profitability(
    trades: Iterable[TradeResult],
    thresholds: QualificationThresholds = QualificationThresholds(),
) -> ProfitabilityReport:
    """Evaluate a completed-trade stream against explicit promotion gates.

    This function does not optimize parameters or alter trades. It only scores
    already-generated, cost-inclusive results in their original sequence.
    """
    ordered = tuple(trades)
    if thresholds.minimum_trades <= 0:
        raise ValueError("minimum_trades must be positive")
    if thresholds.minimum_profit_factor <= 0:
        raise ValueError("minimum_profit_factor must be positive")
    if thresholds.maximum_drawdown_r <= 0:
        raise ValueError("maximum_drawdown_r must be positive")
    if not 0 <= thresholds.minimum_profitable_year_fraction <= 1:
        raise ValueError("minimum_profitable_year_fraction must be between 0 and 1")

    for trade in ordered:
        if trade.side not in ("long", "short"):
            raise ValueError("invalid trade side")
        if trade.year < 1900:
            raise ValueError("invalid trade year")

    count = len(ordered)
    net_pnl = sum(t.net_pnl for t in ordered)
    net_r = sum(t.r_multiple for t in ordered)
    expectancy_r = net_r / count if count else 0.0
    profit_factor = _profit_factor(ordered)
    max_drawdown_r = _maximum_drawdown_r(ordered)
    year_fraction = _profitable_year_fraction(ordered)
    long_expectancy = _expectancy_for_side(ordered, "long")
    short_expectancy = _expectancy_for_side(ordered, "short")

    failed: list[str] = []
    if count < thresholds.minimum_trades:
        failed.append("minimum_trades")
    if profit_factor < thresholds.minimum_profit_factor:
        failed.append("profit_factor")
    if expectancy_r <= thresholds.minimum_expectancy_r:
        failed.append("expectancy")
    if max_drawdown_r > thresholds.maximum_drawdown_r:
        failed.append("maximum_drawdown")
    if year_fraction < thresholds.minimum_profitable_year_fraction:
        failed.append("year_stability")
    if thresholds.require_both_directions_positive:
        if long_expectancy is None or long_expectancy <= 0:
            failed.append("long_expectancy")
        if short_expectancy is None or short_expectancy <= 0:
            failed.append("short_expectancy")

    if count < thresholds.minimum_trades:
        decision: Decision = "inconclusive"
    elif failed:
        decision = "red"
    else:
        decision = "green"

    return ProfitabilityReport(
        decision=decision,
        trade_count=count,
        net_pnl=net_pnl,
        net_r=net_r,
        profit_factor=profit_factor,
        expectancy_r=expectancy_r,
        maximum_drawdown_r=max_drawdown_r,
        profitable_year_fraction=year_fraction,
        long_expectancy_r=long_expectancy,
        short_expectancy_r=short_expectancy,
        failed_gates=tuple(failed),
    )
