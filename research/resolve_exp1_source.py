from __future__ import annotations

import argparse
import hashlib
import os
import re
import sys
from pathlib import Path

NAME_GLOB = "*CONFIRMED_BREAKOUT_EXP1*.mq5"
VERSION_RE = re.compile(r"#property\s+version\s+\"1\.44\"", re.IGNORECASE)
MAGIC_RE = re.compile(r"\bMagicNumber\s*=\s*26073024\s*;", re.IGNORECASE)
TELEMETRY_RE = re.compile(
    r"TelemetryFile\s*=\s*\"peakfx_confirmed_breakout_exp1_events\.csv\"\s*;",
    re.IGNORECASE,
)
LONG_RE = re.compile(
    r"c\s*>\s*g_setup\.pullback_high\s*\+\s*\(\s*0\.10\s*\*\s*atr\s*\)",
    re.IGNORECASE,
)
SHORT_RE = re.compile(
    r"c\s*<\s*g_setup\.pullback_low\s*-\s*\(\s*0\.10\s*\*\s*atr\s*\)",
    re.IGNORECASE,
)


def decode_source(path: Path) -> tuple[str, str]:
    raw = path.read_bytes()
    if not raw:
        raise ValueError("empty file")
    if raw.startswith(b"\xef\xbb\xbf"):
        return raw.decode("utf-8-sig"), "utf-8-sig"
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        return raw.decode("utf-16"), "utf-16"

    sample = raw[:4096]
    even_nulls = sample[0::2].count(0)
    odd_nulls = sample[1::2].count(0)
    pairs = max(1, len(sample) // 2)
    if odd_nulls / pairs > 0.30 and even_nulls / pairs < 0.05:
        return raw.decode("utf-16-le"), "utf-16-le"
    if even_nulls / pairs > 0.30 and odd_nulls / pairs < 0.05:
        return raw.decode("utf-16-be"), "utf-16-be"

    return raw.decode("utf-8"), "utf-8"


def is_verified_exp1(text: str) -> tuple[bool, list[str]]:
    checks = {
        "version_1_44": VERSION_RE.search(text),
        "magic_26073024": MAGIC_RE.search(text),
        "exp1_telemetry": TELEMETRY_RE.search(text),
        "long_0_10_atr": LONG_RE.search(text),
        "short_0_10_atr": SHORT_RE.search(text),
    }
    missing = [name for name, match in checks.items() if match is None]
    return not missing, missing


def iter_candidates(explicit: Path | None) -> list[Path]:
    candidates: list[Path] = []
    seen: set[str] = set()

    def add(path: Path) -> None:
        try:
            key = str(path.resolve()).lower()
        except OSError:
            key = str(path).lower()
        if key not in seen:
            seen.add(key)
            candidates.append(path)

    if explicit is not None:
        add(explicit)

    roots: list[Path] = []
    userprofile = os.environ.get("USERPROFILE")
    appdata = os.environ.get("APPDATA")
    mt5_root = os.environ.get("MT5_ROOT")
    if explicit is not None:
        roots.append(explicit.parent)
    if userprofile:
        roots.append(Path(userprofile) / "Downloads")
    if appdata:
        roots.append(Path(appdata) / "MetaQuotes" / "Terminal")
    if mt5_root:
        roots.append(Path(mt5_root))

    for root in roots:
        if not root.exists():
            continue
        try:
            for path in root.rglob(NAME_GLOB):
                add(path)
        except (OSError, PermissionError):
            continue

    return candidates


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Resolve the exact verified EXP1 MQ5 source")
    parser.add_argument("--explicit", default="", help="Preferred source path")
    parser.add_argument("--github-env", default=os.environ.get("GITHUB_ENV", ""))
    args = parser.parse_args(argv)

    explicit = Path(args.explicit) if args.explicit else None
    diagnostics: list[str] = []

    for path in iter_candidates(explicit):
        if not path.is_file():
            diagnostics.append(f"skip missing: {path}")
            continue
        try:
            text, encoding = decode_source(path)
            valid, missing = is_verified_exp1(text)
            size = path.stat().st_size
            sha256 = hashlib.sha256(path.read_bytes()).hexdigest()
            if valid:
                resolved = str(path.resolve())
                print(
                    f"VERIFIED_EXP1_SOURCE path={resolved} size={size} "
                    f"encoding={encoding} sha256={sha256}"
                )
                if args.github_env:
                    with open(args.github_env, "a", encoding="utf-8") as handle:
                        handle.write(f"RESOLVED_EXP1_SOURCE={resolved}\n")
                return 0
            diagnostics.append(
                f"reject {path} size={size} encoding={encoding} missing={','.join(missing)}"
            )
        except Exception as exc:
            diagnostics.append(f"reject {path}: {type(exc).__name__}: {exc}")

    print("No verified EXP1 source was found.", file=sys.stderr)
    for item in diagnostics:
        print(item, file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
