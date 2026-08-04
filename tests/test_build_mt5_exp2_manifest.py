from __future__ import annotations

from pathlib import Path

import pytest

from research.build_mt5_exp2_manifest import build_manifest, sha256_file
from research.validate_mt5_exp2_run import validate_run


def test_builds_valid_screen_manifest(tmp_path: Path) -> None:
    source = tmp_path / "candidate.mq5"
    report = tmp_path / "report.html"
    source.write_text("candidate", encoding="utf-8")
    report.write_text("report", encoding="utf-8")

    manifest = build_manifest(
        stage="screen_12m",
        source_path=source,
        report_path=report,
        deposit=10000.0,
        leverage="1:100",
        net_profit=250.0,
        profit_factor=1.20,
        expected_payoff=3.5,
        completed_trades=45,
        max_drawdown_percent=4.2,
        safety_violations=0,
    )

    assert manifest["start_date"] == "2024-07-01"
    assert manifest["end_date"] == "2025-06-30"
    assert manifest["source_sha256"] == sha256_file(source)
    assert manifest["report_sha256"] == sha256_file(report)
    assert validate_run(manifest).valid is True


@pytest.mark.parametrize("stage", ["ten_year", "random_window", ""])
def test_rejects_unsupported_stage(tmp_path: Path, stage: str) -> None:
    source = tmp_path / "candidate.mq5"
    report = tmp_path / "report.html"
    source.write_text("candidate", encoding="utf-8")
    report.write_text("report", encoding="utf-8")

    with pytest.raises(ValueError):
        build_manifest(
            stage=stage,
            source_path=source,
            report_path=report,
            deposit=10000.0,
            leverage="1:100",
            net_profit=0.0,
            profit_factor=1.0,
            expected_payoff=0.0,
            completed_trades=0,
            max_drawdown_percent=0.0,
            safety_violations=0,
        )


def test_hash_changes_when_report_changes(tmp_path: Path) -> None:
    report = tmp_path / "report.html"
    report.write_text("first", encoding="utf-8")
    first = sha256_file(report)
    report.write_text("second", encoding="utf-8")
    second = sha256_file(report)
    assert first != second
