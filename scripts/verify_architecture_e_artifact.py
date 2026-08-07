#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

EXPECTED_CONFIGS = {"E01", "E02", "E03", "E04"}
EXPECTED_WINDOWS = {"2020_2021", "2021_2022", "2022_2023", "2023_2024", "2024_2025"}
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


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("artifact_root", type=Path)
    p.add_argument("--output", type=Path)
    a = p.parse_args()
    root = a.artifact_root.resolve()
    errors: list[str] = []
    checks: list[dict[str, Any]] = []

    manifest_path = root / "architecture_e_manifest.json"
    if not manifest_path.is_file():
        print(f"Missing manifest: {manifest_path}", file=sys.stderr)
        return 2
    manifest = load_json(manifest_path)
    runs = manifest.get("runs", [])
    if len(runs) != 20:
        errors.append(f"Expected 20 manifest runs, found {len(runs)}")

    seen: set[tuple[str, str]] = set()
    src: set[str] = set(); binh: set[str] = set(); spec: set[str] = set()
    for run in runs:
        cfg = str(run.get("configuration", "")); win = str(run.get("window", ""))
        pair = (cfg, win)
        if pair in seen: errors.append(f"Duplicate run {cfg}/{win}")
        seen.add(pair)
        if cfg not in EXPECTED_CONFIGS: errors.append(f"Unexpected configuration {cfg}")
        if win not in EXPECTED_WINDOWS: errors.append(f"Unexpected window {win}")
        if run.get("oos_locked") is not True: errors.append(f"OOS lock missing for {cfg}/{win}")
        if str(run.get("model")) != "real_ticks": errors.append(f"Non-real-tick model for {cfg}/{win}")
        if str(run.get("timeframe")) != "M15": errors.append(f"Wrong timeframe for {cfg}/{win}")
        src.add(str(run.get("source_sha256", ""))); binh.add(str(run.get("binary_sha256", ""))); spec.add(str(run.get("spec_sha256", "")))
        execution = run.get("execution", {})
        if float(execution.get("bars", 0)) <= 0 or float(execution.get("ticks", 0)) <= 0:
            errors.append(f"Empty execution for {cfg}/{win}")
        if abs(float(execution.get("initial_deposit", 0)) - 10000.0) > 0.01:
            errors.append(f"Wrong deposit for {cfg}/{win}")

        report = Path(str(run.get("report", "")))
        if not report.is_absolute():
            candidates = [root / report, root / cfg / win / report.name]
            report = next((x for x in candidates if x.is_file()), candidates[-1])
        if not report.is_file():
            errors.append(f"Missing report for {cfg}/{win}: {report}")
            continue
        rh = sha256(report)
        if rh != str(run.get("report_sha256", "")): errors.append(f"Report hash mismatch for {cfg}/{win}")
        meta = root / cfg / win / "run_metadata.json"
        if not meta.is_file(): errors.append(f"Missing run metadata for {cfg}/{win}")
        else:
            m = load_json(meta)
            if m.get("configuration") != cfg or m.get("window") != win: errors.append(f"Metadata identity mismatch for {cfg}/{win}")
            checks.append({"configuration": cfg, "window": win, "report_sha256": rh, "metadata_sha256": sha256(meta)})

    if seen != EXPECTED_RUNS:
        errors.append(f"Matrix mismatch; missing={sorted(EXPECTED_RUNS-seen)} extra={sorted(seen-EXPECTED_RUNS)}")
    if len(src) != 1: errors.append(f"Expected one source hash, found {len(src)}")
    if len(binh) != 1: errors.append(f"Expected one binary hash, found {len(binh)}")
    if len(spec) != 1: errors.append(f"Expected one spec hash, found {len(spec)}")

    frozen = root / "frozen_inputs"
    copies = [
        (frozen / "PeakFX_EURUSD_ARCH_E_DAILY_FOLLOWTHROUGH.mq5", src, "source"),
        (frozen / "PeakFX_EURUSD_ARCH_E_DAILY_FOLLOWTHROUGH.ex5", binh, "binary"),
        (frozen / "ARCHITECTURE_E_FROZEN_BASELINE_SPEC.md", spec, "specification"),
    ]
    for path, hashes, label in copies:
        if not path.is_file(): errors.append(f"Missing frozen {label} copy: {path}")
        elif hashes and sha256(path) != next(iter(hashes)): errors.append(f"Frozen {label} hash mismatch")

    result = {
        "verified": not errors,
        "expected_run_count": 20,
        "observed_run_count": len(runs),
        "matrix_complete": seen == EXPECTED_RUNS,
        "checks": checks,
        "errors": errors,
    }
    out = a.output or root / "independent_verification.json"
    out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    if errors:
        for e in errors: print(f"ERROR: {e}", file=sys.stderr)
        return 1
    print("Verification PASSED: Architecture E 20/20 artifact verified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
