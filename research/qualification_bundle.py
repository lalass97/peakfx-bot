from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from datetime import datetime

from research.combined_qualification import (
    CombinedQualificationReport,
    qualify_exported_run,
)
from research.evidence_consistency import (
    EvidenceConsistencyReport,
    verify_evidence_consistency,
)
from research.open_equity_risk import OpenRiskThresholds
from research.profitability_qualification import QualificationThresholds
from research.qualification_manifest import (
    QualificationRunManifest,
    load_qualification_manifest,
    verify_manifest_exports,
)


@dataclass(frozen=True)
class QualificationBundleReport:
    manifest: QualificationRunManifest
    evidence: EvidenceConsistencyReport
    qualification: CombinedQualificationReport


def _first_last_timestamp(csv_text: str, field: str) -> tuple[datetime, datetime]:
    reader = csv.DictReader(io.StringIO(csv_text))
    values: list[datetime] = []
    for row_number, row in enumerate(reader, start=2):
        raw = row.get(field)
        if raw is None:
            raise ValueError(f"row {row_number}: {field} is required")
        text = raw.strip()
        normalized = text[:-1] + "+00:00" if text.endswith("Z") else text
        try:
            parsed = datetime.fromisoformat(normalized)
        except ValueError as exc:
            raise ValueError(f"row {row_number}: {field} must be ISO-8601") from exc
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise ValueError(f"row {row_number}: {field} must include a timezone")
        values.append(parsed)
    if not values:
        raise ValueError(f"CSV contains no {field} values")
    return values[0], values[-1]


def preflight_qualification_bundle(
    manifest_json: str,
    completed_trades_csv: str,
    open_equity_csv: str,
    profitability_thresholds: QualificationThresholds = QualificationThresholds(),
    open_risk_thresholds: OpenRiskThresholds = OpenRiskThresholds(),
) -> QualificationBundleReport:
    """Verify one immutable evidence bundle before returning a qualification result.

    The order is deliberate: validate the manifest, verify exact export fingerprints,
    verify cross-file coverage, verify the snapshots span the declared test period,
    then score profitability and open-equity risk. No input is sorted or repaired.
    """
    manifest = load_qualification_manifest(manifest_json)
    verify_manifest_exports(manifest, completed_trades_csv, open_equity_csv)
    evidence = verify_evidence_consistency(completed_trades_csv, open_equity_csv)

    period_start = datetime.fromisoformat(manifest.period_start)
    period_end = datetime.fromisoformat(manifest.period_end)
    first_snapshot, last_snapshot = _first_last_timestamp(open_equity_csv, "timestamp")

    if first_snapshot > period_start:
        raise ValueError("open-equity evidence starts after the manifest test period")
    if last_snapshot < period_end:
        raise ValueError("open-equity evidence ends before the manifest test period")

    qualification = qualify_exported_run(
        completed_trades_csv,
        open_equity_csv,
        profitability_thresholds,
        open_risk_thresholds,
    )
    return QualificationBundleReport(
        manifest=manifest,
        evidence=evidence,
        qualification=qualification,
    )
