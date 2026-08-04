from __future__ import annotations

import argparse
import hashlib
import re
import sys
from pathlib import Path

SOURCE_MAGIC = "26073035"
TARGET_MAGIC = "26073045"
SOURCE_TELEMETRY = "peakfx_confirmed_breakout_exp3a_er_events.csv"
TARGET_TELEMETRY = "peakfx_exp4a_er035_confirm015_events.csv"
SOURCE_FILENAME = "PeakFX_EURUSD_H1_PULLBACK_CONFIRMED_BREAKOUT_EXP3A_ER.mq5"
TARGET_FILENAME = "PeakFX_EURUSD_H1_PULLBACK_CONFIRMED_BREAKOUT_EXP4A_ER_CONFIRM015.mq5"

LONG_PATTERN = re.compile(r"c\s*>\s*g_setup\.pullback_high\s*\+\s*\(\s*0\.20\s*\*\s*atr\s*\)")
SHORT_PATTERN = re.compile(r"c\s*<\s*g_setup\.pullback_low\s*-\s*\(\s*0\.20\s*\*\s*atr\s*\)")


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise ValueError(f"expected exactly one {label}, found {count}")
    return text.replace(old, new, 1)


def regex_once(text: str, pattern: re.Pattern[str], replacement: str, label: str) -> str:
    matches = list(pattern.finditer(text))
    if len(matches) != 1:
        raise ValueError(f"expected exactly one {label}, found {len(matches)}")
    return pattern.sub(replacement, text, count=1)


def build(source: str) -> str:
    candidate = source
    candidate = replace_once(candidate, SOURCE_MAGIC, TARGET_MAGIC, "EXP3A magic")
    candidate = replace_once(candidate, SOURCE_TELEMETRY, TARGET_TELEMETRY, "EXP3A telemetry")
    candidate = replace_once(candidate, SOURCE_FILENAME, TARGET_FILENAME, "EXP3A filename")
    candidate = replace_once(candidate, '"1.46"', '"1.47"', "EXP3A version")
    candidate = regex_once(candidate, LONG_PATTERN, "c > g_setup.pullback_high + (0.15*atr)", "EXP3A long trigger")
    candidate = regex_once(candidate, SHORT_PATTERN, "c < g_setup.pullback_low - (0.15*atr)", "EXP3A short trigger")
    candidate = candidate.replace("clear pullback extreme by 0.20 ATR", "clear pullback extreme by 0.15 ATR", 1)

    required = (
        TARGET_MAGIC,
        TARGET_TELEMETRY,
        "MinimumEfficiencyRatio        = 0.35;",
        "EfficiencyPeriod              = 20;",
        "c > g_setup.pullback_high + (0.15*atr)",
        "c < g_setup.pullback_low - (0.15*atr)",
    )
    for marker in required:
        if candidate.count(marker) != 1:
            raise ValueError(f"candidate validation failed for marker: {marker}")
    if "0.20*atr" in candidate:
        raise ValueError("stale 0.20 ATR trigger remains")
    return candidate


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("source")
    parser.add_argument("output")
    args = parser.parse_args()
    source_path = Path(args.source)
    output_path = Path(args.output)
    try:
        source = source_path.read_text(encoding="utf-8")
        print(f"EXP4A source={source_path} sha256={hashlib.sha256(source_path.read_bytes()).hexdigest()}")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(build(source), encoding="utf-8", newline="\n")
        print(f"EXP4A candidate written: {output_path}")
        return 0
    except Exception as exc:
        print(f"EXP4A_BUILDER_ERROR: {type(exc).__name__}: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
