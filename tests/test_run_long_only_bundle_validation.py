from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path

from research.run_long_only_bundle_validation import main


def _file(tmp_path: Path, name: str, content: bytes) -> dict[str, str]:
    path = tmp_path / name
    path.write_bytes(content)
    return {"path": str(path), "sha256_hex": sha256(content).hexdigest()}


def _manifest(tmp_path: Path) -> dict:
    return {
        "baseline_report": _file(tmp_path, "baseline.html", b"baseline report"),
        "candidate_report": _file(tmp_path, "candidate.html", b"candidate report"),
        "baseline_trades": _file(tmp_path, "baseline.csv", b"baseline trades"),
        "candidate_trades": _file(tmp_path, "candidate.csv", b"candidate trades"),
        "candidate_open_equity": _file(tmp_path, "equity.csv", b"equity"),
        "baseline_strategy_id": "PeakFX_pullback_baseline_v142",
        "candidate_strategy_id": "PeakFX_pullback_long_only_exp1",
        "symbol": "EURUSD",
        "timeframe": "H1",
        "test_start": "2016-01-01",
        "test_end": "2025-07-31",
        "initial_deposit": 10000.0,
        "leverage": "1:100",
        "modeling_mode": "every_tick_based_on_real_ticks",
        "cost_stress_multiple": 2.0,
    }


def test_valid_manifest_returns_zero_and_deterministic_json(tmp_path, capsys):
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(_manifest(tmp_path)), encoding="utf-8")
    output = tmp_path / "result.json"

    assert main([str(path), "--output", str(output)]) == 0
    stdout = capsys.readouterr().out.strip()
    assert json.loads(stdout)["status"] == "valid"
    assert output.read_text(encoding="utf-8").strip() == stdout


def test_changed_evidence_returns_invalid_exit_code(tmp_path, capsys):
    manifest = _manifest(tmp_path)
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    Path(manifest["candidate_trades"]["path"]).write_bytes(b"changed")

    assert main([str(path)]) == 4
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "invalid"
    assert "fingerprint mismatch" in result["error"]


def test_unknown_manifest_field_is_rejected(tmp_path, capsys):
    manifest = _manifest(tmp_path)
    manifest["unexpected"] = True
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")

    assert main([str(path)]) == 4
    result = json.loads(capsys.readouterr().out)
    assert "fields mismatch" in result["error"]
