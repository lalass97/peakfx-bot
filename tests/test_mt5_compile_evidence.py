from hashlib import sha256
from pathlib import Path

import pytest

from research.mt5_compile_evidence import MT5CompileEvidence, validate_mt5_compile_evidence


def _write(path: Path, content: bytes) -> tuple[str, str]:
    path.write_bytes(content)
    return str(path), sha256(content).hexdigest()


def _evidence(tmp_path: Path, log: bytes | None = None) -> MT5CompileEvidence:
    source = (
        b'#property version   "1.43"\n'
        b'void ExecuteEntry(bool isLong) { /* long_only_experiment_short_rejected */ }\n'
    )
    log = log or (
        b'PeakFX_EURUSD_H1_PULLBACK_LONG_ONLY_EXP1.mq5 : information: compiling\n'
        b'Result: 0 errors, 0 warnings\n'
    )
    source_path, source_hash = _write(
        tmp_path / "PeakFX_EURUSD_H1_PULLBACK_LONG_ONLY_EXP1.mq5", source
    )
    log_path, log_hash = _write(tmp_path / "compile.log", log)
    return MT5CompileEvidence(source_path, source_hash, log_path, log_hash)


def test_clean_compile_evidence_is_accepted(tmp_path):
    validate_mt5_compile_evidence(_evidence(tmp_path))


@pytest.mark.parametrize(
    "log,message",
    [
        (b'PeakFX_EURUSD_H1_PULLBACK_LONG_ONLY_EXP1.mq5\n1 errors, 0 warnings\n', "zero errors"),
        (b'PeakFX_EURUSD_H1_PULLBACK_LONG_ONLY_EXP1.mq5\n0 errors, 1 warnings\n', "zero warnings"),
        (b'other.mq5\n0 errors, 0 warnings\n', "expected candidate file"),
    ],
)
def test_bad_compile_log_fails_closed(tmp_path, log, message):
    with pytest.raises(ValueError, match=message):
        validate_mt5_compile_evidence(_evidence(tmp_path, log))


def test_changed_source_is_rejected(tmp_path):
    evidence = _evidence(tmp_path)
    Path(evidence.source_path).write_text("changed", encoding="utf-8")
    with pytest.raises(ValueError, match="fingerprint mismatch"):
        validate_mt5_compile_evidence(evidence)


def test_wrong_filename_is_rejected(tmp_path):
    evidence = _evidence(tmp_path)
    wrong = Path(evidence.source_path).with_name("wrong.mq5")
    Path(evidence.source_path).rename(wrong)
    amended = MT5CompileEvidence(
        str(wrong), evidence.source_sha256, evidence.compiler_log_path, evidence.compiler_log_sha256
    )
    with pytest.raises(ValueError, match="filename"):
        validate_mt5_compile_evidence(amended)
