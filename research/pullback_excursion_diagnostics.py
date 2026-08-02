from __future__ import annotations

from dataclasses import dataclass
from statistics import median
from typing import Iterable, Literal, Sequence


Side = Literal["long", "short"]
Decision = Literal["repair_candidate", "retire_candidate", "inconclusive"]


@dataclass(frozen=True)
class TradeExcursion:
    side: Side
    realized_r: float
    mfe_r: float
    mae_r: float
    year: int | None = None
    entry_hour_utc: int | None = None

    @property
    def is_loss(self) -> bool:
        return self.realized_r < 0


@dataclass(frozen=True)
class ExcursionSummary:
    trades: int
    losses: int
    loss_mfe_ge_025_rate: float
    loss_mfe_ge_050_rate: float
    loss_mfe_ge_075_rate: float
    median_loss_mfe_r: float
    median_loss_mae_r: float
    decision: Decision


def _rate(values: Sequence[float], threshold: float) -> float:
    if not values:
        return 0.0
    return sum(value >= threshold for value in values) / len(values)


def summarize_excursions(
    trades: Iterable[TradeExcursion],
    *,
    repair_mfe_threshold_r: float = 0.50,
    repair_rate_threshold: float = 0.50,
    retire_mfe_threshold_r: float = 0.25,
    retire_below_rate_threshold: float = 0.60,
    minimum_losses: int = 30,
) -> ExcursionSummary:
    """Summarize losing-trade excursions without optimizing strategy parameters.

    The decision is deliberately conservative:
    - repair_candidate when enough losses exist and more than the configured
      share reached the repair MFE threshold;
    - retire_candidate when enough losses exist and at least the configured
      share failed to reach the lower MFE threshold;
    - otherwise inconclusive.

    This function does not claim profitability and does not modify trading
    rules. It only applies explicit research gates to supplied trade records.
    """
    records = tuple(trades)
    if minimum_losses <= 0:
        raise ValueError("minimum_losses must be positive")
    if not 0.0 <= repair_rate_threshold <= 1.0:
        raise ValueError("repair_rate_threshold must be between 0 and 1")
    if not 0.0 <= retire_below_rate_threshold <= 1.0:
        raise ValueError("retire_below_rate_threshold must be between 0 and 1")
    if repair_mfe_threshold_r <= retire_mfe_threshold_r:
        raise ValueError("repair threshold must exceed retire threshold")

    loss_records = tuple(record for record in records if record.is_loss)
    loss_mfe = tuple(record.mfe_r for record in loss_records)
    loss_mae = tuple(record.mae_r for record in loss_records)

    rate_025 = _rate(loss_mfe, 0.25)
    rate_050 = _rate(loss_mfe, 0.50)
    rate_075 = _rate(loss_mfe, 0.75)

    decision: Decision = "inconclusive"
    if len(loss_records) >= minimum_losses:
        repair_rate = _rate(loss_mfe, repair_mfe_threshold_r)
        below_retire_rate = 1.0 - _rate(loss_mfe, retire_mfe_threshold_r)
        if repair_rate > repair_rate_threshold:
            decision = "repair_candidate"
        elif below_retire_rate >= retire_below_rate_threshold:
            decision = "retire_candidate"

    return ExcursionSummary(
        trades=len(records),
        losses=len(loss_records),
        loss_mfe_ge_025_rate=rate_025,
        loss_mfe_ge_050_rate=rate_050,
        loss_mfe_ge_075_rate=rate_075,
        median_loss_mfe_r=median(loss_mfe) if loss_mfe else 0.0,
        median_loss_mae_r=median(loss_mae) if loss_mae else 0.0,
        decision=decision,
    )


def split_by_side(trades: Iterable[TradeExcursion]) -> dict[Side, ExcursionSummary]:
    """Return separate long and short summaries using the same decision gates."""
    records = tuple(trades)
    return {
        "long": summarize_excursions(record for record in records if record.side == "long"),
        "short": summarize_excursions(record for record in records if record.side == "short"),
    }
