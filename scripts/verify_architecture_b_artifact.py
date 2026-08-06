#!/usr/bin/env python3
"""Independently verify a PeakFX Architecture B baseline artifact.

This script does not trust manifest hashes. It recomputes hashes from disk,
checks the frozen 4x5 matrix, validates all run metadata, and emits a machine-
readable verification report. It intentionally does not decide profitability;
that decision must be made from the raw MT5 reports under the frozen gates.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

EXPECTED_CONFIGS = {"B01", "B02", "B03", "B04"}
EXPECTED_WINDOWS = {
    "2020_2021",
    "2021_2022",
    "2022_2023",
    "2023_2024",
    "2024_2025",
}
EXPECTED_RUNS = {(c, w) for c in EXPECTED_CONFIGS for w in EXPECTED_WINDOWS}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


def fail(errors: list[str], message: str) -> None:
    errors.append(message)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("artifact_root", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    root = args.artifact_root.resolve()
    errors: list[str] = []
    checks: list[dict[str, Any]] = []

    manifest_path = root / "architecture_b_manifest.json"
    if not manifest_path.is_file():
        print(f"Missing manifest: {manifest_path}", file=sys.stderr)
        return 2

    manifest = load_json(manifest_path)
    runs = manifest.get("runs", [])
    if len(runs) != 20:
        fail(errors, f"Expected 20 manifest runs, found {len(runs)}")

    seen: set[tuple[str, str]] = set()
    source_hashes: set[str] = set()
    binary_hashes: set[str] = set()
    spec_hashes: set[str] = set()

    for index, run in enumerate(runs):
        cfg = str(run.get("configuration", ""))
        window = str(run.get("window", ""))
        pair = (cfg, window)
        if pair in seen:
            fail(errors, f"Duplicate run {cfg}/{window}")
        seen.add(pair)

        if cfg not in EXPECTED_CONFIGS:
            fail(errors, f"Unexpected configuration: {cfg}")
        if window not in EXPECTED_WINDOWS:
            fail(errors, f"Unexpected window: {window}")
        if run.get("tick_volume_revision") is not False:
            fail(errors, f"B-R1 was not disabled for {cfg}/{window}")
        if run.get("oos_locked") is not True:
            fail(errors, f"OOS lock missing for {cfg}/{window}")
        if str(run.get("model")) != "real_ticks":
            fail(errors, f"Non-real-tick model for {cfg}/{window}")

        source_hashes.add(str(run.get("source_sha256", "")))
        binary_hashes.add(str(run.get("binary_sha256", "")))
        if run.get("spec_sha256"):
            spec_hashes.add(str(run["spec_sha256"]))

        report = Path(str(run.get("report", "")))
        if not report.is_absolute():
            candidates = [root / report, root / cfg / window / report.name]
            report = next((p for p in candidates if p.is_file()), candidates[-1])
        if not report.is_file():
            fail(errors, f"Missing report for {cfg}/{window}: {report}")
            continue

        actual_report_hash = sha256(report)
        expected_report_hash = str(run.get("report_sha256", ""))
        if actual_report_hash != expected_report_hash:
            fail(errors, f"Report hash mismatch for {cfg}/{window}")

        metadata_path = root / cfg / window / "run_metadata.json"
        if not metadata_path.is_file():
            fail(errors, f"Missing run metadata for {cfg}/{window}")
        else:
            metadata = load_json(metadata_path)
            if metadata.get("configuration") != cfg or metadata.get("window") != window:
                fail(errors, f"Metadata identity mismatch for {cfg}/{window}")
            checks.append({
                "configuration": cfg,
                "window": window,
                "report": str(report),
                "report_sha256": actual_report_hash,
                "metadata_sha256": sha256(metadata_path),
            })

    missing = EXPECTED_RUNS - seen
    extra = seen - EXPECTED_RUNS
    if missing:
        fail(errors, f"Missing matrix cells: {sorted(missing)}")
    if extra:
        fail(errors, f"Unexpected matrix cells: {sorted(extra)}")

    if len(source_hashes) != 1:
        fail(errors, f"Expected one source hash across all runs, found {len(source_hashes)}")
    if len(binary_hashes) != 1:
        fail(errors, f"Expected one binary hash across all runs, found {len(binary_hashes)}")
    if spec_hashes and len(spec_hashes) != 1:
        fail(errors, f"Expected one spec hash across all runs, found {len(spec_hashes)}")

    source_copy = root / "frozen_inputs" / "PeakFX_EURUSD_ARCH_B_VOLATILITY_EXPANSION.mq5"
    spec_copy = root / "frozen_inputs" / "ARCHITECTURE_B_FROZEN_BASELINE_SPEC.md"
    binary_copy = root / "frozen_inputs" / "PeakFX_EURUSD_ARCH_B_VOLATILITY_EXPANSION.ex5"

    for label, path, hashes in (
        ("source", source_copy, source_hashes),
        ("binary", binary_copy, binary_hashes),
        ("specification", spec_copy, spec_hashes),
    ):
        if not path.is_file():
            fail(errors, f"Missing frozen {label} copy: {path}")
        elif hashes:
            actual = sha256(path)
            expected = next(iter(hashes))
            if actual != expected:
                fail(errors, f"Frozen {label} hash mismatch")

    result = {
        "artifact_root": str(root),
        "verified": not errors,
        "expected_run_count": 20,
        "observed_run_count": len(runs),
        "matrix_complete": seen == EXPECTED_RUNS,
        "source_sha256": next(iter(source_hashes), None),
        "binary_sha256": next(iter(binary_hashes), None),
        "spec_sha256": next(iter(spec_hashes), None),
        "checks": checks,
        "errors": errors,
    }

    output = args.output or (root / "independent_verification.json")
    output.write_text(json.dumps(result, indent=2), encoding="utf-8")

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        print(f"Verification FAILED. Report: {output}", file=sys.stderr)
        return 1

    print(f"Verification PASSED: 20/20 reports and frozen inputs verified. Report: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
