from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path


@dataclass(frozen=True)
class MT5CompileEvidence:
    source_path: str
    source_sha256: str
    compiler_log_path: str
    compiler_log_sha256: str
    expected_filename: str = "PeakFX_EURUSD_H1_PULLBACK_LONG_ONLY_EXP1.mq5"
    expected_version: str = '1.43'


def _validate_digest(value: str, name: str) -> None:
    if len(value) != 64 or any(ch not in "0123456789abcdef" for ch in value):
        raise ValueError(f"{name} must be a lowercase 64-character SHA-256 digest")


def _verified_bytes(path_text: str, expected_digest: str, name: str) -> bytes:
    _validate_digest(expected_digest, f"{name}_sha256")
    path = Path(path_text)
    if not path.is_file():
        raise ValueError(f"{name} file does not exist: {path_text}")
    content = path.read_bytes()
    actual = sha256(content).hexdigest()
    if actual != expected_digest:
        raise ValueError(f"{name} fingerprint mismatch")
    return content


def validate_mt5_compile_evidence(evidence: MT5CompileEvidence) -> None:
    """Accept only immutable evidence of a clean MetaEditor compile.

    This validator does not compile MQL5 itself. It checks that the exact candidate
    source and exported compiler log are unchanged and that the log explicitly
    records zero errors for the intended file/version.
    """
    source = _verified_bytes(evidence.source_path, evidence.source_sha256, "source")
    log = _verified_bytes(evidence.compiler_log_path, evidence.compiler_log_sha256, "compiler_log")

    source_text = source.decode("utf-8")
    log_text = log.decode("utf-8", errors="replace")

    if Path(evidence.source_path).name != evidence.expected_filename:
        raise ValueError("source filename does not match the declared candidate")
    if f'#property version   "{evidence.expected_version}"' not in source_text:
        raise ValueError("source version marker does not match the declared candidate")
    if "long_only_experiment_short_rejected" not in source_text:
        raise ValueError("source is missing the execution-level short-entry guard")

    normalized = " ".join(log_text.lower().split())
    filename_lower = evidence.expected_filename.lower()
    if filename_lower not in normalized:
        raise ValueError("compiler log does not identify the expected candidate file")
    if "0 errors" not in normalized:
        raise ValueError("compiler log does not prove zero errors")
    if "0 warnings" not in normalized:
        raise ValueError("compiler log does not prove zero warnings")
