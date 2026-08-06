from __future__ import annotations

import argparse
import difflib
import hashlib
import re
import sys
from pathlib import Path

CANDIDATE_FILENAME = "PeakFX_EURUSD_H1_PULLBACK_CONFIRMED_BREAKOUT_EXP7_FROZEN.mq5"
LOWER = "0.5667"
UPPER = "0.85"

VERSION_PATTERN = re.compile(r'(?m)^(\s*#property\s+version\s+)"[^"]+"(\s*)$')
DESCRIPTION_PATTERN = re.compile(r'(?m)^(\s*#property\s+description\s+)"[^"]*"(\s*)$')
MAGIC_PATTERN = re.compile(r'(?m)^(\s*input\s+long\s+MagicNumber\s*=\s*)26073025(\s*;\s*)$')
TELEMETRY_PATTERN = re.compile(
    r'(?m)^(\s*input\s+string\s+TelemetryFile\s*=\s*)'
    r'"peakfx_confirmed_breakout_exp2_events\.csv"(\s*;\s*)$'
)
LONG_BLOCK = '''bool LongTriggerCondition(int shift)
  {
   if(!UptrendCondition(shift))
      return(false);
   double c = iClose(InpSymbol,InpTimeframe,shift);
   double atr = GetIndicatorValue(hAtr,shift);
   if(!IsValidValue(atr) || atr<=0.0)
      return(false);
   return(c > g_setup.pullback_high + (0.20*atr));
  }'''
SHORT_BLOCK = '''bool ShortTriggerCondition(int shift)
  {
   if(!DowntrendCondition(shift))
      return(false);
   double c = iClose(InpSymbol,InpTimeframe,shift);
   double atr = GetIndicatorValue(hAtr,shift);
   if(!IsValidValue(atr) || atr<=0.0)
      return(false);
   return(c < g_setup.pullback_low - (0.20*atr));
  }'''
LONG_REPLACEMENT = f'''bool LongTriggerCondition(int shift)
  {{
   if(!UptrendCondition(shift))
      return(false);
   double c = iClose(InpSymbol,InpTimeframe,shift);
   double atr = GetIndicatorValue(hAtr,shift);
   if(!IsValidValue(atr) || atr<=0.0)
      return(false);
   double trigger_clearance_atr = (c-g_setup.pullback_high)/atr;
   if(trigger_clearance_atr >= {LOWER} && trigger_clearance_atr <= {UPPER})
      return(false);
   return(c > g_setup.pullback_high + (0.20*atr));
  }}'''
SHORT_REPLACEMENT = f'''bool ShortTriggerCondition(int shift)
  {{
   if(!DowntrendCondition(shift))
      return(false);
   double c = iClose(InpSymbol,InpTimeframe,shift);
   double atr = GetIndicatorValue(hAtr,shift);
   if(!IsValidValue(atr) || atr<=0.0)
      return(false);
   double trigger_clearance_atr = (g_setup.pullback_low-c)/atr;
   if(trigger_clearance_atr >= {LOWER} && trigger_clearance_atr <= {UPPER})
      return(false);
   return(c < g_setup.pullback_low - (0.20*atr));
  }}'''


def read_source(path: Path) -> str:
    raw = path.read_bytes()
    if raw.startswith(b"\xef\xbb\xbf"):
        return raw.decode("utf-8-sig")
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        return raw.decode("utf-16")
    sample = raw[:4096]
    if sample[1::2].count(0) > max(4, len(sample) // 10):
        return raw.decode("utf-16-le")
    return raw.decode("utf-8")


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise ValueError(f"expected exactly one {label}, found {count}")
    return text.replace(old, new, 1)


def regex_replace_once(text: str, pattern: re.Pattern[str], repl, label: str) -> str:
    matches = list(pattern.finditer(text))
    if len(matches) != 1:
        raise ValueError(f"expected exactly one {label}, found {len(matches)}")
    return pattern.sub(repl, text, count=1)


def build(source: str) -> str:
    candidate = source
    candidate = regex_replace_once(candidate, VERSION_PATTERN,
        lambda m: f'{m.group(1)}"1.50"{m.group(2)}', "version")
    candidate = regex_replace_once(candidate, DESCRIPTION_PATTERN,
        lambda m: f'{m.group(1)}"EXP7 frozen closeout: reject trigger clearance from {LOWER} through {UPPER} ATR; all other EXP2 logic unchanged."{m.group(2)}',
        "description")
    candidate = regex_replace_once(candidate, MAGIC_PATTERN,
        lambda m: f"{m.group(1)}26073030{m.group(2)}", "EXP2 magic number")
    candidate = regex_replace_once(candidate, TELEMETRY_PATTERN,
        lambda m: f'{m.group(1)}"peakfx_exp7_frozen_events.csv"{m.group(2)}', "EXP2 telemetry filename")
    candidate = replace_once(candidate, LONG_BLOCK, LONG_REPLACEMENT, "EXP2 long trigger block")
    candidate = replace_once(candidate, SHORT_BLOCK, SHORT_REPLACEMENT, "EXP2 short trigger block")
    candidate = candidate.replace("PeakFX_EURUSD_H1_PULLBACK_CONFIRMED_BREAKOUT_EXP2.mq5", CANDIDATE_FILENAME, 1)

    required = [
        "26073030",
        "peakfx_exp7_frozen_events.csv",
        f"trigger_clearance_atr >= {LOWER} && trigger_clearance_atr <= {UPPER}",
        "double trigger_clearance_atr = (c-g_setup.pullback_high)/atr;",
        "double trigger_clearance_atr = (g_setup.pullback_low-c)/atr;",
    ]
    for marker in required:
        expected = 2 if marker.startswith("trigger_clearance_atr >=") else 1
        if candidate.count(marker) != expected:
            raise ValueError(f"candidate validation failed for {marker!r}")
    if candidate.count("return(c > g_setup.pullback_high + (0.20*atr));") != 1:
        raise ValueError("EXP2 long trigger changed unexpectedly")
    if candidate.count("return(c < g_setup.pullback_low - (0.20*atr));") != 1:
        raise ValueError("EXP2 short trigger changed unexpectedly")
    return candidate


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build frozen EXP7 from authoritative EXP2")
    parser.add_argument("source")
    parser.add_argument("output")
    parser.add_argument("--diff-output")
    args = parser.parse_args(argv)
    try:
        source_path = Path(args.source)
        output_path = Path(args.output)
        source = read_source(source_path)
        candidate = build(source)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(candidate, encoding="utf-8", newline="\n")
        if args.diff_output:
            diff = "".join(difflib.unified_diff(
                source.splitlines(keepends=True), candidate.splitlines(keepends=True),
                fromfile="EXP2", tofile="EXP7_FROZEN"))
            Path(args.diff_output).write_text(diff, encoding="utf-8")
        print(f"EXP2_SHA256={hashlib.sha256(source_path.read_bytes()).hexdigest()}")
        print(f"EXP7_SHA256={hashlib.sha256(output_path.read_bytes()).hexdigest()}")
        print(f"EXP7 frozen candidate written: {output_path}")
        return 0
    except Exception as exc:
        print(f"EXP7_BUILDER_ERROR: {type(exc).__name__}: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
