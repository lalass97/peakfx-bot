from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path

from research.run_long_only_qualification import main


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


def _metrics(candidate_overrides: dict | None = None) -> dict:
    baseline = {
        "trade_count": 1088,
        "net_profit": -245.50,
        "profit_factor": 0.98,
        "maximum_drawdown_fraction": 0.1378,
        "profitable_year_fraction": 0.40,
        "two_x_cost_net_profit": -600.0,
        "sequence_risk_decision": "red",
    }
    candidate = {
        "trade_count": 500,
        "net_profit": 1000.0,
        "profit_factor": 1.30,
        "maximum_drawdown_fraction": 0.10,
        "profitable_year_fraction": 0.70,
        "two_x_cost_net_profit": 250.0,
        "sequence_risk_decision": "green",
    }
    candidate.update(candidate_overrides or {})
    return {"baseline": baseline, "candidate": candidate}


def _write_inputs(tmp_path: Path, metrics: dict) -> tuple[Path, Path]:
    manifest_path = tmp_path / "manifest.json"
    metrics_path = tmp_path / "metrics.json"
    manifest_path.write_text(json.dumps(_manifest(tmp_path)), encoding="utf-8")
    metrics_path.write_text(json.dumps(metrics), encoding="utf-8")
    return manifest_path, metrics_path


def test_promote_returns_zero_and_deterministic_json(tmp_path, capsys):
    manifest, metrics = _write_inputs(tmp_path, _metrics())
    output = tmp_path / "result.json"

    assert main([str(manifest), str(metrics), "--output", str(output)]) == 0
    stdout = capsys.readouterr().out.strip()
    result = json.loads(stdout)
    assert result["decision"] == "promote"
    assert result["failed_gates"] == []
    assert output.read_text(encoding="utf-8").strip() == stdout


def test_measured_failure_returns_reject_exit_code(tmp_path, capsys):
    manifest, metrics = _write_inputs(tmp_path, _metrics({"profit_factor": 1.05}))

    assert main([str(manifest), str(metrics)]) == 2
    result = json.loads(capsys.readouterr().out)
    assert result["decision"] == "reject"
    assert "minimum_profit_factor" in result["failed_gates"]


def test_insufficient_sequence_evidence_returns_inconclusive(tmp_path, capsys):
    manifest, metrics = _write_inputs(
        tmp_path, _metrics({"sequence_risk_decision": "inconclusive"})
    )

    assert main([str(manifest), str(metrics)]) == 3
    result = json.loads(capsys.readouterr().out)
    assert result["decision"] == "inconclusive"


def test_changed_evidence_returns_invalid_before_scoring(tmp_path, capsys):
    manifest, metrics = _write_inputs(tmp_path, _metrics())
    data = json.loads(manifest.read_text(encoding="utf-8"))
    Path(data["candidate_trades"]["path"]).write_bytes(b"changed")

    assert main([str(manifest), str(metrics)]) == 4
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "invalid"
    assert "fingerprint mismatch" in result["error"]


def test_unknown_metric_field_is_invalid(tmp_path, capsys):
    values = _metrics()
    values["candidate"]["unexpected"] = True
    manifest, metrics = _write_inputs(tmp_path, values)

    assert main([str(manifest), str(metrics)]) == 4
    result = json.loads(capsys.readouterr().out)
    assert "fields mismatch" in result["error"]
