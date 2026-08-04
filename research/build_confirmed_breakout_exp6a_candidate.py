from __future__ import annotations

import argparse
import hashlib
import re
import sys
from pathlib import Path

EXP3_MAGIC = 26073035
EXP6_MAGIC = 26073060
EXP3_TELEMETRY = "peakfx_confirmed_breakout_exp3a_er_events.csv"
EXP6_TELEMETRY = "peakfx_confirmed_breakout_exp6a_rising_er_events.csv"
EXP6_FILENAME = "PeakFX_EURUSD_H1_PULLBACK_CONFIRMED_BREAKOUT_EXP6A_RISING_ER.mq5"

MAGIC_PATTERN = re.compile(r'(?m)^(\s*input\s+long\s+MagicNumber\s*=\s*)26073035(\s*;\s*)$')
TELEMETRY_PATTERN = re.compile(r'(?m)^(\s*input\s+string\s+TelemetryFile\s*=\s*)"peakfx_confirmed_breakout_exp3a_er_events\.csv"(\s*;\s*)$')
GATE_PATTERN = re.compile(
    r'bool\s+EfficiencyGatePasses\s*\(\s*const\s+int\s+shift\s*\)\s*\{\s*'
    r'double\s+er\s*=\s*KaufmanEfficiencyRatio\s*\(\s*shift\s*\)\s*;\s*'
    r'return\s*\(\s*er\s*>=\s*MinimumEfficiencyRatio\s*\)\s*;\s*\}',
    re.S,
)

NEW_GATE = '''bool EfficiencyGatePasses(const int shift)
  {
   double current_er  = KaufmanEfficiencyRatio(shift);
   double previous_er = KaufmanEfficiencyRatio(shift+1);

   if(current_er >= MinimumEfficiencyRatio)
      return(true);

   if(current_er >= 0.30 && (current_er-previous_er) >= 0.05)
      return(true);

   return(false);
  }'''


def read_source(path: Path) -> tuple[str, str]:
    raw = path.read_bytes()
    if raw.startswith(b"\xef\xbb\xbf"):
        return raw.decode("utf-8-sig"), "utf-8-sig"
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        return raw.decode("utf-16"), "utf-16"
    even_nulls = sum(1 for b in raw[0::2] if b == 0)
    odd_nulls = sum(1 for b in raw[1::2] if b == 0)
    pairs = max(1, len(raw) // 2)
    if odd_nulls / pairs > 0.30:
        return raw.decode("utf-16-le"), "utf-16-le"
    if even_nulls / pairs > 0.30:
        return raw.decode("utf-16-be"), "utf-16-be"
    return raw.decode("utf-8"), "utf-8"


def replace_once(source: str, pattern: re.Pattern[str], replacement, label: str) -> str:
    matches = list(pattern.finditer(source))
    if len(matches) != 1:
        raise ValueError(f"expected exactly one {label}, found {len(matches)}")
    return pattern.sub(replacement, source, count=1)


def build_exp6a(source: str) -> str:
    candidate = replace_once(source, MAGIC_PATTERN, lambda m: f"{m.group(1)}{EXP6_MAGIC}{m.group(2)}", "EXP3A magic marker")
    candidate = replace_once(candidate, TELEMETRY_PATTERN, lambda m: f'{m.group(1)}"{EXP6_TELEMETRY}"{m.group(2)}', "EXP3A telemetry marker")
    candidate = replace_once(candidate, GATE_PATTERN, NEW_GATE, "EXP3A efficiency gate")
    candidate = candidate.replace("PeakFX_EURUSD_H1_PULLBACK_CONFIRMED_BREAKOUT_EXP3A_ER.mq5", EXP6_FILENAME, 1)
    candidate = candidate.replace('"1.46"', '"1.47"', 1)

    required = (
        str(EXP6_MAGIC), EXP6_TELEMETRY,
        "current_er >= MinimumEfficiencyRatio",
        "current_er >= 0.30",
        "(current_er-previous_er) >= 0.05",
        "MinimumEfficiencyRatio        = 0.35;",
        "0.20*atr",
    )
    for marker in required:
        if marker not in candidate:
            raise ValueError(f"candidate validation failed: missing {marker}")
    if str(EXP3_MAGIC) in candidate or EXP3_TELEMETRY in candidate:
        raise ValueError("stale EXP3A identity marker remains")
    return candidate


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build isolated EXP6A rising-ER candidate from exact EXP3A source")
    parser.add_argument("source")
    parser.add_argument("output")
    args = parser.parse_args(argv)
    source_path = Path(args.source)
    output_path = Path(args.output)
    try:
        source, encoding = read_source(source_path)
        print(f"EXP6A builder source={source_path} encoding={encoding} sha256={hashlib.sha256(source_path.read_bytes()).hexdigest()}")
        candidate = build_exp6a(source)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(candidate, encoding="utf-8", newline="\n")
        print(f"EXP6A candidate written: {output_path}")
        return 0
    except Exception as exc:
        print(f"EXP6A_BUILDER_ERROR: {type(exc).__name__}: {exc}", file=sys.stdout)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
