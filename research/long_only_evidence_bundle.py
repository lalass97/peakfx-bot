from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path


@dataclass(frozen=True)
class EvidenceFile:
    path: str
    sha256_hex: str


@dataclass(frozen=True)
class LongOnlyEvidenceBundle:
    baseline_report: EvidenceFile
    candidate_report: EvidenceFile
    baseline_trades: EvidenceFile
    candidate_trades: EvidenceFile
    candidate_open_equity: EvidenceFile
    baseline_strategy_id: str
    candidate_strategy_id: str
    symbol: str
    timeframe: str
    test_start: str
    test_end: str
    initial_deposit: float
    leverage: str
    modeling_mode: str
    cost_stress_multiple: float


def _validate_hash(value: str) -> None:
    if len(value) != 64 or any(ch not in "0123456789abcdef" for ch in value):
        raise ValueError("sha256_hex must be a lowercase 64-character SHA-256 digest")


def _verify_file(evidence: EvidenceFile) -> None:
    _validate_hash(evidence.sha256_hex)
    path = Path(evidence.path)
    if not path.is_file():
        raise ValueError(f"evidence file does not exist: {evidence.path}")
    digest = sha256(path.read_bytes()).hexdigest()
    if digest != evidence.sha256_hex:
        raise ValueError(f"evidence fingerprint mismatch: {evidence.path}")


def validate_long_only_evidence_bundle(bundle: LongOnlyEvidenceBundle) -> None:
    """Fail closed unless one immutable A/B evidence bundle is complete and comparable."""
    if bundle.baseline_strategy_id == bundle.candidate_strategy_id:
        raise ValueError("baseline and candidate strategy IDs must differ")
    if not bundle.baseline_strategy_id or not bundle.candidate_strategy_id:
        raise ValueError("strategy IDs must be non-empty")
    if bundle.symbol != "EURUSD" or bundle.timeframe != "H1":
        raise ValueError("long-only experiment must remain EURUSD H1")
    if not bundle.test_start or not bundle.test_end or bundle.test_start >= bundle.test_end:
        raise ValueError("test period must be complete and ordered")
    if bundle.initial_deposit <= 0:
        raise ValueError("initial_deposit must be positive")
    if not bundle.leverage:
        raise ValueError("leverage must be declared")
    if bundle.modeling_mode != "every_tick_based_on_real_ticks":
        raise ValueError("modeling_mode must be every_tick_based_on_real_ticks")
    if bundle.cost_stress_multiple < 2.0:
        raise ValueError("cost_stress_multiple must be at least 2.0")

    evidence = (
        bundle.baseline_report,
        bundle.candidate_report,
        bundle.baseline_trades,
        bundle.candidate_trades,
        bundle.candidate_open_equity,
    )
    paths = tuple(item.path for item in evidence)
    if len(set(paths)) != len(paths):
        raise ValueError("evidence paths must be unique")
    for item in evidence:
        _verify_file(item)
