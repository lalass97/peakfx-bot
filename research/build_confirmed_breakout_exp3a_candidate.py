from __future__ import annotations

import argparse
import hashlib
import re
import sys
from pathlib import Path

EXP2_MAGIC = 26073025
EXP3_MAGIC = 26073035
EXP2_TELEMETRY = "peakfx_confirmed_breakout_exp2_events.csv"
EXP3_TELEMETRY = "peakfx_confirmed_breakout_exp3a_er_events.csv"
EXP3_FILENAME = "PeakFX_EURUSD_H1_PULLBACK_CONFIRMED_BREAKOUT_EXP3A_ER.mq5"

MAGIC_PATTERN = re.compile(r'(?m)^(\s*input\s+long\s+MagicNumber\s*=\s*)26073025(\s*;\s*)$')
TELEMETRY_PATTERN = re.compile(
    r'(?m)^(\s*input\s+string\s+TelemetryFile\s*=\s*)'
    r'"peakfx_confirmed_breakout_exp2_events\.csv"(\s*;\s*)$'
)
INPUT_ANCHOR = re.compile(r'(?m)^(\s*input\s+int\s+HeartbeatSeconds\s*=\s*300\s*;\s*)$')
TRIGGER_ANCHOR = re.compile(r'(?m)^bool\s+LongTriggerCondition\s*\(int\s+shift\)')
ENTRY_ANCHOR = re.compile(r'(?m)^(\s*if\s*\(LongTriggerCondition\(shift\)\)\s*)$')
SHORT_ENTRY_ANCHOR = re.compile(r'(?m)^(\s*if\s*\(ShortTriggerCondition\(shift\)\)\s*)$')

ER_FUNCTION = r'''
// EXP3A isolated regime filter: Kaufman Efficiency Ratio on closed H1 bars.
double KaufmanEfficiencyRatio(const int shift)
  {
   if(EfficiencyPeriod < 2)
      return(0.0);

   double directional = MathAbs(iClose(InpSymbol,InpTimeframe,shift) -
                                iClose(InpSymbol,InpTimeframe,shift+EfficiencyPeriod));
   double path = 0.0;
   for(int i=shift; i<shift+EfficiencyPeriod; i++)
     {
      double currentClose = iClose(InpSymbol,InpTimeframe,i);
      double previousClose = iClose(InpSymbol,InpTimeframe,i+1);
      if(currentClose<=0.0 || previousClose<=0.0)
         return(0.0);
      path += MathAbs(currentClose-previousClose);
     }

   if(path<=0.0)
      return(0.0);
   return(directional/path);
  }

bool EfficiencyGatePasses(const int shift)
  {
   double er = KaufmanEfficiencyRatio(shift);
   return(er >= MinimumEfficiencyRatio);
  }

'''


def _read_source(path: Path) -> tuple[str, str]:
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


def _replace_once(source: str, pattern: re.Pattern[str], replacement, label: str) -> str:
    matches = list(pattern.finditer(source))
    if len(matches) != 1:
        raise ValueError(f"expected exactly one {label}, found {len(matches)}")
    return pattern.sub(replacement, source, count=1)


def build_exp3a(source: str) -> str:
    candidate = source
    candidate = _replace_once(
        candidate, MAGIC_PATTERN,
        lambda m: f"{m.group(1)}{EXP3_MAGIC}{m.group(2)}",
        "EXP2 magic marker",
    )
    candidate = _replace_once(
        candidate, TELEMETRY_PATTERN,
        lambda m: f'{m.group(1)}"{EXP3_TELEMETRY}"{m.group(2)}',
        "EXP2 telemetry marker",
    )
    candidate = _replace_once(
        candidate, INPUT_ANCHOR,
        lambda m: m.group(1) + "\ninput int              EfficiencyPeriod              = 20;\ninput double           MinimumEfficiencyRatio        = 0.35;",
        "input insertion anchor",
    )
    candidate = _replace_once(
        candidate, TRIGGER_ANCHOR,
        ER_FUNCTION + "bool LongTriggerCondition(int shift)",
        "trigger insertion anchor",
    )
    candidate = _replace_once(
        candidate, ENTRY_ANCHOR,
        lambda m: m.group(1).replace("if(LongTriggerCondition(shift))", "if(EfficiencyGatePasses(shift) && LongTriggerCondition(shift))"),
        "long entry gate",
    )
    candidate = _replace_once(
        candidate, SHORT_ENTRY_ANCHOR,
        lambda m: m.group(1).replace("if(ShortTriggerCondition(shift))", "if(EfficiencyGatePasses(shift) && ShortTriggerCondition(shift))"),
        "short entry gate",
    )

    candidate = candidate.replace(
        "PeakFX_EURUSD_H1_PULLBACK_CONFIRMED_BREAKOUT_EXP2.mq5",
        EXP3_FILENAME,
        1,
    )
    candidate = candidate.replace('"1.45"', '"1.46"', 1)

    required = (
        str(EXP3_MAGIC), EXP3_TELEMETRY,
        "EfficiencyPeriod              = 20;",
        "MinimumEfficiencyRatio        = 0.35;",
        "double KaufmanEfficiencyRatio",
        "EfficiencyGatePasses(shift) && LongTriggerCondition(shift)",
        "EfficiencyGatePasses(shift) && ShortTriggerCondition(shift)",
        "0.20*atr",
    )
    for marker in required:
        if marker not in candidate:
            raise ValueError(f"candidate validation failed: missing {marker}")
    if str(EXP2_MAGIC) in candidate or EXP2_TELEMETRY in candidate:
        raise ValueError("stale EXP2 identity marker remains")
    return candidate


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build isolated EXP3A ER-filter candidate from exact EXP2 source")
    parser.add_argument("source")
    parser.add_argument("output")
    args = parser.parse_args(argv)
    source_path = Path(args.source)
    output_path = Path(args.output)
    try:
        source, encoding = _read_source(source_path)
        print(f"EXP3A builder source={source_path} encoding={encoding} sha256={hashlib.sha256(source_path.read_bytes()).hexdigest()}")
        candidate = build_exp3a(source)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(candidate, encoding="utf-8", newline="\n")
        print(f"EXP3A candidate written: {output_path}")
        return 0
    except Exception as exc:
        print(f"EXP3A_BUILDER_ERROR: {type(exc).__name__}: {exc}", file=sys.stdout)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
