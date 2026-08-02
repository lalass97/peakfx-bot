from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from research.open_equity_csv import load_open_equity_snapshots
from research.open_equity_risk import OpenRiskReport, OpenRiskThresholds, qualify_open_risk
from research.profitability_csv import load_completed_trades_csv
from research.profitability_qualification import (
    ProfitabilityReport,
    QualificationThresholds,
    qualify_profitability,
)

Decision = Literal["green", "red", "inconclusive"]


@dataclass(frozen=True)
class CombinedQualificationReport:
    decision: Decision
    profitability: ProfitabilityReport
    open_risk: OpenRiskReport
    failed_sections: tuple[str, ...]


def qualify_exported_run(
    completed_trades_csv: str,
    open_equity_csv: str,
    profitability_thresholds: QualificationThresholds = QualificationThresholds(),
    open_risk_thresholds: OpenRiskThresholds = OpenRiskThresholds(),
) -> CombinedQualificationReport:
    """Apply both closed-trade and mark-to-market gates to one exported run.

    A run is green only when both independent sections are green. Any red section
    makes the combined result red. Otherwise the result is inconclusive.
    """
    trades = load_completed_trades_csv(completed_trades_csv)
    snapshots = load_open_equity_snapshots(open_equity_csv)

    profitability = qualify_profitability(trades, profitability_thresholds)
    open_risk = qualify_open_risk(snapshots, open_risk_thresholds)

    failed_sections: list[str] = []
    if profitability.decision != "green":
        failed_sections.append("profitability")
    if open_risk.decision != "green":
        failed_sections.append("open_risk")

    if "red" in (profitability.decision, open_risk.decision):
        decision: Decision = "red"
    elif profitability.decision == "green" and open_risk.decision == "green":
        decision = "green"
    else:
        decision = "inconclusive"

    return CombinedQualificationReport(
        decision=decision,
        profitability=profitability,
        open_risk=open_risk,
        failed_sections=tuple(failed_sections),
    )
