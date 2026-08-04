from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

SOURCE_FILENAME = "PeakFX_EURUSD_H1_PULLBACK_CONFIRMED_BREAKOUT_EXP1.mq5"
CANDIDATE_FILENAME = "PeakFX_EURUSD_H1_PULLBACK_CONFIRMED_BREAKOUT_EXP2.mq5"
SOURCE_BANNER = "Version 1.44 - confirmed-breakout experiment"
CANDIDATE_BANNER = "Version 1.45 - stronger confirmed-breakout experiment"
SOURCE_VERSION = '#property version   "1.44"'
CANDIDATE_VERSION = '#property version   "1.45"'
SOURCE_DESCRIPTION = "trigger close must clear pullback extreme by 0.10 ATR"
CANDIDATE_DESCRIPTION = "trigger close must clear pullback extreme by 0.20 ATR"
SOURCE_MAGIC = "input long             MagicNumber                  = 26073024;"
CANDIDATE_MAGIC = "input long             MagicNumber                  = 26073025;"
SOURCE_TELEMETRY = 'input string           TelemetryFile                = "peakfx_confirmed_breakout_exp1_events.csv";'
CANDIDATE_TELEMETRY = 'input string           TelemetryFile                = "peakfx_confirmed_breakout_exp2_events.csv";'
SOURCE_LONG_CONDITION = "c > g_setup.pullback_high + (0.10*atr)"
CANDIDATE_LONG_CONDITION = "c > g_setup.pullback_high + (0.20*atr)"
SOURCE_SHORT_CONDITION = "c < g_setup.pullback_low - (0.10*atr)"
CANDIDATE_SHORT_CONDITION = "c < g_setup.pullback_low - (0.20*atr)"


def _read_mql5_source(path: Path) -> tuple[str, str]:
    raw = path.read_bytes()
    if raw.startswith(b"\xef\xbb\xbf"):
        return raw.decode("utf-8-sig"), "utf-8-sig"
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        return raw.decode("utf-16"), "utf-16"
    try:
        return raw.decode("utf-8"), "utf-8"
    except UnicodeDecodeError:
        # MetaEditor commonly saves MQL5 files as UTF-16 LE without a BOM.
        try:
            return raw.decode("utf-16-le"), "utf-16-le"
        except UnicodeDecodeError as exc:
            raise ValueError(
                f"unsupported source encoding for {path}; expected UTF-8 or UTF-16"
            ) from exc


def _require_exact_count(source: str, marker: str, expected: int = 1) -> None:
    count = source.count(marker)
    if count != expected:
        raise ValueError(f"expected {expected} source marker(s), found {count}: {marker}")


def build_confirmed_breakout_exp2(source: str) -> str:
    source_markers = (
        SOURCE_FILENAME,
        SOURCE_BANNER,
        SOURCE_VERSION,
        SOURCE_DESCRIPTION,
        SOURCE_MAGIC,
        SOURCE_TELEMETRY,
        SOURCE_LONG_CONDITION,
        SOURCE_SHORT_CONDITION,
    )
    for marker in source_markers:
        _require_exact_count(source, marker)

    replacements = (
        (SOURCE_FILENAME, CANDIDATE_FILENAME),
        (SOURCE_BANNER, CANDIDATE_BANNER),
        (SOURCE_VERSION, CANDIDATE_VERSION),
        (SOURCE_DESCRIPTION, CANDIDATE_DESCRIPTION),
        (SOURCE_MAGIC, CANDIDATE_MAGIC),
        (SOURCE_TELEMETRY, CANDIDATE_TELEMETRY),
        (SOURCE_LONG_CONDITION, CANDIDATE_LONG_CONDITION),
        (SOURCE_SHORT_CONDITION, CANDIDATE_SHORT_CONDITION),
    )

    candidate = source
    for old, new in replacements:
        candidate = candidate.replace(old, new)

    candidate_markers = (
        CANDIDATE_FILENAME,
        CANDIDATE_BANNER,
        CANDIDATE_VERSION,
        CANDIDATE_DESCRIPTION,
        CANDIDATE_MAGIC,
        CANDIDATE_TELEMETRY,
        CANDIDATE_LONG_CONDITION,
        CANDIDATE_SHORT_CONDITION,
    )
    for marker in candidate_markers:
        _require_exact_count(candidate, marker)

    for marker in source_markers:
        if marker in candidate:
            raise ValueError(f"stale source marker remains: {marker}")

    return candidate


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build PeakFX confirmed-breakout EXP2")
    parser.add_argument("source", help="Exact compiled-clean v1.44 source")
    parser.add_argument("output", help="Destination v1.45 .mq5 path")
    args = parser.parse_args(argv)

    source_path = Path(args.source)
    output_path = Path(args.output)
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


if __name__ == "__main__":
    raise SystemExit(main())
