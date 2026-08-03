from __future__ import annotations

import argparse
import json
from pathlib import Path

from research.mt5_compile_evidence import MT5CompileEvidence, validate_mt5_compile_evidence


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate immutable MetaEditor compile evidence")
    parser.add_argument("manifest", help="JSON compile-evidence manifest")
    parser.add_argument("--output", help="Optional deterministic JSON output path")
    args = parser.parse_args(argv)

    try:
        data = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
        required = {
            "source_path",
            "source_sha256",
            "compiler_log_path",
            "compiler_log_sha256",
            "expected_filename",
            "expected_version",
        }
        if set(data) != required:
            raise ValueError(
                f"manifest fields mismatch; missing={sorted(required-set(data))}, extra={sorted(set(data)-required)}"
            )
        evidence = MT5CompileEvidence(**data)
        validate_mt5_compile_evidence(evidence)
        result = {
            "status": "valid",
            "filename": evidence.expected_filename,
            "version": evidence.expected_version,
            "source_sha256": evidence.source_sha256,
            "compiler_log_sha256": evidence.compiler_log_sha256,
        }
        code = 0
    except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
        result = {"status": "invalid", "error": str(exc)}
        code = 4

    rendered = json.dumps(result, sort_keys=True, separators=(",", ":"), allow_nan=False)
    print(rendered)
    if args.output:
        Path(args.output).write_text(rendered + "\n", encoding="utf-8")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
