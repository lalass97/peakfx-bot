from __future__ import annotations

import argparse
import hashlib
import re
import sys
from pathlib import Path

SOURCE_FILENAME = "PeakFX_EURUSD_H1_PULLBACK_CONFIRMED_BREAKOUT_EXP1.mq5"
CANDIDATE_FILENAME = "PeakFX_EURUSD_H1_PULLBACK_CONFIRMED_BREAKOUT_EXP2.mq5"
SOURCE_BANNER = "Version 1.44 - confirmed-breakout experiment"
CANDIDATE_BANNER = "Version 1.45 - stronger confirmed-breakout experiment"
SOURCE_DESCRIPTION = "trigger close must clear pullback extreme by 0.10 ATR"
CANDIDATE_DESCRIPTION = "trigger close must clear pullback extreme by 0.20 ATR"

ANY_VERSION_PATTERN = re.compile(r'(?m)^(\s*#property\s+version\s+)"[^"]+"(\s*)$')
MAGIC_PATTERN = re.compile(r'(?m)^(\s*input\s+long\s+MagicNumber\s*=\s*)26073024(\s*;\s*)$')
TELEMETRY_PATTERN = re.compile(
    r'(?m)^(\s*input\s+string\s+TelemetryFile\s*=\s*)'
    r'"peakfx_confirmed_breakout_exp1_events\.csv"(\s*;\s*)$'
)
LONG_PATTERN = re.compile(
    r'c\s*>\s*g_setup\.pullback_high\s*\+\s*\(\s*0\.10\s*\*\s*atr\s*\)'
)
SHORT_PATTERN = re.compile(
    r'c\s*<\s*g_setup\.pullback_low\s*-\s*\(\s*0\.10\s*\*\s*atr\s*\)'
)


def _read_mql5_source(path: Path) -> tuple[str, str]:
    raw = path.read_bytes()
    if raw.startswith(b"\xef\xbb\xbf"):
        return raw.decode("utf-8-sig"), "utf-8-sig"
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        return raw.decode("utf-16"), "utf-16"
    try:
        return raw.decode("utf-8"), "utf-8"
    except UnicodeDecodeError:
        try:
            return raw.decode("utf-16-le"), "utf-16-le"
        except UnicodeDecodeError as exc:
            raise ValueError(
                f"unsupported source encoding for {path}; expected UTF-8 or UTF-16"
            ) from exc


def _replace_exactly_once(
    source: str,
    pattern: re.Pattern[str],
    replacement: str | callable,
    label: str,
) -> str:
    matches = list(pattern.finditer(source))
    if len(matches) != 1:
        raise ValueError(
            f"expected exactly one {label} marker, found {len(matches)}"
        )
    return pattern.sub(replacement, source, count=1)


def _replace_optional_once(source: str, old: str, new: str) -> str:
    count = source.count(old)
    if count > 1:
        raise ValueError(f"ambiguous optional source marker, found {count}: {old}")
    return source.replace(old, new, 1) if count == 1 else source


def build_confirmed_breakout_exp2(source: str) -> str:
    candidate = source

    # The version directive is metadata, not trading logic. Require exactly one
    # directive but normalize whatever local formatting/value is present.
    candidate = _replace_exactly_once(
        candidate,
        ANY_VERSION_PATTERN,
        lambda m: f'{m.group(1)}"1.45"{m.group(2)}',
        "MQL5 version directive",
    )

    # These four markers define the actual EXP1 trading hypothesis and remain
    # strict. The builder refuses to proceed unless all are present exactly once.
    candidate = _replace_exactly_once(
        candidate,
        MAGIC_PATTERN,
        lambda m: f"{m.group(1)}26073025{m.group(2)}",
        "EXP1 magic number",
    )
    candidate = _replace_exactly_once(
        candidate,
        TELEMETRY_PATTERN,
        lambda m: (
            f'{m.group(1)}"peakfx_confirmed_breakout_exp2_events.csv"{m.group(2)}'
        ),
        "EXP1 telemetry",
    )
    candidate = _replace_exactly_once(
        candidate,
        LONG_PATTERN,
        "c > g_setup.pullback_high + (0.20*atr)",
        "EXP1 long trigger",
    )
    candidate = _replace_exactly_once(
        candidate,
        SHORT_PATTERN,
        "c < g_setup.pullback_low - (0.20*atr)",
        "EXP1 short trigger",
    )

    candidate = _replace_optional_once(candidate, SOURCE_FILENAME, CANDIDATE_FILENAME)
    candidate = _replace_optional_once(candidate, SOURCE_BANNER, CANDIDATE_BANNER)
    candidate = _replace_optional_once(candidate, SOURCE_DESCRIPTION, CANDIDATE_DESCRIPTION)

    required_literals = (
        '"1.45"',
        "26073025",
        "peakfx_confirmed_breakout_exp2_events.csv",
        "c > g_setup.pullback_high + (0.20*atr)",
        "c < g_setup.pullback_low - (0.20*atr)",
    )
    for marker in required_literals:
        if candidate.count(marker) != 1:
            raise ValueError(f"candidate validation failed for marker: {marker}")

    stale_patterns = (
        MAGIC_PATTERN,
        TELEMETRY_PATTERN,
        LONG_PATTERN,
        SHORT_PATTERN,
    )
    if any(pattern.search(candidate) for pattern in stale_patterns):
        raise ValueError("stale EXP1 semantic marker remains after conversion")

    return candidate


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build PeakFX confirmed-breakout EXP2")
    parser.add_argument("source", help="Exact compiled-clean EXP1 source")
    parser.add_argument("output", help="Destination v1.45 .mq5 path")
    args = parser.parse_args(argv)

    source_path = Path(args.source)
    output_path = Path(args.output)
    try:
        source, detected_encoding = _read_mql5_source(source_path)
        source_sha256 = hashlib.sha256(source_path.read_bytes()).hexdigest()
        print(
            f"EXP2 builder source={source_path} encoding={detected_encoding} "
            f"sha256={source_sha256}"
        )
        candidate = build_confirmed_breakout_exp2(source)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(candidate, encoding="utf-8", newline="\n")
        print(f"EXP2 candidate written: {output_path}")
        return 0
    except Exception as exc:
        print(f"EXP2_BUILDER_ERROR: {type(exc).__name__}: {exc}", file=sys.stdout)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
