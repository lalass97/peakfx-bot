from __future__ import annotations

import argparse
from pathlib import Path

SOURCE_VERSION = '#property version   "1.44"'
CANDIDATE_VERSION = '#property version   "1.45"'
SOURCE_MAGIC = "input long             MagicNumber                  = 26073024;"
CANDIDATE_MAGIC = "input long             MagicNumber                  = 26073025;"
SOURCE_TELEMETRY = 'input string           TelemetryFile                = "peakfx_confirmed_breakout_exp1_events.csv";'
CANDIDATE_TELEMETRY = 'input string           TelemetryFile                = "peakfx_confirmed_breakout_exp2_events.csv";'


def build_confirmed_breakout_exp2(source: str) -> str:
    required = (
        SOURCE_VERSION,
        SOURCE_MAGIC,
        SOURCE_TELEMETRY,
        "0.10*atr",
    )
    for marker in required:
        count = source.count(marker)
        expected = 2 if marker == "0.10*atr" else 1
        if count != expected:
            raise ValueError(f"expected {expected} source marker(s), found {count}: {marker}")

    candidate = source
    replacements = (
        (
            "PeakFX_EURUSD_H1_PULLBACK_CONFIRMED_BREAKOUT_EXP1.mq5",
            "PeakFX_EURUSD_H1_PULLBACK_CONFIRMED_BREAKOUT_EXP2.mq5",
        ),
        (
            "Version 1.44 - confirmed-breakout experiment",
            "Version 1.45 - stronger confirmed-breakout experiment",
        ),
        (SOURCE_VERSION, CANDIDATE_VERSION),
        (
            "trigger close must clear pullback extreme by 0.10 ATR",
            "trigger close must clear pullback extreme by 0.20 ATR",
        ),
        (SOURCE_MAGIC, CANDIDATE_MAGIC),
        (SOURCE_TELEMETRY, CANDIDATE_TELEMETRY),
        ("0.10*atr", "0.20*atr"),
    )
    for old, new in replacements:
        candidate = candidate.replace(old, new)

    if candidate.count(CANDIDATE_VERSION) != 1:
        raise ValueError("candidate version validation failed")
    if candidate.count("0.20*atr") != 2:
        raise ValueError("0.20 ATR confirmation was not applied to both directions")
    if "0.10*atr" in candidate:
        raise ValueError("stale 0.10 ATR confirmation remains")
    return candidate


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build PeakFX confirmed-breakout EXP2")
    parser.add_argument("source", help="Exact compiled-clean v1.44 source")
    parser.add_argument("output", help="Destination v1.45 .mq5 path")
    args = parser.parse_args(argv)

    source = Path(args.source).read_text(encoding="utf-8")
    candidate = build_confirmed_breakout_exp2(source)
    Path(args.output).write_text(candidate, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
