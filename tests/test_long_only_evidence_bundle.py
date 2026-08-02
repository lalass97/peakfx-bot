from hashlib import sha256

import pytest

from research.long_only_evidence_bundle import (
    EvidenceFile,
    LongOnlyEvidenceBundle,
    validate_long_only_evidence_bundle,
)


def _evidence(tmp_path, name: str, content: bytes = b"evidence") -> EvidenceFile:
    path = tmp_path / name
    path.write_bytes(content)
    return EvidenceFile(str(path), sha256(content).hexdigest())


def _bundle(tmp_path, **overrides) -> LongOnlyEvidenceBundle:
    values = dict(
        baseline_report=_evidence(tmp_path, "baseline.html", b"baseline report"),
        candidate_report=_evidence(tmp_path, "candidate.html", b"candidate report"),
        baseline_trades=_evidence(tmp_path, "baseline.csv", b"baseline trades"),
        candidate_trades=_evidence(tmp_path, "candidate.csv", b"candidate trades"),
        candidate_open_equity=_evidence(tmp_path, "candidate_equity.csv", b"equity"),
        baseline_strategy_id="PeakFX_pullback_baseline_v142",
        candidate_strategy_id="PeakFX_pullback_long_only_exp1",
        symbol="EURUSD",
        timeframe="H1",
        test_start="2016-01-01",
        test_end="2025-07-31",
        initial_deposit=10000.0,
        leverage="1:100",
        modeling_mode="every_tick_based_on_real_ticks",
        cost_stress_multiple=2.0,
    )
    values.update(overrides)
    return LongOnlyEvidenceBundle(**values)


def test_complete_bundle_is_accepted(tmp_path):
    validate_long_only_evidence_bundle(_bundle(tmp_path))


def test_changed_evidence_is_rejected(tmp_path):
    bundle = _bundle(tmp_path)
    with open(bundle.candidate_trades.path, "ab") as handle:
        handle.write(b"changed")

    with pytest.raises(ValueError, match="fingerprint mismatch"):
        validate_long_only_evidence_bundle(bundle)


@pytest.mark.parametrize(
    "overrides,message",
    [
        ({"candidate_strategy_id": "PeakFX_pullback_baseline_v142"}, "must differ"),
        ({"symbol": "GBPUSD"}, "EURUSD H1"),
        ({"timeframe": "M30"}, "EURUSD H1"),
        ({"test_start": "2025-01-01", "test_end": "2024-01-01"}, "ordered"),
        ({"initial_deposit": 0.0}, "positive"),
        ({"modeling_mode": "open_prices_only"}, "real_ticks"),
        ({"cost_stress_multiple": 1.5}, "at least 2.0"),
    ],
)
def test_invalid_bundle_metadata_fails_closed(tmp_path, overrides, message):
    with pytest.raises(ValueError, match=message):
        validate_long_only_evidence_bundle(_bundle(tmp_path, **overrides))


def test_duplicate_evidence_paths_are_rejected(tmp_path):
    bundle = _bundle(tmp_path)
    duplicate = LongOnlyEvidenceBundle(
        **{**bundle.__dict__, "candidate_report": bundle.baseline_report}
    )

    with pytest.raises(ValueError, match="paths must be unique"):
        validate_long_only_evidence_bundle(duplicate)
